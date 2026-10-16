"""Prayer schedule and location-adjustment capability catalog."""

from namoz_bot.application.capabilities.base import operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec

GUIDANCE = """
prayer: bomdod,quyosh,peshin,asr,shom,xufton. Jadval yoki bitta namozni ajrat. Nisbiy sana
current_time dan, YYYY-MM-DD. Namoz vaqtlarini hisoblama: xizmat jadvalni oladi. Hududda aynan
aytilgan shahar/tumanni ajrat, noaniq bo‘lsa savol ber. Farq uchun 4 daqiqa keyin=minutes4,mode
set; 4 daqiqa oldin=minutes-4,mode set; yana1qo‘sh=minutes1,mode add. Nol qilish=minutes0.
So‘ralmagan sozlamalarni o‘zgartirma.
""".strip()


def definitions() -> tuple[CapabilitySpec, ...]:
    return tuple(
        operation(
            f"prayer.{action}",
            name,
            description,
            "prayer",
            action,
            effect,
            guidance=GUIDANCE,
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
