from datetime import timedelta

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.roles.registry import RoleRegistry, definitions
from namoz_bot.application.skills.native import NativeSkill
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.execution import TaskExecutionService
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from namoz_bot.infrastructure.workforce.queue import SqlAlchemyTaskQueue
from namoz_bot.infrastructure.workforce.tasks import SqlAlchemyTaskStore
from namoz_bot.presentation.result_messages import render_result, render_task_plan
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.unit.skills.test_native_skills import Input, Output, plan


async def test_new_skill_executes_and_survives_worker_restart_without_core_action_edits(store):
    _, factory, user, _ = store
    calls = []

    async def execute(call, parameters, transaction):
        calls.append(call.idempotency_key)
        return Output(answer=parameters.word.upper())

    native = NativeSkill(
        id="demo.echo",
        name="Echo",
        description="Test word",
        input_model=Input,
        output_model=Output,
        execute=execute,
        render=lambda value: value.answer,
        effect="read",
    )
    caps = build_capability_registry(extra_skills=(native,))
    draft = plan().model_copy(
        update={
            "context": plan().context.model_copy(update={"user_id": user, "message_time": NOW}),
            "expires_at": NOW + timedelta(minutes=15),
        }
    )
    roles = RoleRegistry((*definitions(), draft.role), caps)
    profiles = SqlAlchemyProfileRepository(factory, roles, admin_telegram_ids=frozenset({7}))
    from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog

    runtime = SqlRoleCatalog(factory, roles, profiles=profiles)
    await runtime.initialize()
    # PostgreSQL migrations seeded the built-ins before this synthetic plugin was installed.
    from namoz_bot.infrastructure.orm import AgentRoleRecord, AgentRoleSkillRecord

    async with factory.begin() as session:
        if await session.get(AgentRoleRecord, draft.role.id) is None:
            session.add(
                AgentRoleRecord(
                    id=draft.role.id,
                    name=draft.role.name,
                    name_key=draft.role.name.casefold(),
                    description=draft.role.description,
                    common_rules="",
                    enabled=True,
                    system_role=False,
                    revision=1,
                )
            )
            await session.flush()
            session.add(AgentRoleSkillRecord(role_id=draft.role.id, capability_id="demo.echo"))
    await profiles.set_grants(
        actor_id=user,
        user_id=user,
        role_id="demo_role",
        enabled=True,
        capability_ids=frozenset({"demo.echo"}),
        expected_revision=0,
    )
    current = [NOW]
    tasks = SqlAlchemyTaskStore(factory, clock=lambda: current[0])
    queue = SqlAlchemyTaskQueue(factory)
    await tasks.save_plan(draft, expected_revision=None)
    assert "Echo" in render_task_plan(draft, caps)
    await tasks.approve(draft.task_id, 1, draft.context, "yes", True)
    claim = (await queue.claim(now=NOW, limit=1, lease_seconds=180))[0]
    result = await TaskExecutionService(tasks, AccessService(profiles, roles), caps).run(claim)
    assert render_result(result.service_result) == "HELLO"
    current[0] += timedelta(seconds=181)
    recovered = (await queue.claim(now=current[0], limit=1, lease_seconds=180))[0]
    replay = await TaskExecutionService(tasks, AccessService(profiles, roles), caps).run(recovered)
    assert replay.service_result == result.service_result
    assert len(calls) == 1
