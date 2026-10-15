"""Let application units of work reuse repositories without nested commits."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.workforce.authorization import current_permission
from namoz_bot.domain.workforce.profiles import AccessDenied


async def check_permission(session: AsyncSession) -> None:
    permission = current_permission()
    if permission is None:
        return
    from namoz_bot.infrastructure.workforce.profiles import current_grant, lock_owner

    await lock_owner(session, permission.user_id)
    if (
        await current_grant(
            session, permission.user_id, permission.role_id, permission.capability_id
        )
        is None
    ):
        raise AccessDenied("Bu imkoniyat siz uchun o‘chirilgan.")


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
    session: AsyncSession | None,
    *,
    write: bool,
) -> AsyncIterator[AsyncSession]:
    if session is not None:
        await check_permission(session)
        yield session
    elif write:
        async with factory.begin() as owned:
            await check_permission(owned)
            yield owned
    else:
        async with factory() as owned:
            await check_permission(owned)
            yield owned
