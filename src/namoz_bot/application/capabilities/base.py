"""One compatibility executor per capability; business services remain authoritative."""

from typing import Protocol

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.domain.agent_protocol import (
    ACTION_MODELS,
    AgentRequest,
    AgentResult,
    Domain,
    EmptyParameters,
)
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute


class BusinessAdapters(Protocol):
    async def prepare(self, request: AgentRequest) -> AgentResult: ...
    async def execute(
        self, request: AgentRequest, transaction: AgentTransaction
    ) -> AgentResult: ...


class Capability:
    def __init__(self, spec: CapabilitySpec, adapters: BusinessAdapters) -> None:
        self.spec = spec
        self._adapters = adapters

    def _check(self, request: AgentRequest) -> None:
        if "conversation" not in self.spec.entrypoints:
            raise ValueError("Capability is not available in conversation")
        if not any(route.matches(request) for route in self.spec.routes):
            raise ValueError("Request is outside capability scope")
        self.spec.validate_parameters(request.parameters)

    async def prepare(self, request: AgentRequest) -> AgentResult:
        self._check(request)
        return await self._adapters.prepare(request)

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        self._check(request)
        return await self._adapters.execute(request, transaction)


def operation(
    id: str,
    name: str,
    description: str,
    domain: Domain,
    action: str,
    effect: str,
    *,
    routes: tuple[LegacyRoute, ...] | None = None,
) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "id": id,
            "name": name,
            "description": description,
            "parameters_model": ACTION_MODELS[(domain, action)],
            "effect": effect,
            "routes": routes or (LegacyRoute(domain=domain, action=action),),
        }
    )


def background(id: str, name: str, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        id=id,
        name=name,
        description=description,
        parameters_model=EmptyParameters,
        effect="read",
        entrypoints=("background",),
    )
