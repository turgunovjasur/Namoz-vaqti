"""Versioned role edits serialize with grants before acquiring owner locks."""

from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from namoz_bot.domain.workforce.profiles import ProfileConflict
from namoz_bot.domain.workforce.roles import RoleDefinition, RoleWrite, RuleTemplate
from namoz_bot.infrastructure.orm import (
    AdminAuditRecord,
    AgentRoleRecord,
    AgentRoleSkillRecord,
    RoleAssignmentRecord,
    RoleCapabilityRecord,
    RoleModelRecord,
)
from namoz_bot.infrastructure.roles.locks import lock_catalog
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository, lock_owner

if TYPE_CHECKING:
    from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog


class SqlRoleManagement:
    def __init__(self, catalog: "SqlRoleCatalog", profiles: SqlAlchemyProfileRepository):
        self.catalog, self.profiles = catalog, profiles

    async def archive(self, actor_id: int, role_id: str, expected_revision: int) -> None:
        async with self.catalog.factory.begin() as session:
            await lock_catalog(session)
            await self.profiles.require_admin(session, actor_id)
            row = await session.get(AgentRoleRecord, role_id)
            if row is None or row.system_role or role_id == "assistant":
                raise ValueError("Bu agentni arxivlab bo‘lmaydi")
            if row.revision != expected_revision or row.archived:
                raise ProfileConflict("Role changed")
            owners = list(
                await session.scalars(
                    select(RoleAssignmentRecord.user_id)
                    .where(RoleAssignmentRecord.role_id == role_id)
                    .order_by(RoleAssignmentRecord.user_id)
                )
            )
            for owner in owners:
                await lock_owner(session, owner)
            row.enabled, row.archived, row.revision = False, True, row.revision + 1
            await session.execute(
                update(RoleAssignmentRecord)
                .where(RoleAssignmentRecord.role_id == role_id)
                .values(enabled=False, revision=RoleAssignmentRecord.revision + 1)
            )
            session.add(
                AdminAuditRecord(
                    actor_id=actor_id,
                    action="archive_role",
                    detail={"role_id": role_id, "name": row.name, "revision": row.revision},
                )
            )

    async def write_template(
        self, actor_id: int, rules: str, expected_revision: int
    ) -> RuleTemplate:
        async with self.catalog.factory.begin() as session:
            row = await lock_catalog(session)
            await self.profiles.require_admin(session, actor_id)
            if row.revision != expected_revision:
                raise ProfileConflict("Template changed")
            row.rules, row.revision = rules, row.revision + 1
            session.add(
                AdminAuditRecord(
                    actor_id=actor_id, action="set_role_template", detail={"revision": row.revision}
                )
            )
            return RuleTemplate(rules=row.rules, revision=row.revision)

    async def create(self, actor_id: int, role: RoleDefinition, model_id: str) -> RoleDefinition:
        try:
            async with self.catalog.factory.begin() as session:
                await lock_catalog(session)
                await self.profiles.require_admin(session, actor_id)
                session.add(
                    AgentRoleRecord(
                        id=role.id,
                        name=role.name,
                        name_key=role.name.casefold(),
                        description=role.description,
                        common_rules=role.common_rules,
                        enabled=role.enabled,
                        system_role=False,
                        revision=1,
                    )
                )
                await session.flush()
                session.add_all(
                    AgentRoleSkillRecord(role_id=role.id, capability_id=c)
                    for c in role.capability_ids
                )
                session.add(RoleModelRecord(role_id=role.id, model_id=model_id, version=1))
                session.add(
                    AdminAuditRecord(
                        actor_id=actor_id,
                        action="create_role",
                        detail={
                            "role_id": role.id,
                            "name": role.name,
                            "capability_ids": list(role.capability_ids),
                            "revision": 1,
                            "enabled": role.enabled,
                            "model_id": model_id,
                        },
                    )
                )
        except IntegrityError:
            raise ValueError("Bu nomdagi rol allaqachon mavjud") from None
        return role

    async def update(self, actor_id: int, role: RoleDefinition, draft: RoleWrite) -> RoleDefinition:
        try:
            async with self.catalog.factory.begin() as session:
                await lock_catalog(session)
                await self.profiles.require_admin(session, actor_id)
                row = await session.get(AgentRoleRecord, role.id)
                model = await session.get(RoleModelRecord, role.id)
                if (
                    row is None
                    or row.archived
                    or row.revision != draft.expected_revision
                    or ((model.version if model else 0) != draft.expected_model_version)
                ):
                    raise ProfileConflict("Role or model changed")
                owners = list(
                    await session.scalars(
                        select(RoleAssignmentRecord.user_id)
                        .where(RoleAssignmentRecord.role_id == role.id)
                        .order_by(RoleAssignmentRecord.user_id)
                    )
                )
                for owner in owners:
                    await lock_owner(session, owner)
                old_caps = set(
                    await session.scalars(
                        select(AgentRoleSkillRecord.capability_id).where(
                            AgentRoleSkillRecord.role_id == role.id
                        )
                    )
                )
                removed = old_caps.difference(role.capability_ids)
                if removed:
                    await session.execute(
                        delete(RoleCapabilityRecord).where(
                            RoleCapabilityRecord.role_id == role.id,
                            RoleCapabilityRecord.capability_id.in_(removed),
                        )
                    )
                if removed or row.enabled != role.enabled:
                    await session.execute(
                        update(RoleAssignmentRecord)
                        .where(RoleAssignmentRecord.role_id == role.id)
                        .values(revision=RoleAssignmentRecord.revision + 1)
                    )
                row.name, row.name_key = role.name, role.name.casefold()
                row.description, row.common_rules = role.description, role.common_rules
                row.enabled, row.revision = role.enabled, role.revision
                await session.execute(
                    delete(AgentRoleSkillRecord).where(AgentRoleSkillRecord.role_id == role.id)
                )
                session.add_all(
                    AgentRoleSkillRecord(role_id=role.id, capability_id=c)
                    for c in role.capability_ids
                )
                if model is None:
                    # Persist the current default on its first explicit save.
                    session.add(
                        RoleModelRecord(role_id=role.id, model_id=draft.model_id, version=1)
                    )
                elif model.model_id != draft.model_id:
                    model.model_id, model.version = draft.model_id, model.version + 1
                session.add(
                    AdminAuditRecord(
                        actor_id=actor_id,
                        action="update_role",
                        detail={
                            "role_id": role.id,
                            "name": role.name,
                            "capability_ids": list(role.capability_ids),
                            "revision": role.revision,
                            "enabled": role.enabled,
                            "model_id": draft.model_id,
                        },
                    )
                )
        except IntegrityError:
            raise ValueError("Bu nomdagi rol allaqachon mavjud") from None
        return role
