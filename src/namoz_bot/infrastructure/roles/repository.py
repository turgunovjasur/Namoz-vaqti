"""Load one consistent catalog query, with idempotent bootstrap for embedded/test installations."""

from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from namoz_bot.infrastructure.roles.management import SqlRoleManagement
    from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.roles.base import COMMON_INSTRUCTION
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.application.roles.runtime import RoleCatalogRuntime
from namoz_bot.domain.workforce.roles import RoleDefinition, RoleWrite, RuleTemplate
from namoz_bot.infrastructure.orm import AgentRoleRecord, AgentRoleSkillRecord
from namoz_bot.infrastructure.roles.locks import lock_catalog


def definition(row: AgentRoleRecord, caps: tuple[str, ...]) -> RoleDefinition:
    return RoleDefinition(
        id=row.id,
        name=row.name,
        description=row.description,
        instruction=row.description,
        common_rules=row.common_rules,
        capability_ids=caps,
        enabled=row.enabled,
        revision=row.revision,
        system_role=row.system_role,
    )


class SqlRoleCatalog:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        roles: RoleRegistry,
        *,
        profiles: "SqlAlchemyProfileRepository | None" = None,
    ) -> None:
        self.factory, self.roles = factory, roles
        self._initialized = False
        self._profiles = profiles
        self.runtime = RoleCatalogRuntime(self)

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self.factory.begin() as session:
            if not await session.scalar(select(func.count()).select_from(AgentRoleRecord)):
                await lock_catalog(session)
                if not await session.scalar(select(func.count()).select_from(AgentRoleRecord)):
                    for role in self.roles.defaults():
                        session.add(
                            AgentRoleRecord(
                                id=role.id,
                                name=role.name,
                                name_key=role.name.casefold(),
                                description=role.description,
                                common_rules=COMMON_INSTRUCTION,
                                enabled=role.id != "manager",
                                system_role=role.system_role,
                                revision=1,
                            )
                        )
                    await session.flush()
                    session.add_all(
                        AgentRoleSkillRecord(role_id=role.id, capability_id=c)
                        for role in self.roles.defaults()
                        for c in role.capability_ids
                    )
        self._initialized = True

    async def load(self) -> tuple[RoleDefinition, ...]:
        await self.initialize()
        async with self.factory() as session:
            rows = (
                await session.execute(
                    select(AgentRoleRecord, AgentRoleSkillRecord.capability_id)
                    .outerjoin(
                        AgentRoleSkillRecord, AgentRoleSkillRecord.role_id == AgentRoleRecord.id
                    )
                    .order_by(AgentRoleRecord.id, AgentRoleSkillRecord.capability_id)
                )
            ).all()
            roles: dict[str, AgentRoleRecord] = {}
            caps: dict[str, list[str]] = defaultdict(list)
            for role, cap in rows:
                roles[role.id] = role
                if cap is not None:
                    caps[role.id].append(cap)
            return tuple(definition(role, tuple(caps[role.id])) for role in roles.values())

    @asynccontextmanager
    async def scope(self, *, fresh: bool = False) -> AsyncIterator[None]:
        async with self.runtime.scope(fresh=fresh):
            yield

    async def read_role(self, role_id: str) -> RoleDefinition:
        for role in await self.load():
            if role.id == role_id:
                return role
        raise ValueError("Rol topilmadi")

    async def read_template(self) -> RuleTemplate:
        await self.initialize()
        async with self.factory.begin() as session:
            row = await lock_catalog(session)
            return RuleTemplate(rules=row.rules, revision=row.revision)

    async def write_template(
        self, actor_id: int, rules: str, expected_revision: int
    ) -> RuleTemplate:
        return await self._management().write_template(actor_id, rules, expected_revision)

    async def create_role(
        self, actor_id: int, role: RoleDefinition, model_id: str
    ) -> RoleDefinition:
        return await self._management().create(actor_id, role, model_id)

    async def update_role(
        self, actor_id: int, role: RoleDefinition, draft: RoleWrite
    ) -> RoleDefinition:
        return await self._management().update(actor_id, role, draft)

    def _management(self) -> "SqlRoleManagement":
        from namoz_bot.infrastructure.roles.management import SqlRoleManagement

        if self._profiles is None:
            raise RuntimeError("Role management requires trusted profile authorization")
        return SqlRoleManagement(self, self._profiles)
