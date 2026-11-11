"""Explicit historical role fixtures; production bootstraps only the assistant."""

import importlib.util
from pathlib import Path

from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.infrastructure.orm import AgentRoleRecord, AgentRoleSkillRecord


def definitions():
    path = Path(__file__).parents[2] / "alembic/versions/20261016_01_dynamic_roles.py"
    spec = importlib.util.spec_from_file_location("historical_roles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(
        RoleDefinition(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            instruction=r["description"],
            common_rules=r["common_rules"],
            enabled=r["enabled"],
            system_role=r["system_role"],
            capability_ids=tuple(
                s["capability_id"] for s in module.SKILLS if s["role_id"] == r["id"]
            ),
        )
        for r in module.ROLES
    )


def build_role_registry(capabilities):
    return RoleRegistry(definitions(), capabilities)


async def seed_roles(factory, roles):
    async with factory.begin() as session:
        for role in roles.all():
            if await session.get(AgentRoleRecord, role.id) is not None:
                continue
            session.add(
                AgentRoleRecord(
                    id=role.id,
                    name=role.name,
                    name_key=role.name.casefold(),
                    description=role.description,
                    common_rules=role.common_rules,
                    enabled=role.enabled,
                    system_role=role.system_role,
                    revision=1,
                )
            )
            await session.flush()
            session.add_all(
                AgentRoleSkillRecord(role_id=role.id, capability_id=c) for c in role.capability_ids
            )
