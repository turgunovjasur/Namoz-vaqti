"""Bounded configuration cache; never stores user conversation or mutable chat history."""

from collections import OrderedDict

from namoz_bot.domain.workforce.capabilities import CapabilitySpec
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.ai.role_agent import GeminiRoleAgent


class AgentFactory:
    def __init__(self, transport: GeminiClient, *, capacity: int = 128):
        if capacity < 1:
            raise ValueError("Positive capacity required")
        self.transport, self.capacity = transport, capacity
        self._agents: OrderedDict[
            tuple[RoleDefinition, str, tuple[CapabilitySpec, ...]], GeminiRoleAgent
        ] = OrderedDict()

    def __len__(self) -> int:
        return len(self._agents)

    def resolve(
        self, role: RoleDefinition, capabilities: tuple[CapabilitySpec, ...], model: str
    ) -> GeminiRoleAgent:
        key = (role, model, capabilities)
        agent = self._agents.get(key)
        if agent is None:
            agent = GeminiRoleAgent(self.transport, role, capabilities, model)
            self._agents[key] = agent
        self._agents.move_to_end(key)
        while len(self._agents) > self.capacity:
            self._agents.popitem(last=False)
        return agent
