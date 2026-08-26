import namoz_bot.presentation.keyboards as keyboards_module
from namoz_bot.presentation.keyboards import build_main_menu, build_region_keyboard


def test_region_group_keyboard_shows_fourteen_groups() -> None:
    builder = getattr(keyboards_module, "build_region_group_keyboard", None)

    assert builder is not None
    markup = builder()
    buttons = [button for row in markup.inline_keyboard for button in row]

    assert len(buttons) == 14
    assert buttons[0].text == "Toshkent shahri"
    assert buttons[0].callback_data == "region-group:toshkent-shahri"
    assert buttons[-1].text == "Qoraqalpog‘iston Respublikasi"


def test_main_menu_reflects_notification_state() -> None:
    enabled = build_main_menu(is_active=True)
    disabled = build_main_menu(is_active=False)

    enabled_labels = [button.text for row in enabled.keyboard for button in row]
    disabled_labels = [button.text for row in disabled.keyboard for button in row]
    assert "🔕 Xabarlarni o‘chirish" in enabled_labels
    assert "🔔 Xabarlarni yoqish" in disabled_labels


def test_region_keyboard_contains_only_selected_group_and_back_button() -> None:
    markup = build_region_keyboard(group_code="andijon-viloyati")
    buttons = [button for row in markup.inline_keyboard for button in row]
    labels = [button.text for button in buttons]

    assert len(buttons) == 18
    assert labels[0] == "Andijon viloyati"
    assert "Andijon shahri" in labels
    assert "Andijon tumani" in labels
    assert labels[-1] == "⬅️ Viloyatlar"
    assert buttons[-1].callback_data == "region-groups"


def test_region_callbacks_use_stable_region_codes() -> None:
    markup = build_region_keyboard(group_code="andijon-viloyati")
    callbacks = {
        button.text: button.callback_data for row in markup.inline_keyboard for button in row
    }

    assert callbacks["Andijon shahri"] == "region:Andijon"
    assert callbacks["Andijon tumani"] == "region:andijon"
