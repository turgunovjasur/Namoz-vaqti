from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.profiles import PermissionSnapshot, RoleModelSetting
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.domain.workforce.tasks import TaskPlan


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str


def plan():
    role = RoleDefinition(
        id="demo_role",
        name="Demo",
        description="Echo word",
        instruction="Echo",
        capability_ids=("demo.echo",),
    )
    return TaskPlan(
        task_id="a" * 20,
        revision=1,
        request_id="request",
        context=AgentContext(
            bot_id=123,
            user_id=1,
            telegram_user_id=7,
            chat_id=7,
            message_time=datetime.now(UTC),
            region_code="Toshkent",
        ),
        permission=PermissionSnapshot(
            user_id=1, role_id=role.id, capability_id="demo.echo", assignment_revision=1
        ),
        role=role,
        models={
            key: RoleModelSetting(role_id=key, model_id="model")
            for key in ("assistant", "manager", role.id)
        },
        selection=CapabilitySelection(
            role_id=role.id, capability_id="demo.echo", parameters={"word": "hello"}
        ),
        transcript="Say hello",
        expires_at=datetime.now(UTC),
    )


async def test_native_skill_uses_typed_io_and_server_context_without_legacy_action():
    from namoz_bot.application.skills.native import NativeSkill

    seen = []

    async def execute(call, params, transaction):
        seen.append((call.context.user_id, call.role_id, call.skill_id, call.idempotency_key))
        return Output(answer=params.word.upper())

    skill = NativeSkill(
        id="demo.echo",
        name="Echo",
        description="Echo a word",
        input_model=Input,
        output_model=Output,
        execute=execute,
        render=lambda r: r.answer,
        effect="read",
    )
    task = plan()
    assert skill.spec.routes == ()
    result = await skill.execute_plan(task, None, None)
    assert result.status == "done" and result.data["payload"] == {"answer": "HELLO"}
    assert result.data["text"] == "HELLO"
    assert seen == [(1, "demo_role", "demo.echo", "task:" + "a" * 20 + ":1")]
    assert result.domain == "assistant" and result.action == "skill_result"


async def test_native_skill_invalid_output_never_becomes_success():
    from namoz_bot.application.skills.native import NativeSkill

    async def execute(call, params, transaction):
        return {"bad": "payload"}

    skill = NativeSkill(
        id="demo.echo",
        name="Echo",
        description="Echo",
        input_model=Input,
        output_model=Output,
        execute=execute,
        render=lambda r: r.answer,
        effect="read",
    )
    with pytest.raises(ValidationError):
        await skill.execute_plan(plan(), None, None)


def test_native_skill_rejects_model_supplied_owner_identity():
    from namoz_bot.application.skills.native import NativeSkill

    class BadInput(BaseModel):
        user_id: int

    async def execute(call, params, transaction):
        return Output(answer="no")

    with pytest.raises(ValueError, match="identity"):
        NativeSkill(
            id="demo.echo",
            name="Echo",
            description="Echo",
            input_model=BadInput,
            output_model=Output,
            execute=execute,
            render=lambda r: r.answer,
            effect="read",
        )


def test_duplicate_native_and_legacy_ids_are_rejected():
    from namoz_bot.application.capabilities.registry import (
        CapabilityRegistry,
        build_capability_registry,
    )
    from namoz_bot.application.skills.native import NativeSkill

    async def execute(call, params, transaction):
        return Output(answer="x")

    skill = NativeSkill(
        id="finance.report",
        name="Echo",
        description="Echo",
        input_model=Input,
        output_model=Output,
        execute=execute,
        render=lambda r: r.answer,
        effect="read",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        CapabilityRegistry((*build_capability_registry().all(), skill))


def test_trusted_plugin_discovery_requires_only_one_module(tmp_path, monkeypatch):
    from namoz_bot.infrastructure.skills import plugins
    from namoz_bot.infrastructure.skills.bootstrap import build_runtime_capabilities

    monkeypatch.setattr(plugins, "__path__", [str(tmp_path)])
    (tmp_path / "demo_plugin.py").write_text("""
from pydantic import BaseModel,ConfigDict
from namoz_bot.application.skills.native import NativeSkill
class Input(BaseModel):
    model_config=ConfigDict(extra="forbid")
    word:str
class Output(BaseModel):
    answer:str
async def execute(call,params,transaction):
    return Output(answer=params.word)
def build(dependencies):
    return (NativeSkill(id="test.discovered",name="Discovered",description="Test plugin",
            input_model=Input,output_model=Output,execute=execute,render=lambda r:r.answer,
            effect="read"),)
""")
    assert build_runtime_capabilities().get("test.discovered").spec.routes == ()
