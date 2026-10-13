"""Voice actions reuse authoritative services; every write uses the agent transaction."""

import re
from typing import cast

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.agent_adapters import AgentAdapters, result
from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.religious_reminders import ReligiousReminderService
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.domain.accounting import format_money
from namoz_bot.domain.agent_protocol import AgentRequest, AgentResult
from namoz_bot.domain.models import PRAYER_KEYS, PrayerKey
from namoz_bot.domain.regions import Region, get_region, list_regions
from namoz_bot.domain.reminders import parse_time


def region_candidates(query: str) -> list[Region]:
    def normalize(value: str) -> str:
        return re.sub(r"[^\w]", "", value.casefold())

    value = normalize(query)
    exact = [r for r in list_regions() if normalize(r.display_name) == value]
    if exact:
        return exact
    return [
        r
        for r in list_regions()
        if normalize(re.sub(r" (shahri|tumani|viloyati)$", "", r.display_name)) == value
    ]


class ConversationAdapters(AgentAdapters):
    def __init__(
        self,
        schedules: ScheduleService | None = None,
        religious_reminders: ReligiousReminderService | None = None,
        *,
        reminders: ReminderService,
        ledger: LedgerService,
    ) -> None:
        super().__init__(schedules, religious_reminders)
        self._reminders = reminders
        self._ledger = ledger

    async def prepare(self, request: AgentRequest) -> AgentResult:
        p, action = request.parameters, request.action
        if action in {"delete", "undo"}:
            return await self._prepare_target(request)
        if p.get("page_step"):
            view = request.context.last_view
            if view is None or (view.domain, view.action) != (request.domain, request.action):
                return result(
                    request,
                    "needs_input",
                    missing_fields=["page"],
                    question="Avval ro‘yxat yoki tarixni so‘rang, yoki sahifa raqamini ayting.",
                )
        fields = {
            "set_daily": ("time",),
            "set_interval": ("hours",),
            "set_region": ("region",),
            "set_offset": ("prayer", "minutes"),
        }
        if action in fields:
            missing = [f for f in fields[action] if p.get(f) is None]
            if missing:
                questions = {
                    "time": "Kunlik jadval qaysi vaqtda kelsin? Masalan, ertalab 7 da deng.",
                    "hours": "Nasihat har necha soatda kelsin? O‘chirish uchun o‘chir deng.",
                    "region": "Qaysi hudud? Shahar yoki tuman nomini aniq ayting.",
                    "prayer": "Qaysi namoz vaqtini moslay?",
                    "minutes": "Necha daqiqa farq bor? Oldin yoki keyin ekanini ham ayting.",
                }
                return result(
                    request,
                    "needs_input",
                    missing_fields=missing,
                    question=request.clarification or questions[missing[0]],
                )
            if action == "set_region":
                candidates = region_candidates(str(p["region"]))
                if len(candidates) != 1:
                    names = ", ".join(r.display_name for r in candidates)
                    return result(
                        request,
                        "needs_input",
                        missing_fields=["region"],
                        question=f"Qaysi hudud: {names}?"
                        if names
                        else "Hudud topilmadi. Shahar yoki tuman nomini aniq ayting.",
                    )
            if request.clarification:
                return result(
                    request,
                    "needs_input",
                    missing_fields=["clarification"],
                    question=request.clarification,
                )
            return result(request)
        if action == "reset_offsets":
            return result(request)
        if action in {"open", "open_settings"}:
            if request.clarification:
                return result(
                    request,
                    "needs_input",
                    missing_fields=["clarification"],
                    question=request.clarification,
                )
            return result(request)
        if action == "open_delete":
            return result(
                request,
                "needs_input",
                missing_fields=["target_id"],
                question="Qaysi eslatmani o‘chiray? Nomi yoki raqamini ayting.",
            )
        return await super().prepare(request)

    async def _prepare_target(self, request: AgentRequest) -> AgentResult:
        p, user = request.parameters, request.context.user_id
        target_id = p.get("target_id")
        if p.get("ordinal") is not None and target_id is None:
            view = request.context.last_view
            index = cast(int, p["ordinal"]) - 1
            if view is None or view.domain != request.domain or index >= len(view.ids):
                return result(
                    request,
                    "needs_input",
                    missing_fields=["target_id"],
                    question="Qaysi yozuv? Avval ro‘yxatni so‘rang yoki ID raqamini ayting.",
                )
            target_id = view.ids[index]
        if request.action == "delete":
            if target_id is not None:
                reminder = await self._reminders.get(user, cast(int, target_id))
                candidates = [reminder] if reminder else []
            elif p.get("text"):
                candidates = await self._reminders.repository.find_for_user(user, str(p["text"]))
            else:
                return result(
                    request,
                    "needs_input",
                    missing_fields=["target_id"],
                    question="Qaysi eslatmani o‘chiray? Nomi yoki ID raqamini ayting.",
                )
            options = [(r.id, r.spec.text) for r in candidates]
        else:
            if target_id is not None:
                entry = await self._ledger.get(user, cast(int, target_id))
                entries = [entry] if entry and not entry.cancelled else []
            else:
                entries = await self._ledger.find(user, str(p["text"]) if p.get("text") else None)
            options = [(e.id, f"{e.description}: {format_money(e.amount)}") for e in entries]
        if not options:
            return result(
                request,
                "unsupported",
                data={"text": "Sizga tegishli yozuv topilmadi yoki allaqachon bekor qilingan."},
            )
        if len(options) > 1:
            choices = "; ".join(f"#{value}: {label}" for value, label in options[:5])
            return result(
                request,
                "needs_input",
                missing_fields=["target_id"],
                question=f"Bir nechta yozuv bor. Qaysi ID raqam? {choices}"[:300],
            )
        identifier, label = options[0]
        return result(
            request,
            "needs_confirmation",
            data={
                "draft": {"target_id": identifier},
                "summary": f"#{identifier}: {label}",
            },
        )

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        p, action = request.parameters, request.action
        telegram = request.context.telegram_user_id
        if action == "delete":
            deleted = await transaction.reminders.delete(
                request.context.user_id, cast(int, p["target_id"])
            )
            return result(
                request,
                effect="committed" if deleted else "none",
                data={
                    "text": "✅ Eslatma o‘chirildi."
                    if deleted
                    else "Eslatma allaqachon o‘chirilgan."
                },
            )
        if action == "undo":
            cancelled = await transaction.ledger.cancel(
                request.context.user_id, cast(int, p["target_id"])
            )
            return result(
                request,
                effect="committed" if cancelled else "none",
                data={
                    "text": "✅ Yozuv bekor qilindi."
                    if cancelled
                    else "Yozuv allaqachon bekor qilingan.",
                    "balance": await transaction.ledger.balance(request.context.user_id),
                },
            )
        if action == "set_daily":
            daily_item = await transaction.daily_settings.set_time(
                telegram, parse_time(str(p["time"]))
            )
            return result(
                request,
                effect="committed",
                data={
                    "text": f"✅ Kunlik jadval har kuni {daily_item.at:%H:%M} da keladi. "
                    "Toshkent vaqti."
                },
            )
        if action == "set_interval":
            hours = int(cast(int, p["hours"]))
            interval_item = await transaction.religious_intervals.set_interval(telegram, hours)
            text = (
                f"✅ Nasihat har {interval_item.interval_hours:g} soatda keladi."
                if hours
                else "✅ Avtomatik nasihat o‘chirildi."
            )
            return result(request, effect="committed", data={"text": text})
        if action == "set_region":
            choices = region_candidates(str(p["region"]))
            if len(choices) != 1:
                raise ValueError("Hudud noaniq.")
            await transaction.subscriptions.change_region(telegram, choices[0].code)
            return result(
                request,
                effect="committed",
                data={
                    "text": f"✅ Hudud: {choices[0].display_name}. "
                    "Masjidga moslash farqlari 0 ga qaytarildi."
                },
            )
        if action == "set_offset":
            prayer = cast(PrayerKey, p["prayer"])
            offset_user = await transaction.subscriptions.set_offset(
                telegram, prayer, cast(int, p["minutes"]), relative=p.get("mode") == "add"
            )
            return result(
                request,
                effect="committed",
                data={
                    "text": f"✅ {prayer.capitalize()} farqi "
                    f"{offset_user.offsets.value_for(prayer):+d} daqiqa."
                },
            )
        if action == "reset_offsets":
            await transaction.subscriptions.reset_offsets(telegram)
            return result(
                request,
                effect="committed",
                data={"text": "✅ Barcha namoz farqlari 0 ga qaytarildi."},
            )
        if action in {"open", "open_settings"}:
            view = p.get("view", "interval" if request.domain == "nasihat" else "general")
            if view == "interval":
                interval_item = await transaction.religious_intervals.get(telegram)
                label = (
                    f"Har {interval_item.interval_hours:g} soatda"
                    if interval_item.interval_hours
                    else "O‘chirilgan"
                )
                text = f"Nasihat intervali: {label}.\n"
                text += "«Nasihat har 6 soatda kelsin» yoki «Avtomatik nasihatni o‘chir» deng."
            elif view == "region":
                user = await transaction.subscriptions.get(telegram)
                text = f"Hudud: {get_region(user.region_code).display_name}.\n"
                text += "«Hududni Samarqand shahriga o‘zgartir» deng."
            elif view == "offsets":
                user = await transaction.subscriptions.get(telegram)
                text = "Masjidga moslash:\n" + "\n".join(
                    f"{key.capitalize()}: {user.offsets.value_for(key):+d} daqiqa"
                    for key in PRAYER_KEYS
                )
                text += "\n«Shom vaqtini 4 daqiqa keyinga sur» deng."
            else:
                daily = await transaction.daily_settings.get(telegram)
                text = f"Sozlamalar: kunlik jadval {daily.at:%H:%M} da keladi.\n"
                text += "«Kunlik jadval ertalab 7 da kelsin» deng."
            return result(request, data={"text": text})
        return await super().execute(request, transaction)
