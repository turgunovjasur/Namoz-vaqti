"""V2 domain parsing derives instructions from skills, never from configured roles."""

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.menu_agents import MENU_DOMAINS
from namoz_bot.application.roles.base import LEGACY_OUTPUT_INSTRUCTION
from namoz_bot.domain.agent_protocol import Domain


def specialist_instructions() -> dict[Domain, str]:
    skills = build_capability_registry().all()
    return {
        domain: LEGACY_OUTPUT_INSTRUCTION
        + f"\nFaqat domain={domain} amallarini talqin qil.\n"
        + "\n".join(
            dict.fromkeys(
                f"Amal {route.action}: {skill.spec.description}\n{skill.spec.guidance}"
                for skill in skills
                for route in skill.spec.routes
                if route.domain == domain
            )
        )
        for domain in MENU_DOMAINS
    }
