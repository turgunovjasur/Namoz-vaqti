"""Retry delivery independently of business execution; remote sends may repeat."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

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
                accepted = aliased(WorkforceOutboxRecord)
                waiting_status = (
                    select(accepted.id)
                    .where(
                        accepted.task_id == WorkforceOutboxRecord.task_id,
                        accepted.revision == WorkforceOutboxRecord.revision,
                        accepted.kind == "accepted",
                        accepted.status.in_(["pending", "sending"]),
                    )
                    .exists()
                )
                row = await session.scalar(
                    select(WorkforceOutboxRecord)
                    .where(
                        WorkforceOutboxRecord.status.in_(["pending", "sending"]),
                        WorkforceOutboxRecord.next_attempt <= now,
                        or_(WorkforceOutboxRecord.kind == "accepted", ~waiting_status),
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
                task_id, revision, kind = row.task_id, row.revision, row.kind
            status = "sent"
            try:
                # Keep transport receipts in the existing durable outbox payload. A cleanup
                # retry (including after restart) must never send the final result again.
                delivery = payload.pop("_delivery", None)
                if delivery is None:
                    message = TaskMessage.model_validate(payload)
                    if kind == "accepted":
                        message = message.model_copy(
                            update={"text": "🤖 So‘rovingiz qabul qilindi. Natija tayyorlanmoqda…"}
                        )
                    message_id = await sender.deliver_task(chat_id, message)
                    async with self.factory.begin() as session:
                        sent = await session.scalar(
                            select(WorkforceOutboxRecord)
                            .where(
                                WorkforceOutboxRecord.id == identity,
                                WorkforceOutboxRecord.lease_token == token,
                            )
                            .with_for_update()
                        )
                        if sent is None:
                            continue
                        sent.payload = {**payload, "_delivery": {"message_id": message_id}}
                if kind in {"result", "failure"}:
                    async with self.factory() as session:
                        status_card = await session.scalar(
                            select(WorkforceOutboxRecord).where(
                                WorkforceOutboxRecord.task_id == task_id,
                                WorkforceOutboxRecord.revision == revision,
                                WorkforceOutboxRecord.kind == "accepted",
                            )
                        )
                        receipt = status_card.payload.get("_delivery") if status_card else None
                        status_id = receipt.get("message_id") if isinstance(receipt, dict) else None
                    if isinstance(status_id, int):
                        await sender.delete_task_message(chat_id, status_id)
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
