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
