"""Resolve displayed-page references without reading business records."""

from pydantic import JsonValue

from namoz_bot.domain.agent_protocol import AgentContext, AgentViewState


def page_parameters(
    parameters: dict[str, JsonValue], domain: str, action: str, view: AgentViewState | None
) -> dict[str, JsonValue]:
    values = dict(parameters)
    if values.get("page_step") and view and (view.domain, view.action) == (domain, action):
        direction = 1 if values["page_step"] == "next" else -1
        values["page"] = max(0, min(100000, view.page + direction))
        if action == "list":
            values["today"] = view.today
    return values


def ordinal_target(
    parameters: dict[str, JsonValue], domain: str, context: AgentContext
) -> int | None:
    ordinal = parameters.get("ordinal")
    view = context.target_choices or context.last_view
    if (
        isinstance(ordinal, int)
        and view
        and view.domain == domain
        and 1 <= ordinal <= len(view.ids)
    ):
        return view.ids[ordinal - 1]
    return None
