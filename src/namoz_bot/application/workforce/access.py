"""One deny-by-default policy for roles, capabilities and effect transactions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from namoz_bot.application.profiles.ports import PermissionTransaction, ProfileRepository
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.profiles import AccessDenied, PermissionSnapshot
from namoz_bot.domain.workforce.roles import RoleDefinition


class AccessService:
    def __init__(self, repository: ProfileRepository, roles: RoleRegistry):
        self.repository, self.roles = repository, roles

    def validate(self, role_id: str, capability_id: str) -> None:
        if capability_id not in self.roles.get(role_id).capability_ids:
            raise AccessDenied("Capability outside role")

    async def allowed(self, user_id: int, role_id: str, capability_id: str) -> bool:
        try:
            self.validate(role_id, capability_id)
        except (ValueError, AccessDenied):
            return False
        return await self.repository.current_grant(user_id, role_id, capability_id) is not None

    async def require(self, user_id: int, role_id: str, capability_id: str) -> PermissionSnapshot:
        self.validate(role_id, capability_id)
        grant = await self.repository.current_grant(user_id, role_id, capability_id)
        if grant is None:
            raise AccessDenied(
                "Bu imkoniyat siz uchun yoqilmagan. Administratorga murojaat qiling."
            )
        return grant

    async def available_roles(self, user_id: int) -> tuple[RoleDefinition, ...]:
        profile = await self.repository.get_profile(user_id)
        return tuple(
            self.roles.get(a.role_id).model_copy(
                update={
                    "capability_ids": tuple(
                        c for c in self.roles.get(a.role_id).capability_ids if c in a.capability_ids
                    )
                }
            )
            for a in profile.roles
            if a.enabled and a.capability_ids
        )

    async def require_in(
        self, transaction: PermissionTransaction, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot:
        self.validate(role_id, capability_id)
        grant = await transaction.current_grant(user_id, role_id, capability_id)
        if grant is None:
            raise AccessDenied("Bu imkoniyat siz uchun o‘chirilgan.")
        return grant

    @asynccontextmanager
    async def effect_scope(
        self, user_id: int, role_id: str, capability_id: str, *, now: datetime | None = None
    ) -> AsyncIterator[PermissionTransaction]:
        async with self.repository.effect_scope(user_id, now=now or datetime.now(UTC)) as tx:
            await self.require_in(tx, user_id, role_id, capability_id)
            yield tx
