# Per-User Prayer Time Offsets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let every Telegram user persist separate `−30…+30` minute adjustments for Bomdod, Quyosh, Peshin, Asr, Shom, and Xufton, apply them to every personal schedule, and reset all adjustments when the user changes region.

**Architecture:** Keep the provider schedule canonical and immutable. Add an immutable `PrayerOffsets` value object to the subscription aggregate, persist its six values on `users`, and apply offsets only in the shared schedule formatter after provider/cache lookup. Telegram handlers remain thin: they validate callback payloads, call `SubscriptionService`, and edit the existing inline message. Daily broadcasting caches one raw `PrayerSchedule` per region and formats a distinct message for each subscription.

**Tech Stack:** Python 3.12, aiogram 3, SQLAlchemy 2 async, PostgreSQL, Alembic, pytest, pytest-asyncio, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-26-user-prayer-offsets-design.md`

## Global Constraints

- Support exactly `bomdod`, `quyosh`, `peshin`, `asr`, `shom`, and `xufton`.
- Store every offset as an integer from `-30` through `30`, inclusive.
- Accept exactly three UI actions: `-1`, `0`, and `1`; action `0` resets only the selected prayer.
- Never mutate or cache an adjusted provider schedule.
- Reuse one adjustment and formatting path for `/start`, `/today`, region confirmation, and daily delivery.
- Changing region saves the new region and six zero offsets atomically.
- Starting an existing user preserves both region and offsets.
- Invalid, stale, or out-of-range callbacks never write to the database.
- Preserve delivery idempotency and one provider fetch per unique region during a broadcast.
- Domain/application modules must not import aiogram or SQLAlchemy.
- Write the failing test first, observe RED, implement the smallest behavior, then refactor while green.
- Preserve the user's unstaged `.env.example` deletion; never stage that file.

## Stable Interfaces

- `PrayerKey = Literal["bomdod", "quyosh", "peshin", "asr", "shom", "xufton"]`.
- `OffsetAction = Literal[-1, 0, 1]`.
- `PrayerOffsets.value_for(prayer: PrayerKey) -> int` returns one stored value.
- `PrayerOffsets.change(prayer: PrayerKey, action: OffsetAction) -> PrayerOffsets` returns a
  validated replacement object.
- `apply_offsets(schedule: PrayerSchedule, offsets: PrayerOffsets) -> PrayerSchedule` returns
  a newly validated schedule.
- `format_schedule(schedule, relative_label, offsets=None) -> str` preserves the existing
  two-argument callers and adds personalized rendering when offsets are passed.
- `SubscriptionService.change_offset(telegram_user_id, prayer, action) -> UserSubscription`
  performs one aggregate save.

---

### Task 1: Add the immutable offset domain and shared adjustment path

**Files:** Modify `src/namoz_bot/domain/models.py`, `src/namoz_bot/application/schedules.py`, and `tests/unit/application/test_schedules.py`; create `tests/unit/domain/test_prayer_offsets.py`.

- [ ] Add failing value-object tests for all-zero defaults, `-30` and `+30`, six independent fields, one-minute increment/decrement, selected-field reset, and rejection outside the range.

```python
def test_change_updates_only_selected_prayer_and_zero_resets_it() -> None:
    offsets = PrayerOffsets().change("shom", 1).change("shom", 1)
    assert offsets == PrayerOffsets(shom=2)
    assert offsets.change("shom", 0) == PrayerOffsets()

@pytest.mark.parametrize("value", [-31, 31])
def test_offsets_reject_values_outside_supported_range(value: int) -> None:
    with pytest.raises(ScheduleValidationError):
        PrayerOffsets(shom=value)
