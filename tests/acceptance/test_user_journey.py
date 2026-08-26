from tests.acceptance.harness import AppHarness


async def test_public_user_journey() -> None:
    harness = AppHarness()

    await harness.start(user_id=7, chat_id=9)

    assert "📅 Bugun — 26-avgust, Toshkent shahri" in harness.last_message(9)

    await harness.select_region(user_id=7, chat_id=9, display_name="Samarqand shahri")
    assert "📅 Bugun — 26-avgust, Samarqand shahri" in harness.last_message(9)

    await harness.run_daily_job("2026-08-26T21:00:00+05:00")
    assert "📅 Ertaga — 27-avgust, Samarqand shahri" in harness.last_message(9)
