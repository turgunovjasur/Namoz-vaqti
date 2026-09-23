"""Personal reminder creation, listing and recipient-isolated delivery."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from namoz_bot.application.ports import MessageSender
from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.reminders import Reminder, ReminderDelivery, ReminderSpec

logger = logging.getLogger(__name__)


class ReminderRepository(Protocol):
    async def create(
        self, user_id: int, chat_id: int, spec: ReminderSpec, token: str, now: datetime
    ) -> Reminder: ...
    async def list_for_user(self, user_id: int, *, offset: int, limit: int) -> list[Reminder]: ...
    async def get_for_user(self, user_id: int, reminder_id: int) -> Reminder | None: ...
    async def delete_for_user(self, user_id: int, reminder_id: int) -> bool: ...
    async def can_send(self, delivery: ReminderDelivery) -> bool: ...
    async def claim_due(self, now: datetime, *, limit: int) -> list[ReminderDelivery]: ...
    async def finish(
        self, delivery: ReminderDelivery, status: str, error: str | None = None
    ) -> None: ...
    async def pause_user(self, user_id: int) -> None: ...


class ReminderService:
    def __init__(
        self, repository: ReminderRepository, now: Callable[[], datetime] | None = None
    ) -> None:
        self.repository = repository
        self.now = now or (lambda: datetime.now(UTC))

    async def create(self, user_id: int, chat_id: int, spec: ReminderSpec, token: str) -> Reminder:
        return await self.repository.create(user_id, chat_id, spec, token, self.now())

    async def page(self, user_id: int, page: int) -> tuple[list[Reminder], bool]:
        rows = await self.repository.list_for_user(user_id, offset=max(0, page) * 3, limit=4)
        return rows[:3], len(rows) > 3

    async def get(self, user_id: int, reminder_id: int) -> Reminder | None:
        return await self.repository.get_for_user(user_id, reminder_id)

    async def delete(self, user_id: int, reminder_id: int) -> bool:
        return await self.repository.delete_for_user(user_id, reminder_id)

    async def send_due(self, sender: MessageSender) -> None:
        now = self.now()
        paused: set[int] = set()
        while deliveries := await self.repository.claim_due(now, limit=50):
            for delivery in deliveries:
                try:
                    # Deletion may happen after claiming a batch but before sending.
                    if not await self.repository.can_send(delivery):
                        continue
                    if delivery.user_id in paused:
                        await self.repository.finish(delivery, "failed", "recipient_blocked")
                        continue
                    try:
                        await sender.send(delivery.chat_id, f"🔔 Eslatma\n\n{delivery.text}")
                    except RecipientBlockedError:
                        paused.add(delivery.user_id)
                        await self.repository.pause_user(delivery.user_id)
                        await self.repository.finish(delivery, "failed", "recipient_blocked")
                    except Exception as exc:
                        await self.repository.finish(delivery, "failed", type(exc).__name__)
                        logger.warning(
                            "reminder_delivery_failed id=%s error=%s",
                            delivery.id,
                            type(exc).__name__,
                        )
                    else:
                        await self.repository.finish(delivery, "sent")
                except Exception:
                    logger.exception("reminder_persistence_failed id=%s", delivery.id)
