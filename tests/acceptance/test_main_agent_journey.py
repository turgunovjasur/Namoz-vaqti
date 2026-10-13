import json
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.types import Update
from sqlalchemy import select

from namoz_bot.config import Settings
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.orm import Base, FinanceEntryRecord
from namoz_bot.main import create_application
from tests.acceptance.test_voice_reminder_journey import VoiceJourney

URL = "https://generativelanguage.googleapis.com/v1beta/models/agent-test-model:generateContent"


@pytest.fixture
async def agent_journey(tmp_path, request):
    options = getattr(request, "param", {})
    app = create_application(
        Settings(
            MAIN_AGENT_VERSION=1,
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'main-agent.db'}",
            GEMINI_API_KEY=options.get("key", "agent-test-key"),
            GEMINI_MAIN_AGENT_MODEL="agent-test-model",
            GEMINI_VOICE_MODEL="legacy-test-model",
            GEMINI_BOOK_CORPUS_PATH=None,
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
            MAIN_AGENT_ENABLED=options.get("enabled", True),
        )
    )
    async with app.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    journey = VoiceJourney(app)
    await journey.text("/start")
    yield journey
    await journey.app.dispatcher.storage.close()
    await journey.app.close()


def response(domain, action, parameters=None, **kwargs):
    value = {
        "domain": domain,
        "action": action,
        "parameters": parameters or {},
        "transcript": "Test xabar",
        "clarification": None,
        "multiple_tasks": False,
    } | kwargs
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}
        ]
    }


@pytest.fixture
def agent_route(respx_mock):
    return respx_mock.post(URL).respond(
        200,
        json=response(
            "accounting",
            "expense",
            {
                "amount": 120000,
                "currency": "UZS",
                "category": "kiyim",
                "description": "Kiyim",
            },
        ),
    )


async def records(journey):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(journey.app.db_engine)() as session:
        return list(await session.scalars(select(FinanceEntryRecord)))


@pytest.mark.parametrize("voice", [False, True])
async def test_plain_finance_without_menu_is_saved_once(agent_journey, agent_route, voice):
    if voice:
        await agent_journey.voice()
    else:
        await agent_journey.text("120 mingga kiyim oldim")
    assert len(await records(agent_journey)) == 1
    assert "120 000" in agent_journey.last.text
    assert agent_route.call_count == 1
    assert 7 in agent_journey.session.reply_keyboards


@pytest.mark.parametrize("voice", [False, True])
async def test_reminder_partial_followup_and_button_confirmation(agent_journey, agent_route, voice):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    agent_route.respond(
        200,
        json=response(
            "reminder",
            "create",
            {
                "text": "Uchrashuv",
                "date": tomorrow,
                "kind": "once",
            },
        ),
    )
    if voice:
        await agent_journey.voice()
    else:
        await agent_journey.text("Ertaga uchrashuvni eslat")
    assert "vaqtda" in agent_journey.last.text
    assert not await agent_journey.rows()
    agent_route.respond(200, json=response("reminder", "create", {"time": "09:00"}))
    await agent_journey.text("Ertalab 9 da")
    save = agent_journey.button("✅ Saqlash")
    assert len(save.encode()) <= 64
    assert not await agent_journey.rows()
    await agent_journey.text("ha")
    assert not await agent_journey.rows()
    await agent_journey.click(data=save)
    await agent_journey.click(data=save)
    assert len(await agent_journey.rows()) == 1
    assert agent_route.call_count == 2


async def test_provider_error_keeps_pending_and_logs_no_payload(agent_journey, agent_route, caplog):
    agent_route.respond(200, json=response("reminder", "create", {"text": "Private text"}))
    await agent_journey.text("Private text")
    agent_route.respond(503, json={"error": "agent-test-key Private text"})
    await agent_journey.text("09:00")
    assert "qayta" in agent_journey.last.text
    await agent_journey.text("Davom et")
    assert "Nimani" not in agent_journey.last.text  # Existing content is retained.
    assert "Private text" not in caplog.text and "agent-test-key" not in caplog.text


