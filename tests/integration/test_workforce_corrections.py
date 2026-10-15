import asyncio
from datetime import time

import pytest
from sqlalchemy import select

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.domain.reminders import ReminderSpec
from namoz_bot.domain.workforce.corrections import (
    CorrectionConflict,
    FinanceCorrection,
    ReminderCorrection,
)
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository
from namoz_bot.infrastructure.orm import (
    CorrectionAuditRecord,
    FinanceEntryRecord,
    ReminderDeliveryRecord,
)
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from tests.integration.test_agent_sessions import NOW, finance_request
from tests.integration.test_agent_sessions import store as store


async def test_finance_correction_is_atomic_linked_owned_versioned_and_idempotent(store):
    agents, factory, user, other = store
    service = LedgerService(SqlAlchemyLedgerRepository(factory))
    original = await service.record(user, finance_request(), "original", NOW)
    replacement = finance_request().model_copy(update={"amount": 9000000})
    correction = FinanceCorrection(original.id, original.record_revision, replacement)
    with pytest.raises(RuntimeError):
        async with agents.transaction(user, None, now=NOW) as tx:
            await tx.ledger.correct(user, correction, "rolledback", NOW)
            raise RuntimeError("crash")
    assert await service.balance(user) == 10000000
    with pytest.raises(CorrectionConflict):
        await service.correct(other, correction, "foreign", NOW)
    changed = await service.correct(user, correction, "correct1", NOW)
    repeated = await service.correct(user, correction, "correct1", NOW)
    assert changed.id == repeated.id and changed.supersedes_id == original.id
    assert await service.balance(user) == 9000000
    with pytest.raises(CorrectionConflict):
        await service.correct(user, correction, "different-request", NOW)
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 2
        assert len(list(await session.scalars(select(CorrectionAuditRecord)))) == 1


async def test_category_summary_filters_totals_but_keeps_actual_account_balance(store):
    _, factory, user, _ = store
    service = LedgerService(SqlAlchemyLedgerRepository(factory))
    await service.record(user, finance_request(), "income", NOW)
    food = finance_request().model_copy(
        update={
            "intent": "expense",
            "category": "oziq_ovqat",
            "amount": 100000,
            "description": "Ovqat",
        }
    )
    clothes = food.model_copy(
        update={"category": "kiyim", "amount": 200000, "description": "Kiyim"}
    )
    await service.record(user, food, "food", NOW)
    await service.record(user, clothes, "clothes", NOW)
    report = await service.summary(user, NOW.date(), category="oziq_ovqat")
    assert report.expense == 100000 and report.income == 0
    assert report.closing_balance == 9700000 and report.category == "oziq_ovqat"
    assert (await service.summary(user, NOW.date())).expense == 300000


async def test_reminder_edit_keeps_id_invalidates_claim_and_preserves_delivery_history(store):
    _, factory, user, other = store
    repo = SqlAlchemyReminderRepository(factory)
    service = ReminderService(repo, now=lambda: NOW)
    original = await service.create(user, 7, ReminderSpec("Kitob", time(16), "daily"), "original")
    due = original.next_due
    old = (await repo.claim_due(due, limit=10))[0]
    updated = await service.update(
        user,
        ReminderCorrection(
            original.id, original.record_revision, ReminderSpec("Kitob", time(17), "daily")
        ),
        "edit1",
    )
    assert updated.id == original.id and updated.record_revision == 1
    assert not await repo.can_send(old)
    new = (await repo.claim_due(updated.next_due, limit=10))[0]
    await repo.finish(old, "sent")
    assert await repo.can_send(new)
    assert (await service.page(user, 0))[0][0].spec.at == time(17)
    with pytest.raises(CorrectionConflict):
        await service.update(
            other,
            ReminderCorrection(original.id, 1, ReminderSpec("Foreign", time(18), "daily")),
            "foreign",
        )


async def test_reminder_edit_rolls_back_and_retains_sent_history(store):
    agents, factory, user, _ = store
    repo = SqlAlchemyReminderRepository(factory)
    service = ReminderService(repo, now=lambda: NOW)
    original = await service.create(user, 7, ReminderSpec("Kitob", time(16), "daily"), "original")
    sent = (await repo.claim_due(original.next_due, limit=10))[0]
    await repo.finish(sent, "sent")
    correction = ReminderCorrection(original.id, 0, ReminderSpec("Kitob", time(17), "daily"))
    with pytest.raises(RuntimeError):
        async with agents.transaction(user, None, now=NOW) as tx:
            await tx.reminders.update(user, correction, "rolledback")
            raise RuntimeError("crash")
    assert (await repo.get_for_user(user, original.id)).record_revision == 0
    changed = await service.update(user, correction, "saved")
    repeated = await service.update(user, correction, "saved")
    assert changed.id == repeated.id and repeated.record_revision == 1
    async with factory() as session:
        history = await session.get(ReminderDeliveryRecord, sent.id)
        assert history.status == "sent" and history.record_revision == 0
        assert len(list(await session.scalars(select(CorrectionAuditRecord)))) == 1


async def test_two_concurrent_corrections_only_replace_original_once(store):
    _, factory, user, _ = store
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL owner/record locks")
    service = LedgerService(SqlAlchemyLedgerRepository(factory))
    original = await service.record(user, finance_request(), "original", NOW)
    correction = FinanceCorrection(original.id, 0, finance_request())
    results = await asyncio.gather(
        service.correct(user, correction, "one", NOW),
        service.correct(user, correction, "two", NOW),
        return_exceptions=True,
    )
    assert sum(isinstance(r, CorrectionConflict) for r in results) == 1
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 2
        assert len(list(await session.scalars(select(CorrectionAuditRecord)))) == 1
