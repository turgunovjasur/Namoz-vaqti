"""Book quotation and automatic advice settings."""

from namoz_bot.application.capabilities.base import background, operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute

GUIDANCE = """
Kitobdan asl parcha va manbani xizmat oladi: nasihatni, iqtibosni yoki manbani o‘zing yozma.
Erkin diniy savol-javob yoki fatvo mavjud skillga kirmaydi. Interval hours butun0..168:
har6soat=6,o‘chirish=0; yoqish intervali aytilmasa savol ber. Joriy interval ko‘rish uchun view
interval.
""".strip()


def definitions() -> tuple[CapabilitySpec, ...]:
    return (
        operation(
            "nasihat.excerpt",
            "Kitobdan nasihat",
            "Kitobdan asl parcha va manbasini olish.",
            "nasihat",
            "religious_excerpt",
            "generate",
            guidance=GUIDANCE,
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
            guidance=GUIDANCE,
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
            guidance=GUIDANCE,
            correction_id="nasihat.set_interval",
        ),
        background(
            "nasihat.deliver", "Avtomatik nasihat", "Sozlangan vaqtda kitobdan nasihat yuborish."
        ),
    )
