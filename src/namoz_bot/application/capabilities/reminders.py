"""Reminder metadata shared by profiles, routing and execution."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute

GUIDANCE = """
Shaxsiy eslatma matni va vaqtini ajrat. kind once/daily/weekly; dushanba=0,yakshanba=6. Har
kuni=daily, har juma=weekly; takrorsiz juma=yaqin kelajakdagi sana,once. Nisbiy sana/vaqt
current_time orqali. Daily/weekly uchun date bo‘sh. Once uchun weekdays bo‘sh.
Ertalab9=09:00,kechqurun8=20:00; kun qismi noaniq sakkizda bo‘lsa vaqtni taxmin qilmay savol
ber. O‘tgan sanani ertaga surma. Followupda oldingi matn/sana/takrorni saqla. IDni to‘qima;
ochiq ID=target_id, nom=text, ikkinchisi=ordinal2. Sahifa0dan, keyingi=page_step next,
oldingi=previous. today=true faqat bugungi ro‘yxat so‘ralsa.
""".strip()


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "reminder.update",
            "Eslatmani tahrirlash",
            "Asl eslatma matni yoki vaqtini tasdiqlab yangilash.",
            "reminder",
            "update",
            "write",
            guidance=GUIDANCE,
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
            guidance=GUIDANCE,
            correction_id="reminder.update",
        ),
        operation(
            "reminder.list",
            "Eslatmalar ro‘yxati",
            "Shaxsiy eslatmalarni ko‘rish.",
            "reminder",
            "list",
            "read",
            guidance=GUIDANCE,
        ),
        operation(
            "reminder.delete",
            "Eslatmani o‘chirish",
            "Shaxsiy eslatmani tasdiqlab o‘chirish.",
            "reminder",
            "delete",
            "write",
            guidance=GUIDANCE,
            routes=(
                LegacyRoute(domain="reminder", action="delete"),
                LegacyRoute(domain="reminder", action="open_delete"),
            ),
        ),
        background(
            "reminder.deliver", "Eslatma yuborish", "Vaqti kelgan shaxsiy eslatmalarni yuborish."
        ),
    )
