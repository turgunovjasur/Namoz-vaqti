"""Role information comes from the same catalog used for execution."""

from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.workforce.profiles import ProfileView


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
