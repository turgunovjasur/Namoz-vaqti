"""Strict admin API inputs; bounded before database work."""

from pydantic import BaseModel, ConfigDict, Field

from namoz_bot.domain.workforce.profiles import GrantChange


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TicketInput(Input):
    token: str = Field(min_length=1, max_length=128)


class AssignmentInput(Input):
    changes: list[GrantChange] = Field(min_length=1, max_length=20)


class ModelInput(Input):
    model_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    expected_version: int = Field(ge=0)
