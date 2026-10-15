"""The same preference views are available to prayer and settings roles."""

from namoz_bot.application.capabilities.base import operation
from namoz_bot.domain.workforce.capabilities import CapabilitySpec, LegacyRoute


def definitions() -> tuple[CapabilitySpec, ...]:
    return tuple(
        operation(
            f"preferences.{view}_view",
            name,
            description,
            "settings",
            "open",
            "read",
            routes=(
                LegacyRoute(domain="prayer", action="open_settings", view=view),
                LegacyRoute(domain="settings", action="open", view=view),
            ),
        )
        for view, name, description in (
            ("region", "Joriy hudud", "Tanlangan shahar yoki tumanni ko‘rish."),
            ("offsets", "Joriy farqlar", "Masjidga moslash daqiqa farqlarini ko‘rish."),
        )
    )
