import json
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.types import Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.config import Settings
from namoz_bot.domain.agent_protocol import AgentContext, AgentResult, AgentSessionState
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.orm import Base, FinanceEntryRecord, UserRecord
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
    book = tmp_path / "book.json"
    book.write_text(
        json.dumps(
            {
                "title": "Sinov kitobi",
                "author": "Sinov muallifi",
                "passages": [
                    {"id": "p1", "text": "Yaxshilik qiling.", "page_start": 1, "page_end": 1}
                ],
            }
        )
    )
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
            GEMINI_NASIHAT_AGENT_MODEL="nasihat-model",
            GEMINI_MODEL="book-model",
            GEMINI_BUTTON_COOLDOWN_SECONDS=0,
            MAIN_AGENT_VERSION=2,
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
            GEMINI_BOOK_CORPUS_PATH=book,
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


async def test_nasihat_has_own_agent_and_returns_original_book_passage(
    menu_journey, routes, respx_mock
):
    helper = respx_mock.post(url("nasihat-model")).respond(
        200, json=response("nasihat", "religious_excerpt", {})
    )
    book = respx_mock.post(url("book-model")).respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": json.dumps({"passage_id": "p1"})}]},
                }
            ]
        },
    )
    routes[0].respond(200, json=route_response("nasihat", "Nasihat ber"))
    await menu_journey.text("Nasihat ber")
    assert "Yaxshilik qiling." in menu_journey.last.text
    assert "Sinov kitobi" in menu_journey.last.text
    assert [r.call_count for r in routes] == [1, 0, 0, 0, 0]
    assert helper.call_count == 1 and book.call_count == 1
    assert not await entries(menu_journey) and not await menu_journey.rows()


@pytest.mark.parametrize("parameters", [{"view": "interval"}, {}])
async def test_nasihat_agent_opens_interval_settings(menu_journey, routes, respx_mock, parameters):
    respx_mock.post(url("nasihat-model")).respond(
        200, json=response("nasihat", "open_settings", parameters)
    )
    routes[0].respond(200, json=route_response("nasihat", "Nasihat oralig‘ini sozla"))
    await menu_journey.text("Nasihat oralig‘ini sozla")
    assert "Nasihat intervali" in menu_journey.last.text
    assert [r.call_count for r in routes] == [1, 0, 0, 0, 0]


async def test_prayer_agent_cannot_generate_nasihat(menu_journey, routes, respx_mock):
    book = respx_mock.post(url("book-model")).respond(500)
    routes[0].respond(200, json=route_response("prayer"))
    routes[2].respond(200, json=response("prayer", "religious_excerpt", {}))
    await menu_journey.text("Nasihat ber")
    assert "qayta" in menu_journey.last.text and book.call_count == 0


async def test_prayer_agent_cannot_open_nasihat_interval(menu_journey, routes):
    routes[0].respond(200, json=route_response("prayer"))
    routes[2].respond(200, json=response("prayer", "open_settings", {"view": "interval"}))
    await menu_journey.text("Nasihat oralig‘ini sozla")
    assert "qayta" in menu_journey.last.text


@pytest.mark.parametrize(
    "old_domain,old_action,parameters,new_action",
    [
        ("prayer", "religious_excerpt", {}, "religious_excerpt"),
        ("settings", "open", {"view": "interval"}, "open_settings"),
        ("prayer", "open_settings", {"view": "interval"}, "open_settings"),
    ],
)
@pytest.mark.parametrize("path", ["resume", "followup", "receipt_replay"])
async def test_legacy_nasihat_draft_survives_section_split(
    menu_journey, routes, respx_mock, old_domain, old_action, parameters, new_action, path
):
    main = menu_journey.app.dispatcher["main_agent"]
    async with async_sessionmaker(menu_journey.app.db_engine)() as session:
        user_id = await session.scalar(
            select(UserRecord.id).where(UserRecord.telegram_user_id == 7)
        )
    now = datetime.now(UTC)
    context = AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=user_id,
        message_time=now,
        region_code="Toshkent",
    )
    old = AgentSessionState(
        domain=old_domain,
        action=old_action,
        parameters=parameters,
        operation_id="legacy-nasihat",
        origin_source_key="legacy-origin",
        origin_time=now,
        missing_fields=["clarification"],
        question="Qaysi nasihat?",
        revision=1,
        expires_at=now + timedelta(hours=24),
    )
    receipt = AgentResult(
        request_id="legacy:pending",
        operation_id=old.operation_id,
        domain=old_domain,
        action=old_action,
        status="needs_input",
        missing_fields=old.missing_fields,
        question=old.question,
    )
    async with main.store.transaction(user_id, None, now=now) as transaction:
        await transaction.save_session(old)
        await transaction.save_receipt(receipt)
    loaded = await main.store.get_session(user_id, now)
    assert (loaded.domain, loaded.action) == ("nasihat", new_action)
    assert loaded.model_dump(exclude={"domain", "action"}) == old.model_dump(
        exclude={"domain", "action"}
    )
    if path == "resume":
        output = await main.resume(context=context, request_id="resume:legacy")
    elif path == "receipt_replay":
        output = await main.respond(context=context, request_id="legacy:pending", text="unused")
    else:
        routes[0].respond(200, json=route_response("nasihat", "Nasihat ber"))
        helper = respx_mock.post(url("nasihat-model")).respond(
            200, json=response("nasihat", new_action, parameters)
        )
        respx_mock.post(url("book-model")).respond(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps({"passage_id": "p1"})}]},
                    }
                ]
            },
        )
        output = await main.respond(
            context=context, request_id="followup:legacy", text="Nasihat ber"
        )
        assert output.status == "done"
        assert await main.store.get_session(user_id, now) is None
        pending = json.loads(helper.calls.last.request.content)["contents"][0]["parts"][0]["text"]
        assert json.loads(pending)["pending"]["domain"] == "nasihat"
    assert output.domain == "nasihat" and output.operation_id == old.operation_id
    if path != "followup":
        assert output.status == "needs_input" and output.question == old.question
        assert output.data["revision"] == 1 and routes[0].call_count == 0


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
