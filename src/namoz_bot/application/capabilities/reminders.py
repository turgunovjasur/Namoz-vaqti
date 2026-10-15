"""Reminder metadata shared by profiles, routing and execution."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "reminder.update",
            "Eslatmani tahrirlash",
            "Asl eslatma matni yoki vaqtini tasdiqlab yangilash.",
            "reminder",
            "update",
            "write",
            requires_result=True,
            correction_id="reminder.update",
        ),
        operation(
            "reminder.create",
            "Eslatma yaratish",
            "Shaxsiy eslatma yaratish.",
            "reminder",
            "create",
            "write",
            correction_id="reminder.update",
        ),
        operation(
            "reminder.list",
            "Eslatmalar ro‘yxati",
            "Shaxsiy eslatmalarni ko‘rish.",
            "reminder",
            "list",
            "read",
        ),
        operation(
            "reminder.delete",
            "Eslatmani o‘chirish",
            "Shaxsiy eslatmani tasdiqlab o‘chirish.",
            "reminder",
            "delete",
            "write",
            routes=(
                LegacyRoute(domain="reminder", action="delete"),
                LegacyRoute(domain="reminder", action="open_delete"),
            ),
        ),
        background(
            "reminder.deliver", "Eslatma yuborish", "Vaqti kelgan shaxsiy eslatmalarni yuborish."
        ),
    )
