"""Optional production-dialect checks enabled with NAMOZ_TEST_DATABASE_URL."""

import asyncio
import os
from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from namoz_bot.domain.models import DeliveryType, UserSubscription
from namoz_bot.infrastructure.orm import DeliveryRecord, UserRecord
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)


async def test_postgres_concurrent_delivery_claim_uses_single_winner() -> None:
    database_url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    database_name = make_url(database_url).database or ""
    if not any(marker in database_name for marker in ("test", "verify")):
        pytest.fail("Refusing to modify a database not explicitly named test/verify")

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _clear_test_records(factory)
        subscriptions = SqlAlchemySubscriptionRepository(factory)
        user = await subscriptions.add(UserSubscription(991001, 991001, "Toshkent", True))
        assert user.id is not None

        first, second = await asyncio.gather(
            SqlAlchemyDeliveryRepository(factory).claim_batch(
                [user.id], date(2026, 8, 27), DeliveryType.DAILY
            ),
            SqlAlchemyDeliveryRepository(factory).claim_batch(
                [user.id], date(2026, 8, 27), DeliveryType.DAILY
            ),
        )

        assert sum(user.id in claimed for claimed in (first, second)) == 1
    finally:
        await _clear_test_records(factory)
        await engine.dispose()


async def _clear_test_records(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory.begin() as session:
        await session.execute(delete(DeliveryRecord))
        await session.execute(delete(UserRecord))