```

- [ ] Run `./.venv/bin/pytest -q tests/unit/domain/test_prayer_offsets.py`; expect import or assertion failure.
- [ ] Implement `PRAYER_KEYS`, `PrayerKey`, `OffsetAction`, and frozen `PrayerOffsets`. Validate every field in `__post_init__`; build a replacement value in `change` and let construction enforce the range.
- [ ] Add failing schedule tests proving positive and negative values apply to all six fields, the input schedule remains unchanged, only non-zero fields receive a suffix, and the old two-argument formatter remains unchanged.

```python
def test_format_schedule_marks_only_adjusted_values() -> None:
    text = format_schedule(make_schedule(), "Bugun", PrayerOffsets(shom=4, xufton=-2))
    assert "Shom — 19:14 (+4 daqiqa)" in text
    assert "Xufton — 20:28 (−2 daqiqa)" in text
    assert "Asr — 17:08\n" in text
    assert "Asr — 17:08 (" not in text
```

- [ ] Add failing tests that adjustment crossing `00:00…23:59` or breaking strict prayer ordering raises `ScheduleValidationError`.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_schedules.py`; expect the new assertions to fail.
- [ ] Implement minute conversion helpers and `apply_offsets`. Construct a new `PrayerTimes`, so existing clock/range/order validation is the single authority. Make `format_schedule` call `apply_offsets`, use the adjusted clock values, and append `(+N daqiqa)` or `(−N daqiqa)` from the canonical offset only when non-zero.
- [ ] Run `./.venv/bin/pytest -q tests/unit/domain/test_prayer_offsets.py tests/unit/application/test_schedules.py`; expect PASS.
- [ ] Run `./.venv/bin/ruff check src/namoz_bot/domain src/namoz_bot/application/schedules.py tests/unit/domain tests/unit/application/test_schedules.py && ./.venv/bin/mypy src`; expect exit 0.
- [ ] Commit only Task 1 paths with `git add src/namoz_bot/domain/models.py src/namoz_bot/application/schedules.py tests/unit/domain/test_prayer_offsets.py tests/unit/application/test_schedules.py && git commit -m "feat: add prayer time offset domain"`.

### Task 2: Persist all six offsets and migrate existing users safely

**Files:** Modify `src/namoz_bot/infrastructure/orm.py`, `src/namoz_bot/infrastructure/repositories.py`, `tests/integration/test_repositories.py`, and `tests/integration/test_postgres_claims.py`; create `alembic/versions/20260826_03_user_prayer_offsets.py`.

- [ ] Add a failing SQLite repository round-trip test that saves six distinct values, recreates the repository/session boundary, and reads the same `PrayerOffsets`.

```python
saved = await repository.save(
    subscription.with_preferences(
        offsets=PrayerOffsets(bomdod=-3, quyosh=-2, peshin=-1, asr=1, shom=4, xufton=5)
    )
)
loaded = await repository.get_by_telegram_user_id(saved.telegram_user_id)
assert loaded is not None
assert loaded.offsets == PrayerOffsets(-3, -2, -1, 1, 4, 5)
```

- [ ] Update `UserSubscription` with `offsets: PrayerOffsets = field(default_factory=PrayerOffsets)` after `id`, and let `with_preferences` accept `offsets: PrayerOffsets | None`; run the repository test and observe RED because ORM columns do not exist.
- [ ] Add six `SmallInteger`, non-null, server-default-zero ORM columns and six named `CheckConstraint`s such as `ck_users_shom_offset_range`.
- [ ] Centralize repository conversion in `_offset_values(offsets)` and `_to_subscription(record)`. Include all six columns in add/upsert/save values while ensuring an existing `upsert_start` record keeps its stored offsets.
- [ ] Create Alembic revision `20260826_03` with `down_revision = "20260826_02"`. In `upgrade`, add each column with `server_default="0"`, `nullable=False`, and its range check; in `downgrade`, drop checks before columns in reverse order.
- [ ] Extend the isolated PostgreSQL migration test to migrate a pre-offset user to head, assert all six values are zero, reject `shom_offset = 31` with `IntegrityError`, then accept `shom_offset = -30` and `30` in separate transactions.
- [ ] Run `./.venv/bin/pytest -q tests/integration/test_repositories.py`; expect PASS.
- [ ] Run `TEST_DATABASE_URL="$DATABASE_URL" ./.venv/bin/pytest -q tests/integration/test_postgres_claims.py`; expect PASS when PostgreSQL is configured, otherwise retain the existing explicit skip.
- [ ] Run `./.venv/bin/ruff check src/namoz_bot/infrastructure tests/integration alembic/versions/20260826_03_user_prayer_offsets.py && ./.venv/bin/mypy src`; expect exit 0.
- [ ] Commit Task 2 paths with `git add src/namoz_bot/domain/models.py src/namoz_bot/infrastructure/orm.py src/namoz_bot/infrastructure/repositories.py alembic/versions/20260826_03_user_prayer_offsets.py tests/integration/test_repositories.py tests/integration/test_postgres_claims.py && git commit -m "feat: persist user prayer offsets"`.

