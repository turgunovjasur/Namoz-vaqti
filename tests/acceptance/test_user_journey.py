from tests.acceptance.harness import AppHarness


async def test_public_user_journey() -> None:
    harness = AppHarness()

    await harness.start(user_id=7, chat_id=9)
    assert "📅 26.08.2026 (Toshkent shahri)" in harness.last_message(9)

    await harness.adjust_offset(
        user_id=7,
        chat_id=9,
        prayer="shom",
        action=1,
        repeat=4,
    )
    await harness.today_schedule(user_id=7, chat_id=9)
    assert "Shom — 19:07 (+4 daqiqa)" in harness.last_message(9)

    harness.restart_application()
    await harness.today_schedule(user_id=7, chat_id=9)
    assert "Shom — 19:07 (+4 daqiqa)" in harness.last_message(9)

    harness.clear_messages()
    first_daily = await harness.run_daily_job("2026-08-26T21:00:00+05:00")
    assert first_daily.sent == 1
    assert "Shom — 19:07 (+4 daqiqa)" in harness.last_message(9)

    await harness.select_region(user_id=7, chat_id=9, display_name="Samarqand shahri")
    assert "📅 26.08.2026 (Samarqand shahri)" in harness.last_message(9)
    assert "(+4 daqiqa)" not in harness.last_message(9)

    harness.clear_messages()
    second_daily = await harness.run_daily_job("2026-08-27T21:00:00+05:00")
    assert second_daily.sent == 1
    assert "📅 28.08.2026 (Samarqand shahri)" in harness.last_message(9)
    assert "(+4 daqiqa)" not in harness.last_message(9)
