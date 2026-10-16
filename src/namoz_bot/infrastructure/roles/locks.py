"""All catalog/grant mutations acquire this lock before locking affected owners."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from namoz_bot.application.roles.base import COMMON_INSTRUCTION
from namoz_bot.infrastructure.orm import AgentRuleTemplateRecord


async def lock_catalog(session: AsyncSession) -> AgentRuleTemplateRecord:
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(AgentRuleTemplateRecord)
        .values(id="default", rules=COMMON_INSTRUCTION, revision=1)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    row = await session.scalar(
        select(AgentRuleTemplateRecord)
        .where(AgentRuleTemplateRecord.id == "default")
        .with_for_update()
    )
    assert row is not None
    return row
