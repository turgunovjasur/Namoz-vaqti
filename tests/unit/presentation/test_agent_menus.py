from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.presentation.agent_menu_context import action_labels, agent_label, agent_menu_scope
from namoz_bot.presentation.keyboards import build_main_menu


def test_dynamic_menu_uses_database_name_and_only_granted_actions():
    role = RoleDefinition(
        id="custom",
        name="Mening hisobchim",
        description="Hisob",
        instruction="Hisob",
        capability_ids=("finance.report", "finance.history"),
    )
    with agent_menu_scope((role,), build_capability_registry(), role.id):
        labels = [b.text for row in build_main_menu().keyboard for b in row]
        assert labels == ["💰 Mening hisobchim"]
        assert set(action_labels()) == {"📊 Oy hisoboti", "📒 Shu oy tarixi"}
    renamed = role.model_copy(update={"name": "Yangi nom"})
    with agent_menu_scope((renamed,), build_capability_registry(), renamed.id):
        assert agent_label(renamed) == "💰 Yangi nom"