async def test_menu_does_not_discard_agent_draft(agent_journey, agent_route):
    agent_route.respond(200, json=response("reminder", "create", {"text": "Kitob"}))
    await agent_journey.text("Kitob eslat")
    await agent_journey.text("💰 Kirim-chiqim")
    assert "Tugallanmagan" in agent_journey.last.text
    await agent_journey.text("Davom et")
    assert "vaqtda" in agent_journey.last.text


async def test_legacy_time_input_is_not_consumed(agent_journey, agent_route):
    await agent_journey.text("⚙️ Sozlamalar")
    await agent_journey.text("📅 Kunlik jadval")
    await agent_journey.click("✍️ Boshqa vaqt")
    await agent_journey.text("07:30")
    assert agent_route.call_count == 0
    assert "07:30" in agent_journey.last.text


async def test_group_chat_is_not_processed(agent_journey, agent_route):
    await agent_journey.voice(group=True)
    assert agent_route.call_count == 0


async def test_duplicate_update_skips_extraction(agent_journey, agent_route):
    payload = Update.model_validate(
        {
            "update_id": 777,
            "message": {
                "message_id": 777,
                "date": datetime.now(UTC),
                "text": "120 ming kiyim",
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Test"},
            },
        }
    )
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    assert len(await records(agent_journey)) == 1 and agent_route.call_count == 1


@pytest.mark.parametrize("voice", [False, True])
async def test_prayer_while_accounting_open_uses_provider(
    agent_journey, agent_route, respx_mock, voice
):
    from tests.integration.test_namoz_vaqti_api import today_payload

    await agent_journey.text("💰 Kirim-chiqim")
    target = datetime.now(TASHKENT).date()
    payload = today_payload()
    payload["meta"].update(ym=target.strftime("%Y-%m"))
    payload["period_table"] = [
        {"date": target.strftime("%d.%m.%Y"), "times": payload["today"]["times"]}
    ]
    respx_mock.get("https://namoz-vaqti.uz/").respond(200, json=payload)
    agent_route.respond(200, json=response("prayer", "schedule", {"prayer": "shom"}))
    if voice:
        await agent_journey.voice()
    else:
        await agent_journey.text("Bugun shom nechida?")
    assert "Shom:" in agent_journey.last.text and "namoz-vaqti.uz" in agent_journey.last.text
    assert not await records(agent_journey)


async def test_old_or_foreign_callback_cannot_save(agent_journey, agent_route):
    agent_route.respond(
        200,
        json=response(
            "reminder",
            "create",
            {
                "text": "Kitob",
                "time": "09:00",
                "kind": "daily",
            },
        ),
    )
    await agent_journey.text("Har kuni 9 da kitob eslat")
    old = agent_journey.button("✅ Saqlash")
    await agent_journey.text("/start", user=8)
    await agent_journey.click(data=old, user=8)
    assert not await agent_journey.rows()
    agent_route.respond(200, json=response("reminder", "create", {"time": "10:00"}))
    await agent_journey.text("10 da")
    await agent_journey.click(data=old)
    assert not await agent_journey.rows()
    await agent_journey.click("✅ Saqlash")
    assert len(await agent_journey.rows()) == 1


async def test_replay_after_undo_stays_cancelled(agent_journey, agent_route):
    payload = Update.model_validate(
        {
            "update_id": 778,
            "message": {
                "message_id": 778,
                "date": datetime.now(UTC),
                "text": "120 ming kiyim",
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Test"},
            },
        }
    )
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    await agent_journey.click("↩️ Yozuvni bekor qilish")
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    assert "bekor qilingan" in agent_journey.last.text
    assert "0 so‘m" in agent_journey.last.text and agent_route.call_count == 1


async def test_start_offers_pending_resume(agent_journey, agent_route):
    agent_route.respond(200, json=response("reminder", "create", {"text": "Kitob"}))
    await agent_journey.text("Kitob eslat")
    await agent_journey.text("/start")
    assert "vaqtda" in agent_journey.last.text


@pytest.mark.parametrize("agent_journey", [{"key": None}, {"enabled": False}], indirect=True)
async def test_missing_key_and_disabled_agent_preserve_menus(agent_journey, respx_mock):
    assert agent_journey.app.dispatcher["main_agent"] is None
    await agent_journey.text("💰 Kirim-chiqim")
    assert "Joriy balans: 0 so‘m" in agent_journey.last.text
    assert not respx_mock.calls


