"""Durable, owner-scoped state and atomic business-effect persistence ports."""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.domain.agent_protocol import AgentResult, AgentSessionState


class AgentTransaction(Protocol):
    ledger: LedgerService
    reminders: ReminderService
    revision: int

    async def save_session(self, state: AgentSessionState | None) -> None: ...
    async def save_receipt(self, result: AgentResult) -> None: ...


class AgentStore(Protocol):
    async def get_session(self, user_id: int, now: datetime) -> AgentSessionState | None: ...
    async def get_receipt(
        self,
        user_id: int,
        request_id: str,
        now: datetime,
    ) -> AgentResult | None: ...
    async def cleanup(self, now: datetime) -> None: ...
    def transaction(
        self,
        user_id: int,
        expected_revision: int | None,
        *,
        now: datetime,
    ) -> AbstractAsyncContextManager[AgentTransaction]: ...
