from namoz_bot.presentation.keyboards import build_main_menu, build_region_keyboard


def test_main_menu_reflects_notification_state() -> None:
    enabled = build_main_menu(is_active=True)
    disabled = build_main_menu(is_active=False)

    enabled_labels = [button.text for row in enabled.keyboard for button in row]
    disabled_labels = [button.text for row in disabled.keyboard for button in row]
    assert "🔕 Xabarlarni o‘chirish" in enabled_labels
    assert "🔔 Xabarlarni yoqish" in disabled_labels


def test_region_keyboard_contains_catalog_regions_and_next_page() -> None:
    markup = build_region_keyboard(page=0, page_size=10)
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "Oltiariq" in labels
    assert "Keyingi ▶️" in labels


def test_last_region_page_has_previous_without_next() -> None:
    markup = build_region_keyboard(page=100, page_size=10)
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "◀️ Oldingi" in labels
    assert "Keyingi ▶️" not in labels
