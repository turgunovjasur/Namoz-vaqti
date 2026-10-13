"""Human-readable interpretations; execution identities stay in callback payloads."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from namoz_bot.domain.accounting import CATEGORY_LABELS, format_money
from namoz_bot.domain.agent_protocol import AgentDecision, AgentResult
from namoz_bot.presentation.keyboards import PRAYER_LABELS

ACTION_LABELS = {
    "schedule": "Namoz vaqtini ko‘rsatish",
    "religious_excerpt": "Kitobdan nasihat olish",
    "set_daily": "Kunlik jadval yuborish vaqtini o‘zgartirish",
    "set_interval": "Avtomatik nasihat oralig‘ini o‘zgartirish",
    "set_region": "Hududni o‘zgartirish",
    "set_offset": "Namoz vaqtini masjidga moslash",
    "reset_offsets": "Barcha namoz farqlarini nolga qaytarish",
    "create": "Eslatma yaratish",
    "delete": "Eslatmani o‘chirish",
    "list": "Eslatmalar ro‘yxatini ko‘rsatish",
    "income": "Kirimni yozish",
    "expense": "Xarajatni yozish",
    "balance": "Balansni ko‘rsatish",
    "report": "Oylik hisobotni ko‘rsatish",
    "history": "Yozuvlar tarixini ko‘rsatish",
    "undo": "Hisobdagi yozuvni bekor qilish",
    "open": "Sozlamalarni ko‘rsatish",
    "open_settings": "Sozlamalarni ko‘rsatish",
    "confirm": "Oldingi buyruqni tasdiqlash",
    "cancel": "Vazifani bekor qilish",
    "resume": "Oldingi vazifani davom ettirish",
    "help": "Yordam ko‘rsatish",
    "clarify": "Buyruqni aniqlashtirish",
}
FIELD_LABELS = {
    "text": "Matn yoki nom",
    "time": "Vaqt",
    "date": "Sana",
    "month": "Oy",
    "region": "Hudud",
    "minutes": "Daqiqa farqi",
    "hours": "Soat oralig‘i (0 — o‘chiq)",
    "description": "Izoh",
    "target_id": "Yozuv ID",
    "ordinal": "Ro‘yxatdagi tartib raqami",
}


def interpretation_text(output: AgentResult) -> str:
    decision = AgentDecision.model_validate(output.data["draft"])
    p = decision.parameters
    action = ACTION_LABELS.get(decision.action, "Buyruqni qayta ishlash")
    if decision.action == "undo" and not any(
        p.get(key) for key in ("target_id", "text", "ordinal")
    ):
        action = "Hisobdagi oxirgi yozuvni bekor qilish"
    lines = [f"Men buyruqni shunday tushundim: {action}."]
    if p.get("amount"):
        amount = (
            format_money(int(str(p["amount"])))
            if p.get("currency") != "OTHER"
            else f"{p['amount']} (so‘mdan boshqa valyuta)"
        )
        lines.append(f"Summa: {amount}")
    if p.get("prayer"):
        lines.append(f"Namoz: {PRAYER_LABELS[p['prayer']]}")  # type: ignore[index]
    if p.get("category"):
        lines.append(f"Kategoriya: {CATEGORY_LABELS[p['category']]}")  # type: ignore[index]
    for key, label in FIELD_LABELS.items():
        if p.get(key) is not None:
            lines.append(f"{label}: {p[key]}")
    if p.get("kind"):
        lines.append(
            "Takrorlanish: "
            + {"once": "bir marta", "daily": "har kuni", "weekly": "har hafta"}[str(p["kind"])]
        )
    if p.get("weekdays"):
        names = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        lines.append("Kunlar: " + ", ".join(names[int(str(day))] for day in p["weekdays"]))  # type: ignore[union-attr]
    if p.get("mode") == "add":
        lines.append("Farq mavjud qiymatga qo‘shiladi.")
    if p.get("page_step"):
        lines.append("Sahifa: " + ("keyingi" if p["page_step"] == "next" else "avvalgi"))
    elif decision.action in {"list", "history"}:
        lines.append(f"Sahifa: {int(str(p.get('page', 0))) + 1}")
    if p.get("today"):
        lines.append("Faqat bugungi eslatmalar.")
    if p.get("report_type"):
        report = {"summary": "umumiy", "income": "kirim", "expense": "xarajat", "salary": "oylik"}
        lines.append(f"Hisobot turi: {report[str(p['report_type'])]}")
    if p.get("view"):
        views = {
            "general": "umumiy",
            "daily": "kunlik jadval",
            "region": "hudud",
            "offsets": "masjidga moslash",
            "interval": "nasihat oralig‘i",
        }
        lines.append(f"Sozlama: {views[str(p['view'])]}")
    if decision.multiple_tasks:
        lines.append("Bir nechta vazifa aytilgan. Qaysi biri kerakligini aniqlashtiramiz.")
    if decision.clarification:
        lines.append(f"Aniqlashtirish kerak: {decision.clarification}")
    lines.extend([f"\nEshitilgan gap: {decision.transcript}", "\nTo‘g‘ri tushundimmi?"])
    return "\n".join(lines)


def approval_buttons(output: AgentResult) -> InlineKeyboardMarkup:
    prefix = "vr" if output.data.get("voice_review") else "ag"
    token = f"{prefix}:{output.operation_id}:{output.data['revision']}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"{token}:y"),
                InlineKeyboardButton(text="❌ Yo‘q", callback_data=f"{token}:n"),
            ]
        ]
    )
