"""Personal ledger operations and bounded structured input extraction."""

import asyncio
from datetime import date, datetime
from typing import Protocol

from namoz_bot.application.workforce.authorization import authorized
from namoz_bot.domain.accounting import (
    AccountingRequest,
    Category,
    LedgerEntry,
    LedgerSpec,
    LedgerSummary,
)
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.workforce.corrections import FinanceCorrection


class LedgerRepository(Protocol):
    async def correct(
        self, user_id: int, correction: FinanceCorrection, source_key: str, now: datetime
    ) -> LedgerEntry: ...
    async def find_for_user(self, user_id: int, text: str | None) -> list[LedgerEntry]: ...
    async def get_for_user(self, user_id: int, entry_id: int) -> LedgerEntry | None: ...
    async def create(self, user_id: int, spec: LedgerSpec, source_key: str) -> LedgerEntry: ...
    async def balance(self, user_id: int) -> int: ...
    async def summary(
        self, user_id: int, month: date, *, category: Category | None = None
    ) -> LedgerSummary: ...
    async def history(self, user_id: int, *, offset: int, limit: int) -> list[LedgerEntry]: ...
    async def cancel(self, user_id: int, entry_id: int) -> bool: ...


class AccountingExtractor(Protocol):
    async def extract(
        self, *, text: str | None, audio: bytes | None, mime_type: str, now: datetime
    ) -> AccountingRequest: ...


class LedgerService:
    def __init__(self, repository: LedgerRepository, extractor: AccountingExtractor | None = None):
        self._repository = repository
        self._extractor = extractor
        self._slots = asyncio.Semaphore(3)

    @property
    def input_enabled(self) -> bool:
        return self._extractor is not None

    async def extract(
        self, *, text: str | None, audio: bytes | None, mime_type: str, now: datetime
    ) -> AccountingRequest:
        if self._extractor is None:
            raise ExternalServiceError("Kirim-chiqim ovozli xizmati sozlanmagan.")
        async with self._slots:
            return await self._extractor.extract(
                text=text, audio=audio, mime_type=mime_type, now=now
            )

    @authorized(lambda self, user_id, request, *a, **k: "finance." + request.intent)
    async def record(
        self, user_id: int, request: AccountingRequest, source_key: str, now: datetime
    ) -> LedgerEntry:
        return await self._repository.create(user_id, request.transaction(now), source_key)

    @authorized("finance.balance")
    async def balance(self, user_id: int) -> int:
        return await self._repository.balance(user_id)

    @authorized("finance.report")
    async def summary(
        self, user_id: int, month: date, *, category: Category | None = None
    ) -> LedgerSummary:
        return await self._repository.summary(
            user_id, month.replace(day=1), **({"category": category} if category else {})
        )

    @authorized("finance.history")
    async def history(self, user_id: int, page: int) -> tuple[list[LedgerEntry], bool]:
        if not 0 <= page <= 100000:
            raise ValueError("Tarix sahifasi noto‘g‘ri.")
        entries = await self._repository.history(user_id, offset=page * 5, limit=6)
        return entries[:5], len(entries) > 5

    @authorized("finance.undo")
    async def cancel(self, user_id: int, entry_id: int) -> bool:
        return await self._repository.cancel(user_id, entry_id)

    @authorized("finance.undo")
    async def get(self, user_id: int, entry_id: int) -> LedgerEntry | None:
        return await self._repository.get_for_user(user_id, entry_id)

    @authorized("finance.undo")
    async def find(self, user_id: int, text: str | None) -> list[LedgerEntry]:
        return await self._repository.find_for_user(user_id, text)

    @authorized("finance.correct")
    async def correct(
        self, user_id: int, correction: FinanceCorrection, source_key: str, now: datetime
    ) -> LedgerEntry:
        return await self._repository.correct(user_id, correction, source_key, now)
