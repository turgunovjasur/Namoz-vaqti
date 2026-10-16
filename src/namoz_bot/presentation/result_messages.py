"""Canonical service-result rendering shared by voice, menus and workforce."""

from datetime import date
from typing import cast

from pydantic import JsonValue

from namoz_bot.application.capabilities.registry import (
    CapabilityRegistry,
    build_capability_registry,
)
from namoz_bot.domain.accounting import CATEGORY_LABELS, format_money
from namoz_bot.domain.agent_protocol import AgentDecision, AgentResult
from namoz_bot.domain.models import PrayerKey
from namoz_bot.domain.reminders import ReminderSpec, parse_time
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.tasks import TaskPlan
from namoz_bot.presentation.keyboards import PRAYER_LABELS

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
    try:
        action = build_capability_registry().for_request(decision).spec.name
    except ValueError:
        action = {
            "confirm": "Oldingi buyruqni tasdiqlash",
            "cancel": "Vazifani bekor qilish",
            "resume": "Oldingi vazifani davom ettirish",
            "help": "Yordam ko‘rsatish",
            "clarify": "Buyruqni aniqlashtirish",
        }.get(decision.action, "Buyruqni qayta ishlash")
    return _interpretation(decision, action)


def render_interpretation(
    transcript: str, selection: CapabilitySelection, registry: CapabilityRegistry
) -> str:
    spec = registry.get(selection.capability_id).spec
    parameters = spec.validate_parameters(selection.parameters)
    if not spec.routes:
        lines = [f"Men buyruqni shunday tushundim: {spec.name}."]
        fields = spec.parameters_model.model_fields
        lines.extend(f"{fields[key].title or key}: {value}" for key, value in parameters.items())
        return "\n".join([*lines, f"\nEshitilgan gap: {transcript}", "\nTo‘g‘ri tushundimmi?"])
    route = spec.routes[0]
    decision = AgentDecision(
        domain=route.domain, action=route.action, parameters=parameters, transcript=transcript
    )
    return _interpretation(decision, spec.name)


def _interpretation(decision: AgentDecision, action: str) -> str:
    p = decision.parameters
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


VOICE_HELP = (
    "Ovozli xabar yuboring — kerakli bo‘limni o‘zim aniqlayman. Javoblar matnda keladi.\n\n"
    "🕌 «Bugun shom nechida?»\n"
    "📍 «Hududni Samarqand shahriga o‘zgartir»\n"
    "🕌 «Shom vaqtini 4 daqiqa keyinga sur»\n"
    "📖 «Kitobdan nasihat ber»\n"
    "📖 «Nasihat har 6 soatda kelsin» yoki «Avtomatik nasihatni o‘chir»\n"
    "🔔 «Ertaga ertalab 9 da uchrashuvni eslat»\n"
    "🔔 «Eslatmalarimni ko‘rsat», «Kitob eslatmasini o‘chir»\n"
    "💰 «120 mingga kiyim oldim», «Balansim qancha?»\n"
    "📊 «Shu oy qancha sarfladim?», «Yozuvlar tarixini ko‘rsat»\n"
    "↩️ «Oxirgi yozuvni bekor qil»\n"
    "⚙️ «Kunlik jadval ertalab 7 da kelsin»\n\n"
    "Ovozdan nima tushunganimni ko‘rsataman. "
    "To‘g‘ri bo‘lsa «✅ Ha», aks holda «❌ Yo‘q»ni bosing.\n"
    "Menyu va matnli buyruqlar ham ishlaydi. Vaqtlar Toshkent vaqti bo‘yicha."
)


