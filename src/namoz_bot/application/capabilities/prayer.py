"""Prayer schedule and location-adjustment capability catalog."""

from namoz_bot.application.capabilities.base import operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec


def definitions() -> tuple[CapabilitySpec, ...]:
    return tuple(
        operation(
            f"prayer.{action}",
            name,
            description,
            "prayer",
            action,
            effect,
            correction_id=f"prayer.{action}" if action in {"set_region", "set_offset"} else None,
        )
        for action, name, description, effect in (
            ("schedule", "Namoz jadvali", "Tanlangan hudud uchun namoz vaqtlarini olish.", "read"),
            ("set_region", "Hududni o‘zgartirish", "Shahar yoki tumanni tanlash.", "write"),
            ("set_offset", "Masjidga moslash", "Namoz vaqtiga daqiqa farqini sozlash.", "write"),
            (
                "reset_offsets",
                "Farqlarni nolga qaytarish",
                "Barcha namoz farqlarini nolga qaytarish.",
                "write",
            ),
        )
    )
