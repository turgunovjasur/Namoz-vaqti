"""AI role metadata, independent of account access profiles."""

from pydantic import BaseModel, ConfigDict, Field


class RoleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=32)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    instruction: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = ()
    system_role: bool = False
