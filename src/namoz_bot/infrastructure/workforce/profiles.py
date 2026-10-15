"""SQL assignments, authoritative admin identity and owner-serialized effects."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.profiles.ports import PermissionTransaction
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.profiles import (
    AccessDenied,
    PermissionSnapshot,
    ProfileConflict,
    ProfileView,
    RoleAssignment,
)
from namoz_bot.infrastructure.agent_sessions import SqlAlchemyAgentTransaction
from namoz_bot.infrastructure.orm import (
    AdminAuditRecord,
    AgentSessionRecord,
    ProfileRecord,
    RoleAssignmentRecord,
    RoleCapabilityRecord,
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
        role = self.roles.get(role_id)
        if role.system_role or not capability_ids.issubset(role.capability_ids):
            raise ValueError("Invalid role capabilities")
        async with self.factory.begin() as session:
            await self.require_admin(session, actor_id)
            await lock_owner(session, user_id)
            row = await session.get(RoleAssignmentRecord, (user_id, role_id))
            if (row.revision if row else 0) != expected_revision:
                raise ProfileConflict("Assignment changed")
            if row is None:
                row = RoleAssignmentRecord(user_id=user_id, role_id=role_id, revision=0)
                session.add(row)
            row.enabled, row.revision = enabled, row.revision + 1
            await session.execute(
                delete(RoleCapabilityRecord).where(
                    RoleCapabilityRecord.user_id == user_id, RoleCapabilityRecord.role_id == role_id
                )
            )
            session.add_all(
                RoleCapabilityRecord(user_id=user_id, role_id=role_id, capability_id=c)
                for c in sorted(capability_ids)
            )
            session.add(
                AdminAuditRecord(
                    actor_id=actor_id,
                    target_id=user_id,
                    action="set_grants",
                    detail={
                        "role_id": role_id,
                        "enabled": enabled,
                        "capability_ids": sorted(capability_ids),
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
