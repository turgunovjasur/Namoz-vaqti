import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.orm import DailyScheduleRecord, FinanceEntryRecord
from tests.acceptance.test_main_agent_journey import response
from tests.acceptance.test_menu_agent_journey import menu_journey as _fixture
from tests.acceptance.test_menu_agent_journey import route_response, url
from tests.acceptance.test_menu_agent_journey import routes as _routes_fixture

conversation = _fixture
routes = _routes_fixture


def labels(journey):
    return [button.text for row in journey.session.reply_keyboards[7].keyboard for button in row]


async def test_voice_expense_requires_yes_and_appends_result(conversation, routes):
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.voice()
    preview_id = conversation.session.last_ids[7]
    assert "120 000" in conversation.last.text and "Kiyim" in conversation.last.text
    yes = conversation.button("✅ Ha")
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    await conversation.click(data=yes)
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != preview_id and "saqlandi" in conversation.last.text
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.click(data=yes)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_voice_no_cancels_without_business_effect(conversation, routes):
    await conversation.voice()
    await conversation.click("❌ Yo‘q")
    assert "bekor" in conversation.last.text.lower()
    assert isinstance(conversation.last, SendMessage)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    assert "💰 Kirim-chiqim" in labels(conversation)


async def test_voice_setting_works_inside_manual_menu_only_after_yes(conversation, routes):
    await conversation.text("⚙️ Sozlamalar")
    await conversation.text("📅 Kunlik jadval")
    await conversation.click("✍️ Boshqa vaqt")
    routes[0].respond(200, json=route_response("settings", "Kunlik jadval ertalab 7 da kelsin"))
    routes[4].respond(200, json=response("settings", "set_daily", {"time": "07:00"}))
    await conversation.voice()
    assert "07:00" in conversation.last.text
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        before = await session.scalar(select(DailyScheduleRecord))
        assert before.at == "21:00"
    await conversation.click("✅ Ha")
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        after = await session.scalar(select(DailyScheduleRecord))
        assert after.at == "07:00"
    assert "💰 Kirim-chiqim" in labels(conversation)


async def test_voice_read_waits_for_yes_before_fetching_book(conversation, routes, respx_mock):
    import json

    routes[0].respond(200, json=route_response("nasihat", "Kitobdan nasihat ber"))
    respx_mock.post(url("nasihat-model")).respond(
        200, json=response("nasihat", "religious_excerpt", {})
    )
    book = respx_mock.post(url("book-model")).respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"text": json.dumps({"passage_id": "p1"})},
                        ]
                    },
                }
            ]
        },
    )
    await conversation.voice()
    assert "nasihat" in conversation.last.text.lower() and book.call_count == 0
    await conversation.click("✅ Ha")
    assert "Yaxshilik qiling" in conversation.last.text and book.call_count == 1


async def test_new_voice_retires_old_approval_and_text_yes_does_not_approve(conversation, routes):
    await conversation.voice()
    old_yes = conversation.button("✅ Ha")
    routes[0].respond(200, json=route_response("settings", "Kunlik jadval ertalab 7 da kelsin"))
    routes[4].respond(200, json=response("settings", "set_daily", {"time": "07:00"}))
    await conversation.voice()
    new_yes = conversation.button("✅ Ha")
    await conversation.text("Ha")
    await conversation.click(data=old_yes)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
        assert await session.scalar(select(DailyScheduleRecord)) is None
    await conversation.click(data=new_yes)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert (await session.scalar(select(DailyScheduleRecord))).at == "07:00"


async def test_another_user_cannot_approve_voice(conversation, routes):
    await conversation.voice()
    yes = conversation.button("✅ Ha")
    await conversation.text("/start", user=8)
    await conversation.click(data=yes, user=8)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    await conversation.click(data=yes)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_manual_daily_result_is_new_message_and_menu_stays_visible(conversation):
    await conversation.text("📅 Kunlik jadval")
    panel = conversation.session.last_ids[7]
    await conversation.click("18:00")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != panel and "18:00" in conversation.last.text
    assert "💰 Kirim-chiqim" in labels(conversation)


async def test_manual_nasihat_result_is_new_message(conversation):
    await conversation.text("⚙️ Nasihat intervali")
    panel = conversation.session.last_ids[7]
    await conversation.click(data="nasihat:set:6")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != panel and "6 soatda" in conversation.last.text


