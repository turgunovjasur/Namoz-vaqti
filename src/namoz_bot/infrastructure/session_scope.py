"""Let application units of work reuse repositories without nested commits."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
    session: AsyncSession | None,
    *,
    write: bool,
) -> AsyncIterator[AsyncSession]:
    if session is not None:
        yield session
    elif write:
        async with factory.begin() as owned:
            yield owned
    else:
        async with factory() as owned:
            yield owned