async def test_restart_and_old_valid_save_create_one_reminder(agent_journey, agent_route):
    agent_route.respond(
        200,
        json=response(
            "reminder",
            "create",
            {
                "text": "Kitob",
                "time": "09:00",
                "kind": "daily",
            },
        ),
    )
    await agent_journey.text("Har kuni ertalab 9 da kitob eslat")
    save = agent_journey.button("✅ Saqlash")
    old = agent_journey.app
    database_url = str(old.db_engine.url)
    await old.dispatcher.storage.close()
    await old.close()
    new = create_application(
        Settings(
            MAIN_AGENT_VERSION=1,
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=database_url,
            GEMINI_API_KEY="agent-test-key",
            GEMINI_MAIN_AGENT_MODEL="agent-test-model",
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
            MAIN_AGENT_ENABLED=True,
        )
    )
    await new.bot.session.close()
    new.bot.session = agent_journey.session
    agent_journey.app = new
    await agent_journey.text("Davom et")
    assert "Kitob" in agent_journey.last.text
    await agent_journey.click(data=save)
    await agent_journey.click(data=save)
    assert len(await agent_journey.rows()) == 1
    assert agent_route.call_count == 1


async def test_send_failure_then_replay_has_one_entry(agent_journey, agent_route):
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import EditMessageText, SendMessage

    payload = Update.model_validate(
        {
            "update_id": 779,
            "message": {
                "message_id": 779,
                "date": datetime.now(UTC),
                "text": "120 ming kiyim",
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Test"},
            },
        }
    )
    normal = agent_journey.session.make_request
    failed = False

    async def failing(bot, method, timeout=None):  # noqa: ASYNC109
        nonlocal failed
        if (
            not failed
            and isinstance(method, (EditMessageText, SendMessage))
            and "Chiqim qayd" in (method.text or "")
        ):
            failed = True
            raise TelegramBadRequest(method=method, message="Synthetic transport failure")
        return await normal(bot, method, timeout)

    agent_journey.session.make_request = failing
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    await agent_journey.app.dispatcher.feed_update(agent_journey.app.bot, payload)
    assert failed and len(await records(agent_journey)) == 1
    assert agent_route.call_count == 1 and "120 000" in agent_journey.last.text


async def test_weekly_confirmation_lists_selected_days(agent_journey, agent_route):
    agent_route.respond(
        200,
        json=response(
            "reminder",
            "create",
            {
                "text": "Kitob",
                "time": "09:00",
                "kind": "weekly",
                "weekdays": [0, 4],
            },
        ),
    )
    await agent_journey.text("Har dushanba va juma 9 da kitob eslat")
    assert "Dushanba" in agent_journey.last.text and "Juma" in agent_journey.last.text


async def test_today_reminder_list_pagination_preserves_filter(agent_journey, agent_route):
    from datetime import time

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from namoz_bot.domain.reminders import ReminderSpec
    from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
    from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository

    factory = async_sessionmaker(agent_journey.app.db_engine, expire_on_commit=False)
    user = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    repo = SqlAlchemyReminderRepository(factory)
    now = datetime.now(UTC)
    for index in range(4):
        await repo.create(
            user.id,
            7,
            ReminderSpec(f"Daily {index + 1}", time(9 + index), "daily"),
            f"daily{index}",
            now,
        )
    await repo.create(
        user.id,
        7,
        ReminderSpec(
            "Tomorrow only", time(14), "once", (now.astimezone(TASHKENT) + timedelta(days=1)).date()
        ),
        "tomorrow",
        now,
    )
    agent_route.respond(200, json=response("reminder", "list", {"today": True}))
    await agent_journey.text("Bugungi eslatmalarimni ko‘rsat")
    assert "Daily 1" in agent_journey.last.text and "Tomorrow only" not in agent_journey.last.text
    await agent_journey.click("Keyingi ➡️")
    assert "Daily 4" in agent_journey.last.text and "Tomorrow only" not in agent_journey.last.text
    assert agent_route.call_count == 1
