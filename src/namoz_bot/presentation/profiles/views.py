"""Role information comes from the same catalog used for execution."""

from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.domain.workforce.profiles import AuditPage, ProfileView


def profile_text(profile: ProfileView, roles: RoleRegistry) -> str:
    lines = [f"👤 Profil · {profile.profile_type}", f"Telegram ID: {profile.telegram_user_id}"]
    active = [a for a in profile.roles if a.enabled]
    if not active:
        lines.append("Hozircha sizga rollar yoqilmagan.")
    for assignment in active:
        role = roles.get(assignment.role_id)
        lines.extend([f"\n{role.name}", role.description])
        capabilities = [
            roles.capabilities.get(c).spec
            for c in role.capability_ids
            if c in assignment.capability_ids
        ]
        lines.extend(f"• {c.name}: {c.description}" for c in capabilities)
        if not capabilities:
            lines.append("Bu rol ichida imkoniyatlar yoqilmagan.")
    return "\n".join(lines)


def role_text(role_id: str, roles: RoleRegistry) -> str:
    role = roles.get(role_id)
    return "\n".join(
        [
            role.name,
            role.description,
            "",
            *(
                f"• {roles.capabilities.get(c).spec.name}: "
                f"{roles.capabilities.get(c).spec.description}"
                for c in role.capability_ids
            ),
        ]
    )


def history_text(page: AuditPage, roles: RoleRegistry) -> str:
    lines = ["🕘 O‘zgarishlar tarixi"]
    for change in page.changes:
        role = roles.get(str(change.detail["role_id"]))
        text = (
            f"{change.created_at.astimezone(TASHKENT):%d.%m.%Y %H:%M} · "
            f"{change.actor_telegram_id}\n{role.name}"
        )
        if change.action == "set_grants":
            state = "yoqilgan" if change.detail.get("enabled") else "o‘chirilgan"
            text += f" → {change.target_telegram_id}: {state}"
            caps = change.detail.get("capability_ids", [])
            names = (
                [roles.capabilities.get(str(c)).spec.name for c in caps]
                if isinstance(caps, list)
                else []
            )
            text += "\nImkoniyatlar: " + (", ".join(names) or "yo‘q")
        elif change.action == "set_model":
            text += f" · model: {change.detail['model_id']}"
        lines.append(text)
    if not page.changes:
        lines.append("Hozircha o‘zgarishlar yo‘q.")
    return "\n\n".join(lines)
