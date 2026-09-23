from datetime import UTC, datetime, timedelta

import pytest
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import Chat, Message, Update
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.config import Settings
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.orm import Base
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from namoz_bot.main import create_application


class LocalSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        self.calls.append(method)
        if isinstance(method, AnswerCallbackQuery):
            return True
        return Message(
            message_id=len(self.calls),
            date=datetime.now(UTC),
            chat=Chat(id=method.chat_id, type="private"),
            text=getattr(method, "text", None),
            reply_markup=method.reply_markup if isinstance(method, EditMessageText) else None,
        )


class Journey:
    def __init__(self, app):
        self.app = app
        self.session = LocalSession()
        self.app.bot.session = self.session
        self.sequence = 0

    @property
    def last(self):
        return next(
            call
            for call in reversed(self.session.calls)
            if isinstance(call, (SendMessage, EditMessageText))
        )

    def button(self, label):
        markup = self.last.reply_markup
        return next(
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
            if button.text == label
        )

    async def text(self, text, user=7, group=False):
        self.sequence += 1
        payload = {
            "message_id": self.sequence,
            "date": datetime.now(UTC),
            "chat": {"id": -100 if group else user, "type": "group" if group else "private"},
            "from": {"id": user, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
        await self.app.dispatcher.feed_update(
            self.app.bot, Update.model_validate({"update_id": self.sequence, "message": payload})
        )

    async def click(self, label=None, data=None, user=7):
        data = data or self.button(label)
        self.sequence += 1
        await self.app.dispatcher.feed_update(
            self.app.bot,
            Update.model_validate(
                {
                    "update_id": self.sequence,
                    "callback_query": {
                        "id": str(self.sequence),
                        "chat_instance": "test",
                        "data": data,
                        "from": {"id": user, "is_bot": False, "first_name": "Test"},
                        "message": {
                            "message_id": 100,
                            "date": datetime.now(UTC),
                            "chat": {"id": user, "type": "private"},
                            "from": {"id": 123456, "is_bot": True, "first_name": "Bot"},
                        },
                    },
                }
            ),
        )
        return data

    async def begin(self, text="Kitob o‘qish", user=7):
        await self.text("/start", user)
        await self.text("🔔 Eslatmalar", user)
        await self.text("➕ Eslatma qo‘shish", user)
        await self.text(text, user)
        await self.text("20:00", user)

    async def rows(self, user=7):
        factory = async_sessionmaker(self.app.db_engine, expire_on_commit=False)
        subscription = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(user)
        return await SqlAlchemyReminderRepository(factory).list_for_user(
            subscription.id, offset=0, limit=20
        )


@pytest.fixture
async def journey(tmp_path):
    app = create_application(
        Settings(
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'ui.db'}",
        )
    )
    async with app.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    yield Journey(app)
    await app.dispatcher.storage.close()
    await app.close()


async def test_menu_and_daily_creation_list_with_duplicate_save(journey):
    await journey.text("/start")
    labels = [b.text for row in journey.last.reply_markup.keyboard for b in row]
    assert labels == ["🕌 Namoz vaqti", "🔔 Eslatmalar"]
    await journey.text("🕌 Namoz vaqti")
    labels = [b.text for row in journey.last.reply_markup.keyboard for b in row]
    assert "📅 Bugungi jadval" in labels and "⬅️ Asosiy menyu" in labels
    await journey.begin()
    await journey.click("🔁 Har kuni")
    assert "20:00" in journey.last.text
    token = await journey.click("✅ Saqlash")
    await journey.click(data=token)
    assert len(await journey.rows()) == 1
    await journey.text("📋 Eslatma ro‘yxati")
    assert "Kitob o‘qish" in journey.last.text and "Har kuni" in journey.last.text


@pytest.mark.parametrize("kind", ["once", "weekly"])
async def test_date_and_weekly_creation(journey, kind):
    await journey.begin()
    if kind == "weekly":
        await journey.click("📆 Har hafta")
        await journey.click("Yakshanba")
    else:
        await journey.click("📅 Sana tanlash")
        tomorrow = (datetime.now(TASHKENT) + timedelta(days=1)).date()
        if tomorrow.day == 1:
            await journey.click("Keyingi oy ➡️")
        await journey.click(str(tomorrow.day))
    await journey.click("✅ Saqlash")
    row = (await journey.rows())[0]
    assert row.spec.kind == kind
    if kind == "weekly":
        assert row.spec.weekday == 6
    else:
        assert row.spec.on_date == tomorrow


async def test_validation_back_cancel_old_buttons_and_navigation(journey):
    await journey.text("/start")
    await journey.text("➕ Eslatma qo‘shish")
    await journey.text(" ")
    assert "1–1000" in journey.last.text
    await journey.text("Original")
    await journey.text("25:30")
    assert "00:00–23:59" in journey.last.text
    await journey.text("20:00")
    old = journey.button("🔁 Har kuni")
    await journey.click("⬅️ Orqaga")
    await journey.text("21:00")
    await journey.click(data=old)
    assert "eskirgan" in journey.session.calls[-1].text
    await journey.click("🔁 Har kuni")
    await journey.click("❌ Bekor qilish")
    assert await journey.rows() == []
    await journey.begin()
    old = journey.button("🔁 Har kuni")
    await journey.text("⬅️ Asosiy menyu")
    await journey.click(data=old)
    assert await journey.rows() == []


async def test_private_chat_owner_and_empty_list(journey):
    await journey.text("➕ Eslatma qo‘shish", group=True)
    assert "shaxsiy chat" in journey.last.text
    await journey.begin(user=7)
    old = journey.button("🔁 Har kuni")
    await journey.begin(user=8)
    await journey.click(data=old, user=8)
    assert "eskirgan" in journey.session.calls[-1].text
    await journey.click("🔁 Har kuni", user=8)
    await journey.click("✅ Saqlash", user=8)
    await journey.text("📋 Eslatma ro‘yxati", user=7)
    assert "Hozircha" in journey.last.text
    assert len(await journey.rows(8)) == 1


async def test_long_unicode_list_fits_telegram_and_paginates(journey):
    for _ in range(4):
        await journey.begin(text="📚" * 1000)
        await journey.click("🔁 Har kuni")
        await journey.click("✅ Saqlash")
    start = len(journey.session.calls)
    await journey.text("📋 Eslatma ro‘yxati")
    responses = [call for call in journey.session.calls[start:] if isinstance(call, SendMessage)]
    assert all(len(call.text.encode("utf-16-le")) // 2 <= 4096 for call in responses)
    assert sum(call.text.count("📚") for call in responses) == 3000
    await journey.click("Keyingi ➡️")
    assert journey.last.text.count("📚") == 1000


async def test_past_date_and_expired_confirmation_do_not_save(journey):
    await journey.begin()
    await journey.click("📅 Sana tanlash")
    data = journey.button("Keyingi oy ➡️").split(":")
    yesterday = (datetime.now(TASHKENT) - timedelta(days=1)).date()
    await journey.click(data=f"rem:{data[1]}:date:{yesterday.isoformat()}")
    assert "o‘tib ketgan" in journey.session.calls[-1].text
    assert await journey.rows() == []


@pytest.mark.parametrize("command", ["/cancel", "/anything"])
async def test_unknown_slash_command_does_not_corrupt_draft(journey, command):
    await journey.text("/start")
    await journey.text("➕ Eslatma qo‘shish")
    await journey.text(command)
    assert "Eslatma" in journey.last.text or "menyu" in journey.last.text
    state = journey.app.dispatcher.fsm.get_context(bot=journey.app.bot, chat_id=7, user_id=7)
    assert await state.get_state() is None
    assert await state.get_data() == {}
    await journey.begin("New reminder")
    await journey.click("🔁 Har kuni")
    await journey.click("✅ Saqlash")
    assert (await journey.rows())[0].spec.text == "New reminder"


async def test_old_list_callback_cannot_cancel_current_draft(journey):
    for _ in range(4):
        await journey.begin()
        await journey.click("🔁 Har kuni")
        await journey.click("✅ Saqlash")
    await journey.text("📋 Eslatma ro‘yxati")
    old_list_button = journey.button("Keyingi ➡️")
    await journey.begin("Unfinished")
    await journey.click("🔁 Har kuni")
    save_button = journey.button("✅ Saqlash")
    await journey.click(data=old_list_button)
    await journey.click(data=save_button)
    assert any(row.spec.text == "Unfinished" for row in await journey.rows())


async def test_scheduler_sends_saved_reminder_through_local_transport(journey):
    from namoz_bot.domain.reminders import ReminderSpec

    await journey.text("/start")
    factory = async_sessionmaker(journey.app.db_engine, expire_on_commit=False)
    owner = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    local_due = datetime.now(TASHKENT).replace(second=0, microsecond=0) - timedelta(minutes=1)
    await SqlAlchemyReminderRepository(factory).create(
        owner.id,
        7,
        ReminderSpec("Runtime delivery", local_due.time(), "once", on_date=local_due.date()),
        "runtime",
        local_due - timedelta(minutes=1),
    )
    before = len(journey.session.calls)
    job = journey.app.scheduler.get_job("personal-reminders")
    await job.func()
    await job.func()
    sends = [call for call in journey.session.calls[before:] if isinstance(call, SendMessage)]
    assert [call.text for call in sends] == ["🔔 Eslatma\n\nRuntime delivery"]
    assert (await journey.rows())[0].status == "completed"
