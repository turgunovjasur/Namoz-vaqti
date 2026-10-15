"""A single capability catalog and a narrow bridge for existing requests."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from namoz_bot.application.agent_adapters import AgentAdapters
from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.capabilities import (
    finance,
    nasihat,
    prayer,
    preferences,
    reminders,
    settings,
)
from namoz_bot.application.capabilities.base import BusinessAdapters, Capability
from namoz_bot.application.profiles.ports import PermissionTransaction
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.authorization import access_context
from namoz_bot.domain.agent_protocol import AgentDecision, AgentRequest, AgentResult

if TYPE_CHECKING:
    from namoz_bot.application.roles.registry import RoleRegistry


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability]) -> None:
        self._items: dict[str, Capability] = {}
        self._routes: dict[tuple[str, str, str | None], Capability] = {}
        for capability in capabilities:
            if capability.spec.id in self._items:
                raise ValueError(f"Duplicate capability: {capability.spec.id}")
            self._items[capability.spec.id] = capability
            for route in capability.spec.routes:
                key = (route.domain, route.action, route.view)
                if key in self._routes:
                    raise ValueError("Duplicate capability route")
                self._routes[key] = capability

    def get(self, capability_id: str) -> Capability:
        try:
            return self._items[capability_id]
        except KeyError:
            raise ValueError(f"Unknown capability: {capability_id}") from None

    def all(self) -> tuple[Capability, ...]:
        return tuple(self._items.values())

    def for_request(self, request: AgentDecision) -> Capability:
        view = request.parameters.get("view")
        key = (request.domain, request.action, view if isinstance(view, str) else None)
        try:
            return self._routes[key]
        except KeyError:
            raise ValueError("Request is outside registered capabilities") from None


def build_capability_registry(adapters: BusinessAdapters | None = None) -> CapabilityRegistry:
    business = adapters or AgentAdapters()
    return CapabilityRegistry(
        Capability(spec, business)
        for module in (finance, reminders, prayer, nasihat, settings, preferences)
        for spec in module.definitions()
    )


class CapabilityDispatcher:
    def __init__(
        self,
        roles: "RoleRegistry",
        capabilities: CapabilityRegistry,
        access: AccessService | None = None,
    ) -> None:
        self.access = access
        self.roles = roles
        self.capabilities = capabilities
        self._assistant = AgentAdapters()

    def _resolve(self, request: AgentRequest) -> Capability:
        capability = self.capabilities.for_request(request)
        if capability.spec.requires_result:
            raise ValueError("Correction requires a result-bound task")
        # V1 prayer religious excerpts retain their original request envelope.
        owner = (
            "nasihat"
            if (request.domain, request.action) == ("prayer", "religious_excerpt")
            else request.domain
        )
        role = self.roles.get(owner)
        if capability.spec.id not in role.capability_ids:
            raise ValueError("Request is outside role capabilities")
        return capability

    def _role(self, request: AgentRequest) -> str:
        return (
            "nasihat"
            if (request.domain, request.action) == ("prayer", "religious_excerpt")
            else request.domain
        )

    async def prepare(self, request: AgentRequest) -> AgentResult:
        if request.domain == "assistant":
            return await self._assistant.prepare(request)
        capability = self._resolve(request)
        if self.access is None:
            return await capability.prepare(request)
        role = self._role(request)
        await self.access.require(request.context.user_id, role, capability.spec.id)
        with access_context(
            self.access,
            user_id=request.context.user_id,
            telegram_user_id=request.context.telegram_user_id,
            role_id=role,
            capability_id=capability.spec.id,
        ):
            output = await capability.prepare(request)
        await self.access.require(request.context.user_id, role, capability.spec.id)
        return output

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        if request.domain == "assistant":
            return await self._assistant.execute(request, transaction)
        capability = self._resolve(request)
        if self.access is None:
            return await capability.execute(request, transaction)
        role = self._role(request)
        await self.access.require_in(
            cast(PermissionTransaction, transaction),
            request.context.user_id,
            role,
            capability.spec.id,
        )
        with access_context(
            self.access,
            user_id=request.context.user_id,
            telegram_user_id=request.context.telegram_user_id,
            role_id=role,
            capability_id=capability.spec.id,
        ):
            return await capability.execute(request, transaction)
