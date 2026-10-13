import json
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.types import Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.config import Settings
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.orm import Base, FinanceEntryRecord
from namoz_bot.main import create_application
from tests.acceptance.test_main_agent_journey import response
from tests.acceptance.test_voice_reminder_journey import VoiceJourney


def url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def route_response(domain, transcript="120 mingga kiyim oldim", control=None, multiple=False):
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "domain": domain,
                                    "transcript": transcript,
                                    "control_action": control,
                                    "clarification": None,
                                    "multiple_tasks": multiple,
                                }
                            )
                        }
                    ]
                },
            }
        ]
    }


@pytest.fixture
async def menu_journey(tmp_path):
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'v2.db'}",
            GEMINI_API_KEY="test-key",
            GEMINI_MAIN_AGENT_MODEL="router-model",
            GEMINI_PRAYER_AGENT_MODEL="prayer-model",
            GEMINI_REMINDER_AGENT_MODEL="reminder-model",
            GEMINI_ACCOUNTING_AGENT_MODEL="finance-model",
            GEMINI_SETTINGS_AGENT_MODEL="settings-model",
            MAIN_AGENT_VERSION=2,
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
            GEMINI_BOOK_CORPUS_PATH=None,
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


@pytest.fixture
def routes(respx_mock):
    router = respx_mock.post(url("router-model")).respond(200, json=route_response("accounting"))
    finance = respx_mock.post(url("finance-model")).respond(
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
    prayer = respx_mock.post(url("prayer-model")).respond(
        200, json=response("prayer", "schedule", {"prayer": "shom"})
    )
    reminder = respx_mock.post(url("reminder-model")).respond(
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
    settings = respx_mock.post(url("settings-model")).respond(
        200, json=response("settings", "open", {"view": "general"})
    )
    return router, finance, prayer, reminder, settings


async def entries(journey):
    async with async_sessionmaker(journey.app.db_engine)() as session:
        return list(await session.scalars(select(FinanceEntryRecord)))


@pytest.mark.parametrize("voice", [False, True])
async def test_v2_calls_only_router_and_selected_finance_agent(menu_journey, routes, voice):
    if voice:
        await menu_journey.voice()
    else:
        await menu_journey.text("120 mingga kiyim oldim")
    assert len(await entries(menu_journey)) == 1 and "120 000" in menu_journey.last.text
    assert [r.call_count for r in routes] == [1, 1, 0, 0, 0]
    body = json.loads(routes[1].calls.last.request.content)
    assert not any("inlineData" in part for part in body["contents"][0]["parts"])


async def test_v2_reminder_followup_confirmation_preserves_day(menu_journey, routes):
    tomorrow = (datetime.now(TASHKENT) + timedelta(days=1)).date().isoformat()
    routes[0].respond(200, json=route_response("reminder", "Ertaga kitob eslat"))
    routes[3].respond(
        200,
        json=response("reminder", "create", {"text": "Kitob", "kind": "once", "date": tomorrow}),
    )
    await menu_journey.text("Ertaga kitob eslat")
    assert "vaqtda" in menu_journey.last.text
    routes[3].respond(200, json=response("reminder", "create", {"time": "09:00"}))
    await menu_journey.text("Ertalab 9 da")
    assert not await menu_journey.rows()
    await menu_journey.click("✅ Saqlash")
    assert (await menu_journey.rows())[0].spec.on_date.isoformat() == tomorrow
    assert [r.call_count for r in routes] == [2, 0, 0, 2, 0]


async def test_helper_failure_keeps_pending(menu_journey, routes):
    routes[0].respond(200, json=route_response("reminder"))
    routes[3].respond(200, json=response("reminder", "create", {"text": "Kitob"}))
    await menu_journey.text("Kitob eslat")
    routes[3].respond(503, json={"error": "private-provider-detail"})
    await menu_journey.text("Ertalab 9 da")
    assert "qayta" in menu_journey.last.text
    await menu_journey.text("Davom et")
    assert "vaqtda" in menu_journey.last.text
    assert not await menu_journey.rows()


async def test_duplicate_update_skips_both_agents(menu_journey, routes):
    update = Update.model_validate(
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
    await menu_journey.app.dispatcher.feed_update(menu_journey.app.bot, update)
    await menu_journey.app.dispatcher.feed_update(menu_journey.app.bot, update)
    assert len(await entries(menu_journey)) == 1 and [r.call_count for r in routes] == [
        1,
        1,
        0,
        0,
        0,
    ]


async def test_wrong_domain_helper_never_writes(menu_journey, routes):
    routes[0].respond(200, json=route_response("reminder"))
    routes[3].respond(
        200,
        json=response(
            "accounting",
            "expense",
            {"amount": 120000, "currency": "UZS", "category": "kiyim", "description": "Kiyim"},
        ),
    )
    await menu_journey.text("Kitob eslat")
    assert not await entries(menu_journey) and not await menu_journey.rows()
    assert "qayta" in menu_journey.last.text


@pytest.mark.parametrize("multiple", [False, True])
async def test_assistant_and_multi_task_do_not_call_menu_agents(menu_journey, routes, multiple):
    routes[0].respond(
        200,
        json=route_response(
            "assistant", control="clarify" if multiple else "help", multiple=multiple
        ),
    )
    await menu_journey.text("Salom" if not multiple else "Ikki vazifa")
    assert [r.call_count for r in routes] == [1, 0, 0, 0, 0]


async def test_settings_agent_opens_existing_settings(menu_journey, routes):
    routes[0].respond(200, json=route_response("settings"))
    await menu_journey.text("Sozlamalarni och")
    assert "Sozlamalar" in menu_journey.last.text
    assert [r.call_count for r in routes] == [1, 0, 0, 0, 1]


async def test_prayer_agent_uses_existing_schedule_service(menu_journey, routes, respx_mock):
    from tests.integration.test_namoz_vaqti_api import today_payload

    today = datetime.now(TASHKENT).date()
    payload = today_payload()
    payload["meta"]["ym"] = today.strftime("%Y-%m")
    payload["period_table"] = [
        {"date": today.strftime("%d.%m.%Y"), "times": payload["today"]["times"]}
    ]
    respx_mock.get("https://namoz-vaqti.uz/").respond(200, json=payload)
    routes[0].respond(200, json=route_response("prayer"))
    await menu_journey.text("Shom nechida?")
    assert "Shom:" in menu_journey.last.text and "namoz-vaqti.uz" in menu_journey.last.text
    assert [r.call_count for r in routes] == [1, 0, 1, 0, 0]


async def test_v1_draft_is_resumed_after_switching_to_v2(menu_journey, routes, respx_mock):
    old = menu_journey.app
    database_url = str(old.db_engine.url)
    await old.dispatcher.storage.close()
    await old.close()
    v1 = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=database_url,
            GEMINI_API_KEY="test-key",
            MAIN_AGENT_VERSION=1,
            GEMINI_MAIN_AGENT_MODEL="v1-model",
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
        )
    )
    await v1.bot.session.close()
    v1.bot.session = menu_journey.session
    menu_journey.app = v1
    tomorrow = (datetime.now(TASHKENT) + timedelta(days=1)).date().isoformat()
    respx_mock.post(url("v1-model")).respond(
        200,
        json=response(
            "reminder", "create", {"text": "Existing V1 draft", "kind": "once", "date": tomorrow}
        ),
    )
    await menu_journey.text("Ertaga eslat")
    assert "vaqtda" in menu_journey.last.text
    await v1.dispatcher.storage.close()
    await v1.close()
    v2 = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=database_url,
            GEMINI_API_KEY="test-key",
            MAIN_AGENT_VERSION=2,
            GEMINI_MAIN_AGENT_MODEL="router-model",
            GEMINI_REMINDER_AGENT_MODEL="reminder-model",
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
        )
    )
    await v2.bot.session.close()
    v2.bot.session = menu_journey.session
    menu_journey.app = v2
    await menu_journey.text("Davom et")
    assert "vaqtda" in menu_journey.last.text and routes[0].call_count == 0
    routes[0].respond(200, json=route_response("reminder", "09:00"))
    routes[3].respond(200, json=response("reminder", "create", {"time": "09:00"}))
    await menu_journey.text("Ertalab 9 da")
    body = json.loads(routes[3].calls.last.request.content)
    assert "Existing V1 draft" in body["contents"][0]["parts"][0]["text"]
    await menu_journey.click("✅ Saqlash")
    row = (await menu_journey.rows())[0]
    assert row.spec.text == "Existing V1 draft" and row.spec.on_date.isoformat() == tomorrow
