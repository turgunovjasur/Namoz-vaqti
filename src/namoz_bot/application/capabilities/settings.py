"""General settings and daily-delivery capability metadata."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute

GUIDANCE = """
Joriy kunlik jadval sozlamalarida view general yoki daily. Vaqtni HH:MM ajrat:
ertalab7=07:00,kechqurun7=19:00; kun qismi noaniq7da bo‘lsa taxmin qilma va savol ber. Yangi
vaqtni xizmat saqlaydi. Tugma yoki menyu talab qilma.
""".strip()


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "settings.open",
            "Umumiy sozlamalar",
            "Kunlik jadvalning joriy sozlamalarini ko‘rish.",
            "settings",
            "open",
            "read",
            guidance=GUIDANCE,
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
            guidance=GUIDANCE,
            correction_id="settings.set_daily",
        ),
        background(
            "settings.deliver_daily",
            "Kunlik jadval yuborish",
            "Kunlik namoz jadvalini avtomatik yuborish.",
        ),
    )
