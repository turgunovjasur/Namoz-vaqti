import json

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.domain.workforce.tasks import TaskRevision
from tests.unit.skills.test_native_skills import plan


class Transport:
    def __init__(self):
        self.calls = []

    async def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"capability_id": "finance.report", "parameters": {}, "question": None}


async def test_roles_have_distinct_immutable_agents_and_no_foreign_pending_context():
    from namoz_bot.infrastructure.ai.agent_factory import AgentFactory

    transport = Transport()
    factory = AgentFactory(transport, capacity=2)
    caps = (build_capability_registry().get("finance.report").spec,)
    role = RoleDefinition(
        id="role_law",
        name="Law",
        description="Only reports",
        instruction="Only reports",
        common_rules="Ask first",
        capability_ids=("finance.report",),
        revision=1,
    )
    agent = factory.resolve(role, caps, "model-a")
    other = factory.resolve(role.model_copy(update={"id": "role_other"}), caps, "model-b")
    assert agent is factory.resolve(role, caps, "model-a")
    assert agent is not other
    pending = TaskRevision(plan=plan(), status="needs_input")
    await agent.interpret(text="Hisobot", context=plan().context, pending=pending)
    request = transport.calls[-1]
    assert request["model"] == "model-a"
    assert "Ask first" in request["instruction"]
    assert "Only reports" in request["instruction"]
    assert json.loads(request["parts"][0]["text"])["context"]["pending"] is None
    newer = factory.resolve(
        role.model_copy(update={"revision": 2, "common_rules": "Updated"}), caps, "model-a"
    )
    assert newer is not agent
    assert len(factory) == 2


async def test_independent_skill_parameter_types_and_nested_objects_do_not_overwrite():
    from pydantic import BaseModel, ConfigDict

    from namoz_bot.domain.workforce.capabilities import CapabilitySpec
    from namoz_bot.infrastructure.ai.agent_factory import AgentFactory

    class NumericDetail(BaseModel):
        count: int

    class TextDetail(BaseModel):
        label: str

    class Numeric(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        value: int
        detail: NumericDetail

    class Textual(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        value: str
        detail: TextDetail

    specs = tuple(
        CapabilitySpec(id=id, name=id, description=id, parameters_model=shape, effect="read")
        for id, shape in [("demo.numeric", Numeric), ("demo.textual", Textual)]
    )
    role = RoleDefinition(
        id="mixed",
        name="Mixed",
        description="Typed skills",
        instruction="Typed skills",
        capability_ids=tuple(s.id for s in specs),
    )

    class AI:
        async def generate_json(self, **kwargs):
            parameters = kwargs["schema"]["properties"]["parameters"]
            variants = parameters.get("anyOf", [parameters])
            numeric = next(
                (
                    v
                    for v in variants
                    if v.get("properties", {}).get("value", {}).get("type") == "INTEGER"
                ),
                None,
            )
            textual = next(
                (
                    v
                    for v in variants
                    if v.get("properties", {}).get("value", {}).get("type") == "STRING"
                ),
                None,
            )
            assert numeric is not None and textual is not None
            assert set(numeric["required"]) == {"value", "detail"}
            assert set(textual["required"]) == {"value", "detail"}
            assert numeric["properties"]["detail"]["properties"]["count"]["type"] == "INTEGER"
            assert textual["properties"]["detail"]["properties"]["label"]["type"] == "STRING"
            return {
                "capability_id": "demo.numeric",
                "parameters": {"value": 3, "detail": {"count": 2}},
                "question": None,
            }

    selected = (
        await AgentFactory(AI())
        .resolve(role, specs, "model-a")
        .interpret(text="Count", context=plan().context, pending=None)
    )
    assert selected.parameters == {"value": 3, "detail": {"count": 2}}