### Task 3: Add subscription use cases and atomic region reset

**Files:** Modify `src/namoz_bot/application/subscriptions.py`, `tests/unit/application/test_subscriptions.py`, and fake repositories in `tests/unit/application/test_broadcasting.py` and `tests/acceptance/harness.py`.

- [ ] First update every fake repository to round-trip `subscription.offsets`; this prevents tests from accidentally erasing the new aggregate field.
- [ ] Add failing tests that `change_offset` increments/decrements only the chosen prayer, action `0` resets only that prayer, boundary attempts do not call `save`, and a missing user raises `SubscriptionNotFoundError`.

```python
updated = await service.change_offset(telegram_user_id=7, prayer="shom", action=1)
assert updated.offsets == PrayerOffsets(shom=1)
assert repository.saved[-1].offsets == PrayerOffsets(shom=1)
```

- [ ] Add failing tests that `change_region` writes the new region and `PrayerOffsets()` in the same `save` call, while `start` on an existing user preserves non-zero offsets.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_subscriptions.py`; expect failures.
- [ ] Implement `SubscriptionService.change_offset` with typed `PrayerKey` and `OffsetAction`. Get the aggregate, derive `subscription.offsets.change(prayer, action)`, and perform exactly one repository save.
- [ ] Change `change_region` to save `subscription.with_preferences(region_code=region_code, offsets=PrayerOffsets())`; do not add a second persistence operation.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_subscriptions.py tests/unit/application/test_broadcasting.py`; expect PASS.
- [ ] Commit Task 3 paths with `git add src/namoz_bot/application/subscriptions.py tests/unit/application/test_subscriptions.py tests/unit/application/test_broadcasting.py tests/acceptance/harness.py && git commit -m "feat: manage prayer offset preferences"`.

### Task 4: Build the Telegram offset settings interaction

**Files:** Modify `src/namoz_bot/presentation/keyboards.py`, `src/namoz_bot/presentation/handlers.py`, `tests/unit/presentation/test_keyboards.py`, and `tests/unit/presentation/test_handlers.py`.

- [ ] Add failing keyboard tests for the new `⏱ Vaqtlarni sozlash` main-menu button, six prayer selector buttons, callback data `offset:<prayer>`, and the detail row `−1 | 0 | +1` with stable `offset-change:<prayer>:<action>` payloads.

```python
keyboard = build_offset_adjustment_keyboard("shom", 4)
buttons = [button for row in keyboard.inline_keyboard for button in row]
assert [button.callback_data for button in buttons[:3]] == [
    "offset-change:shom:-1",
    "offset-change:shom:0",
    "offset-change:shom:1",
]
```

