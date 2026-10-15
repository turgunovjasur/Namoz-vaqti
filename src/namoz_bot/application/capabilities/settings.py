"""General settings and daily-delivery capability metadata."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "settings.open",
            "Umumiy sozlamalar",
            "Kunlik jadvalning joriy sozlamalarini ko‘rish.",
            "settings",
            "open",
            "read",
            routes=tuple(
                LegacyRoute(domain="settings", action="open", view=view)
                for view in (None, "general", "daily")
            ),
        ),
        operation(
            "settings.set_daily",
            "Kunlik jadval vaqti",
            "Kunlik namoz jadvali yuborish vaqtini o‘zgartirish.",
            "settings",
            "set_daily",
            "write",
            correction_id="settings.set_daily",
        ),
        background(
            "settings.deliver_daily",
            "Kunlik jadval yuborish",
            "Kunlik namoz jadvalini avtomatik yuborish.",
        ),
    )
