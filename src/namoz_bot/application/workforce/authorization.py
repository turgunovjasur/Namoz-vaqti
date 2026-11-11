"""Request-scoped trusted identity; services declare their business permission once."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

if TYPE_CHECKING:
    from namoz_bot.application.workforce.access import AccessService
from namoz_bot.domain.workforce.profiles import AccessDenied, PermissionSnapshot


@dataclass(frozen=True)
class AccessContext:
    access: AccessService
    user_id: int
    telegram_user_id: int
    role_id: str | None = None
    capability_id: str | None = None


_context: ContextVar[AccessContext | None] = ContextVar("workforce_access", default=None)
_permission: ContextVar[PermissionSnapshot | None] = ContextVar(
    "workforce_permission", default=None
)


@contextmanager
def access_context(
    access: AccessService,
    *,
    user_id: int,
    telegram_user_id: int,
    role_id: str | None = None,
    capability_id: str | None = None,
) -> Iterator[None]:
    token = _context.set(AccessContext(access, user_id, telegram_user_id, role_id, capability_id))
    try:
        yield
    finally:
        _context.reset(token)


def current_permission() -> PermissionSnapshot | None:
    return _permission.get()


@contextmanager
def selected_operation(role_id: str, capability_id: str) -> Iterator[None]:
    context = _context.get()
    token = (
        _context.set(
            AccessContext(
                context.access, context.user_id, context.telegram_user_id, role_id, capability_id
            )
        )
        if context
        else None
    )
    try:
        yield
    finally:
        if token is not None:
            _context.reset(token)


async def require_operation(
    capability_id: str, *, owner: int | None = None, telegram_id: int | None = None
) -> PermissionSnapshot | None:
    context = _context.get()
    if context is None:
        return None  # Standalone internal services; production boundaries always bind identity.
    if (owner is not None and owner != context.user_id) or (
        telegram_id is not None and telegram_id != context.telegram_user_id
    ):
        raise AccessDenied("Foreign account")
    selected = context.capability_id
    # A saved transaction's receipt includes its actual balance, not a separate balance request.
    helpers = {
        "finance.balance": {"finance.income", "finance.expense", "finance.undo", "finance.correct"},
        "preferences.region_view": {"prayer.set_region"},
        "preferences.offsets_view": {"prayer.set_offset", "prayer.reset_offsets"},
        "settings.open": {"settings.set_daily"},
        "nasihat.settings_view": {"nasihat.set_interval"},
        "reminder.list": {"reminder.delete"},
    }
    if selected is not None and selected != capability_id:
        if selected not in helpers.get(capability_id, set()):
            raise AccessDenied("Capability outside selected operation")
        capability_id = selected
    async with context.access.role_scope():
        roles = (
            (context.access.roles.get(context.role_id),)
            if context.role_id
            else context.access.roles.all()
        )
        for role in roles:
            if capability_id in role.capability_ids and await context.access.allowed(
                context.user_id, role.id, capability_id
            ):
                return await context.access.require(context.user_id, role.id, capability_id)
    raise AccessDenied("Bu imkoniyat siz uchun yoqilmagan. Administratorga murojaat qiling.")


P = ParamSpec("P")
R = TypeVar("R")


def authorized(
    capability: str | Callable[..., str], *, identity: str = "user_id"
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorate(method: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(method)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            values = cast(tuple[Any, ...], args)
            cap = capability(*args, **kwargs) if callable(capability) else capability
            candidate = values[1] if len(values) > 1 else kwargs.get(identity)
            owner = candidate if isinstance(candidate, int) else None
            grant = await require_operation(
                cap, **{"telegram_id" if identity == "telegram_user_id" else "owner": owner}
            )
            token = _permission.set(grant)
            try:
                return await method(*args, **kwargs)
            finally:
                _permission.reset(token)

        return wrapped

    return decorate
