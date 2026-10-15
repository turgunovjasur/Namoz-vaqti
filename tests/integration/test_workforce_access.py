import asyncio

import pytest
from sqlalchemy import select

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.domain.workforce.profiles import AccessDenied, ProfileConflict
from namoz_bot.infrastructure.orm import FinanceEntryRecord, ProfileRecord
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from tests.integration.test_agent_sessions import NOW, finance_request
from tests.integration.test_agent_sessions import store as store


@pytest.fixture
async def access_setup(store):
    _, factory, user, other = store
    roles = build_role_registry(build_capability_registry())
    profiles = SqlAlchemyProfileRepository(factory, roles, admin_telegram_ids=frozenset({7}))
    return profiles, AccessService(profiles, roles), user, other


async def grant(profiles, actor, user, role, caps, enabled=True):
    view = await profiles.get_profile(user)
    revision = next((r.revision for r in view.roles if r.role_id == role), 0)
    return await profiles.set_grants(
        actor_id=actor,
        user_id=user,
        role_id=role,
        enabled=enabled,
        capability_ids=frozenset(caps),
        expected_revision=revision,
    )


async def test_capability_subset_is_per_user_role_and_role_off_suspends(access_setup):
    profiles, access, user, other = access_setup
    assert not await access.allowed(user, "accounting", "finance.expense")
    await grant(profiles, user, user, "accounting", {"finance.expense"})
    await grant(profiles, user, other, "accounting", {"finance.report"})
    assert await access.allowed(user, "accounting", "finance.expense")
    assert not await access.allowed(user, "accounting", "finance.report")
    assert not await access.allowed(other, "accounting", "finance.expense")
    await grant(profiles, user, user, "accounting", {"finance.expense"}, enabled=False)
    assert not await access.allowed(user, "accounting", "finance.expense")
    view = await profiles.get_profile(user)
    assert view.roles[0].capability_ids == frozenset({"finance.expense"})


async def test_admin_source_unknown_caps_stale_cards_and_shared_cap(access_setup, store):
    profiles, access, user, other = access_setup
    with pytest.raises(AccessDenied):
        await grant(profiles, other, other, "prayer", {"prayer.schedule"})
    with pytest.raises(ValueError):
        await grant(profiles, user, other, "prayer", {"finance.expense"})
    await grant(profiles, user, other, "prayer", {"preferences.region_view"})
    await grant(profiles, user, other, "settings", {"preferences.region_view"})
    await grant(profiles, user, other, "prayer", set())
    assert not await access.allowed(other, "prayer", "preferences.region_view")
    assert await access.allowed(other, "settings", "preferences.region_view")
    with pytest.raises(ProfileConflict):
        await profiles.set_grants(
            actor_id=user,
            user_id=other,
            role_id="prayer",
            enabled=True,
            capability_ids=frozenset(),
            expected_revision=0,
        )
    _, factory, _, _ = store
    async with factory() as session:
        assert (await session.get(ProfileRecord, user)).profile_type == "admin"
    revoked_admin = SqlAlchemyProfileRepository(
        factory, profiles.roles, admin_telegram_ids=frozenset()
    )
    assert (await revoked_admin.get_profile(user)).profile_type == "user"
    with pytest.raises(AccessDenied):
        await grant(revoked_admin, user, other, "prayer", set())


async def test_effect_rechecks_revocation_and_rolls_back(access_setup, store):
    profiles, access, user, _ = access_setup
    _, factory, _, _ = store
    await grant(profiles, user, user, "accounting", {"finance.expense"})
    with pytest.raises(RuntimeError):
        async with access.effect_scope(user, "accounting", "finance.expense", now=NOW) as tx:
            await tx.ledger.record(user, finance_request(), "rollback", NOW)
            raise RuntimeError("rollback")
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    await grant(profiles, user, user, "accounting", set())
    with pytest.raises(AccessDenied):
        async with access.effect_scope(user, "accounting", "finance.expense", now=NOW):
            pytest.fail("revoked capability executed")


async def test_revoke_waits_for_same_owner_effect_lock(access_setup, store):
    profiles, access, user, _ = access_setup
    _, factory, _, _ = store
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row lock race is PostgreSQL specific")
    await grant(profiles, user, user, "accounting", {"finance.expense"})
    entered, release = asyncio.Event(), asyncio.Event()

    async def effect():
        async with access.effect_scope(user, "accounting", "finance.expense", now=NOW) as tx:
            entered.set()
            await release.wait()
            await tx.ledger.record(user, finance_request(), "before-revoke", NOW)

    effect_task = asyncio.create_task(effect())
    await entered.wait()
    revocation = asyncio.create_task(grant(profiles, user, user, "accounting", set()))
    await asyncio.sleep(0.05)
    assert not revocation.done()
    release.set()
    await effect_task
    await revocation
    assert not await access.allowed(user, "accounting", "finance.expense")
