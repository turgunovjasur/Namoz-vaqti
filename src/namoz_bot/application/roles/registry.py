"""Authoritative role catalog; callers narrow capabilities using user grants."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from namoz_bot.application.roles.base import COMMON_INSTRUCTION, LEGACY_OUTPUT_INSTRUCTION
from namoz_bot.domain.agent_protocol import Domain
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.roles import RoleDefinition

if TYPE_CHECKING:
    from namoz_bot.application.capabilities.registry import CapabilityRegistry


class RoleRegistry:
    def __init__(self, roles: Iterable[RoleDefinition], capabilities: "CapabilityRegistry") -> None:
        self._items: dict[str, RoleDefinition] = {}
        self.capabilities = capabilities
        for role in roles:
            if role.id in self._items:
                raise ValueError(f"Duplicate role: {role.id}")
            if len(set(role.capability_ids)) != len(role.capability_ids):
                raise ValueError("Duplicate role capability")
            for capability_id in role.capability_ids:
                capabilities.get(capability_id)
            self._items[role.id] = role

    def get(self, role_id: str) -> RoleDefinition:
        try:
            return self._items[role_id]
        except KeyError:
            raise ValueError("Unknown role") from None

    def all(self) -> tuple[RoleDefinition, ...]:
        return tuple(self._items.values())

    def validate_selection(
        self, selection: CapabilitySelection, *, entrypoint: str = "conversation"
    ) -> CapabilitySelection:
        role = self.get(selection.role_id)
        if selection.capability_id not in role.capability_ids:
            raise ValueError("Selected capability is outside role scope")
        spec = self.capabilities.get(selection.capability_id).spec
        if entrypoint not in spec.entrypoints:
            raise ValueError(f"Capability is not available in {entrypoint}")
        return selection.model_copy(
            update={"parameters": spec.validate_parameters(selection.parameters)}
        )


def definitions() -> tuple[RoleDefinition, ...]:
    from namoz_bot.application.roles import (
        accountant,
        adviser,
        assistant,
        manager,
        planner,
        prayer_calendar,
        settings,
    )

    return tuple(
        module.ROLE
        for module in (assistant, manager, prayer_calendar, adviser, planner, accountant, settings)
    )


def build_role_registry(capabilities: "CapabilityRegistry") -> RoleRegistry:
    return RoleRegistry(definitions(), capabilities)


def specialist_instructions() -> dict[Domain, str]:
    return {
        cast(Domain, role.id): LEGACY_OUTPUT_INSTRUCTION
        + "\n\n"
        + role.instruction.removeprefix(COMMON_INSTRUCTION + "\n\n")
        for role in definitions()
        if not role.system_role
    }
