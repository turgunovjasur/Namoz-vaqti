"""Book quotation and automatic advice settings."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "nasihat.excerpt",
            "Kitobdan nasihat",
            "Kitobdan asl parcha va manbasini olish.",
            "nasihat",
            "religious_excerpt",
            "generate",
            routes=(
                LegacyRoute(domain="nasihat", action="religious_excerpt"),
                LegacyRoute(domain="prayer", action="religious_excerpt"),
            ),
        ),
        operation(
            "nasihat.settings_view",
            "Nasihat sozlamalari",
            "Joriy nasihat oralig‘ini ko‘rish.",
            "nasihat",
            "open_settings",
            "read",
            routes=(
                LegacyRoute(domain="nasihat", action="open_settings"),
                LegacyRoute(domain="nasihat", action="open_settings", view="interval"),
            ),
        ),
        operation(
            "nasihat.set_interval",
            "Nasihat oralig‘i",
            "Avtomatik nasihatni sozlash yoki o‘chirish.",
            "nasihat",
            "set_interval",
            "write",
            correction_id="nasihat.set_interval",
        ),
        background(
            "nasihat.deliver", "Avtomatik nasihat", "Sozlangan vaqtda kitobdan nasihat yuborish."
        ),
    )
