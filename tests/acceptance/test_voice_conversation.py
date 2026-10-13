import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.orm import DailyScheduleRecord, ReligiousIntervalRecord, UserRecord
from namoz_bot.presentation.settings import DailySettingsStates
from tests.acceptance.test_main_agent_journey import response
from tests.acceptance.test_menu_agent_journey import (
    menu_journey as _fixture,
)
from tests.acceptance.test_menu_agent_journey import (
    route_response,
    url,
)
from tests.acceptance.test_menu_agent_journey import (
    routes as _routes_fixture,
)

conversation = _fixture
routes = _routes_fixture


def assert_voice_ui(journey):
    labels = [b.text for row in journey.session.reply_keyboards[7].keyboard for b in row]
    assert labels == ["ℹ️ Yordam"]
    assert not any(
        getattr(getattr(call, "reply_markup", None), "inline_keyboard", None)
        for call in journey.session.calls
    )


async def test_start_and_help_expose_only_help_without_agent_calls(conversation, routes):
    assert_voice_ui(conversation)
    await conversation.text("ℹ️ Yordam")
    assert "ovoz" in conversation.last.text.lower()
    assert_voice_ui(conversation)
    assert not any(r.call_count for r in routes)


@pytest.mark.parametrize("voice", [True, False])
async def test_daily_time_saves_directly_from_command(conversation, routes, voice):
    routes[0].respond(200, json=route_response("settings", "Kunlik jadval ertalab 7 da kelsin"))
    routes[4].respond(200, json=response("settings", "set_daily", {"time": "07:00"}))
    if voice:
        await conversation.voice()
    else:
        await conversation.text("Kunlik jadval ertalab 7 da kelsin")
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        item = await session.scalar(select(DailyScheduleRecord))
    assert item.at == "07:00" and "07:00" in conversation.last.text
    assert_voice_ui(conversation)
    assert [r.call_count for r in routes] == [1, 0, 0, 0, 1]


async def test_voice_time_clarification_survives_old_manual_state(conversation, routes):
    state = conversation.app.dispatcher.fsm.get_context(
        bot=conversation.app.bot, chat_id=7, user_id=7
    )
    await state.set_state(DailySettingsStates.custom_time)
    routes[0].respond(200, json=route_response("settings", "Kunlik jadval vaqtini o‘zgartir"))
    routes[4].respond(200, json=response("settings", "set_daily", {}))
    await conversation.voice()
    assert "qaysi vaqtda" in conversation.last.text.lower()
    routes[4].respond(200, json=response("settings", "set_daily", {"time": "07:00"}))
    await conversation.voice()
    assert "07:00" in conversation.last.text and await state.get_state() is None
    assert_voice_ui(conversation)


async def test_reminder_confirmed_by_immediate_voice_yes_without_button(conversation, routes):
    routes[0].respond(200, json=route_response("reminder", "Har kuni 9 da kitobni eslat"))
    await conversation.voice()
    assert not await conversation.rows() and "tasdiq" in conversation.last.text.lower()
    assert_voice_ui(conversation)
    routes[0].respond(200, json=route_response("assistant", "Ha, saqla", control="confirm"))
    await conversation.voice()
    assert len(await conversation.rows()) == 1 and "saqlandi" in conversation.last.text
    assert [r.call_count for r in routes] == [2, 0, 0, 1, 0]
    assert_voice_ui(conversation)


@pytest.mark.parametrize("hours", [0, 6])
async def test_nasihat_interval_updated_by_voice(conversation, routes, respx_mock, hours):
    routes[0].respond(200, json=route_response("nasihat", "Nasihat har 6 soatda kelsin"))
    helper = respx_mock.post(url("nasihat-model")).respond(
        200, json=response("nasihat", "set_interval", {"hours": hours})
    )
    await conversation.voice()
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        item = await session.scalar(select(ReligiousIntervalRecord))
    assert item.interval_hours == hours and helper.call_count == 1
    assert_voice_ui(conversation)


