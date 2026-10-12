"""Personal ledger operations and bounded structured input extraction."""

import asyncio
from datetime import date, datetime
from typing import Protocol

from namoz_bot.domain.accounting import AccountingRequest, LedgerEntry, LedgerSpec, LedgerSummary
from namoz_bot.domain.errors import ExternalServiceError


class LedgerRepository(Protocol):
    async def create(self, user_id: int, spec: LedgerSpec, source_key: str) -> LedgerEntry: ...
    async def balance(self, user_id: int) -> int: ...
    async def summary(self, user_id: int, month: date) -> LedgerSummary: ...
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

    async def record(
        self, user_id: int, request: AccountingRequest, source_key: str, now: datetime
    ) -> LedgerEntry:
        return await self._repository.create(user_id, request.transaction(now), source_key)

    async def balance(self, user_id: int) -> int:
        return await self._repository.balance(user_id)

    async def summary(self, user_id: int, month: date) -> LedgerSummary:
        return await self._repository.summary(user_id, month.replace(day=1))

    async def history(self, user_id: int, page: int) -> tuple[list[LedgerEntry], bool]:
        if not 0 <= page <= 100000:
            raise ValueError("Tarix sahifasi noto‘g‘ri.")
        entries = await self._repository.history(user_id, offset=page * 5, limit=6)
        return entries[:5], len(entries) > 5

    async def cancel(self, user_id: int, entry_id: int) -> bool:
        return await self._repository.cancel(user_id, entry_id)
