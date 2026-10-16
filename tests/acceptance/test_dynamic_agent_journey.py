from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.catalog import RoleCatalogService
from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.application.skills.native import NativeSkill
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.assistant import AssistantService
from namoz_bot.application.workforce.execution import TaskExecutionService
from namoz_bot.application.workforce.planning import Manager
from namoz_bot.domain.workforce.roles import RoleWrite
from namoz_bot.infrastructure.ai.role_interpreter import GeminiRoleInterpreter
from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from namoz_bot.infrastructure.workforce.queue import SqlAlchemyTaskQueue
from namoz_bot.infrastructure.workforce.tasks import SqlAlchemyTaskStore
from namoz_bot.presentation.result_messages import render_result, render_task_plan
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_dynamic_roles import ValidModels
from tests.unit.skills.test_native_skills import Input, Output, plan


async def test_admin_creates_agent_grants_native_skill_and_user_approves_execution(store):
    _, factory, user, _ = store
    calls = []

    async def execute(call, params, tx):
        calls.append(call.context.user_id)
        return Output(answer=params.word.upper())

    skill = NativeSkill(
        id="demo.echo",
        name="Echo",
        description="Echo the word",
        input_model=Input,
        output_model=Output,
        execute=execute,
        render=lambda r: r.answer,
        effect="read",
    )
    caps = build_capability_registry(extra_skills=(skill,))
    roles = build_role_registry(caps)
    profiles = SqlAlchemyProfileRepository(factory, roles, admin_telegram_ids=frozenset({7}))
    catalog = SqlRoleCatalog(factory, roles, profiles=profiles)
    access = AccessService(profiles, roles, runtime=catalog.runtime)
    service = ProfileService(
        profiles,
        roles,
        ValidModels(None, ("model-a", "model-b")),
        default_models={r.id: "model-a" for r in roles.all()},
    )
    role = await RoleCatalogService(catalog, profiles, service).create(
        user,
        RoleWrite(
            name="New worker",
            description="Echo words only",
            model_id="model-b",
            capability_ids=frozenset({"demo.echo"}),
        ),
    )
    async with catalog.scope():
        await profiles.set_grants(
            actor_id=user,
            user_id=user,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"demo.echo"}),
            expected_revision=0,
        )

    class AI:
        async def generate_json(self, **kwargs):
            if "role_id" in kwargs["schema"]["properties"]:
                assert kwargs["model"] == "model-a"
                return {"role_id": role.id, "question": None}
            assert kwargs["model"] == "model-b"
            return {"capability_id": "demo.echo", "parameters": {"word": "hello"}, "question": None}

    tasks = SqlAlchemyTaskStore(factory, clock=lambda: NOW)
    context = plan().context.model_copy(update={"user_id": user, "message_time": NOW})
    coordinator = Manager(access, service, GeminiRoleInterpreter(AI()), tasks, clock=lambda: NOW)
    assistant = AssistantService(
        coordinator, None, tasks, service, lambda p: render_task_plan(p, caps)
    )
    response = await assistant.receive(context, "message", text="Echo hello")
    assert response.buttons == "approval" and not calls
    await assistant.approve(context, "yes", response.task_id, 1, True)
    queue = SqlAlchemyTaskQueue(factory)
    claim = (await queue.claim(now=NOW, limit=1, lease_seconds=180))[0]
    result = await TaskExecutionService(tasks, access, caps).run(claim)
    assert render_result(result.service_result) == "HELLO" and calls == [user]
    assert result.plan.coordinator_role == "assistant"
    assert result.plan.role.id == role.id
