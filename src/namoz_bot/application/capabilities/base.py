"""One compatibility executor per capability; business services remain authoritative."""

from typing import Protocol, cast

from pydantic import JsonValue

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.domain.agent_protocol import (
    ACTION_MODELS,
    AgentRequest,
    AgentResult,
    Domain,
    EmptyParameters,
)
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute
from namoz_bot.domain.workforce.tasks import TaskPlan


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

    def _plan_request(self, plan: TaskPlan) -> AgentRequest:
        view = plan.selection.parameters.get("view")
        route = next((r for r in self.spec.routes if r.view == view), self.spec.routes[0])
        return AgentRequest(
            domain=route.domain,
            action=route.action,
            parameters=plan.selection.parameters,
            transcript=plan.transcript,
            context=plan.context,
            operation_id=f"{plan.task_id}{plan.revision:06x}",
            request_id=f"task:{plan.task_id}:{plan.revision}",
        )

    async def prepare_plan(self, plan: TaskPlan) -> AgentResult | None:
        return await self.prepare(self._plan_request(plan))

    async def execute_plan(
        self, plan: TaskPlan, transaction: AgentTransaction, prepared: AgentResult | None
    ) -> AgentResult:
        if prepared is None:
            raise ValueError("Legacy skill requires preparation")
        request = self._plan_request(plan)
        if prepared.status == "needs_confirmation":
            request = AgentRequest.model_validate(
                {
                    **request.model_dump(),
                    "context": request.context,
                    "parameters": cast(dict[str, JsonValue], prepared.data["draft"]),
                }
            )
            return await self.execute(request, transaction)
        if prepared.status == "done" and not prepared.data:
            return await self.execute(request, transaction)
        return prepared


def operation(
    id: str,
    name: str,
    description: str,
    domain: Domain,
    action: str,
    effect: str,
    *,
    routes: tuple[LegacyRoute, ...] | None = None,
    requires_result: bool = False,
    correction_id: str | None = None,
) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "id": id,
            "name": name,
            "description": description,
            "parameters_model": ACTION_MODELS[(domain, action)],
            "effect": effect,
            "requires_result": requires_result,
            "correction_id": correction_id,
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
