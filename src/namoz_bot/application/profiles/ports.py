"""Persistence boundary for trusted account and assignment management."""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.domain.workforce.profiles import (
    ModelOption,
    PermissionSnapshot,
    ProfileView,
    RoleModelSetting,
    UserPage,
)
from namoz_bot.domain.workforce.roles import RoleDefinition


class PermissionTransaction(AgentTransaction, Protocol):
    async def current_grant(
        self, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot | None: ...


class ProfileRepository(Protocol):
    async def get_profile(self, user_id: int) -> ProfileView: ...
    async def current_grant(
        self, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot | None: ...
    def effect_scope(
        self, user_id: int, *, now: datetime
    ) -> AbstractAsyncContextManager[PermissionTransaction]: ...
    async def set_grants(
        self,
        *,
        actor_id: int,
        user_id: int,
        role_id: str,
        enabled: bool,
        capability_ids: frozenset[str],
        expected_revision: int,
    ) -> ProfileView: ...


class ModelCatalog(Protocol):
    def list_for_role(self, role_id: str) -> tuple[ModelOption, ...]: ...
    async def validate(self, model_id: str, role: RoleDefinition) -> None: ...


class ProfileManagementRepository(ProfileRepository, Protocol):
    async def list_users(self, actor_id: int, *, after_id: int, limit: int) -> UserPage: ...
    async def get_model(self, role_id: str, default: str) -> RoleModelSetting: ...
    async def set_model(
        self, *, actor_id: int, role_id: str, model_id: str, expected_version: int
    ) -> RoleModelSetting: ...