async def test_manual_offset_result_is_new_message(conversation, respx_mock):
    from datetime import datetime

    from namoz_bot.domain.reminders import TASHKENT
    from tests.integration.test_namoz_vaqti_api import today_payload

    today = datetime.now(TASHKENT).date()
    payload = today_payload()
    payload["meta"]["date"] = today.isoformat()
    payload["meta"]["ym"] = today.strftime("%Y-%m")
    payload["period_table"] = [
        {"date": today.strftime("%d.%m.%Y"), "times": payload["today"]["times"]}
    ]
    respx_mock.get("https://namoz-vaqti.uz/").respond(200, json=payload)
    await conversation.text("🕌 Masjidga moslash")
    await conversation.click(data="offset:shom")
    panel = conversation.session.last_ids[7]
    await conversation.click("+1")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != panel and "+1" in conversation.last.text


async def test_manual_reminder_keeps_menu_in_every_step_and_appends_saved_result(conversation):
    await conversation.text("🔔 Eslatmalar")
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.click("📋 Eslatma ro‘yxati")
    await conversation.click("➕ Qo‘shish")
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.text("Kitob")
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.choose_time(hour=20, minute=0)
    assert "💰 Kirim-chiqim" in labels(conversation)
    await conversation.click("🔁 Har kuni")
    before = conversation.session.last_ids[7]
    await conversation.click("✅ Saqlash")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != before and len(await conversation.rows()) == 1
    assert "💰 Kirim-chiqim" in labels(conversation)


async def test_manual_accounting_read_appends_result(conversation, routes):
    await conversation.text("💰 Kirim-chiqim")
    before = conversation.session.last_ids[7]
    await conversation.click("💳 Balans")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.last_ids[7] != before and "balans" in conversation.last.text.lower()
    result_id = conversation.session.last_ids[7]
    await conversation.approved_voice()
    assert (7, result_id) in conversation.session.messages
    assert "balans" in conversation.session.messages[(7, result_id)].text.lower()


async def test_saved_reminder_result_survives_starting_next_reminder(conversation):
    await conversation.text("🔔 Eslatmalar")
    await conversation.click("📋 Eslatma ro‘yxati")
    await conversation.click("➕ Qo‘shish")
    await conversation.text("Kitob")
    await conversation.choose_time(hour=20, minute=0)
    await conversation.click("🔁 Har kuni")
    await conversation.click("✅ Saqlash")
    saved_id = conversation.session.last_ids[7]
    saved_text = conversation.session.messages[(7, saved_id)].text
    await conversation.click("➕ Qo‘shish")
    assert conversation.session.messages[(7, saved_id)].text == saved_text
    assert conversation.session.last_ids[7] != saved_id


async def test_manual_balance_result_survives_switching_to_reminders(conversation):
    await conversation.text("💰 Kirim-chiqim")
    await conversation.click("💳 Balans")
    saved_id = conversation.session.last_ids[7]
    saved_text = conversation.session.messages[(7, saved_id)].text
    await conversation.text("🔔 Eslatmalar")
    assert conversation.session.messages[(7, saved_id)].text == saved_text
    assert conversation.session.last_ids[7] != saved_id


async def test_offset_result_survives_returning_to_calendar(conversation, respx_mock):
    from datetime import datetime

    from namoz_bot.domain.reminders import TASHKENT
    from tests.integration.test_namoz_vaqti_api import today_payload

    today = datetime.now(TASHKENT).date()
    payload = today_payload()
    payload["meta"]["date"] = today.isoformat()
    payload["meta"]["ym"] = today.strftime("%Y-%m")
    payload["period_table"] = [
        {"date": today.strftime("%d.%m.%Y"), "times": payload["today"]["times"]}
    ]
    respx_mock.get("https://namoz-vaqti.uz/").respond(200, json=payload)
    await conversation.text("🕌 Masjidga moslash")
    await conversation.click(data="offset:shom")
    await conversation.click("+1")
    saved_id = conversation.session.last_ids[7]
    saved_text = conversation.session.messages[(7, saved_id)].text
    await conversation.click("📅 Taqvimga qaytish")
    assert isinstance(conversation.last, SendMessage)
    assert conversation.session.messages[(7, saved_id)].text == saved_text


@pytest.mark.parametrize("failure", ["download", "size", "duration"])
async def test_rejected_new_voice_retires_old_approval(conversation, routes, failure):
    await conversation.voice()
    old_yes = conversation.button("✅ Ha")
    if failure == "download":

        async def broken_download(*args, **kwargs):
            raise OSError("synthetic download failure")
            yield b"unreachable"

        conversation.session.stream_content = broken_download
        await conversation.voice()
        assert "yuklab bo‘lmadi" in conversation.last.text
    else:
        await conversation.voice(
            **({"size": 6_000_000} if failure == "size" else {"duration": 121})
        )
        assert "2 daqiqagacha" in conversation.last.text
    await conversation.click(data=old_yes)
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    assert "eskirgan" in conversation.last.text
