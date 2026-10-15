"""Persistence boundary for trusted account and assignment management."""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.domain.workforce.profiles import PermissionSnapshot, ProfileView


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
