"""Atomic journal insertion, owner-scoped cancellation, and exact SQL totals."""

from datetime import date

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.accounting import LedgerEntry, LedgerSpec, LedgerSummary
from namoz_bot.infrastructure.orm import FinanceEntryRecord


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
    )


class SqlAlchemyLedgerRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create(self, user_id: int, spec: LedgerSpec, source_key: str) -> LedgerEntry:
        if not source_key or len(source_key) > 64:
            raise ValueError("Yozuv manbasi noto‘g‘ri.")
        async with self._factory.begin() as session:
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

    async def balance(self, user_id: int) -> int:
        r = FinanceEntryRecord
        signed = case((r.kind == "income", r.amount), else_=-r.amount)
        async with self._factory() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(signed), 0)).where(
                    r.user_id == user_id, r.cancelled_at.is_(None)
                )
            )
            return int(total or 0)

    async def summary(self, user_id: int, month: date) -> LedgerSummary:
        r = FinanceEntryRecord
        monthly = r.period == month
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
        ).where(r.user_id == user_id, r.cancelled_at.is_(None))
        async with self._factory() as session:
            row = (await session.execute(query)).one()
            return LedgerSummary(month, int(row[0]), int(row[1]), int(row[2]), int(row[3]))

    async def history(self, user_id: int, *, offset: int, limit: int) -> list[LedgerEntry]:
        async with self._factory() as session:
            rows = await session.scalars(
                select(FinanceEntryRecord)
                .where(FinanceEntryRecord.user_id == user_id)
                .order_by(FinanceEntryRecord.id.desc())
                .offset(offset)
                .limit(limit)
            )
            return [_entry(row) for row in rows]

    async def cancel(self, user_id: int, entry_id: int) -> bool:
        async with self._factory.begin() as session:
            cancelled = await session.scalar(
                update(FinanceEntryRecord)
                .where(
                    FinanceEntryRecord.id == entry_id,
                    FinanceEntryRecord.user_id == user_id,
                    FinanceEntryRecord.cancelled_at.is_(None),
                )
                .values(cancelled_at=func.now())
                .returning(FinanceEntryRecord.id)
            )
            return cancelled is not None
