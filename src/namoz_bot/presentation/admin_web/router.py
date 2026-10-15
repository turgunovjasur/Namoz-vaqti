"""Private administrator-only web entry; every click issues a fresh one-use ticket."""

from urllib.parse import urlsplit

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.infrastructure.admin_web.auth import AdminAuth


class AdminWebEntry:
    def __init__(self, auth: AdminAuth, base_url: str) -> None:
        self.auth, self.base_url = auth, base_url

    async def send(self, message: Message, telegram_id: int) -> None:
        if message.chat.type != "private" or message.chat.id != telegram_id:
            return
        try:
            ticket = await self.auth.issue_ticket(telegram_id)
        except AccessDenied:
            await message.answer("Bu bo‘lim faqat administrator uchun.", parse_mode=None)
            return
        local = urlsplit(self.base_url).scheme == "http"
        text = "🌐 Admin web panel\n\nHavola 5 daqiqa amal qiladi va faqat bir marta ishlaydi."
        if local:
            text += (
                "\n\nLokal panel shu kompyuterda ochiladi. "
                "Telefonda kirish uchun HTTPS manzili kerak."
            )
        await message.answer(
            text,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🌐 Panelni ochish", url=f"{self.base_url}/#login={ticket}"
                        )
                    ]
                ]
            ),
        )


def build_admin_web_router(entry: AdminWebEntry) -> Router:
    router = Router(name="admin-web-entry")

    @router.message(Command("admin"))
    async def open_panel(message: Message) -> None:
        if message.from_user is not None:
            await entry.send(message, message.from_user.id)

    return router
