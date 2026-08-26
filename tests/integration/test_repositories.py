import asyncio
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from namoz_bot.domain.models import (
    DeliveryStatus,
    DeliveryType,
    PrayerOffsets,
    UserSubscription,
)
from namoz_bot.infrastructure.orm import Base
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)


@pytest.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_path = tmp_path / "repository.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_subscription_repository_round_trips_domain_entity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    created = await repository.add(UserSubscription(123456789, 987654321, "Toshkent", True))

    loaded = await repository.get_by_telegram_user_id(123456789)

    assert created.id is not None
    assert loaded == created


async def test_subscription_repository_round_trips_all_prayer_offsets(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    created = await repository.add(UserSubscription(123, 321, "Toshkent", True))

    saved = await repository.save(
        created.with_preferences(
            offsets=PrayerOffsets(
                bomdod=-3,
                quyosh=-2,
                peshin=-1,
                asr=1,
                shom=4,
                xufton=5,
            )
        )
    )
    loaded = await SqlAlchemySubscriptionRepository(session_factory).get_by_telegram_user_id(
        saved.telegram_user_id
    )

    assert loaded is not None
    assert loaded.offsets == PrayerOffsets(-3, -2, -1, 1, 4, 5)


async def test_start_upsert_preserves_region_and_reactivates_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    original, created = await repository.upsert_start(UserSubscription(1, 11, "Toshkent", True))
    await repository.save(
        original.with_preferences(
            region_code="Samarqand",
            is_active=False,
            offsets=PrayerOffsets(shom=4),
        )
    )

    reactivated, created_again = await repository.upsert_start(
        UserSubscription(1, 22, "Toshkent", True)
    )

    assert created is True
    assert created_again is False
    assert reactivated.chat_id == 22
    assert reactivated.region_code == "Samarqand"
    assert reactivated.is_active is True
    assert reactivated.offsets == PrayerOffsets(shom=4)


async def test_atomic_offset_updates_do_not_lose_concurrent_increments(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    await repository.add(UserSubscription(700, 900, "Toshkent", True))

    await asyncio.gather(*(repository.change_offset(700, "shom", 1) for _ in range(4)))

    loaded = await repository.get_by_telegram_user_id(700)
    assert loaded is not None
    assert loaded.offsets == PrayerOffsets(shom=4)


async def test_targeted_region_and_active_updates_preserve_unrelated_preferences(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    created = await repository.add(
        UserSubscription(701, 901, "Toshkent", True, offsets=PrayerOffsets(shom=4))
    )

    changed_region = await repository.change_region(created.telegram_user_id, "Samarqand")
    disabled = await repository.set_active(created.telegram_user_id, False)

    assert changed_region.region_code == "Samarqand"
    assert changed_region.offsets == PrayerOffsets()
    assert disabled.region_code == "Samarqand"
    assert disabled.offsets == PrayerOffsets()
    assert disabled.is_active is False


async def test_subscription_repository_pages_only_active_users(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySubscriptionRepository(session_factory)
    first = await repository.add(UserSubscription(1, 11, "Toshkent", True))
    await repository.add(UserSubscription(2, 22, "Samarqand", False))
    third = await repository.add(UserSubscription(3, 33, "Buxoro", True))
    assert first.id is not None

    page = await repository.list_active_page(after_id=first.id, limit=1)

    assert page == [third]


async def test_delivery_claim_is_atomic_across_concurrent_workers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    subscriptions = SqlAlchemySubscriptionRepository(session_factory)
    user = await subscriptions.add(UserSubscription(1, 11, "Toshkent", True))
    assert user.id is not None
    first = SqlAlchemyDeliveryRepository(session_factory)
    second = SqlAlchemyDeliveryRepository(session_factory)

    claims = await asyncio.gather(
        first.claim_batch([user.id], date(2026, 8, 27), DeliveryType.DAILY),
        second.claim_batch([user.id], date(2026, 8, 27), DeliveryType.DAILY),
    )

    assert sum(user.id in claim for claim in claims) == 1


async def test_existing_claim_is_never_reclaimed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    subscriptions = SqlAlchemySubscriptionRepository(session_factory)
    user = await subscriptions.add(UserSubscription(1, 11, "Toshkent", True))
    assert user.id is not None
    deliveries = SqlAlchemyDeliveryRepository(session_factory)

    first = await deliveries.claim_batch([user.id], date(2026, 8, 27), DeliveryType.DAILY)
    await deliveries.mark_status(
        user.id,
        date(2026, 8, 27),
        DeliveryType.DAILY,
        DeliveryStatus.FAILED,
        error_code="telegram_timeout",
    )
    second = await deliveries.claim_batch([user.id], date(2026, 8, 27), DeliveryType.DAILY)

    assert first == {user.id}
    assert second == set()
