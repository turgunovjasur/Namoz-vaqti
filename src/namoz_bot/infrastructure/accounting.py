"""Atomic journal insertion, owner-scoped cancellation, and exact SQL totals."""

from dataclasses import asdict
from datetime import UTC, date, datetime

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.accounting import Category, LedgerEntry, LedgerSpec, LedgerSummary
from namoz_bot.domain.workforce.corrections import CorrectionConflict, FinanceCorrection
from namoz_bot.infrastructure.orm import FinanceEntryRecord
from namoz_bot.infrastructure.session_scope import session_scope
from namoz_bot.infrastructure.workforce.corrections import audit_correction, existing_correction


def _entry(row: FinanceEntryRecord) -> LedgerEntry:
    return LedgerEntry(
        row.id,
        row.kind,
        row.amount,
        row.category,
        row.description,
        row.period,
        row.occurred_on,
        row.cancelled_at is not None,
        row.record_revision,
        row.supersedes_id,
    )


class SqlAlchemyLedgerRepository:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], *, session: AsyncSession | None = None
    ) -> None:
        self._factory = factory
        self._session = session

    async def find_for_user(self, user_id: int, text: str | None) -> list[LedgerEntry]:
        query = select(FinanceEntryRecord).where(
            FinanceEntryRecord.user_id == user_id,
            FinanceEntryRecord.cancelled_at.is_(None),
        )
        if text:
            query = query.where(FinanceEntryRecord.description.icontains(text, autoescape=True))
        async with session_scope(self._factory, self._session, write=False) as session:
            rows = await session.scalars(
                query.order_by(FinanceEntryRecord.id.desc()).limit(20 if text else 1)
            )
            return [_entry(row) for row in rows]

    async def get_for_user(self, user_id: int, entry_id: int) -> LedgerEntry | None:
        async with session_scope(self._factory, self._session, write=False) as session:
            row = await session.scalar(
                select(FinanceEntryRecord).where(
                    FinanceEntryRecord.user_id == user_id,
                    FinanceEntryRecord.id == entry_id,
                )
            )
            return _entry(row) if row is not None else None

    async def create(self, user_id: int, spec: LedgerSpec, source_key: str) -> LedgerEntry:
        if not source_key or len(source_key) > 64:
            raise ValueError("Yozuv manbasi noto‘g‘ri.")
        async with session_scope(self._factory, self._session, write=True) as session:
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(FinanceEntryRecord)
                .values(
                    user_id=user_id,
                    kind=spec.kind,
                    amount=spec.amount,
                    category=spec.category,
                    description=spec.description,
                    period=spec.period,
                    occurred_on=spec.occurred_on,
                    source_key=source_key,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "source_key"])
            )
            row = await session.scalar(
                select(FinanceEntryRecord).where(
                    FinanceEntryRecord.user_id == user_id,
                    FinanceEntryRecord.source_key == source_key,
                )
            )
            assert row is not None
            return _entry(row)

    async def balance(self, user_id: int, *, month: date | None = None) -> int:
        r = FinanceEntryRecord
        signed = case((r.kind == "income", r.amount), else_=-r.amount)
        async with session_scope(self._factory, self._session, write=False) as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(signed), 0)).where(
                    r.user_id == user_id,
                    r.cancelled_at.is_(None),
                    *([r.period == month.replace(day=1)] if month else []),
                )
            )
            return int(total or 0)

    async def summary(
        self, user_id: int, month: date, *, category: Category | None = None
    ) -> LedgerSummary:
        r = FinanceEntryRecord
        whole_month = r.period == month
        monthly = and_(whole_month, r.category == category) if category else whole_month
        signed = case((r.kind == "income", r.amount), else_=-r.amount)
        query = select(
            func.coalesce(
                func.sum(case((and_(monthly, r.kind == "income"), r.amount), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((and_(monthly, r.kind == "expense"), r.amount), else_=0)), 0
            ),
            func.coalesce(
                func.sum(
                    case(
                        (and_(monthly, r.kind == "income", r.category == "oylik"), r.amount),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(case((r.period < month, signed), else_=0)), 0),
            func.coalesce(func.sum(case((whole_month, signed), else_=0)), 0),
        ).where(r.user_id == user_id, r.cancelled_at.is_(None))
        async with session_scope(self._factory, self._session, write=False) as session:
            row = (await session.execute(query)).one()
            return LedgerSummary(
                month,
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
                category,
                int(row[3]) + int(row[4]) if category else None,
            )

    async def history(
        self, user_id: int, *, offset: int, limit: int, month: date | None = None
    ) -> list[LedgerEntry]:
        async with session_scope(self._factory, self._session, write=False) as session:
            rows = await session.scalars(
                select(FinanceEntryRecord)
                .where(
                    FinanceEntryRecord.user_id == user_id,
                    *([FinanceEntryRecord.period == month.replace(day=1)] if month else []),
                )
                .order_by(FinanceEntryRecord.id.desc())
                .offset(offset)
                .limit(limit)
            )
            return [_entry(row) for row in rows]

    async def cancel(self, user_id: int, entry_id: int) -> bool:
        async with session_scope(self._factory, self._session, write=True) as session:
            cancelled = await session.scalar(
                update(FinanceEntryRecord)
                .where(
                    FinanceEntryRecord.id == entry_id,
                    FinanceEntryRecord.user_id == user_id,
                    FinanceEntryRecord.cancelled_at.is_(None),
                )
                .values(
                    cancelled_at=func.now(), record_revision=FinanceEntryRecord.record_revision + 1
                )
                .returning(FinanceEntryRecord.id)
            )
            return cancelled is not None

    async def correct(
        self, user_id: int, correction: FinanceCorrection, source_key: str, now: datetime
    ) -> LedgerEntry:
        spec = correction.replacement.transaction(now)
        async with session_scope(self._factory, self._session, write=True) as session:
            from namoz_bot.infrastructure.workforce.profiles import lock_owner

            await lock_owner(session, user_id)
            receipt = await existing_correction(
                session, user_id, source_key, "finance", correction.original_entry_id
            )
            if receipt:
                linked = await session.get(FinanceEntryRecord, receipt.replacement_id)
                if linked is None or linked.user_id != user_id:
                    raise CorrectionConflict("Missing replacement")
                return _entry(linked)
            original = await session.scalar(
                select(FinanceEntryRecord)
                .where(
                    FinanceEntryRecord.id == correction.original_entry_id,
                    FinanceEntryRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if (
                original is None
                or original.cancelled_at is not None
                or original.record_revision != correction.expected_record_revision
            ):
                raise CorrectionConflict("Original entry changed; confirm again")
            before = asdict(_entry(original))
            original.cancelled_at = now.astimezone(UTC)
            original.record_revision += 1
            replacement = await SqlAlchemyLedgerRepository(self._factory, session=session).create(
                user_id, spec, source_key
            )
            row = await session.get(FinanceEntryRecord, replacement.id)
            assert row is not None
            row.supersedes_id = original.id
            await session.flush()
            value = _entry(row)
            audit_correction(
                session,
                user_id=user_id,
                source_key=source_key,
                kind="finance",
                original_id=original.id,
                replacement_id=row.id,
                before=before,
                after=asdict(value),
            )
            return value
