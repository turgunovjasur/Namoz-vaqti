"""Short PostgreSQL SKIP LOCKED leases, with fenced heartbeats and retries."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.domain.workforce.tasks import ClaimedTask, TaskMessage
from namoz_bot.infrastructure.orm import WorkforceRevisionRecord, WorkforceTaskRecord
from namoz_bot.infrastructure.workforce.tasks import put_outbox, revision_value


def failure_message(row: WorkforceRevisionRecord) -> TaskMessage:
    label = f"Vazifa: {str(row.plan.get('transcript', row.task_id))[:200]}\n\n"
    if row.service_result is not None:
        saved = row.service_result.get("effect") == "committed"
        text = (
            "Amal saqlandi." if saved else "Natija olindi."
        ) + " Natijani tekshirish yakunlanmadi. Amalni qayta bajarmang."
    else:
        text = "Vazifa bajarilmadi. Ruxsatlar yoki ma’lumotlarni tekshirib qayta ayting."
    return TaskMessage(
        text="🤖 " + label + text,
        task_id=row.task_id,
        revision=row.revision,
    )


class SqlAlchemyTaskQueue:
    def __init__(self, factory: async_sessionmaker[AsyncSession]):
        self.factory = factory

    async def claim(
        self, *, now: datetime, limit: int = 3, lease_seconds: int = 180
    ) -> list[ClaimedTask]:
        claimed = []
        async with self.factory.begin() as session:
            tasks = list(
                await session.scalars(
                    select(WorkforceTaskRecord)
                    .where(
                        WorkforceTaskRecord.status.in_(["queued", "running", "reviewing"]),
                        or_(
                            WorkforceTaskRecord.lease_until.is_(None),
                            WorkforceTaskRecord.lease_until <= now,
                        ),
                    )
                    .order_by(WorkforceTaskRecord.created_at, WorkforceTaskRecord.id)
                    .limit(min(32, max(1, limit)))
                    .with_for_update(skip_locked=True)
                )
            )
            for task in tasks:
                row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
                assert row is not None
                if task.attempts >= 3:
                    row.status = task.status = "failed"
                    await put_outbox(
                        session,
                        task,
                        "failure",
                        failure_message(row),
                        now,
                    )
                    continue
                token = uuid4().hex
                task.lease_token, task.lease_until = token, now + timedelta(seconds=lease_seconds)
                task.attempts += 1
                row.status = task.status = "reviewing" if row.service_result else "running"
                claimed.append(ClaimedTask(task=revision_value(row), lease_token=token))
        return claimed

    async def heartbeat(self, task_id: str, token: str, now: datetime) -> bool:
        async with self.factory.begin() as session:
            return (
                await session.scalar(
                    update(WorkforceTaskRecord)
                    .where(
                        WorkforceTaskRecord.id == task_id,
                        WorkforceTaskRecord.lease_token == token,
                        WorkforceTaskRecord.lease_until > now,
                        WorkforceTaskRecord.status.in_(["running", "reviewing"]),
                    )
                    .values(lease_until=now + timedelta(seconds=180))
                    .returning(WorkforceTaskRecord.id)
                )
                is not None
            )

    async def fail(self, claim: ClaimedTask, *, permanent: bool, now: datetime) -> None:
        async with self.factory.begin() as session:
            task = await session.scalar(
                select(WorkforceTaskRecord)
                .where(
                    WorkforceTaskRecord.id == claim.task.plan.task_id,
                    WorkforceTaskRecord.lease_token == claim.lease_token,
                    WorkforceTaskRecord.revision == claim.task.plan.revision,
                    WorkforceTaskRecord.lease_until > now,
                )
                .with_for_update()
            )
            if task is None:
                return
            row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
            assert row is not None
            if permanent or task.attempts >= 3:
                row.status = task.status = "failed"
                await put_outbox(
                    session,
                    task,
                    "failure",
                    failure_message(row),
                    now,
                )
            task.lease_token = None
            task.lease_until = now + timedelta(seconds=5)
