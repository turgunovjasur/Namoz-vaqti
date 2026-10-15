"""Persist conversations and their effects in the same database transaction."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.daily_schedule import DailyScheduleSettingsService
from namoz_bot.application.religious_reminders import ReligiousIntervalService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.subscriptions import SubscriptionService
from namoz_bot.domain.agent_protocol import (
    AgentResult,
    AgentRevisionConflict,
    AgentSessionState,
    AgentViewState,
)
from namoz_bot.domain.workforce.profiles import PermissionSnapshot
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository, _entry
from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from namoz_bot.infrastructure.orm import AgentReceiptRecord, AgentSessionRecord, FinanceEntryRecord
from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SqlAlchemyAgentTransaction:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        session: AsyncSession,
        row: AgentSessionRecord,
        now: datetime,
        *,
        default_daily_time: time = time(21),
        default_interval_hours: float = 24,
    ) -> None:
        self._session = session
        self._row = row
        self._now = now
        self._updated = False
        self.revision = row.revision
        self.ledger = LedgerService(SqlAlchemyLedgerRepository(factory, session=session))
        self.reminders = ReminderService(
            SqlAlchemyReminderRepository(factory, session=session),
            now=lambda: now,
        )
        self.subscriptions = SubscriptionService(
            SqlAlchemySubscriptionRepository(factory, session=session)
        )
        self.daily_settings = DailyScheduleSettingsService(
            SqlAlchemyDailyScheduleRepository(factory, session=session),
            default_time=default_daily_time,
            clock=lambda: now,
        )
        self.religious_intervals = ReligiousIntervalService(
            SqlAlchemyReligiousIntervalRepository(factory, session=session),
            default_hours=default_interval_hours,
            clock=lambda: now,
        )

    async def current_grant(
        self, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot | None:
        from namoz_bot.infrastructure.workforce.profiles import current_grant

        if user_id != self._row.user_id:
            return None
        return await current_grant(self._session, user_id, role_id, capability_id)

    async def save_session(self, state: AgentSessionState | None) -> None:
        if self._updated:
            raise ValueError("Session must be updated once per transaction")
        if state is not None and state.revision != self.revision + 1:
            raise AgentRevisionConflict("Invalid next revision")
        self._row.revision = self.revision + 1
        self._row.state = state.model_dump(mode="json") if state else None
        self._row.expires_at = state.expires_at if state else None
        self._updated = True
        await self._session.flush()

    async def save_receipt(self, result: AgentResult) -> None:
        insert = (
            pg_insert if self._session.get_bind().dialect.name == "postgresql" else sqlite_insert
        )
        inserted = await self._session.scalar(
            insert(AgentReceiptRecord)
            .values(
                user_id=self._row.user_id,
                request_id=result.request_id,
                result=result.model_dump(mode="json"),
                created_at=self._now,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "request_id"])
            .returning(AgentReceiptRecord.id)
        )
        if inserted is None:
            # Roll back effects too if another processing attempt won this request.
            raise AgentRevisionConflict("Request already processed")


class SqlAlchemyAgentStore:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        default_daily_time: time = time(21),
        default_interval_hours: float = 24,
    ) -> None:
        self._factory = factory
        self._default_daily_time = default_daily_time
        self._default_interval_hours = default_interval_hours

    async def get_last_view(self, user_id: int, now: datetime) -> AgentViewState | None:
        async with self._factory() as session:
            results = await session.scalars(
                select(AgentReceiptRecord.result)
                .where(
                    AgentReceiptRecord.user_id == user_id,
                    AgentReceiptRecord.created_at > now - timedelta(minutes=30),
                )
                .order_by(AgentReceiptRecord.created_at.desc(), AgentReceiptRecord.id.desc())
                .limit(20)
            )
            for payload in results:
                if payload.get("status") != "done" or (
                    payload.get("domain"),
                    payload.get("action"),
                ) not in {("reminder", "list"), ("accounting", "history")}:
                    continue
                data = AgentResult.model_validate_json(json.dumps(payload)).data
                entries = data.get("entries", [])
                if not isinstance(entries, list):
                    continue
                return AgentViewState.model_validate(
                    {
                        "domain": payload["domain"],
                        "action": payload["action"],
                        "page": data.get("page", 0),
                        "today": data.get("today", False),
                        "ids": [entry["id"] for entry in entries if isinstance(entry, dict)],
                    }
                )
        return None

    async def get_session(self, user_id: int, now: datetime) -> AgentSessionState | None:
        async with self._factory.begin() as session:
            row = await session.get(AgentSessionRecord, user_id)
            if row is None or row.state is None:
                return None
            if row.expires_at is None or _aware(row.expires_at) <= now:
                await session.execute(
                    update(AgentSessionRecord)
                    .where(
                        AgentSessionRecord.user_id == user_id,
                        AgentSessionRecord.revision == row.revision,
                    )
                    .values(state=None, expires_at=None, revision=row.revision + 1)
                )
                return None
            pending = AgentSessionState.model_validate_json(json.dumps(row.state))
            if (pending.domain, pending.action) == ("reminder", "open_delete"):
                return pending.model_copy(update={"action": "delete"})
            # Normalize old routing names without changing operation/revision/expiry.
            # All consumers (resume, followup and receipt replay) use this boundary.
            if (pending.domain, pending.action) == ("prayer", "religious_excerpt"):
                return pending.model_copy(update={"domain": "nasihat"})
            if (pending.domain, pending.action) in {
                ("prayer", "open_settings"),
                ("settings", "open"),
            } and pending.parameters.get("view") == "interval":
                return pending.model_copy(update={"domain": "nasihat", "action": "open_settings"})
            return pending

    async def get_receipt(
        self,
        user_id: int,
        request_id: str,
        now: datetime,
    ) -> AgentResult | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(AgentReceiptRecord).where(
                    AgentReceiptRecord.user_id == user_id,
                    AgentReceiptRecord.request_id == request_id,
                    AgentReceiptRecord.created_at > now - timedelta(days=7),
                )
            )
            if row is None:
                return None
            result = AgentResult.model_validate_json(json.dumps(row.result))
            if result.domain == "accounting" and result.action in {"income", "expense"}:
                entry_id = result.data.get("entry_id")
                if type(entry_id) is int:
                    entry = await session.scalar(
                        select(FinanceEntryRecord).where(
                            FinanceEntryRecord.id == entry_id,
                            FinanceEntryRecord.user_id == user_id,
                        )
                    )
                    if entry is not None:
                        result.data["cancelled"] = _entry(entry).cancelled
                        result.data["balance"] = await SqlAlchemyLedgerRepository(
                            self._factory,
                            session=session,
                        ).balance(user_id)
            return result

    async def cleanup(self, now: datetime) -> None:
        async with self._factory.begin() as session:
            await session.execute(
                delete(AgentReceiptRecord).where(
                    AgentReceiptRecord.created_at <= now - timedelta(days=7),
                )
            )
            await session.execute(
                update(AgentSessionRecord)
                .where(
                    AgentSessionRecord.expires_at <= now,
                )
                .values(state=None, expires_at=None, revision=AgentSessionRecord.revision + 1)
            )

    @asynccontextmanager
    async def transaction(
        self,
        user_id: int,
        expected_revision: int | None,
        *,
        now: datetime,
    ) -> AsyncIterator[AgentTransaction]:
        async with self._factory.begin() as session:
            from namoz_bot.infrastructure.workforce.profiles import lock_owner

            await lock_owner(session, user_id)
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(AgentSessionRecord)
                .values(
                    user_id=user_id,
                    revision=0,
                )
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            row = await session.scalar(
                select(AgentSessionRecord)
                .where(
                    AgentSessionRecord.user_id == user_id,
                )
                .with_for_update()
            )
            assert row is not None
            actual = row.revision if row.state is not None else None
            if actual != expected_revision:
                raise AgentRevisionConflict("Session changed")
            # A conditional write reserves this revision on SQLite as well as PostgreSQL.
            won = await session.scalar(
                update(AgentSessionRecord)
                .where(
                    AgentSessionRecord.user_id == user_id,
                    AgentSessionRecord.revision == row.revision,
                )
                .values(revision=row.revision)
                .returning(AgentSessionRecord.user_id)
            )
            if won is None:
                raise AgentRevisionConflict("Session changed")
            yield SqlAlchemyAgentTransaction(
                self._factory,
                session,
                row,
                now,
                default_daily_time=self._default_daily_time,
                default_interval_hours=self._default_interval_hours,
            )
