"""Thin owner-bound profile cards; services revalidate every admin operation."""

import secrets
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.workforce.profiles import AccessDenied, ProfileConflict
from namoz_bot.presentation.admin_web.router import AdminWebEntry
from namoz_bot.presentation.handlers import HandlerServices
from namoz_bot.presentation.keyboards import PROFILE_LABEL, build_main_menu
from namoz_bot.presentation.profiles.keyboards import profile_keyboard
from namoz_bot.presentation.profiles.views import history_text, profile_text, role_text


class ProfileStates(StatesGroup):
    search = State()


class ProfileController:
    def __init__(self, service: ProfileService, web_entry: AdminWebEntry | None = None):
        self.service, self.web_entry = service, web_entry

    async def _actor(self, telegram_id: int, services: HandlerServices) -> int:
        user = await services.subscriptions.get(telegram_id)
        assert user.id is not None
        return user.id

    async def _card(
        self,
        message: Message,
        state: FSMContext,
        text: str,
        buttons: list[tuple[str, dict[str, Any]]],
        *,
        owner: int,
        card: dict[str, Any] | None = None,
    ) -> None:
        token = secrets.token_hex(6)
        await state.update_data(
            profile_ui={
                "token": token,
                "owner": owner,
                "actions": [a for _, a in buttons],
                "card": card or {},
            }
        )
        await message.answer(
            text, reply_markup=profile_keyboard(token, [b for b, _ in buttons]), parse_mode=None
        )

    async def open(
        self, message: Message, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        assert message.from_user is not None
        actor = await self._actor(message.from_user.id, handler_services)
        profile = await self.service.self_view(actor)
        await state.clear()
        await message.answer("👤 Profil", reply_markup=build_main_menu(), parse_mode=None)
        buttons: list[tuple[str, dict[str, Any]]] = (
            [
                ("👥 Foydalanuvchilar", {"type": "users", "after": 0}),
                ("🔎 ID bo‘yicha qidirish", {"type": "search"}),
                ("🕘 O‘zgarishlar tarixi", {"type": "history", "before": 0}),
                ("🎭 Rollar va modellar", {"type": "catalog"}),
            ]
            if profile.profile_type == "admin"
            else []
        )
        if profile.profile_type == "admin" and self.web_entry is not None:
            buttons.insert(0, ("🌐 Admin web panel", {"type": "web_panel"}))
        await self._card(
            message, state, profile_text(profile, self.service.roles), buttons, owner=actor
        )

    async def _assignment(
        self, message: Message, state: FSMContext, actor: int, card: dict[str, Any]
    ) -> None:
        role = self.service.roles.get(card["role"])
        buttons = [
            ("✅ Rol yoqilgan" if card["enabled"] else "⏸ Rol o‘chiq", {"type": "toggle_role"})
        ]
        buttons.extend(
            (
                f"{'✅' if c in card['caps'] else '⬜'} "
                f"{self.service.roles.capabilities.get(c).spec.name}",
                {"type": "toggle_cap", "cap": c},
            )
            for c in role.capability_ids
        )
        buttons.extend(
            [
                ("💾 Saqlash", {"type": "save"}),
                ("⬅️ Foydalanuvchi", {"type": "user", "user": card["user"]}),
            ]
        )
        await self._card(
            message, state, role_text(role.id, self.service.roles), buttons, owner=actor, card=card
        )

    async def callback(
        self, callback: CallbackQuery, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        if (
            not isinstance(callback.message, Message)
            or callback.message.chat.id != callback.from_user.id
        ):
            await callback.answer("Bu karta sizga tegishli emas.", show_alert=True)
            return
        actor = await self._actor(callback.from_user.id, handler_services)
        ui = (await state.get_data()).get("profile_ui", {})
        parts = (callback.data or "").split(":")
        if (
            len(parts) != 3
            or ui.get("token") != parts[1]
            or ui.get("owner") != actor
            or not parts[2].isdigit()
            or int(parts[2]) >= len(ui.get("actions", []))
        ):
            await callback.message.answer(
                "Bu karta eskirgan yoki sizga tegishli emas. Profilni qayta oching.",
                parse_mode=None,
            )
            await callback.answer()
            return
        action, card = ui["actions"][int(parts[2])], dict(ui.get("card", {}))
        kind = action["type"]
        message = callback.message
        try:
            # Even catalog/selection cards cannot be opened by forged user callbacks.
            if (await self.service.self_view(actor)).profile_type != "admin":
                raise AccessDenied("Bu boshqaruv administrator uchun.")
            if kind == "web_panel" and self.web_entry is not None:
                await self.web_entry.send(message, callback.from_user.id)
            elif kind == "users":
                page = await self.service.list_users(actor, after_id=action["after"], limit=10)
                buttons = [
                    (str(u.telegram_user_id), {"type": "user", "user": u.user_id})
                    for u in page.users
                ]
                if page.more:
                    buttons.append(
                        ("Keyingi ➡️", {"type": "users", "after": page.users[-1].user_id})
                    )
                await self._card(message, state, "Foydalanuvchini tanlang:", buttons, owner=actor)
            elif kind == "search":
                await state.set_state(ProfileStates.search)
                await state.update_data(profile_ui={})
                await message.answer(
                    "Foydalanuvchining raqamli Telegram ID sini yuboring.", parse_mode=None
                )
            elif kind == "history":
                history = await self.service.history(actor, before_id=action["before"])
                buttons = []
                if history.more:
                    buttons.append(
                        ("Keyingi ➡️", {"type": "history", "before": history.changes[-1].id})
                    )
                await self._card(
                    message, state, history_text(history, self.service.roles), buttons, owner=actor
                )
            elif kind == "user":
                target = await self.service.user_view(actor, action["user"])
                buttons = [
                    (r.name, {"type": "assignment", "user": target.user_id, "role": r.id})
                    for r in self.service.roles.all()
                    if not r.system_role
                ]
                await self._card(
                    message, state, profile_text(target, self.service.roles), buttons, owner=actor
                )
            elif kind == "assignment":
                target = await self.service.user_view(actor, action["user"])
                assigned = next((a for a in target.roles if a.role_id == action["role"]), None)
                card = {
                    "user": target.user_id,
                    "role": action["role"],
                    "enabled": assigned.enabled if assigned else False,
                    "caps": sorted(assigned.capability_ids) if assigned else [],
                    "revision": assigned.revision if assigned else 0,
                }
                await self._assignment(message, state, actor, card)
            elif kind in {"toggle_role", "toggle_cap"}:
                if kind == "toggle_role":
                    card["enabled"] = not card["enabled"]
                else:
                    caps = set(card["caps"])
                    caps.symmetric_difference_update({action["cap"]})
                    card["caps"] = sorted(caps)
                await self._assignment(message, state, actor, card)
            elif kind == "save":
                await self.service.set_grants(
                    actor_id=actor,
                    user_id=card["user"],
                    role_id=card["role"],
                    enabled=card["enabled"],
                    capability_ids=frozenset(card["caps"]),
                    expected_revision=card["revision"],
                )
                await state.update_data(profile_ui={})
                await message.answer("✅ Ruxsatlar saqlandi.", parse_mode=None)
            elif kind == "catalog":
                await self._card(
                    message,
                    state,
                    "Rolni tanlang:",
                    [(r.name, {"type": "role", "role": r.id}) for r in self.service.roles.all()],
                    owner=actor,
                )
            elif kind == "role":
                setting = await self.service.model(action["role"])
                await self._card(
                    message,
                    state,
                    role_text(action["role"], self.service.roles)
                    + f"\n\nGemini modeli: {setting.model_id}",
                    [("🤖 Modelni almashtirish", {"type": "models", "role": action["role"]})],
                    owner=actor,
                )
            elif kind == "models":
                setting = await self.service.model(action["role"])
                await self._card(
                    message,
                    state,
                    "Modelni tanlang. Saqlashdan oldin Gemini orqali tekshiriladi.",
                    [
                        (
                            m,
                            {
                                "type": "model",
                                "role": setting.role_id,
                                "model": m,
                                "version": setting.version,
                            },
                        )
                        for m in self.service.model_options(setting.role_id)
                    ],
                    owner=actor,
                )
            elif kind == "model":
                setting = await self.service.set_model(
                    actor_id=actor,
                    role_id=action["role"],
                    model_id=action["model"],
                    expected_version=action["version"],
                )
                await state.update_data(profile_ui={})
                await message.answer(
                    f"✅ Model saqlandi: {setting.model_id}. Yangi vazifalarda ishlaydi.",
                    parse_mode=None,
                )
        except (AccessDenied, ProfileConflict, ValueError, ExternalServiceError):
            await message.answer(
                "Amal bajarilmadi. Ruxsatlar yoki karta eskirgan, "
                "yoxud model tekshiruvi o‘tmadi. Profilni qayta oching.",
                parse_mode=None,
            )
        await callback.answer()

    async def search(
        self, message: Message, state: FSMContext, handler_services: HandlerServices
    ) -> None:
        assert message.from_user is not None and message.text is not None
        actor = await self._actor(message.from_user.id, handler_services)
        try:
            user = await self.service.find_user(actor, int(message.text))
        except (AccessDenied, ValueError):
            await state.clear()
            await message.answer(
                "Qidirish uchun admin huquqi va to‘g‘ri Telegram ID kerak.", parse_mode=None
            )
            return
        await state.set_state(None)
        buttons = (
            [(str(user.telegram_user_id), {"type": "user", "user": user.user_id})] if user else []
        )
        await self._card(
            message,
            state,
            "Qidiruv natijasi:" if user else "Foydalanuvchi topilmadi.",
            buttons,
            owner=actor,
        )


def build_profile_router(
    service: ProfileService, *, web_entry: AdminWebEntry | None = None
) -> Router:
    controller = ProfileController(service, web_entry)
    router = Router(name="profiles")
    router.message.filter(F.chat.type == "private")
    router.message.register(controller.open, F.text == PROFILE_LABEL)
    router.message.register(controller.open, Command("profile"))
    router.message.register(controller.search, ProfileStates.search, F.text.regexp(r"^\d{1,20}$"))
    router.callback_query.register(controller.callback, F.data.startswith("pf:"))
    return router
