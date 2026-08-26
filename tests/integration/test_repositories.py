from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from namoz_bot.domain.models import DeliveryStatus, DeliveryType, UserSubscription
from namoz_bot.infrastructure.orm import Base
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session

    await engine.dispose()


async def test_subscription_repository_round_trips_domain_entity(session: AsyncSession) -> None:
    repository = SqlAlchemySubscriptionRepository(session)
    created = await repository.add(
        UserSubscription(
            telegram_user_id=123456789,
            chat_id=987654321,
            region_code="Toshkent",
            is_active=True,
        )
    )
    await session.commit()

    loaded = await repository.get_by_telegram_user_id(123456789)

    assert created.id is not None
    assert loaded == created


async def test_subscription_repository_lists_only_active_users(session: AsyncSession) -> None:
    repository = SqlAlchemySubscriptionRepository(session)
    await repository.add(UserSubscription(1, 11, "Toshkent", True))
    await repository.add(UserSubscription(2, 22, "Samarqand", False))
    await session.commit()

    active = await repository.list_active()

    assert [item.telegram_user_id for item in active] == [1]


async def test_delivery_reservation_is_idempotent_after_success(session: AsyncSession) -> None:
    subscriptions = SqlAlchemySubscriptionRepository(session)
    user = await subscriptions.add(UserSubscription(1, 11, "Toshkent", True))
    await session.commit()
    assert user.id is not None
    deliveries = SqlAlchemyDeliveryRepository(session)

    first = await deliveries.reserve(user.id, date(2026, 8, 27), DeliveryType.DAILY)
    await deliveries.mark_status(
        user.id,
        date(2026, 8, 27),
        DeliveryType.DAILY,
        DeliveryStatus.SENT,
    )
    second = await deliveries.reserve(user.id, date(2026, 8, 27), DeliveryType.DAILY)
    await session.commit()

    assert first is True
    assert second is False


async def test_failed_delivery_can_be_reserved_again(session: AsyncSession) -> None:
    subscriptions = SqlAlchemySubscriptionRepository(session)
    user = await subscriptions.add(UserSubscription(1, 11, "Toshkent", True))
    await session.commit()
    assert user.id is not None
    deliveries = SqlAlchemyDeliveryRepository(session)

    await deliveries.reserve(user.id, date(2026, 8, 27), DeliveryType.DAILY)
    await deliveries.mark_status(
        user.id,
        date(2026, 8, 27),
        DeliveryType.DAILY,
        DeliveryStatus.FAILED,
        error_code="telegram_timeout",
    )

    assert await deliveries.reserve(user.id, date(2026, 8, 27), DeliveryType.DAILY) is True
