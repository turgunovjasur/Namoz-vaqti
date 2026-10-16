"""SQL assignments, authoritative admin identity and owner-serialized effects."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.profiles.ports import PermissionTransaction
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.profiles import (
    AccessDenied,
    AdminChange,
    AuditPage,
    GrantChange,
    PermissionSnapshot,
    ProfileConflict,
    ProfileView,
    RoleAssignment,
    RoleModelSetting,
    UserPage,
)
from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentTransaction
from namoz_bot.infrastructure.orm import (
    AdminAuditRecord,
    AgentRoleRecord,
    AgentRoleSkillRecord,
    AgentSessionRecord,
    ProfileRecord,
    RoleAssignmentRecord,
    RoleCapabilityRecord,
    RoleModelRecord,
    UserRecord,
)


async def lock_owner(session: AsyncSession, user_id: int) -> UserRecord:
    row = await session.scalar(select(UserRecord).where(UserRecord.id == user_id).with_for_update())
    if row is None:
        raise AccessDenied("Unknown account")
    return row


async def current_grant(
    session: AsyncSession, user_id: int, role_id: str, capability_id: str
) -> PermissionSnapshot | None:
    if await session.scalar(select(AgentRoleRecord.id).limit(1)) is not None:
        role = await session.get(AgentRoleRecord, role_id)
        link = await session.get(AgentRoleSkillRecord, (role_id, capability_id))
        if role is None or not role.enabled or link is None:
            return None
    row = await session.get(RoleAssignmentRecord, (user_id, role_id))
    cap = await session.get(RoleCapabilityRecord, (user_id, role_id, capability_id))
    if row is None or not row.enabled or cap is None:
        return None
    return PermissionSnapshot(
        user_id=user_id,
        role_id=role_id,
        capability_id=capability_id,
        assignment_revision=row.revision,
    )


class SqlPermissionTransaction(SqlAlchemyAgentTransaction):
    async def current_grant(
        self, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot | None:
        if user_id != self._row.user_id:
            return None
        return await current_grant(self._session, user_id, role_id, capability_id)


class SqlAlchemyProfileRepository:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        roles: RoleRegistry,
        *,
        admin_telegram_ids: frozenset[int] = frozenset(),
    ) -> None:
        self.factory, self.roles = factory, roles
        self.admin_telegram_ids = admin_telegram_ids

    async def _profile(self, session: AsyncSession, user_id: int) -> ProfileView:
        user = await session.get(UserRecord, user_id)
        if user is None:
            raise AccessDenied("Unknown account")
        kind = "admin" if user.telegram_user_id in self.admin_telegram_ids else "user"
        row = await session.get(ProfileRecord, user_id)
        if row is None:
            session.add(ProfileRecord(user_id=user_id, profile_type=kind))
        else:
            row.profile_type = kind
        rows = list(
            await session.scalars(
                select(RoleAssignmentRecord)
                .where(RoleAssignmentRecord.user_id == user_id)
                .order_by(RoleAssignmentRecord.role_id)
            )
        )
        caps = list(
            await session.scalars(
                select(RoleCapabilityRecord).where(RoleCapabilityRecord.user_id == user_id)
            )
        )
        return ProfileView(
            user_id=user_id,
            telegram_user_id=user.telegram_user_id,
            display_name=user.display_name,
            username=user.username,
            is_active=user.is_active,
            profile_type=cast(Literal["admin", "user"], kind),
            roles=tuple(
                RoleAssignment(
                    role_id=r.role_id,
                    enabled=r.enabled,
                    revision=r.revision,
                    capability_ids=frozenset(
                        c.capability_id for c in caps if c.role_id == r.role_id
                    ),
                )
                for r in rows
            ),
        )

    async def get_profile(self, user_id: int) -> ProfileView:
        async with self.factory.begin() as session:
            await lock_owner(session, user_id)
            return await self._profile(session, user_id)

    async def require_admin(self, session: AsyncSession, actor_id: int) -> None:
        actor = await session.get(UserRecord, actor_id)
        if actor is None or actor.telegram_user_id not in self.admin_telegram_ids:
            raise AccessDenied("Administrator required")
        await self._profile(session, actor_id)

    async def current_grant(
        self, user_id: int, role_id: str, capability_id: str
    ) -> PermissionSnapshot | None:
        async with self.factory() as session:
            return await current_grant(session, user_id, role_id, capability_id)

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
        return await self.set_assignments(
            actor_id=actor_id,
            user_id=user_id,
            changes=(
                GrantChange(
                    role_id=role_id,
                    enabled=enabled,
                    capability_ids=capability_ids,
                    expected_revision=expected_revision,
                ),
            ),
        )

    async def set_assignments(
        self, *, actor_id: int, user_id: int, changes: tuple[GrantChange, ...]
    ) -> ProfileView:
        if not changes or len({c.role_id for c in changes}) != len(changes):
            raise ValueError("Har bir rolni faqat bir marta yuboring.")
        for change in changes:
            role = self.roles.get(change.role_id)
            if role.system_role or not change.capability_ids.issubset(role.capability_ids):
                raise ValueError("Invalid role capabilities")
        async with self.factory.begin() as session:
            from namoz_bot.infrastructure.roles.locks import lock_catalog

            await lock_catalog(session)
            await self.require_admin(session, actor_id)
            if await session.scalar(select(AgentRoleRecord.id).limit(1)) is not None:
                for change in changes:
                    role_row = await session.get(AgentRoleRecord, change.role_id)
                    links = set(
                        await session.scalars(
                            select(AgentRoleSkillRecord.capability_id).where(
                                AgentRoleSkillRecord.role_id == change.role_id
                            )
                        )
                    )
                    if (
                        role_row is None
                        or role_row.system_role
                        or (change.enabled and not role_row.enabled)
                        or not change.capability_ids.issubset(links)
                    ):
                        raise ValueError("Role or skills changed; refresh the catalog")
            await lock_owner(session, user_id)
            for change in changes:
                row = await session.get(RoleAssignmentRecord, (user_id, change.role_id))
                if (row.revision if row else 0) != change.expected_revision:
                    raise ProfileConflict("Assignment changed")
                if row is None:
                    row = RoleAssignmentRecord(user_id=user_id, role_id=change.role_id, revision=0)
                    session.add(row)
                row.enabled, row.revision = change.enabled, row.revision + 1
                await session.execute(
                    delete(RoleCapabilityRecord).where(
                        RoleCapabilityRecord.user_id == user_id,
                        RoleCapabilityRecord.role_id == change.role_id,
                    )
                )
                session.add_all(
                    RoleCapabilityRecord(user_id=user_id, role_id=change.role_id, capability_id=c)
                    for c in sorted(change.capability_ids)
                )
                session.add(
                    AdminAuditRecord(
                        actor_id=actor_id,
                        target_id=user_id,
                        action="set_grants",
                        detail={
                            "role_id": change.role_id,
                            "enabled": change.enabled,
                            "capability_ids": sorted(change.capability_ids),
                            "revision": row.revision,
                        },
                    )
                )
                await session.flush()
            return await self._profile(session, user_id)

    @asynccontextmanager
    async def effect_scope(
        self, user_id: int, *, now: datetime
    ) -> AsyncIterator[PermissionTransaction]:
        async with self.factory.begin() as session:
            await lock_owner(session, user_id)
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(AgentSessionRecord)
                .values(user_id=user_id, revision=0)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            row = await session.get(AgentSessionRecord, user_id)
            assert row is not None
            yield SqlPermissionTransaction(self.factory, session, row, now)

    async def list_users(self, actor_id: int, *, after_id: int, limit: int) -> UserPage:
        async with self.factory.begin() as session:
            await self.require_admin(session, actor_id)
            ids = list(
                await session.scalars(
                    select(UserRecord.id)
                    .where(UserRecord.id > after_id)
                    .order_by(UserRecord.id)
                    .limit(limit + 1)
                )
            )
            return UserPage(
                users=tuple([await self._profile(session, uid) for uid in ids[:limit]]),
                more=len(ids) > limit,
            )

    async def find_user(self, actor_id: int, telegram_id: int) -> ProfileView | None:
        async with self.factory.begin() as session:
            await self.require_admin(session, actor_id)
            user_id = await session.scalar(
                select(UserRecord.id).where(UserRecord.telegram_user_id == telegram_id)
            )
            return await self._profile(session, user_id) if user_id is not None else None

    async def history(self, actor_id: int, *, before_id: int, limit: int) -> AuditPage:
        async with self.factory.begin() as session:
            await self.require_admin(session, actor_id)
            query = select(AdminAuditRecord).order_by(AdminAuditRecord.id.desc()).limit(limit + 1)
            if before_id:
                query = query.where(AdminAuditRecord.id < before_id)
            rows = list(await session.scalars(query))
            changes = []
            for row in rows[:limit]:
                actor = await session.get(UserRecord, row.actor_id)
                target = (
                    await session.get(UserRecord, row.target_id)
                    if row.target_id is not None
                    else None
                )
                assert actor is not None
                changes.append(
                    AdminChange(
                        id=row.id,
                        actor_telegram_id=actor.telegram_user_id,
                        target_telegram_id=target.telegram_user_id if target else None,
                        action=row.action,
                        detail=row.detail,
                        created_at=row.created_at
                        if row.created_at.tzinfo
                        else row.created_at.replace(tzinfo=UTC),
                    )
                )
            return AuditPage(changes=tuple(changes), more=len(rows) > limit)

    async def get_model(self, role_id: str, default: str) -> RoleModelSetting:
        async with self.factory() as session:
            row = await session.get(RoleModelRecord, role_id)
            return RoleModelSetting(
                role_id=role_id,
                model_id=row.model_id if row else default,
                version=row.version if row else 0,
            )

    async def set_model(
        self, *, actor_id: int, role_id: str, model_id: str, expected_version: int
    ) -> RoleModelSetting:
        async with self.factory.begin() as session:
            from namoz_bot.infrastructure.roles.locks import lock_catalog

            await lock_catalog(session)
            await self.require_admin(session, actor_id)
            if expected_version == 0:
                insert = (
                    pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
                )
                won = await session.scalar(
                    insert(RoleModelRecord)
                    .values(role_id=role_id, model_id=model_id, version=1)
                    .on_conflict_do_nothing(index_elements=["role_id"])
                    .returning(RoleModelRecord.version)
                )
            else:
                won = await session.scalar(
                    update(RoleModelRecord)
                    .where(
                        RoleModelRecord.role_id == role_id,
                        RoleModelRecord.version == expected_version,
                    )
                    .values(model_id=model_id, version=expected_version + 1)
                    .returning(RoleModelRecord.version)
                )
            if won is None:
                raise ProfileConflict("Model setting changed")
            session.add(
                AdminAuditRecord(
                    actor_id=actor_id,
                    target_id=None,
                    action="set_model",
                    detail={"role_id": role_id, "model_id": model_id, "version": won},
                )
            )
            return RoleModelSetting(role_id=role_id, model_id=model_id, version=won)
