"""Plugin dependencies have one process-owned lifecycle; no client secrets enter prompts."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class SkillDependencies:
    http: httpx.AsyncClient | None = None
