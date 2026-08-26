from typing import Any, cast

from namoz_bot.config import Settings
from namoz_bot.main import ApplicationResources, create_application


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
    assert resources.dispatcher.sub_routers

    await resources.close()
