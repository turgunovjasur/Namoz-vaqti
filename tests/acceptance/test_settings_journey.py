from datetime import time

from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from tests.acceptance.test_gemini_journey import gemini_journey as _fixture

settings_journey = _fixture


async def test_settings_menu_daily_time_custom_validation_and_return(settings_journey):
    journey = settings_journey
    await journey.text("/start")
    labels = [b.text for row in journey.session.reply_keyboards[7].keyboard for b in row]
    assert "⚙️ Sozlamalar" in labels
    await journey.text("⚙️ Sozlamalar")
    labels = [b.text for row in journey.session.reply_keyboards[7].keyboard for b in row]
    assert "⚙️ Nasihat intervali" in labels
    assert "📅 Kunlik jadval" in labels
    await journey.text("📅 Kunlik jadval")
    assert "21:00" in journey.last.text
    assert "ertangi" in journey.last.text.lower()
    await journey.click(data="daily:set:18:00")
    repo = SqlAlchemyDailyScheduleRepository(
        async_sessionmaker(journey.app.db_engine, expire_on_commit=False)
    )
    assert (await repo.get(7)).at == time(18)
    await journey.click("✍️ Boshqa vaqt")
    await journey.text("25:00")
    assert (await repo.get(7)).at == time(18)
    await journey.text("07:30")
    assert (await repo.get(7)).at == time(7, 30)
    assert "07:30" in journey.last.text
    await journey.text("⚙️ Nasihat intervali")
    assert "Nasihat intervali" in journey.last.text
    await journey.text("⬅️ Asosiy menyu")
    assert "Asosiy menyu" in journey.last.text


async def test_retired_daily_callback_does_not_interrupt_personal_reminders(settings_journey):
    journey = settings_journey
    await journey.text("/start")
    await journey.text("⚙️ Sozlamalar")
    await journey.text("📅 Kunlik jadval")
    old_custom = journey.button("✍️ Boshqa vaqt")
    await journey.text("⬅️ Asosiy menyu")
    await journey.text("🔔 Eslatmalar")
    await journey.click(data=old_custom)
    context = journey.app.dispatcher.fsm.get_context(bot=journey.app.bot, chat_id=7, user_id=7)
    assert await context.get_state() is None
    await journey.click("📋 Eslatma ro‘yxati")
    assert "eskirgan" not in journey.last.text.lower()
