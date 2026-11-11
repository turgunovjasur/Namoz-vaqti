"""Durable per-user surah selections."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.infrastructure.orm import SelectedSurahRecord


class SurahSelection:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def list_for(self, user_id: int) -> set[int]:
        async with self.factory() as session:
            return set(
                await session.scalars(
                    select(SelectedSurahRecord.chapter).where(
                        SelectedSurahRecord.user_id == user_id
                    )
                )
            )

    async def set_selected(self, user_id: int, chapter: int, *, selected: bool) -> None:
        async with self.factory.begin() as session:
            if selected:
                insert = (
                    pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
                )
                await session.execute(
                    insert(SelectedSurahRecord)
                    .values(user_id=user_id, chapter=chapter)
                    .on_conflict_do_nothing()
                )
            else:
                await session.execute(
                    delete(SelectedSurahRecord).where(
                        SelectedSurahRecord.user_id == user_id,
                        SelectedSurahRecord.chapter == chapter,
                    )
                )
