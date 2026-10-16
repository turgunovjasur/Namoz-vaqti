"""AI role metadata, independent of account access profiles."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=32)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    instruction: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = ()
    system_role: bool = False
    common_rules: str = Field(default="", max_length=8000)
    enabled: bool = True
    revision: int = Field(default=0, ge=0)


class RoleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    common_rules: str | None = Field(default=None, max_length=8000)
    capability_ids: frozenset[str] = frozenset()
    model_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    enabled: bool = True
    expected_revision: int = Field(default=0, ge=0)
    expected_model_version: int = Field(default=0, ge=0)

    @field_validator("name", "description")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Bo‘sh nom yoki vazifa mumkin emas")
        return value.strip()


class RuleTemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    rules: str = Field(max_length=8000)
    revision: int = Field(ge=1)
