import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from namoz_bot.domain.agent_protocol import AgentResult, AgentRevisionConflict, AgentSessionState
from namoz_bot.domain.models import UserSubscription
from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentStore
from namoz_bot.infrastructure.orm import Base, FinanceEntryRecord
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.integration.test_accounting import request as finance_request
from tests.integration.test_reminder_repository import migrate

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgres"])
async def store(tmp_path, request):
    admin = None
    schema = f"agent_test_{uuid4().hex}"
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
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(migrate if admin else Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    users = SqlAlchemySubscriptionRepository(factory)
    first = await users.add(UserSubscription(7, 7, "Toshkent", True))
    other = await users.add(UserSubscription(8, 8, "Toshkent", True))
    yield SqlAlchemyAgentStore(factory), factory, first.id, other.id
    await engine.dispose()
    if admin:
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


def draft(revision=1):
    return AgentSessionState(
        operation_id="operation",
        origin_source_key="origin",
        origin_time=NOW,
        domain="reminder",
        action="create",
        parameters={"text": "Kitob"},
        missing_fields=["time"],
        revision=revision,
        expires_at=NOW + timedelta(hours=24),
    )


def receipt(request_id="r1"):
    return AgentResult(
        request_id=request_id,
        operation_id="operation",
        domain="assistant",
        action="help",
        status="done",
        data={"text": "Yordam"},
    )


async def test_draft_survives_store_recreation_and_owner_isolation(store):
    repo, factory, user, other = store
    async with repo.transaction(user, None, now=NOW) as tx:
        await tx.save_session(draft())
        await tx.save_receipt(receipt())
    restarted = SqlAlchemyAgentStore(factory)
    assert (await restarted.get_session(user, NOW)).parameters == {"text": "Kitob"}
    assert await restarted.get_session(other, NOW) is None
    assert await restarted.get_receipt(other, "r1", NOW) is None


async def test_expired_draft_and_old_receipts_are_removed(store):
    repo, _, user, _ = store
    async with repo.transaction(user, None, now=NOW) as tx:
        await tx.save_session(draft())
        await tx.save_receipt(receipt())
    assert await repo.get_session(user, NOW + timedelta(hours=24)) is None
    await repo.cleanup(NOW + timedelta(days=7))
    assert await repo.get_receipt(user, "r1", NOW + timedelta(days=7)) is None


async def test_stale_revision_rolls_back(store):
    repo, _, user, _ = store
    async with repo.transaction(user, None, now=NOW) as tx:
        await tx.save_session(draft())
    with pytest.raises(AgentRevisionConflict):
        async with repo.transaction(user, None, now=NOW) as tx:
            await tx.ledger.record(user, finance_request(), "must-not-write", NOW)
    async with repo.transaction(user, 1, now=NOW) as tx:
        assert await tx.ledger.balance(user) == 0


async def test_write_and_receipt_rollback_together(store):
    repo, factory, user, _ = store
    with pytest.raises(RuntimeError):
        async with repo.transaction(user, None, now=NOW) as tx:
            await tx.ledger.record(user, finance_request(), "origin", NOW)
            await tx.save_receipt(receipt())
            raise RuntimeError("abort")
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    assert await repo.get_receipt(user, "r1", NOW) is None


async def test_duplicate_origin_and_cancelled_entry_are_not_reactivated(store):
    repo, _, user, _ = store
    async with repo.transaction(user, None, now=NOW) as tx:
        entry = await tx.ledger.record(user, finance_request(), "origin", NOW)
        await tx.save_receipt(receipt())
    async with repo.transaction(user, None, now=NOW) as tx:
        repeated = await tx.ledger.record(user, finance_request(), "origin", NOW)
        assert repeated.id == entry.id
        await tx.ledger.cancel(user, entry.id)
    async with repo.transaction(user, None, now=NOW) as tx:
        repeated = await tx.ledger.record(user, finance_request(), "origin", NOW)
        assert repeated.cancelled
        assert await tx.ledger.balance(user) == 0
