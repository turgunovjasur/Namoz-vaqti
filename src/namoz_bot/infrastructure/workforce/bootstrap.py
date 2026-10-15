"""Shared profile model configuration for Telegram and web entrypoints."""

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.config import Settings
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.ai.model_catalog import ModelCatalog
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository


def build_profile_service(
    settings: Settings, profiles: SqlAlchemyProfileRepository, transport: GeminiClient | None
) -> ProfileService:
    role_registry = profiles.roles
    base_role_model = settings.gemini_main_agent_model or settings.gemini_voice_model
    defaults = {r.id: base_role_model for r in role_registry.all()}
    defaults.update(
        {
            r: m
            for r, m in {
                "prayer": settings.gemini_prayer_agent_model,
                "nasihat": settings.gemini_nasihat_agent_model,
                "reminder": settings.gemini_reminder_agent_model,
                "accounting": settings.gemini_accounting_agent_model,
                "settings": settings.gemini_settings_agent_model,
            }.items()
            if m
        }
    )
    catalog = ModelCatalog(
        transport, tuple(dict.fromkeys((*settings.gemini_allowed_models, *defaults.values())))
    )
    return ProfileService(profiles, role_registry, catalog, default_models=defaults)
