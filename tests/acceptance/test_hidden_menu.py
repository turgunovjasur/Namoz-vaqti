from datetime import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from tests.acceptance.test_menu_agent_journey import menu_journey as _fixture
from tests.acceptance.test_menu_agent_journey import routes as _routes_fixture

conversation = _fixture
routes = _routes_fixture


def keyboard_labels(journey, user=7):
    return [button.text for row in journey.session.reply_keyboards[user].keyboard for button in row]


async def test_menu_command_opens_working_sections_without_advertising_entry(conversation):
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    assert "/menu" not in conversation.last.text
    await conversation.text("/menu")
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    await conversation.text("🕌 Namoz vaqti")
    assert "📅 Bugungi jadval" in keyboard_labels(conversation)
    await conversation.text("⬅️ Asosiy menyu")
    await conversation.text("📖 Nasihat")
    assert "⚙️ Nasihat intervali" in keyboard_labels(conversation)
    await conversation.text("⬅️ Asosiy menyu")
    await conversation.text("💰 Kirim-chiqim")
    assert "Oy farqi" in conversation.last.text
    await conversation.click("💳 Umumiy balans")
    assert "balans" in conversation.last.text.lower()
    await conversation.click("⬅️ Asosiy menyu")
    assert "📅 Taqvimchi" in keyboard_labels(conversation)


async def test_hidden_menu_reminder_wizard_keeps_callbacks_and_text_input_working(conversation):
    await conversation.text("/menu")
    await conversation.text("🔔 Eslatmalar")
    await conversation.click("📋 Eslatma ro‘yxati")
    await conversation.click("➕ Qo‘shish")
    await conversation.text("Kitob o‘qish")
    await conversation.choose_time(hour=20, minute=0)
    await conversation.click("🔁 Har kuni")
    assert not await conversation.rows()
    await conversation.click("✅ Saqlash")
    row = (await conversation.rows())[0]
    assert row.spec.text == "Kitob o‘qish" and row.spec.at == time(20)
    assert row.spec.kind == "daily"


async def test_hidden_menu_settings_survive_state_resets_and_save_custom_time(conversation):
    await conversation.text("/menu")
    await conversation.text("🕌 Namoz vaqti")
    await conversation.text("⚙️ Sozlash")
    await conversation.click(data="daily:set:18:00")
    await conversation.click("✍️ Boshqa vaqt")
    await conversation.text("07:30")
    repo = SqlAlchemyDailyScheduleRepository(async_sessionmaker(conversation.app.db_engine))
    assert (await repo.get(7)).at == time(7, 30)
    await conversation.text("⬅️ Asosiy menyu")
    await conversation.text("📖 Nasihat")
    assert "⚙️ Nasihat intervali" in keyboard_labels(conversation)


@pytest.mark.parametrize("exit_command", ["/start", "/help", "ℹ️ Yordam"])
async def test_start_and_help_close_hidden_menu_and_retire_settings_callback(
    conversation, exit_command
):
    await conversation.text("/menu")
    await conversation.text("⚙️ Sozlash")
    old = conversation.button("18:00")
    await conversation.text(exit_command)
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    assert "/menu" not in conversation.last.text
    await conversation.click(data=old)
    repo = SqlAlchemyDailyScheduleRepository(async_sessionmaker(conversation.app.db_engine))
    assert (await repo.get(7)).at == time(21)
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]


async def test_voice_exits_hidden_menu_wizard_and_uses_main_agent(conversation, routes):
    await conversation.text("/menu")
    await conversation.text("⚙️ Sozlash")
    old = conversation.button("18:00")
    await conversation.click("✍️ Boshqa vaqt")
    await conversation.approved_voice()
    assert "120 000" in conversation.last.text
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    await conversation.click(data=old)
    repo = SqlAlchemyDailyScheduleRepository(async_sessionmaker(conversation.app.db_engine))
    assert (await repo.get(7)).at == time(21)


async def test_hidden_menu_is_scoped_to_user_and_not_opened_in_groups(conversation):
    await conversation.text("/menu")
    await conversation.text("⚙️ Sozlash")
    await conversation.text("/start", user=8)
    await conversation.click(data="daily:set:18:00", user=8)
    assert keyboard_labels(conversation, user=8) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    await conversation.click(data="daily:set:18:00")
    repo = SqlAlchemyDailyScheduleRepository(async_sessionmaker(conversation.app.db_engine))
    assert (await repo.get(7)).at == time(18)
    count = len(conversation.session.calls)
    await conversation.text("/menu", group=True)
    assert len(conversation.session.calls) == count


async def test_menu_cannot_interrupt_active_main_agent_draft(conversation, routes):
    from tests.acceptance.test_menu_agent_journey import route_response

    routes[0].respond(200, json=route_response("reminder"))
    await conversation.voice()
    await conversation.text("/menu")
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]
    assert "To‘g‘ri tushundimmi" in conversation.last.text
    await conversation.click("✅ Ha")
    assert len(await conversation.rows()) == 1


async def test_plain_text_after_menu_returns_to_main_conversation(conversation, routes):
    await conversation.text("/menu")
    assert "📅 Taqvimchi" in keyboard_labels(conversation)
    await conversation.text("120 mingga kiyim oldim")
    assert "120 000" in conversation.last.text
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]


async def test_free_text_in_accounting_menu_returns_to_main_for_another_domain(
    conversation,
    routes,
):
    from sqlalchemy import select

    from namoz_bot.infrastructure.orm import DailyScheduleRecord
    from tests.acceptance.test_main_agent_journey import response
    from tests.acceptance.test_menu_agent_journey import route_response

    await conversation.text("/menu")
    await conversation.text("💰 Kirim-chiqim")
    routes[0].respond(200, json=route_response("settings", "Kunlik jadval ertalab 7 da kelsin"))
    routes[4].respond(200, json=response("settings", "set_daily", {"time": "07:00"}))
    await conversation.text("Kunlik jadval ertalab 7 da kelsin")
    async with async_sessionmaker(conversation.app.db_engine)() as session:
        item = await session.scalar(select(DailyScheduleRecord))
    assert item is not None and item.at == "07:00"
    assert keyboard_labels(conversation) == [
        "📅 Taqvimchi",
        "🔔 Rejalashtiruvchi",
        "💰 Hisobchi",
        "📖 Nasihatgo‘y",
        "🤖 Sozlovchi",
    ]


async def test_malformed_agent_callback_does_not_change_preferences(conversation):
    await conversation.text("⚙️ Sozlash")
    await conversation.click(data="ag:old:confirm:1")
    repo = SqlAlchemyDailyScheduleRepository(async_sessionmaker(conversation.app.db_engine))
    assert (await repo.get(7)).at == time(21)
