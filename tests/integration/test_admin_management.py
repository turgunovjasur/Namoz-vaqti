import pytest
from sqlalchemy import func, select

from namoz_bot.domain.workforce.profiles import ProfileConflict
from namoz_bot.infrastructure.orm import AdminAuditRecord
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup


def change(role, caps, revision=0, enabled=True):
    from namoz_bot.domain.workforce.profiles import GrantChange

    return GrantChange(
        role_id=role, capability_ids=frozenset(caps), enabled=enabled, expected_revision=revision
    )


async def test_batch_stale_last_role_rolls_back_first_role_and_audit(access_setup, store):
    repo, _, actor, target = access_setup
    await repo.set_grants(
        actor_id=actor,
        user_id=target,
        role_id="prayer",
        enabled=True,
        capability_ids=frozenset({"prayer.schedule"}),
        expected_revision=0,
    )
    with pytest.raises(ProfileConflict):
        await repo.set_assignments(
            actor_id=actor,
            user_id=target,
            changes=(
                change("accounting", {"finance.report"}),
                change("prayer", set()),
            ),
        )
    profile = await repo.get_profile(target)
    assert [(r.role_id, r.revision) for r in profile.roles] == [("prayer", 1)]
    _, factory, _, _ = store
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(AdminAuditRecord)) == 1


async def test_batch_preserves_explicit_capabilities_when_role_disabled(access_setup):
    repo, _, actor, target = access_setup
    profile = await repo.set_assignments(
        actor_id=actor,
        user_id=target,
        changes=(
            change("accounting", {"finance.report"}),
            change("prayer", {"prayer.schedule"}, enabled=False),
        ),
    )
    assert len(profile.roles) == 2
    assert next(r for r in profile.roles if r.role_id == "prayer").capability_ids == {
        "prayer.schedule"
    }
    assert not next(r for r in profile.roles if r.role_id == "prayer").enabled


async def test_batch_invalid_or_duplicate_role_changes_nothing(access_setup):
    repo, _, actor, target = access_setup
    for changes in (
        (change("prayer", {"finance.report"}),),
        (change("accounting", set()), change("accounting", set())),
        (change("assistant", set()),),
    ):
        with pytest.raises(ValueError):
            await repo.set_assignments(actor_id=actor, user_id=target, changes=changes)
    assert (await repo.get_profile(target)).roles == ()
