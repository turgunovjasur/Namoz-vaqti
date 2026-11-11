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
    # Older deployments may have per-domain environment defaults. These are
    # fallbacks only; persisted admin model choices always take precedence.
    defaults = {"assistant": base_role_model}
    for field in type(settings).model_fields:
        if field.startswith("gemini_") and field.endswith("_agent_model"):
            value = getattr(settings, field)
            if value:
                defaults[field.removeprefix("gemini_").removesuffix("_agent_model")] = value
    catalog = ModelCatalog(
        transport, tuple(dict.fromkeys((*settings.gemini_allowed_models, *defaults.values())))
    )
    return ProfileService(profiles, role_registry, catalog, default_models=defaults)
