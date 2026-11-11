"""Explicit synthetic grants for journeys modelling existing migrated users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.domain.models import UserSubscription
from namoz_bot.infrastructure.orm import RoleAssignmentRecord, RoleCapabilityRecord
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.helpers.roles import build_role_registry


async def seed_legacy_user(engine: AsyncEngine, telegram_id: int) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user, _ = await SqlAlchemySubscriptionRepository(factory).upsert_start(
        UserSubscription(telegram_id, telegram_id, "Toshkent", True)
    )
    from tests.helpers.roles import seed_roles

    registry = build_role_registry(build_capability_registry())
    await seed_roles(factory, registry)
    async with factory.begin() as session:
        if await session.scalar(
            select(RoleAssignmentRecord).where(RoleAssignmentRecord.user_id == user.id)
        ):
            return
        registry = build_role_registry(build_capability_registry())
        for role in registry.all():
            if role.system_role:
                continue
            session.add(
                RoleAssignmentRecord(user_id=user.id, role_id=role.id, enabled=True, revision=1)
            )
            session.add_all(
                RoleCapabilityRecord(user_id=user.id, role_id=role.id, capability_id=c)
                for c in role.capability_ids
            )


async def drain_workforce(app):
    """Run accepted work and delivery separately, as the two scheduler jobs do."""
    from datetime import UTC, datetime

    await app.workforce_worker.run_once(datetime.now(UTC))
    await app.scheduler.get_job("workforce-delivery").func()
