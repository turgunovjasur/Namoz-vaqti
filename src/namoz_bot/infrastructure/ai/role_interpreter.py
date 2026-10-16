"""Coordinator routes granted roles; a factory supplies distinct specialist agents."""

import json
from collections.abc import Callable

from namoz_bot.application.roles.manager import ROUTING_INSTRUCTION
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.workforce.capabilities import CapabilitySelection, CapabilitySpec
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.domain.workforce.tasks import ClarificationRequired, TaskRevision
from namoz_bot.infrastructure.ai.agent_factory import AgentFactory
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.ai.role_protocol import RouteResponse, safe_context


class GeminiRoleInterpreter:
    def __init__(
        self, transport: GeminiClient, *, coordinator: Callable[[], RoleDefinition] | None = None
    ):
        self.transport = transport
        self.factory = AgentFactory(transport)
        self.coordinator = coordinator

    async def route(
        self,
        *,
        text: str,
        context: AgentContext,
        roles: tuple[RoleDefinition, ...],
        pending: TaskRevision | None,
        model: str,
    ) -> str:
        offered = {r.id: r for r in roles}
        catalog = [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "capabilities": list(r.capability_ids),
            }
            for r in roles
        ]
        payload = await self.transport.generate_json(
            model=model,
            instruction=(self.coordinator().common_rules + "\n" if self.coordinator else "")
            + ROUTING_INSTRUCTION,
            schema={
                "type": "OBJECT",
                "properties": {
                    "role_id": {"type": "STRING", "nullable": True, "enum": list(offered)},
                    "question": {"type": "STRING", "nullable": True},
                },
                "required": ["role_id", "question"],
            },
            parts=[
                {
                    "text": json.dumps(
                        {"text": text, "roles": catalog, "context": safe_context(context, pending)},
                        ensure_ascii=False,
                    )
                }
            ],
        )
        route = RouteResponse.model_validate(payload)
        if route.role_id is None:
            raise ClarificationRequired(
                route.question or "Qaysi vazifani bajarishimni aniqroq ayting."
            )
        if route.role_id not in offered:
            raise AccessDenied("Role is not granted")
        return route.role_id

    async def interpret(
        self,
        *,
        text: str,
        context: AgentContext,
        role: RoleDefinition,
        capabilities: tuple[CapabilitySpec, ...],
        pending: TaskRevision | None,
        model: str,
    ) -> CapabilitySelection:
        return await self.factory.resolve(role, capabilities, model).interpret(
            text=text, context=context, pending=pending
        )
