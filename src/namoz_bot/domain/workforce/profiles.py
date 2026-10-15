"""Account profiles are independent of AI roles and deny absent grants."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class AccessDenied(Exception):
    """A trusted actor lacks the requested permission."""


class ProfileConflict(Exception):
    """An old management card cannot overwrite newer settings."""


class RoleAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    role_id: str
    enabled: bool
    capability_ids: frozenset[str]
    revision: int


class GrantChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    role_id: str = Field(min_length=1, max_length=32)
    enabled: bool
    capability_ids: frozenset[str]
    expected_revision: int = Field(ge=0)


class ProfileView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: int
    telegram_user_id: int
    profile_type: Literal["admin", "user"]
    roles: tuple[RoleAssignment, ...] = ()
    display_name: str | None = None
    username: str | None = None
    is_active: bool = True


class PermissionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: int
    role_id: str
    capability_id: str
    assignment_revision: int


class RoleModelSetting(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    role_id: str
    model_id: str
    version: int = 0


class UserPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    users: tuple[ProfileView, ...]
    more: bool


class AdminChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int
    actor_telegram_id: int
    target_telegram_id: int | None
    action: str
    detail: dict[str, JsonValue]
    created_at: datetime


class AuditPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    changes: tuple[AdminChange, ...]
    more: bool


@dataclass(frozen=True)
class ModelOption:
    id: str
    name: str
