"""Trusted profile views, assignment changes and global role model management."""

from namoz_bot.application.profiles.ports import ModelCatalog, ProfileManagementRepository
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.profiles import (
    AccessDenied,
    ProfileView,
    RoleModelSetting,
    UserPage,
)


class ProfileService:
    def __init__(
        self,
        repository: ProfileManagementRepository,
        roles: RoleRegistry,
        catalog: ModelCatalog,
        *,
        default_models: dict[str, str],
    ):
        self.repository, self.roles, self.catalog = repository, roles, catalog
        self.default_models = dict(default_models)

    async def self_view(self, actor_id: int) -> ProfileView:
        return await self.repository.get_profile(actor_id)

    async def _admin(self, actor_id: int) -> None:
        if (await self.self_view(actor_id)).profile_type != "admin":
            raise AccessDenied("Bu amal administrator uchun.")

    async def user_view(self, actor_id: int, user_id: int) -> ProfileView:
        if actor_id != user_id:
            await self._admin(actor_id)
        return await self.repository.get_profile(user_id)

    async def list_users(self, actor_id: int, *, after_id: int = 0, limit: int = 10) -> UserPage:
        await self._admin(actor_id)
        return await self.repository.list_users(
            actor_id, after_id=max(0, after_id), limit=min(20, max(1, limit))
        )

    async def set_grants(
        self,
        *,
        actor_id: int,
        user_id: int,
        role_id: str,
        enabled: bool,
        capability_ids: frozenset[str],
        expected_revision: int,
    ) -> ProfileView:
        await self._admin(actor_id)
        return await self.repository.set_grants(
            actor_id=actor_id,
            user_id=user_id,
            role_id=role_id,
            enabled=enabled,
            capability_ids=capability_ids,
            expected_revision=expected_revision,
        )

    def model_options(self, role_id: str) -> tuple[str, ...]:
        self.roles.get(role_id)
        return tuple(m.id for m in self.catalog.list_for_role(role_id))

    async def model(self, role_id: str) -> RoleModelSetting:
        self.roles.get(role_id)
        return await self.repository.get_model(role_id, self.default_models[role_id])

    async def set_model(
        self, *, actor_id: int, role_id: str, model_id: str, expected_version: int
    ) -> RoleModelSetting:
        await self._admin(actor_id)
        await self.catalog.validate(model_id, self.roles.get(role_id))
        return await self.repository.set_model(
            actor_id=actor_id, role_id=role_id, model_id=model_id, expected_version=expected_version
        )
