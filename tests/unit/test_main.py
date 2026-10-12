import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from namoz_bot.config import Settings
from namoz_bot.main import ApplicationResources, create_application


@pytest.fixture(autouse=True)
def configured_book(tmp_path, monkeypatch):
    path = tmp_path / "book.json"
    path.write_text(
        json.dumps(
            {
                "title": "Sinov kitobi",
                "author": "Muallif",
                "passages": [
                    {"id": "p1", "text": "Asl kitob matni.", "page_start": 1, "page_end": 1}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GEMINI_BOOK_CORPUS_PATH", str(path))


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBot:
    def __init__(self) -> None:
        self.session = FakeSession()


class FakeHttpClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeScheduler:
    def __init__(self) -> None:
        self.running = True
        self.shutdown_called = False

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_called = True
        self.running = False


async def test_application_shutdown_closes_every_owned_resource() -> None:
    bot = FakeBot()
    http_client = FakeHttpClient()
    engine = FakeEngine()
    scheduler = FakeScheduler()
    resources = ApplicationResources(
        bot=cast(Any, bot),
        dispatcher=cast(Any, object()),
        http_client=cast(Any, http_client),
        db_engine=cast(Any, engine),
        scheduler=cast(Any, scheduler),
    )

    await resources.close()

    assert bot.session.closed is True
    assert http_client.closed is True
    assert engine.disposed is True
    assert scheduler.shutdown_called is True


async def test_create_application_wires_daily_job_without_network_calls() -> None:
    resources = create_application(
        Settings(
            telegram_bot_token="123456:TEST_TOKEN_VALUE",
            database_url="sqlite+aiosqlite:///:memory:",
        )
    )

    assert resources.scheduler.get_job("daily-prayer-schedule") is not None
    assert resources.scheduler.get_job("personal-reminders") is not None
    assert resources.dispatcher.sub_routers
    assert resources.bot.default.parse_mode is None
    await resources.close()


async def test_duplicate_start_exits_before_creating_resources(tmp_path, monkeypatch, caplog):
    from functools import partial

    from namoz_bot import main
    from namoz_bot.infrastructure.instance_lock import BotInstanceLock

    settings = Settings(
        _env_file=None,
        telegram_bot_token="123456:LOCK_TEST_SECRET",
        database_url="sqlite+aiosqlite:///:memory:",
    )

    def unexpected_resources(_):
        pytest.fail("A duplicate process must not initialize resources or polling")

    monkeypatch.setattr(main, "Settings", lambda: settings)
    monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
    # Alembic's logging configuration in PostgreSQL tests disables existing loggers.
    monkeypatch.setattr(main.logger, "disabled", False)
    monkeypatch.setattr(main, "BotInstanceLock", partial(BotInstanceLock, directory=tmp_path))
    monkeypatch.setattr(main, "create_application", unexpected_resources)
    with BotInstanceLock(settings.telegram_bot_token, directory=tmp_path):
        with pytest.raises(SystemExit) as rejected:
            await main.run()
    assert rejected.value.code == 1
    assert "allaqachon ishlayapti" in caplog.text
    assert "LOCK_TEST_SECRET" not in caplog.text


async def test_gemini_job_polls_personal_due_times() -> None:
    resources = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:TEST_TOKEN_VALUE",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_API_KEY="gemini-test-key",
            GEMINI_REMINDER_INTERVAL_HOURS=6,
        )
    )
    try:
        job = resources.scheduler.get_job("automatic-religious-reminders")
        assert job is not None
        assert job.trigger.get_next_fire_time(
            None, datetime(2026, 10, 9, 10, 40, tzinfo=UTC)
        ) == datetime(2026, 10, 9, 11, tzinfo=UTC)
        assert job.coalesce is True
        assert job.max_instances == 1
    finally:
        await resources.close()


@pytest.mark.parametrize("key,interval", [(None, 1), ("", 1)])
async def test_gemini_job_is_disabled_without_key(key, interval) -> None:
    resources = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:TEST_TOKEN_VALUE",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_API_KEY=key,
            GEMINI_REMINDER_INTERVAL_HOURS=interval,
        )
    )
    try:
        assert resources.scheduler.get_job("automatic-religious-reminders") is None
        assert resources.scheduler.get_job("daily-prayer-schedule") is not None
    finally:
        await resources.close()


async def test_gemini_without_book_has_no_free_form_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_BOOK_CORPUS_PATH", raising=False)
    resources = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:TEST_TOKEN_VALUE",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_API_KEY="test-key",
            GEMINI_REMINDER_INTERVAL_HOURS=24,
        )
    )
    try:
        assert resources.scheduler.get_job("automatic-religious-reminders") is None
    finally:
        await resources.close()


async def test_overdue_two_hour_job_runs_once_after_waking_up():
    resources = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:TEST_TOKEN_VALUE",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_API_KEY="test-key",
            GEMINI_REMINDER_INTERVAL_HOURS=2,
        )
    )
    calls = []
    completed = asyncio.Event()

    async def broadcast():
        calls.append(True)
        completed.set()

    try:
        resources.scheduler.start(paused=True)
        resources.scheduler.modify_job(
            "automatic-religious-reminders",
            func=broadcast,
            next_run_time=datetime.now(UTC) - timedelta(hours=6, minutes=1),
        )
        resources.scheduler.resume()
        await asyncio.wait_for(completed.wait(), timeout=1)
        await asyncio.sleep(0.02)
        assert calls == [True]
        job = resources.scheduler.get_job("automatic-religious-reminders")
        assert job.next_run_time > datetime.now(UTC)
    finally:
        await resources.close()
