"""Database role names and granted skills for the current Telegram update."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from namoz_bot.application.capabilities.registry import CapabilityRegistry
from namoz_bot.domain.workforce.roles import RoleDefinition

ROLE_KEY = "agent_menu_role"

# These are UI adapters for skills, never a catalog of role IDs or names.
ACTION_LABELS = {
    "prayer.schedule": "📅 Bugungi jadval",
    "prayer.set_region": "📍 Hududni o‘zgartirish",
    "prayer.set_offset": "🕌 Masjidga moslash",
    "preferences.region_view": "📍 Hududni o‘zgartirish",
    "preferences.offsets_view": "🕌 Masjidga moslash",
    "settings.open": "⚙️ Sozlash",
    "settings.set_daily": "🕒 Kunlik jadval yuborish vaqti",
    "nasihat.excerpt": "📖 Diniy eslatma",
    "nasihat.settings_view": "⚙️ Nasihat intervali",
    "nasihat.set_interval": "⏱ Avtomatik nasihat oralig‘i",
    "reminder.create": "➕ Eslatma qo‘shish",
    "reminder.list": "📋 Eslatma ro‘yxati",
    "reminder.delete": "🗑 Eslatmani o‘chirish",
    "finance.income": "➕ Kirim yozish",
    "finance.expense": "\N{HEAVY MINUS SIGN} Xarajat yozish",
    "finance.balance": "💳 Umumiy balans",
    "finance.report": "📊 Oy hisoboti",
    "finance.history": "📒 Shu oy tarixi",
    "finance.undo": "↩️ Yozuvni bekor qilish",
}


@dataclass(frozen=True)
class MenuContext:
    roles: tuple[RoleDefinition, ...]
    capabilities: CapabilityRegistry
    selected: str | None
    qori_enabled: bool


_current: ContextVar[MenuContext | None] = ContextVar("agent_menu", default=None)


@contextmanager
def agent_menu_scope(
    roles: tuple[RoleDefinition, ...],
    capabilities: CapabilityRegistry,
    selected: str | None = None,
    *,
    qori_enabled: bool = False,
) -> Iterator[None]:
    token = _current.set(MenuContext(roles, capabilities, selected, qori_enabled))
    try:
        yield
    finally:
        _current.reset(token)


def agent_label(role: RoleDefinition) -> str:
    icons = {"prayer": "📅", "finance": "💰", "reminder": "🔔", "nasihat": "📖"}
    icon = next(
        (
            icon
            for prefix, icon in icons.items()
            if any(c.startswith(prefix + ".") for c in role.capability_ids)
        ),
        "🤖",
    )
    return f"{icon} {role.name}"


def menu_roles() -> tuple[RoleDefinition, ...] | None:
    context = _current.get()
    if context is None:
        return None
    priority = {"📅": 0, "🔔": 1, "💰": 2, "📖": 3}
    return tuple(
        sorted(context.roles, key=lambda r: (priority.get(agent_label(r).split()[0], 4), r.name))
    )


def show_qori() -> bool:
    context = _current.get()
    return context is not None and context.qori_enabled


def selected_role() -> RoleDefinition | None:
    context = _current.get()
    return next((r for r in context.roles if r.id == context.selected), None) if context else None


def menu_allows(capability: str) -> bool:
    context = _current.get()
    if context is None:
        return True
    roles = [r for r in context.roles if not context.selected or r.id == context.selected]
    return any(capability in r.capability_ids for r in roles)


def action_labels() -> dict[str, str]:
    context, role = _current.get(), selected_role()
    if context is None or role is None:
        return {}
    result: dict[str, str] = {}
    for cap in role.capability_ids:
        spec = context.capabilities.get(cap).spec
        if "conversation" in spec.entrypoints and not spec.requires_result:
            result.setdefault(ACTION_LABELS.get(cap, "▶️ " + spec.name), cap)
    if "reminder.list" in role.capability_ids:
        result["📅 Bugungi eslatmalar"] = "reminder.list"
    return result


def is_agent_navigation(text: str | None) -> bool:
    return bool(
        text
        and (
            text in action_labels()
            or any(text in {agent_label(r), r.name} for r in menu_roles() or ())
        )
    )
