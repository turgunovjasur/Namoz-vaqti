"""Action adapters reuse authoritative schedules, ledger and reminder services."""

import json
from dataclasses import asdict
from datetime import date
from typing import cast

from pydantic import JsonValue

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.religious_reminders import ReligiousReminderService
from namoz_bot.application.schedules import ScheduleService, apply_offsets, format_schedule
from namoz_bot.domain.accounting import AccountingRequest
from namoz_bot.domain.agent_protocol import AgentRequest, AgentResult
from namoz_bot.domain.models import PrayerKey
from namoz_bot.domain.reminders import TASHKENT, ReminderSpec, parse_time

HELP_TEXT = (
    "Xabaringizni yozing yoki ovozli yuboring:\n"
    "🕌 «Bugun shom nechida?»\n"
    "🔔 «Ertaga ertalab 9 da uchrashuvni eslat»\n"
    "💰 «120 mingga kiyim oldim»\n"
    "📊 «Shu oy qancha sarfladim?»\n\n"
    "Tugallanmagan vazifa uchun «Davom et» yoki «Bekor qil» deb yozing."
)


def result(request: AgentRequest, status: str = "done", **kwargs: object) -> AgentResult:
    return AgentResult.model_validate(
        {
            "request_id": request.request_id,
            "operation_id": request.operation_id,
            "domain": request.domain,
            "action": request.action,
            "status": status,
            **kwargs,
        }
    )


def json_data(value: object) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(json.dumps(value, default=str)))


def reminder_spec(request: AgentRequest) -> ReminderSpec:
    p = request.parameters
    return ReminderSpec(
        str(p["text"]),
        parse_time(str(p["time"])),
        str(p["kind"]),
        date.fromisoformat(str(p["date"])) if p.get("date") else None,
        tuple(cast(list[int], p.get("weekdays", []))),
    )


def accounting_request(request: AgentRequest) -> AccountingRequest:
    p = request.parameters
    return AccountingRequest.model_validate(
        {
            "transcript": request.transcript,
            "intent": request.action,
            "amount": p.get("amount"),
            "currency": p.get("currency") or "UZS",
            "category": p.get("category"),
            "description": p.get("description"),
            "month": p.get("month"),
            "date": p.get("date"),
            "report_type": p.get("report_type"),
            "clarification": None,
        }
    )


