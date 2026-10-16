import pytest

from tests.integration.test_agent_sessions import store as store
from tests.integration.test_dynamic_roles import catalog_setup as catalog_setup
from tests.integration.test_dynamic_roles import draft
from tests.integration.test_workforce_access import access_setup as access_setup


async def test_global_role_off_and_skill_removal_are_authoritative(catalog_setup):
    catalog, runtime, profiles, access, actor, target = catalog_setup
    role = await catalog.create(actor, draft())
    async with runtime.scope():
        await profiles.set_grants(
            actor_id=actor,
            user_id=target,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"finance.report"}),
            expected_revision=0,
        )
        assert await access.allowed(target, role.id, "finance.report")
        await catalog.update(
            actor, role.id, draft(enabled=False, expected_revision=1, expected_model_version=1)
        )
        # Still in the old request snapshot: authoritative SQL must reject the revoked role.
        assert not await access.allowed(target, role.id, "finance.report")


async def test_background_permission_uses_any_role_with_the_skill(catalog_setup):
    catalog, runtime, profiles, access, actor, target = catalog_setup
    role = await catalog.create(actor, draft(capability_ids=["reminder.deliver"]))
    async with runtime.scope():
        await profiles.set_grants(
            actor_id=actor,
            user_id=target,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"reminder.deliver"}),
            expected_revision=0,
        )
        assert await access.allowed_any(target, "reminder.deliver")
        assert not await access.allowed_any(actor, "reminder.deliver")


async def test_role_revision_invalidates_pending_approval_and_queued_execution(
    catalog_setup, store
):
    from namoz_bot.domain.workforce.profiles import AccessDenied
    from namoz_bot.infrastructure.workforce.queue import SqlAlchemyTaskQueue
    from namoz_bot.infrastructure.workforce.tasks import SqlAlchemyTaskStore
    from tests.integration.test_agent_sessions import NOW
    from tests.unit.skills.test_native_skills import plan

    catalog, runtime, profiles, access, actor, target = catalog_setup
    _, factory, _, _ = store
    role = await catalog.create(actor, draft())
    async with runtime.scope():
        await profiles.set_grants(
            actor_id=actor,
            user_id=target,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"finance.report"}),
            expected_revision=0,
        )
        template = plan()
        selection = template.selection.model_copy(
            update={"role_id": role.id, "capability_id": "finance.report", "parameters": {}}
        )
        context = template.context.model_copy(update={"user_id": target, "message_time": NOW})
        task_plan = template.model_copy(
            update={
                "context": context,
                "role": role,
                "selection": selection,
                "permission": await access.require(target, role.id, "finance.report"),
                "expires_at": NOW.replace(year=2099),
                "models": {
                    **template.models,
                    role.id: template.models["demo_role"].model_copy(update={"role_id": role.id}),
                },
            }
        )
    tasks = SqlAlchemyTaskStore(factory, clock=lambda: NOW)
    queue = SqlAlchemyTaskQueue(factory)
    await tasks.save_plan(task_plan, expected_revision=None)
    await tasks.approve(task_plan.task_id, 1, context, "yes", True)
    claim = (await queue.claim(now=NOW, limit=1, lease_seconds=180))[0]
    second = task_plan.model_copy(update={"task_id": "b" * 20, "request_id": "other_input"})
    await tasks.save_plan(second, expected_revision=None)
    await catalog.update(
        actor,
        role.id,
        draft(common_rules="Updated task rules", expected_revision=1, expected_model_version=1),
    )
    with pytest.raises(AccessDenied):
        await tasks.approve(second.task_id, 1, context, "yes2", True)
    with pytest.raises(AccessDenied):
        async with tasks.effect_scope(task_plan.task_id, 1, claim.lease_token):
            pytest.fail("stale role reached effect")


async def test_global_revoke_waits_for_owner_effect_and_cannot_restore_stale_grant(
    catalog_setup, store
):
    import asyncio

    from tests.integration.test_agent_sessions import NOW

    catalog, runtime, profiles, access, actor, target = catalog_setup
    _, factory, _, _ = store
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row lock race")
    role = await catalog.create(actor, draft())
    async with runtime.scope():
        await profiles.set_grants(
            actor_id=actor,
            user_id=target,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"finance.report"}),
            expected_revision=0,
        )
        async with access.effect_scope(target, role.id, "finance.report", now=NOW):
            change = asyncio.create_task(
                catalog.update(
                    actor,
                    role.id,
                    draft(
                        capability_ids=["reminder.create"],
                        expected_revision=1,
                        expected_model_version=1,
                    ),
                )
            )
            await asyncio.sleep(0.05)
            assert not change.done()
        await asyncio.wait_for(change, 5)
        with pytest.raises(ValueError):
            await profiles.set_grants(
                actor_id=actor,
                user_id=target,
                role_id=role.id,
                enabled=True,
                capability_ids=frozenset({"finance.report"}),
                expected_revision=2,
            )
    assert not await access.allowed_any(target, "finance.report")
