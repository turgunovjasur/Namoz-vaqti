from typing import Any, cast

from aiogram.types import TelegramObject

from namoz_bot.presentation.middleware import ErrorHandlingMiddleware


class FakeEvent:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


async def test_error_middleware_returns_safe_user_message() -> None:
    event = FakeEvent()

    async def failing_handler(_event: TelegramObject, _data: dict[str, Any]) -> None:
        raise RuntimeError("database password must not reach the user")

    result = await ErrorHandlingMiddleware()(
        failing_handler,
        cast(TelegramObject, event),
        {},
    )

    assert result is None
    assert event.answers == [
        "Vaqtincha xatolik yuz berdi. Iltimos, birozdan keyin qayta urinib ko‘ring."
    ]