class AgentAdapters:
    def __init__(
        self,
        schedules: ScheduleService | None = None,
        religious_reminders: ReligiousReminderService | None = None,
    ) -> None:
        self._schedules = schedules
        self._religious = religious_reminders

    async def prepare(self, request: AgentRequest) -> AgentResult:
        p = request.parameters
        if request.domain == "reminder" and request.action == "create":
            missing = [field for field in ("text", "time", "kind") if not p.get(field)]
            if p.get("kind") == "once" and not p.get("date"):
                missing.append("date")
            if p.get("kind") == "weekly" and not p.get("weekdays"):
                missing.append("weekdays")
            if missing:
                questions = {
                    "text": "Nimani eslatay?",
                    "time": "Qaysi vaqtda? Masalan, 09:00.",
                    "kind": "Qaysi kuni yoki qanday takrorlansin?",
                    "date": "Qaysi sanada eslatay?",
                    "weekdays": "Qaysi hafta kunlarida?",
                }
                return result(
                    request,
                    "needs_input",
                    missing_fields=missing,
                    question=request.clarification or questions[missing[0]],
                )
            try:
                reminder_spec(request).next_after(request.context.message_time)
            except ValueError as exc:
                return result(
                    request, "needs_input", missing_fields=["date", "time"], question=str(exc)
                )
            return result(request, "needs_confirmation", data={"draft": p})
        if request.domain == "accounting" and request.action in {"income", "expense"}:
            if p.get("currency") == "OTHER":
                return result(
                    request, "unsupported", data={"text": "Hozircha faqat so‘m (UZS) qo‘llanadi."}
                )
            missing = [field for field in ("amount", "category", "description") if not p.get(field)]
            if missing:
                return result(
                    request,
                    "needs_input",
                    missing_fields=missing,
                    question=request.clarification
                    or (
                        "Summa qancha so‘m?"
                        if missing[0] == "amount"
                        else "Bu kirim yoki xarajat nima uchun bo‘lgan?"
                    ),
                )
            try:
                accounting_request(request).transaction(request.context.message_time)
            except ValueError as exc:
                return result(request, "unsupported", data={"text": str(exc)})
        if request.clarification and request.domain not in {"assistant"}:
            return result(
                request,
                "needs_input",
                missing_fields=["clarification"],
                question=request.clarification,
            )
        if request.domain == "prayer" and request.action == "schedule":
            if self._schedules is None:
                return result(request, "error", error_code="schedule_unavailable", retryable=True)
            today = request.context.message_time.astimezone(TASHKENT).date()
            target = date.fromisoformat(str(p["date"])) if p.get("date") else today
            schedule = await self._schedules.get_schedule(request.context.region_code, target)
            adjusted = apply_offsets(schedule, request.context.offsets)
            prayer = p.get("prayer")
            data: dict[str, JsonValue] = {
                "text": format_schedule(schedule, request.context.offsets),
                "date": target.isoformat(),
                "region": schedule.region_name,
            }
            if prayer:
                data.update(prayer=prayer, time=getattr(adjusted.times, cast(PrayerKey, prayer)))
            return result(request, data=data)
        if request.domain == "prayer" and request.action == "religious_excerpt":
            if self._religious is None:
                return result(request, "unsupported", data={"text": "Nasihat xizmati sozlanmagan."})
            passage = await self._religious.generate(request.context.telegram_user_id)
            return result(request, data={"text": passage})
        if request.domain == "settings" or request.action == "open_settings":
            return result(request, data={"view": p.get("view", "general")})
        if request.action == "open_delete":
            return result(request, data={"view": "reminder_delete"})
        if request.domain == "assistant":
            return result(
                request,
                "unsupported" if request.action == "clarify" else "done",
                data={"text": request.clarification or HELP_TEXT},
            )
        return result(request)

    async def execute(self, request: AgentRequest, transaction: AgentTransaction) -> AgentResult:
        user = request.context.user_id
        p = request.parameters
        if request.domain == "accounting":
            ledger = transaction.ledger
            if request.action in {"income", "expense"}:
                entry = await ledger.record(
                    user,
                    accounting_request(request),
                    f"agent:{request.operation_id}",
                    request.context.message_time,
                )
                return result(
                    request,
                    effect="committed",
                    data=json_data(
                        {
                            **asdict(entry),
                            "entry_id": entry.id,
                            "balance": await ledger.balance(user),
                        }
                    ),
                )
            if request.action == "balance":
                return result(request, data={"balance": await ledger.balance(user)})
            if request.action == "report":
                period = accounting_request(request).period(request.context.message_time)
                summary = await ledger.summary(user, period)
                return result(
                    request,
                    data=json_data(
                        {
                            **asdict(summary),
                            "closing_balance": summary.closing_balance,
                            "report_type": p.get("report_type", "summary"),
                        }
                    ),
                )
            if request.action == "history":
                page = int(str(p.get("page", 0)))
                entries, more = await ledger.history(user, page)
                return result(
                    request,
                    data=json_data(
                        {
                            "entries": [asdict(entry) for entry in entries],
                            "page": page,
                            "more": more,
                        }
                    ),
                )
        if request.domain == "reminder":
            if request.action == "create":
                reminder = await transaction.reminders.create(
                    user,
                    request.context.chat_id,
                    reminder_spec(request),
                    request.operation_id,
                )
                return result(
                    request,
                    effect="committed",
                    data={
                        "reminder_id": reminder.id,
                        "text": reminder.spec.text,
                        "time": reminder.spec.at.strftime("%H:%M"),
                        "schedule": reminder.spec.schedule_label(),
                    },
                )
            if request.action == "list":
                target = (
                    request.context.message_time.astimezone(TASHKENT).date()
                    if p.get("today")
                    else None
                )
                reminders, more = await transaction.reminders.page(
                    user, int(str(p.get("page", 0))), on_date=target
                )
                rows: list[dict[str, object]] = [
                    {
                        "id": entry.id,
                        "text": entry.spec.text,
                        "time": entry.spec.at.strftime("%H:%M"),
                        "schedule": entry.spec.schedule_label(),
                    }
                    for entry in reminders
                ]
                payload: dict[str, object] = {
                    "entries": rows,
                    "more": more,
                    "page": p.get("page", 0),
                    "today": p.get("today", False),
                }
                return result(
                    request,
                    data=json_data(payload),
                )
        return result(request)
