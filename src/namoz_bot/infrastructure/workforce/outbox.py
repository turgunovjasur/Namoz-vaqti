"""Retry delivery independently of business execution; remote sends may repeat."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.workforce.ports import TaskSender
from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.workforce.tasks import TaskMessage
from namoz_bot.infrastructure.orm import WorkforceOutboxRecord


class SqlAlchemyTaskOutbox:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.factory, self.clock = factory, clock

    async def send_due(self, sender: TaskSender) -> None:
        for _ in range(30):
            now = self.clock()
            async with self.factory.begin() as session:
                row = await session.scalar(
                    select(WorkforceOutboxRecord)
                    .where(
                        WorkforceOutboxRecord.status.in_(["pending", "sending"]),
                        WorkforceOutboxRecord.next_attempt <= now,
                        or_(
                            WorkforceOutboxRecord.lease_until.is_(None),
                            WorkforceOutboxRecord.lease_until <= now,
                        ),
                    )
                    .order_by(WorkforceOutboxRecord.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if row is None:
                    return
                token = uuid4().hex
                row.status, row.lease_token, row.lease_until = (
                    "sending",
                    token,
                    now + timedelta(seconds=180),
                )
                row.attempts += 1
                identity, chat_id, payload = row.id, row.chat_id, dict(row.payload)
            status = "sent"
            try:
                await sender.deliver_task(chat_id, TaskMessage.model_validate(payload))
            except RecipientBlockedError:
                status = "blocked"
            except Exception:
                status = "pending"
            async with self.factory.begin() as session:
                row = await session.scalar(
                    select(WorkforceOutboxRecord)
                    .where(
                        WorkforceOutboxRecord.id == identity,
                        WorkforceOutboxRecord.lease_token == token,
                    )
                    .with_for_update()
                )
                if row is not None:
                    row.status = status
                    row.lease_token = row.lease_until = None
                    row.next_attempt = self.clock() + timedelta(
                        seconds=min(3600, 5 * 2 ** min(row.attempts, 9))
                    )
