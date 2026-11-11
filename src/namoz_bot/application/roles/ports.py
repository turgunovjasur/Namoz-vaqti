"""Persistent catalog boundary; role creation is configuration, never executable code."""

from typing import Protocol

from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.roles import RoleDefinition, RoleWrite, RuleTemplate


class RoleCatalogStore(Protocol):
    roles: RoleRegistry

    async def load(self) -> tuple[RoleDefinition, ...]: ...
    async def read_role(self, role_id: str) -> RoleDefinition: ...
    async def read_template(self) -> RuleTemplate: ...
    async def write_template(
        self, actor_id: int, rules: str, expected_revision: int
    ) -> RuleTemplate: ...
    async def create_role(
        self, actor_id: int, role: RoleDefinition, model_id: str
    ) -> RoleDefinition: ...
    async def update_role(
        self, actor_id: int, role: RoleDefinition, draft: RoleWrite
    ) -> RoleDefinition: ...
    async def archive_role(self, actor_id: int, role_id: str, expected_revision: int) -> None: ...
