from datetime import UTC, datetime, timedelta

import pytest
from aiogram.methods import SendMessage

from tests.acceptance.test_gemini_journey import gemini_journey as _journey_fixture

interval_journey = _journey_fixture


@pytest.mark.parametrize(
    "interval_journey", [{"GEMINI_REMINDER_INTERVAL_HOURS": 24}], indirect=True
)
async def test_user_changes_interval_custom_value_and_disables_without_disabling_prayers(
    interval_journey,
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository

    journey = interval_journey
    await journey.text("/start")
    await journey.text("⚙️ Sozlamalar")
    labels = [button.text for row in journey.session.reply_keyboards[7].keyboard for button in row]
    assert "⚙️ Nasihat intervali" in labels
    await journey.text("⚙️ Nasihat intervali")
    assert "24 soatda" in journey.last.text
    assert "nasihat:set:6" in [
        button.callback_data for row in journey.last.reply_markup.inline_keyboard for button in row
    ]
    await journey.click(data="nasihat:set:6")
    repo = SqlAlchemyReligiousIntervalRepository(
        async_sessionmaker(journey.app.db_engine, expire_on_commit=False)
    )
    saved = await repo.get(7)
    assert saved.interval_hours == 6
    assert saved.next_due == datetime.now(UTC).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=6)
    await journey.click(data="nasihat:custom")
    await journey.text("0")
    assert "1–168" in journey.last.text
    assert (await repo.get(7)).interval_hours == 6
    await journey.text("9")
    assert (await repo.get(7)).interval_hours == 9
    await journey.click(data="nasihat:set:0")
    assert (await repo.get(7)).interval_hours == 0
    assert (await repo.get(7)).next_due is None
    from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository

    users = SqlAlchemySubscriptionRepository(
        async_sessionmaker(journey.app.db_engine, expire_on_commit=False)
    )
    assert (await users.get_by_telegram_user_id(7)).is_active is True


@pytest.mark.parametrize(
    "interval_journey", [{"GEMINI_REMINDER_INTERVAL_HOURS": 24}], indirect=True
)
async def test_leaving_custom_interval_input_does_not_consume_other_commands(interval_journey):
    gemini_journey = interval_journey
    await gemini_journey.text("/start")
    await gemini_journey.text("⚙️ Nasihat intervali")
    await gemini_journey.click(data="nasihat:custom")
    assert "1–168" in gemini_journey.last.text
    await gemini_journey.text("⬅️ Asosiy menyu")
    assert isinstance(gemini_journey.last, SendMessage)
    assert "Asosiy menyu" in gemini_journey.last.text
    context = gemini_journey.app.dispatcher.fsm.get_context(
        bot=gemini_journey.app.bot, chat_id=7, user_id=7
    )
    assert await context.get_state() is None


@pytest.mark.parametrize(
    "interval_journey", [{"GEMINI_REMINDER_INTERVAL_HOURS": 24}], indirect=True
)
async def test_retired_interval_callback_does_not_interrupt_personal_reminders(interval_journey):
    journey = interval_journey
    await journey.text("/start")
    await journey.text("⚙️ Nasihat intervali")
    old_custom = journey.button("✍️ Boshqa interval")
    await journey.text("⬅️ Asosiy menyu")
    await journey.text("🔔 Eslatmalar")
    await journey.click(data=old_custom)
    context = journey.app.dispatcher.fsm.get_context(bot=journey.app.bot, chat_id=7, user_id=7)
    assert await context.get_state() is None
    await journey.click("📋 Eslatma ro‘yxati")
    assert "eskirgan" not in journey.last.text.lower()
