"""Scoped specialists behind a single router and a versioned handoff boundary."""

import logging
from collections.abc import Mapping
from typing import ClassVar, Protocol
from uuid import uuid4

from namoz_bot.application.agent_adapters import AgentAdapters
from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.domain.agent_protocol import (
    AgentContext,
    AgentDecision,
    AgentHandoff,
    AgentHandoffReply,
    AgentRequest,
    AgentResult,
    AgentRoutingDecision,
    AgentSessionState,
    Domain,
    menu_actions,
    operation_id_for,
)

logger = logging.getLogger(__name__)
MENU_DOMAINS: tuple[Domain, ...] = ("prayer", "nasihat", "reminder", "accounting", "settings")


class RoutingAgent(Protocol):
    async def route(
        self,
        *,
        text: str | None,
        audio: bytes | None,
        mime_type: str,
        context: AgentContext,
        pending: AgentSessionState | None,
    ) -> AgentRoutingDecision: ...


class MenuInterpreter(Protocol):
    async def interpret(self, handoff: AgentHandoff) -> AgentDecision: ...


class MenuAgent:
    domain: ClassVar[Domain]

    def __init__(self, interpreter: MenuInterpreter, adapters: AgentAdapters) -> None:
        self.interpreter = interpreter
        self._adapters = adapters

    async def interpret(self, handoff: AgentHandoff) -> AgentHandoffReply:
        if handoff.domain != self.domain:
            raise ValueError("Handoff belongs to another menu agent")
        decision = await self.interpreter.interpret(handoff)
        if decision.domain == self.domain:
            self._check_scope(decision)
        return AgentHandoffReply(
            request_id=handoff.request_id,
            operation_id=handoff.operation_id,
            domain=self.domain,
            decision=decision,
        )

    def _check_scope(self, request: AgentDecision) -> None:
        if request.domain != self.domain or request.action not in menu_actions(self.domain):
            raise ValueError("Action is outside menu agent capabilities")
        if request.action in {"open", "open_settings"}:
            views = {
                "prayer": {"region", "offsets"},
                "nasihat": {"interval"},
                "settings": {"general", "daily", "region", "offsets"},
            }
            default = "interval" if self.domain == "nasihat" else "general"
            if request.parameters.get("view", default) not in views.get(self.domain, set()):
                raise ValueError("Settings view is outside menu agent capabilities")

    async def prepare(self, request: AgentRequest) -> AgentResult:
        self._check_scope(request)
        return await self._adapters.prepare(request)

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        self._check_scope(request)
        return await self._adapters.execute(request, transaction)


class PrayerAgent(MenuAgent):
    domain = "prayer"


class NasihatAgent(MenuAgent):
    domain = "nasihat"


class ReminderAgent(MenuAgent):
    domain = "reminder"


class AccountingAgent(MenuAgent):
    domain = "accounting"


class SettingsAgent(MenuAgent):
    domain = "settings"


def validate_registry(agents: Mapping[Domain, MenuAgent]) -> None:
    if set(agents) != set(MENU_DOMAINS) or any(
        key != agent.domain for key, agent in agents.items()
    ):
        raise ValueError("Every menu must have exactly one matching agent")


class RoutedAgentExtractor:
    def __init__(self, router: RoutingAgent, agents: Mapping[Domain, MenuAgent]) -> None:
        validate_registry(agents)
        self._router = router
        self._agents = dict(agents)

    async def extract(
        self,
        *,
        text: str | None,
        audio: bytes | None,
        mime_type: str,
        context: AgentContext,
        pending: AgentSessionState | None,
        request_id: str | None = None,
    ) -> AgentDecision:
        route = await self._router.route(
            text=text, audio=audio, mime_type=mime_type, context=context, pending=pending
        )
        original = text.strip() if text is not None else route.transcript
        if route.domain == "assistant":
            return AgentDecision(
                domain="assistant",
                action=route.control_action or "clarify",
                transcript=original,
                clarification=route.clarification,
                multiple_tasks=route.multiple_tasks,
            )
        correlation = request_id or f"interpret:{uuid4().hex}"
        relevant = pending if pending and pending.domain == route.domain else None
        handoff = AgentHandoff(
            request_id=correlation,
            operation_id=relevant.operation_id
            if relevant
            else operation_id_for(context, correlation),
            domain=route.domain,
            input=original,
            context=context,
            pending=relevant,
        )
        reply = await self._agents[route.domain].interpret(handoff)
        if (reply.request_id, reply.operation_id, reply.domain, reply.protocol_version) != (
            handoff.request_id,
            handoff.operation_id,
            handoff.domain,
            handoff.protocol_version,
        ):
            raise ValueError("Menu reply does not match the handoff")
        # Revalidate programmatic/custom-agent replies too, not only provider JSON.
        checked = AgentHandoffReply.model_validate_json(reply.model_dump_json())
        logger.info(
            "agent_handoff request=%s operation=%s domain=%s status=interpreted",
            handoff.request_id,
            handoff.operation_id,
            handoff.domain,
        )
        return checked.decision


class MenuAgentDispatcher:
    def __init__(self, agents: Mapping[Domain, MenuAgent]) -> None:
        validate_registry(agents)
        self._agents = dict(agents)
        self._assistant = AgentAdapters()

    async def prepare(self, request: AgentRequest) -> AgentResult:
        if request.domain == "assistant":
            return await self._assistant.prepare(request)
        return await self._agents[request.domain].prepare(request)

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        if request.domain == "assistant":
            return await self._assistant.execute(request, transaction)
        return await self._agents[request.domain].execute(request, transaction)
