from tests.acceptance.harness import AppHarness


async def test_daily_delivery_is_grouped_and_idempotent() -> None:
    harness = AppHarness()
    await harness.start(user_id=1, chat_id=10)
    await harness.start(user_id=2, chat_id=20)
    harness.clear_messages()

    first = await harness.run_daily_job("2026-08-26T21:00:00+05:00")
    second = await harness.run_daily_job("2026-08-26T21:00:00+05:00")

    assert first.sent == 2
    assert second.skipped == 2
    assert harness.provider_calls_for("Toshkent", "2026-08-27") == 1
    assert len(harness.messages_for(10)) == 1
    assert len(harness.messages_for(20)) == 1
