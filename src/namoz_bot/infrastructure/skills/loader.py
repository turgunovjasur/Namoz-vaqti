"""Deterministic discovery limited to the installed backend skill package."""

from importlib import import_module
from pkgutil import iter_modules

from namoz_bot.application.capabilities.base import Capability
from namoz_bot.infrastructure.skills import plugins
from namoz_bot.infrastructure.skills.dependencies import SkillDependencies


def load_skills(dependencies: SkillDependencies) -> tuple[Capability, ...]:
    skills: list[Capability] = []
    for item in sorted(iter_modules(plugins.__path__), key=lambda item: item.name):
        if item.name.startswith("_"):
            continue
        module = import_module(f"{plugins.__name__}.{item.name}")
        build = getattr(module, "build", None)
        if not callable(build):
            raise ValueError(f"Skill module {item.name} must export build(dependencies)")
        for skill in build(dependencies):
            if not isinstance(skill, Capability):
                raise TypeError(f"Invalid skill from {item.name}")
            skills.append(skill)
    return tuple(skills)
