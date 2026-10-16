"""Composition root: application registries do not import infrastructure plugins."""

import httpx

from namoz_bot.application.capabilities.base import BusinessAdapters
from namoz_bot.application.capabilities.registry import (
    CapabilityRegistry,
    build_capability_registry,
)
from namoz_bot.infrastructure.skills.dependencies import SkillDependencies
from namoz_bot.infrastructure.skills.loader import load_skills


def build_runtime_capabilities(
    adapters: BusinessAdapters | None = None, *, http: httpx.AsyncClient | None = None
) -> CapabilityRegistry:
    return build_capability_registry(adapters, extra_skills=load_skills(SkillDependencies(http)))