def render_result(output: AgentResult, *, legacy: bool = False) -> str:
    if output.domain == "assistant" and output.action == "skill_result":
        return str(output.data["text"])
    data = output.data
    if data.get("voice_review"):
        return interpretation_text(output)
    if output.status == "needs_input":
        return output.question or "Xabarni aniqlashtiring."
    if output.status == "needs_confirmation":
        if output.action == "create":
            draft = cast(dict[str, JsonValue], data["draft"])
            text = f"📝 {draft['text']}\n🕒 {draft['time']} · Toshkent\n"
            schedule = ReminderSpec(
                str(draft["text"]),
                parse_time(str(draft["time"])),
                str(draft["kind"]),
                date.fromisoformat(str(draft["date"])) if draft.get("date") else None,
                tuple(cast(list[int], draft.get("weekdays", []))),
            ).schedule_label()
            text += f"📅 {schedule}\n\nEslatmani saqlashni tasdiqlaysizmi?"
        else:
            verb = "o‘chirishni" if output.action == "delete" else "bekor qilishni"
            text = f"{data.get('summary')}\n\nShu yozuvni {verb} tasdiqlaysizmi?"
        return text + "\n«Ha, tasdiqlayman» yoki «Bekor qil» deng."
    if output.status == "error":
        return {
            "no_active_task": "Tugallanmagan vazifa yo‘q. Yangi buyruqni ovoz bilan ayting.",
            "stale_operation": "Bu tasdiq eskirgan. «Davom et» deb joriy vazifani so‘rang.",
            "invalid_input": "Ma’lumotlar mos kelmadi. Aniqlashtirib qayta ayting.",
        }.get(
            output.error_code or "", "Xabarni qayta ishlay olmadim. Birozdan keyin qayta yuboring."
        )
    if output.status == "cancelled":
        return str(data.get("text") or "Vazifa yakunlangan yoki bekor qilingan.")
    if output.domain == "prayer" and data.get("prayer") and data.get("time"):
        return (
            f"🕌 {PRAYER_LABELS[cast(PrayerKey, data['prayer'])]}: {data['time']}\n"
            f"📍 {data['region']} · {data['date']}\nManba: namoz-vaqti.uz"
        )
    if (
        output.domain == "reminder"
        and output.action in {"create", "update"}
        and output.status == "done"
    ):
        return f"✅ Eslatma saqlandi.\n📝 {data['text']}\n🕒 {data['time']}\n📅 {data['schedule']}"
    if data.get("text"):
        return str(data["text"])
    if output.domain == "accounting":
        if output.action == "correct":
            return (
                f"✅ Yozuv tuzatildi: #{data['entry_id']}\n{data['description']} — "
                f"{format_money(int(str(data['amount'])))}\n"
                f"Balans: {format_money(int(str(data['balance'])))}"
            )
        if output.action in {"income", "expense"}:
            label = "Kirim" if output.action == "income" else ("Chiqim" if legacy else "Xarajat")
            if data.get("cancelled"):
                return (
                    f"↩️ #{data['entry_id']} yozuvi bekor qilingan.\n"
                    f"Balans: {format_money(int(str(data['balance'])))}"
                )
            return (
                f"✅ {label} {'qayd etildi' if legacy else 'saqlandi'}: #{data['entry_id']}\n"
                f"{data['description']} — "
                f"{format_money(int(str(data['amount'])))}\n"
                f"Balans: {format_money(int(str(data['balance'])))}"
            )
        if output.action == "balance":
            label = "Joriy balans" if legacy else "Balans"
            return f"💰 {label}: {format_money(int(str(data['balance'])))}"
        if output.action == "report":
            kind = data.get("report_type", "summary")
            parts = {"income": "Kirim", "expense": "Xarajat", "salary": "Oylik"}
            report_lines = [f"📊 Hisobot: {str(data['month'])[:7]}"]
            if data.get("category"):
                report_lines.append(
                    f"Kategoriya: {CATEGORY_LABELS[str(data['category'])]} "
                    "(faqat shu kategoriya jamlari)"
                )
            for field, label in parts.items():
                if kind == "summary" or kind == field:
                    report_lines.append(f"{label}: {format_money(int(str(data[field])))}")
            closing_balance = format_money(int(str(data["closing_balance"])))
            balance_label = (
                "Hisobning haqiqiy balansi" if data.get("category") else "Oy oxiridagi balans"
            )
            report_lines.append(f"{balance_label}: {closing_balance}")
            return "\n".join(report_lines)
    if output.action in {"list", "history"}:
        rows = cast(list[dict[str, JsonValue]], data.get("entries", []))
        lines = ["📋 Eslatmalar" if output.action == "list" else "📋 Yozuvlar tarixi"]
        for number, row in enumerate(rows, 1):
            detail = (
                f"{row['text']} · {row['time']} · {row['schedule']}"
                if output.action == "list"
                else f"{row['description']} · {format_money(int(str(row['amount'])))}"
                + (" · bekor qilingan" if row.get("cancelled") else "")
            )
            lines.append(f"{number}. #{row['id']}: {detail}")
        if not rows:
            lines.append("Hozircha yozuvlar yo‘q.")
        if data.get("more"):
            lines.append("Davomi uchun «Keyingi sahifa» deng.")
        return "\n\n".join(lines)
    return VOICE_HELP


def render_task_plan(plan: TaskPlan, registry: CapabilityRegistry) -> str:
    details = render_interpretation(plan.transcript, plan.selection, registry).splitlines()
    # Keep the common parameter rendering, with the workforce's requested conversation labels.
    details = [
        line
        for line in details[1:]
        if not line.startswith("Eshitilgan gap:") and line.strip() != "To‘g‘ri tushundimmi?"
    ]
    name = registry.get(plan.selection.capability_id).spec.name
    if plan.original_result and registry.get(plan.selection.capability_id).spec.requires_result:
        before = plan.original_result.data
        if plan.original_result.domain == "accounting":
            old = (
                f"#{before['entry_id']} · {before['description']} · "
                f"{format_money(int(str(before['amount'])))} · "
                f"{CATEGORY_LABELS[str(before['category'])]} · "
                f"{before.get('occurred_on') or str(before['period'])[:7]}"
            )
        else:
            old = (
                f"#{before['reminder_id']} · {before['text']} · "
                f"{before['time']} · {before['schedule']}"
            )
        details = [f"Oldin: {old}", "Keyin:", *details]
    return "\n".join(
        [
            f"Eshitdim: “{plan.transcript}”",
            f"Tushundim: {plan.role.name} — {name}.",
            *details,
            "To‘g‘ri tushundimmi?",
        ]
    )
