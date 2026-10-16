"""One deny-by-default policy for roles, capabilities and effect transactions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from namoz_bot.application.profiles.ports import PermissionTransaction, ProfileRepository
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.application.roles.runtime import RoleCatalogRuntime
from namoz_bot.domain.workforce.profiles import AccessDenied, PermissionSnapshot
from namoz_bot.domain.workforce.roles import RoleDefinition


class AccessService:
    def __init__(
        self,
        repository: ProfileRepository,
        roles: RoleRegistry,
        *,
        runtime: RoleCatalogRuntime | None = None,
    ):
        self.repository, self.roles, self.runtime = repository, roles, runtime

    @asynccontextmanager
    async def role_scope(self) -> AsyncIterator[None]:
        if self.runtime is None:
            yield
        else:
            async with self.runtime.scope():
                yield

    def validate(self, role_id: str, capability_id: str) -> None:
        if (
            not self.roles.get(role_id).enabled
            or capability_id not in self.roles.get(role_id).capability_ids
        ):
            raise AccessDenied("Capability outside role")

    async def allowed(self, user_id: int, role_id: str, capability_id: str) -> bool:
        async with self.role_scope():
            try:
                self.validate(role_id, capability_id)
            except (ValueError, AccessDenied):
                return False
            return await self.repository.current_grant(user_id, role_id, capability_id) is not None

    async def allowed_any(self, user_id: int, capability_id: str) -> bool:
        async with self.role_scope():
            for role in await self.available_roles(user_id):
                if capability_id in role.capability_ids and await self.allowed(
                    user_id, role.id, capability_id
                ):
                    return True
            return False

    async def require(self, user_id: int, role_id: str, capability_id: str) -> PermissionSnapshot:
        async with self.role_scope():
            self.validate(role_id, capability_id)
            grant = await self.repository.current_grant(user_id, role_id, capability_id)
            if grant is None:
                raise AccessDenied(
                    "Bu imkoniyat siz uchun yoqilmagan. Administratorga murojaat qiling."
                )
            return grant

    async def available_roles(self, user_id: int) -> tuple[RoleDefinition, ...]:
        async with self.role_scope():
            profile = await self.repository.get_profile(user_id)
            available = {r.id: r for r in self.roles.all() if r.enabled and not r.system_role}
            result = []
            for assignment in profile.roles:
                role = available.get(assignment.role_id)
                if role is None or not assignment.enabled:
                    continue
                caps = tuple(c for c in role.capability_ids if c in assignment.capability_ids)
                if caps:
                    result.append(role.model_copy(update={"capability_ids": caps}))
            return tuple(result)

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
