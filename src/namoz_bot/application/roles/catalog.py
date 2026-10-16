"""Role configuration and model checks; executable skills stay in the trusted backend."""

from uuid import uuid4

from namoz_bot.application.profiles.ports import ProfileRepository
from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.ports import RoleCatalogStore
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.roles import RoleDefinition, RoleWrite, RuleTemplate


class RoleCatalogService:
    def __init__(
        self, store: RoleCatalogStore, profiles: ProfileRepository, models: ProfileService
    ):
        self.store, self.profiles, self.models = store, profiles, models

    async def _admin(self, actor_id: int) -> None:
        if (await self.profiles.get_profile(actor_id)).profile_type != "admin":
            raise AccessDenied("Bu amal administrator uchun")

    def _validate_skills(self, ids: frozenset[str]) -> None:
        for capability_id in ids:
            self.store.roles.capabilities.get(capability_id)

    async def create(self, actor_id: int, draft: RoleWrite) -> RoleDefinition:
        await self._admin(actor_id)
        if draft.expected_revision or draft.expected_model_version:
            raise ValueError("Yangi rol versiyasi 0 bo‘lishi kerak")
        self._validate_skills(draft.capability_ids)
        rules = draft.common_rules
        if rules is None:
            rules = (await self.store.read_template()).rules
        role = RoleDefinition(
            id="role_" + uuid4().hex[:20],
            name=draft.name,
            description=draft.description,
            instruction=draft.description,
            common_rules=rules,
            capability_ids=tuple(sorted(draft.capability_ids)),
            enabled=draft.enabled,
            revision=1,
        )
        await self.models.catalog.validate(draft.model_id, role)
        return await self.store.create_role(actor_id, role, draft.model_id)

    async def update(self, actor_id: int, role_id: str, draft: RoleWrite) -> RoleDefinition:
        await self._admin(actor_id)
        current = await self.store.read_role(role_id)
        if current.system_role and (
            current.id != "assistant"
            or draft.name != current.name
            or draft.description != current.description
            or draft.enabled != current.enabled
            or draft.capability_ids != frozenset(current.capability_ids)
        ):
            raise ValueError("Tizim rolining nomi, vazifasi va skilllari himoyalangan")
        self._validate_skills(draft.capability_ids)
        role = current.model_copy(
            update={
                "name": draft.name,
                "description": draft.description,
                "instruction": draft.description,
                "common_rules": current.common_rules
                if draft.common_rules is None
                else draft.common_rules,
                "capability_ids": tuple(sorted(draft.capability_ids)),
                "enabled": draft.enabled,
                "revision": current.revision + 1,
            }
        )
        old_model = await self.models.repository.get_model(
            role_id, self.models.default_model(role_id)
        )
        if draft.model_id != old_model.model_id:
            await self.models.catalog.validate(draft.model_id, role)
        return await self.store.update_role(actor_id, role, draft)

    async def template(self, actor_id: int) -> RuleTemplate:
        await self._admin(actor_id)
        return await self.store.read_template()

    async def set_template(self, actor_id: int, rules: str, expected_revision: int) -> RuleTemplate:
        await self._admin(actor_id)
        checked = RuleTemplate(rules=rules, revision=expected_revision)
        return await self.store.write_template(actor_id, checked.rules, checked.revision)