- [ ] Run `./.venv/bin/pytest -q tests/unit/presentation/test_keyboards.py`; expect missing symbol failures.
- [ ] Add `OFFSETS_LABEL`, a single ordered prayer-label mapping, `build_offsets_keyboard(offsets)`, and `build_offset_adjustment_keyboard(prayer, value)`. Put `⬅️ Orqaga` on the detail keyboard with callback `offsets`.
- [ ] Add failing handler tests for `/offsets`, the reply-menu label, overview callback, prayer selection, `+1` repeated four times, selected-prayer reset, existing-message edit, `−30/+30` alert, invalid prayer, invalid action, missing callback message, and repository failure.
- [ ] Extend `FakeMessage` with `edit_text`; assert successful offset callbacks call `edit_text` and do not call `answer` on the message.
- [ ] Run `./.venv/bin/pytest -q tests/unit/presentation/test_handlers.py`; expect failures.
- [ ] Implement `_format_offsets_overview` and `_format_offset_detail` using the shared prayer-label mapping. Parse callback payloads with exact segment counts, a `PRAYER_KEYS` membership check, and an action map `{"-1": -1, "0": 0, "1": 1}` before calling the service.
- [ ] Catch `ScheduleValidationError` only for the range boundary and answer `"Chegara: −30…+30 daqiqa"` with `show_alert=True`. Let persistence failures propagate so middleware reports failure rather than acknowledging success.
- [ ] Register handlers in this order: `/offsets`, `OFFSETS_LABEL`, exact `offsets`, `offset-change:` prefix, then `offset:` prefix. Always call `callback.answer()` after a successful edit.
- [ ] Update help text to mention `/offsets` and the persistent personal adjustments.
- [ ] Run `./.venv/bin/pytest -q tests/unit/presentation/test_keyboards.py tests/unit/presentation/test_handlers.py`; expect PASS.
- [ ] Run `./.venv/bin/ruff check src/namoz_bot/presentation tests/unit/presentation && ./.venv/bin/mypy src`; expect exit 0.
- [ ] Commit Task 4 paths with `git add src/namoz_bot/presentation/keyboards.py src/namoz_bot/presentation/handlers.py tests/unit/presentation/test_keyboards.py tests/unit/presentation/test_handlers.py && git commit -m "feat: add prayer offset settings UI"`.

### Task 5: Personalize direct schedules and region confirmation

**Files:** Modify `src/namoz_bot/presentation/handlers.py` and `tests/unit/presentation/test_handlers.py`.

- [ ] Add failing tests that `/start` for a returning user and `/today` display `Shom — 19:14 (+4 daqiqa)` when the canonical value is `19:10` and stored `shom=4`.
- [ ] Add a failing region-selection test starting from non-zero offsets. Assert the service saves the new region with all-zero offsets and the confirmation schedule contains canonical times with no offset suffix.
- [ ] Run `./.venv/bin/pytest -q tests/unit/presentation/test_handlers.py`; expect failures.
- [ ] Refactor `_send_today` to receive or retrieve the current subscription and call `format_schedule(schedule, "Bugun", subscription.offsets)`. Avoid a second subscription lookup from `handle_start` by passing `result.subscription`.
- [ ] In region selection, use the `UserSubscription` returned by `change_region` and format with its reset offsets; avoid re-reading it from the repository.
- [ ] Run `./.venv/bin/pytest -q tests/unit/presentation/test_handlers.py`; expect PASS.
- [ ] Commit Task 5 paths with `git add src/namoz_bot/presentation/handlers.py tests/unit/presentation/test_handlers.py && git commit -m "feat: apply offsets to personal schedules"`.

### Task 6: Personalize daily broadcasts without increasing API calls

**Files:** Modify `src/namoz_bot/application/broadcasting.py` and `tests/unit/application/test_broadcasting.py`.

- [ ] Add a failing test with two active users in the same region, `shom=0` and `shom=4`. Assert the schedule provider is called once, both messages are sent once, and only the second message contains `Shom — 19:14 (+4 daqiqa)`.

```python
assert schedule_provider.calls == [("toshkent", target_date)]
assert sender.messages[user_one.chat_id] != sender.messages[user_two.chat_id]
assert "(+4 daqiqa)" not in sender.messages[user_one.chat_id]
assert "Shom — 19:14 (+4 daqiqa)" in sender.messages[user_two.chat_id]
```

- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_broadcasting.py`; expect the messages to be identical under the current string cache.
- [ ] Change the cache type to `dict[str, PrayerSchedule | Exception]`. Make `_prepare_schedule` return the canonical schedule without formatting. In `_send_one_workflow`, call `format_schedule(cached, "Ertaga", subscription.offsets)` immediately before `sender.send`.
- [ ] Keep claim batching, failed-region handling, blocked-user deactivation, semaphore use, and delivery status transitions unchanged.
- [ ] Add a failing test for an invalid adjusted schedule; assert it marks only that user's delivery failed while another user sharing the same canonical schedule still receives a message.
- [ ] Implement per-recipient adjustment failure handling inside the existing recipient workflow and log only region plus exception class.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_broadcasting.py`; expect PASS.
- [ ] Run `./.venv/bin/ruff check src/namoz_bot/application/broadcasting.py tests/unit/application/test_broadcasting.py && ./.venv/bin/mypy src`; expect exit 0.
- [ ] Commit Task 6 paths with `git add src/namoz_bot/application/broadcasting.py tests/unit/application/test_broadcasting.py && git commit -m "feat: personalize daily prayer broadcasts"`.

### Task 7: Verify the full journey, document behavior, and integrate

**Files:** Modify `tests/acceptance/test_user_journey.py`, `tests/acceptance/test_daily_delivery.py`, `README.md`, and only the acceptance harness files required to preserve offsets.

- [ ] Add an acceptance journey: start with default Toshkent, open offsets, select Shom, press `+1` four times, verify `/today` shows `(+4 daqiqa)`, run the daily job and verify tomorrow also shows `(+4 daqiqa)`, change region, then verify the confirmation and next daily message have no offset suffix.
- [ ] Add a persistence acceptance assertion that reconstructs services/repositories after saving `shom=4` and still reads `PrayerOffsets(shom=4)`.
- [ ] Run `./.venv/bin/pytest -q tests/acceptance`; observe RED before finishing the harness, then make the smallest harness changes and rerun for PASS.
- [ ] Update `README.md` with `/offsets`, all six adjustable fields, `−30…+30`, repeated one-minute controls, reset behavior, displayed suffix, persistence, and automatic reset on region change.
- [ ] Run the focused feature suite:

```bash
./.venv/bin/pytest -q \
  tests/unit/domain/test_prayer_offsets.py \
  tests/unit/application/test_schedules.py \
  tests/unit/application/test_subscriptions.py \
  tests/unit/application/test_broadcasting.py \
  tests/unit/presentation/test_keyboards.py \
  tests/unit/presentation/test_handlers.py \
  tests/integration/test_repositories.py \
  tests/acceptance
```

- [ ] Run the complete quality gate: `./.venv/bin/pytest -q && ./.venv/bin/ruff check src tests alembic && ./.venv/bin/ruff format --check src tests alembic && ./.venv/bin/mypy src && git diff --check`; expect exit 0, with only the existing optional PostgreSQL test skipped when no test database is configured.
- [ ] If PostgreSQL is available, run `TEST_DATABASE_URL="$DATABASE_URL" ./.venv/bin/pytest -q tests/integration/test_postgres_claims.py`; expect PASS.
- [ ] Inspect `git status --short`; confirm `.env.example` remains the user's unstaged deletion and no secret-bearing `.env` file is staged.
- [ ] Commit acceptance and docs paths with `git add tests/acceptance README.md && git commit -m "test: verify persistent prayer offsets"`.
- [ ] Request code review against the pre-feature commit and resolve every Critical or Important finding with a focused test before continuing.
- [ ] Re-run the complete quality gate after review fixes and commit any fixes separately.
- [ ] Stop the currently running bot process, apply `alembic upgrade head`, and restart from the verified `dev1` working tree using the project `.venv`; confirm polling starts without an exception.
- [ ] Push `dev1`, verify the remote hash, merge `dev1` into `main` non-interactively, rerun the complete quality gate on `main`, push `main`, and report both exact remote hashes.

## Required Final Evidence

- Full pytest count and skip count.
- Ruff, format-check, mypy, and `git diff --check` exit status.
- PostgreSQL migration result or the explicit reason it was skipped.
- Code-review result and resolved findings.
- Bot restart/polling confirmation.
- Exact `origin/dev1` and `origin/main` commit hashes.
- Confirmation that `.env.example` was not staged or overwritten.
