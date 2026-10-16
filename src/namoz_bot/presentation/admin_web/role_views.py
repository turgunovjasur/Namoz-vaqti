"""Public admin catalog DTOs, shared by create, edit and list endpoints."""

from typing import Any

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.domain.workforce.roles import RoleDefinition


def skill_view(service: ProfileService, skill_id: str) -> dict[str, Any]:
    spec = service.roles.capabilities.get(skill_id).spec
    return {
        "id": spec.id,
        "name": spec.name,
        "description": spec.description,
        "effect": spec.effect,
        "entrypoints": spec.entrypoints,
        "guidance": spec.guidance,
    }


async def role_view(service: ProfileService, role: RoleDefinition) -> dict[str, Any]:
    model = await service.repository.get_model(role.id, service.default_model(role.id))
    return {
        "id": role.id,
        "agent_id": role.id,
        "name": role.name,
        "description": role.description,
        "common_rules": role.common_rules,
        "enabled": role.enabled,
        "revision": role.revision,
        "system_role": role.system_role,
        "reserved": role.id == "manager",
        "capabilities": [skill_view(service, c) for c in role.capability_ids],
        "model": {
            **model.model_dump(mode="json"),
            "options": tuple(m.id for m in service.catalog.list_for_role(role.id)),
        },
    }
