"""Bounded admin metadata queries; business records and conversations stay private."""

from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.workforce.profiles import UserPage
from namoz_bot.infrastructure.orm import RoleAssignmentRecord, UserRecord
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository


async def sync_identity(
    factory: async_sessionmaker[AsyncSession], user_id: int, name: str, username: str | None
) -> None:
    async with factory.begin() as session:
        await session.execute(
            update(UserRecord)
            .where(UserRecord.id == user_id)
            .values(display_name=name[:256], username=username[:64] if username else None)
        )


class AdminQueries:
    def __init__(self, profiles: SqlAlchemyProfileRepository) -> None:
        self.profiles = profiles

    async def users(
        self,
        actor_id: int,
        *,
        q: str = "",
        role_id: str | None = None,
        after_id: int = 0,
        limit: int = 20,
    ) -> UserPage:
        if role_id:
            if self.profiles.roles.get(role_id).system_role:
                role_id = None  # System roles apply to every account.
        async with self.profiles.factory.begin() as session:
            await self.profiles.require_admin(session, actor_id)
            query = select(UserRecord.id).where(UserRecord.id > after_id)
            if q.strip():
                text = q.strip().lstrip("@").lower()
                query = query.where(
                    or_(
                        func.lower(UserRecord.display_name).contains(text, autoescape=True),
                        func.lower(UserRecord.username).contains(text, autoescape=True),
                        cast(UserRecord.telegram_user_id, String).contains(text, autoescape=True),
                    )
                )
            if role_id:
                query = query.where(
                    select(RoleAssignmentRecord.user_id)
                    .where(
                        RoleAssignmentRecord.user_id == UserRecord.id,
                        RoleAssignmentRecord.role_id == role_id,
                        RoleAssignmentRecord.enabled.is_(True),
                    )
                    .exists()
                )
            ids = list(await session.scalars(query.order_by(UserRecord.id).limit(limit + 1)))
            return UserPage(
                users=tuple([await self.profiles._profile(session, uid) for uid in ids[:limit]]),
                more=len(ids) > limit,
            )

    async def counts(self, actor_id: int) -> dict[str, int]:
        async with self.profiles.factory.begin() as session:
            await self.profiles.require_admin(session, actor_id)
            total = await session.scalar(select(func.count()).select_from(UserRecord))
            assigned = await session.scalar(
                select(func.count(func.distinct(RoleAssignmentRecord.user_id))).where(
                    RoleAssignmentRecord.enabled.is_(True)
                )
            )
            return {"users": total or 0, "assigned_users": assigned or 0}
