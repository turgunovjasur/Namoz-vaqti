import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from namoz_bot.domain.models import UserSubscription
from namoz_bot.infrastructure.orm import Base
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.integration.test_reminder_repository import migrate

NOW = datetime(2026, 10, 12, 10, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgres"])
async def ledger(tmp_path, request):
    from namoz_bot.application.accounting import LedgerService
    from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository

    admin = None
    schema = f"finance_test_{uuid4().hex}"
    if request.param == "postgres":
        url = os.getenv("NAMOZ_TEST_DATABASE_URL")
        if not url:
            pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
        assert "test" in (make_url(url).database or "")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ledger.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate if admin else Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        users = SqlAlchemySubscriptionRepository(factory)
        first = await users.add(UserSubscription(7, 7, "Toshkent", True))
        second = await users.add(UserSubscription(8, 8, "Toshkent", True))
        yield LedgerService(SqlAlchemyLedgerRepository(factory)), first.id, second.id
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await admin.dispose()


def request(**changes):
    from namoz_bot.domain.accounting import AccountingRequest

    return AccountingRequest.model_validate(
        {
            "transcript": "Oktyabrda o‘n million oylik tushdi",
            "intent": "income",
            "amount": 10_000_000,
            "currency": "UZS",
            "category": "oylik",
            "description": "Oylik",
            "month": "2026-10",
            "date": None,
            "report_type": None,
            "clarification": None,
        }
        | changes
    )


async def test_income_expense_and_month_salary_are_exact(ledger):
    service, user, _ = ledger
    income = await service.record(user, request(), "telegram:7:1", NOW)
    assert income.occurred_on is None  # Month was spoken; no invented day.
    await service.record(
        user,
        request(
            intent="expense",
            amount=120_000,
            category="kiyim",
            description="Kiyim",
            date="2026-10-12",
        ),
        "telegram:7:2",
        NOW,
    )
    assert await service.balance(user) == 9_880_000
    summary = await service.summary(user, date(2026, 10, 1))
    assert (summary.income, summary.expense, summary.salary) == (10_000_000, 120_000, 10_000_000)
    assert summary.opening_balance == 0
    assert summary.closing_balance == 9_880_000


async def test_previous_month_balance_rolls_over_and_other_users_are_isolated(ledger):
    service, user, other = ledger
    await service.record(user, request(amount=2_000_000, month="2026-09"), "old", NOW)
    await service.record(user, request(), "new", NOW)
    await service.record(other, request(amount=99_000_000), "new", NOW)
    summary = await service.summary(user, date(2026, 10, 1))
    assert summary.income == 10_000_000
    assert summary.opening_balance == 2_000_000
    assert summary.closing_balance == 12_000_000
    assert await service.balance(user) == 12_000_000
    assert await service.balance(other) == 99_000_000


async def test_duplicate_message_and_replayed_cancelled_record_do_not_change_balance(ledger):
    service, user, _ = ledger
    first = await service.record(user, request(), "same-message", NOW)
    repeated = await service.record(user, request(amount=12_000_000), "same-message", NOW)
    assert first.id == repeated.id
    assert await service.balance(user) == 10_000_000
    assert await service.cancel(user, first.id) is True
    assert await service.cancel(user, first.id) is False
    await service.record(user, request(), "same-message", NOW)
    assert await service.balance(user) == 0
    entries, more = await service.history(user, 0)
    assert len(entries) == 1
    assert entries[0].cancelled is True
    assert more is False


async def test_cancellation_is_owner_scoped_and_can_make_balance_negative(ledger):
    service, user, other = ledger
    income = await service.record(user, request(), "in", NOW)
    await service.record(
        user, request(intent="expense", amount=120_000, category="kiyim"), "out", NOW
    )
    assert await service.cancel(other, income.id) is False
    assert await service.balance(user) == 9_880_000
    await service.cancel(user, income.id)
    assert await service.balance(user) == -120_000


async def test_missing_date_uses_tashkent_message_date(ledger):
    service, user, _ = ledger
    at = datetime(2026, 9, 30, 21, tzinfo=UTC)
    entry = await service.record(user, request(month=None), "boundary", at)
    assert entry.period == date(2026, 10, 1)
    assert entry.occurred_on == date(2026, 10, 1)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": None},
        {"month": "2026-11"},
        {"date": "2026-10-13"},
        {"intent": "balance"},
        {"category": None},
        {"currency": "OTHER"},
    ],
)
async def test_incomplete_or_future_transaction_cannot_be_recorded(ledger, changes):
    service, user, _ = ledger
    with pytest.raises(ValueError):
        await service.record(user, request(**changes), "invalid", NOW)
    assert await service.balance(user) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"amount": -120_000},
        {"amount": 12.5},
        {"amount": True},
        {"amount": 10**15 + 1},
        {"date": "2026-02-30"},
        {"month": "2026-13"},
        {"date": "2026-09-12"},
        {"category": "arbitrary"},
        {"intent": "delete_all"},
    ],
)
def test_extracted_contract_rejects_invalid_fields(changes):
    with pytest.raises(ValidationError):
        request(**changes)
