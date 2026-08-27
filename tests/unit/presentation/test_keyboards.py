import namoz_bot.presentation.keyboards as keyboards_module
from namoz_bot.presentation.keyboards import (
    build_main_menu,
    build_offset_adjustment_keyboard,
    build_offsets_keyboard,
    build_region_keyboard,
)


def test_region_group_keyboard_shows_fourteen_groups() -> None:
    builder = getattr(keyboards_module, "build_region_group_keyboard", None)

    assert builder is not None
    markup = builder()
    buttons = [button for row in markup.inline_keyboard for button in row]

    assert len(buttons) == 14
    assert buttons[0].text == "Toshkent shahri"
    assert buttons[0].callback_data == "region-group:toshkent-shahri"
    assert buttons[-1].text == "Qoraqalpog‘iston Respublikasi"


def test_main_menu_has_no_notification_toggle() -> None:
    menu = build_main_menu()

    labels = [button.text for row in menu.keyboard for button in row]
    assert labels == [
        "📅 Bugungi jadval",
        "📍 Hududni o‘zgartirish",
        "⏱ Vaqtlarni sozlash",
        "ℹ️ Yordam",
    ]
    assert [len(row) for row in menu.keyboard] == [2, 2]
    assert [button.text for button in menu.keyboard[1]] == [
        "⏱ Vaqtlarni sozlash",
        "ℹ️ Yordam",
    ]


def test_offsets_keyboard_exposes_all_six_stable_prayer_callbacks() -> None:
    markup = build_offsets_keyboard()
    buttons = [button for row in markup.inline_keyboard for button in row]

    assert [button.callback_data for button in buttons] == [
        "offset:bomdod",
        "offset:quyosh",
        "offset:peshin",
        "offset:asr",
        "offset:shom",
        "offset:xufton",
    ]
    assert [button.text for button in buttons] == [
        "Bomdod",
        "Quyosh",
        "Peshin",
        "Asr",
        "Shom",
        "Xufton",
    ]
    assert [len(row) for row in markup.inline_keyboard] == [2, 2, 2]


def test_offset_adjustment_keyboard_has_minute_controls_and_calendar_button() -> None:
    markup = build_offset_adjustment_keyboard("shom", 4)
    buttons = [button for row in markup.inline_keyboard for button in row]

    assert [button.text for button in buttons[:3]] == ["\N{MINUS SIGN}1", "0", "+1"]
    assert [button.callback_data for button in buttons[:3]] == [
        "offset-change:shom:-1",
        "offset-change:shom:0",
        "offset-change:shom:1",
    ]
    assert buttons[-1].text == "📅 Taqvimga qaytish"
    assert buttons[-1].callback_data == "offset-schedule"


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