async def test_region_and_offsets_updated_by_voice(conversation, routes):
    routes[0].respond(200, json=route_response("prayer", "Hududim Samarqand shahri"))
    routes[2].respond(200, json=response("prayer", "set_region", {"region": "Samarqand shahri"}))
    await conversation.voice()
    routes[2].respond(
        200, json=response("prayer", "set_offset", {"prayer": "shom", "minutes": 4, "mode": "set"})
    )
    await conversation.voice()
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        user = await session.scalar(select(UserRecord))
    assert user.region_code == "Samarqand" and user.shom_offset == 4
    assert_voice_ui(conversation)


async def test_delete_and_undo_use_voice_confirmation(conversation, routes):
    routes[0].respond(200, json=route_response("reminder"))
    await conversation.voice()
    await conversation.text("Ha, saqla")
    target = (await conversation.rows())[0]
    routes[3].respond(200, json=response("reminder", "delete", {"target_id": target.id}))
    await conversation.voice()
    assert "o‘chir" in conversation.last.text.lower() and await conversation.rows()
    routes[0].respond(200, json=route_response("assistant", "Ha", control="confirm"))
    await conversation.voice()
    assert not await conversation.rows()
    routes[0].respond(200, json=route_response("accounting"))
    await conversation.voice()
    routes[1].respond(200, json=response("accounting", "undo", {}))
    await conversation.voice()
    routes[0].respond(200, json=route_response("assistant", "Ha", control="confirm"))
    await conversation.voice()
    assert "bekor qilindi" in conversation.last.text
    assert_voice_ui(conversation)


async def test_voice_provider_failure_preserves_draft_and_help_ui(conversation, routes):
    routes[0].respond(200, json=route_response("settings"))
    routes[4].respond(200, json=response("settings", "set_daily", {}))
    await conversation.voice()
    routes[4].respond(503, json={"error": "private detail"})
    await conversation.voice()
    assert "private" not in conversation.last.text
    await conversation.text("Davom et")
    assert "qaysi vaqtda" in conversation.last.text.lower()
    assert_voice_ui(conversation)


async def test_helpers_receive_text_only_and_no_other_domain_view(conversation, routes):
    await conversation.voice()
    body = json.loads(routes[1].calls.last.request.content)
    assert not any("inlineData" in part for part in body["contents"][0]["parts"])
    assert_voice_ui(conversation)


@pytest.mark.parametrize(
    "domain,action,parameters,route_index,expected",
    [
        ("accounting", "balance", {}, 1, "Balans"),
        ("accounting", "report", {"report_type": "expense"}, 1, "Xarajat"),
        ("accounting", "history", {}, 1, "tarixi"),
        ("reminder", "list", {"today": True}, 3, "Eslatmalar"),
    ],
)
async def test_voice_read_operations_do_not_open_visual_menu(
    conversation, routes, domain, action, parameters, route_index, expected
):
    routes[0].respond(200, json=route_response(domain))
    routes[route_index].respond(200, json=response(domain, action, parameters))
    await conversation.voice()
    assert expected in conversation.last.text
    assert_voice_ui(conversation)


async def test_voice_nasihat_returns_book_source(conversation, routes, respx_mock):
    routes[0].respond(200, json=route_response("nasihat", "Nasihat ber"))
    respx_mock.post(url("nasihat-model")).respond(
        200, json=response("nasihat", "religious_excerpt", {})
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
    await conversation.voice()
    assert "Yaxshilik qiling" in conversation.last.text and "Sinov kitobi" in conversation.last.text
    assert_voice_ui(conversation)


async def test_replayed_finance_receipt_shows_current_cancelled_state(conversation, routes):
    from datetime import UTC, datetime

    from aiogram.types import Update

    update = Update.model_validate(
        {
            "update_id": 777,
            "message": {
                "message_id": 777,
                "date": datetime.now(UTC),
                "text": "120 mingga kiyim oldim",
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Test"},
            },
        }
    )
    await conversation.app.dispatcher.feed_update(conversation.app.bot, update)
    routes[1].respond(200, json=response("accounting", "undo", {}))
    await conversation.voice()
    await conversation.text("Ha, saqla")
    await conversation.app.dispatcher.feed_update(conversation.app.bot, update)
    assert "bekor qilingan" in conversation.last.text
    assert_voice_ui(conversation)
