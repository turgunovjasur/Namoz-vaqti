"""Personal reminder creation, listing and recipient-isolated delivery."""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Protocol

from namoz_bot.application.ports import DeliveryAccess, MessageSender
from namoz_bot.application.workforce.authorization import authorized
from namoz_bot.domain.errors import RecipientBlockedError
from namoz_bot.domain.reminders import Reminder, ReminderDelivery, ReminderSpec
from namoz_bot.domain.workforce.corrections import ReminderCorrection

logger = logging.getLogger(__name__)


class ReminderRepository(Protocol):
    async def update(
        self, user_id: int, correction: ReminderCorrection, source_key: str, now: datetime
    ) -> Reminder: ...
    async def find_for_user(self, user_id: int, text: str) -> list[Reminder]: ...
    async def create(
        self, user_id: int, chat_id: int, spec: ReminderSpec, token: str, now: datetime
    ) -> Reminder: ...
    async def list_for_user(self, user_id: int, *, offset: int, limit: int) -> list[Reminder]: ...
    async def list_for_date(
        self, user_id: int, on_date: date, *, offset: int, limit: int
    ) -> list[Reminder]: ...
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
        self,
        repository: ReminderRepository,
        now: Callable[[], datetime] | None = None,
        *,
        access: DeliveryAccess | None = None,
    ) -> None:
        self.access = access
        self.repository = repository
        self.now = now or (lambda: datetime.now(UTC))

    @authorized("reminder.create")
    async def create(self, user_id: int, chat_id: int, spec: ReminderSpec, token: str) -> Reminder:
        return await self.repository.create(user_id, chat_id, spec, token, self.now())

    @authorized("reminder.list")
    async def page(
        self, user_id: int, page: int, *, on_date: date | None = None
    ) -> tuple[list[Reminder], bool]:
        if on_date is None:
            rows = await self.repository.list_for_user(user_id, offset=max(0, page) * 3, limit=4)
        else:
            rows = await self.repository.list_for_date(
                user_id, on_date, offset=max(0, page) * 3, limit=4
            )
        return rows[:3], len(rows) > 3

    @authorized("reminder.delete")
    async def get(self, user_id: int, reminder_id: int) -> Reminder | None:
        return await self.repository.get_for_user(user_id, reminder_id)

    @authorized("reminder.delete")
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
                    if self.access and not await self.access.allowed_any(
                        delivery.user_id, "reminder.deliver"
                    ):
                        await self.repository.finish(delivery, "skipped", "permission_disabled")
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

    @authorized("reminder.update")
    async def update(
        self, user_id: int, correction: ReminderCorrection, source_key: str
    ) -> Reminder:
        return await self.repository.update(user_id, correction, source_key, self.now())
