"""A reusable operation's authoritative schema and legacy routes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from namoz_bot.domain.agent_protocol import AgentRequest, AgentResult, Domain


class LegacyRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    domain: Domain
    action: str
    view: str | None = None

    def matches(self, request: AgentRequest) -> bool:
        return (self.domain, self.action, self.view) == (
            request.domain,
            request.action,
            request.parameters.get("view"),
        )


class CapabilitySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    parameters_model: type[BaseModel]
    result_model: type[BaseModel] = AgentResult
    effect: Literal["read", "write", "generate"]
    entrypoints: tuple[Literal["conversation", "background"], ...] = ("conversation",)
    routes: tuple[LegacyRoute, ...] = ()

    def validate_parameters(self, parameters: dict[str, JsonValue]) -> dict[str, JsonValue]:
        checked = self.parameters_model.model_validate(parameters).model_dump(
            mode="json", exclude_unset=True
        )
        views = {route.view for route in self.routes if route.view is not None}
        if views:
            if len(views) == 1:
                checked.setdefault("view", next(iter(views)))
            if checked.get("view") is not None and checked["view"] not in views:
                raise ValueError("View is outside capability scope")
        return checked


class CapabilitySelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    role_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=32)
    capability_id: str = Field(max_length=64)
    question: str | None = Field(default=None, max_length=500)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
