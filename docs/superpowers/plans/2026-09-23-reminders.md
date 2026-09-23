# Reminders implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the approved two-section Telegram menu and personal dated, daily and weekly reminders on `dev1`, verified locally.

**Architecture:** Keep the existing domain/application/adapters layering. Persist reminders and delivery reservations in SQLAlchemy; a single periodic job claims due occurrences transactionally before sending. Use aiogram FSM with per-user event isolation for the creation dialog.

**Tech Stack:** Python 3.12, aiogram 3, SQLAlchemy 2, Alembic, APScheduler 3, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-reminders-design.md`

## Global constraints

- Branch `dev1`; local execution, no production deployment.
- Preserve existing user changes to `.env.example` and `DEPLOYMENT_QA_SERVER.md`.
- Asia/Tashkent reminder wall time; store occurrence instants in UTC.
- No new runtime dependencies; plain text Telegram output.
- Text → time → date/daily/weekly → confirmation; private chats only.
- 1000-character text limit, three reminders per list page, 15-second polling interval.

## Review focus

1. Midnight, leap day and weekly rollover: literal next-occurrence fixtures in domain tests.
2. Concurrent save/claim: unique creation token and compare-and-swap occurrence tests against SQLite and isolated PostgreSQL.
3. Stale buttons after back/cancel/restart: rotated dialog token and real Dispatcher journey tests.
4. Cross-user/group access: private-chat guard and owner-filtered page tests.
5. Slow/failed delivery and downtime: per-recipient exception isolation and next-future-occurrence tests.

## Task 1: Rules and persistent delivery

Files: create `domain/reminders.py`, `application/reminders.py`, `infrastructure/reminders.py`; extend `infrastructure/orm.py`; add Alembic migration and domain/repository tests.

Interfaces: `ReminderSpec(text, at, kind, on_date=None, weekday=None).next_after(now)` returns aware UTC datetime. Repository `create(user_id, chat_id, spec, token, now)`, `list_for_user(user_id, offset, limit)`, `claim_due(now, limit)`, `finish(delivery, status, error=None)`, `pause_user(user_id)`. Application service owns create validation, listing and recipient-isolated delivery.

- [x] Write literal tests for a daily 20:00 reminder at 20:01 yielding tomorrow 15:00 UTC, Sunday rollover, leap-day date, malformed specs, persisted creation and concurrent claim.
- [x] Run `.venv/bin/pytest -q tests/unit/domain/test_reminders.py tests/integration/test_reminder_repository.py`; observe missing behavior.
- [x] Implement validated immutable spec and recurrence calculation; SQL tables and migration; dialect-specific idempotent insertion and conditional due-time update in one transaction.
- [x] Add service delivery tests using real SQLite repository and a capturing Telegram boundary; check restart, failure and blocked recipient behavior.
- [x] Run the focused tests and verify green.

## Task 2: Telegram navigation and dialog

Files: update `presentation/keyboards.py`, `presentation/handlers.py`, `presentation/middleware.py`, `main.py`; create `presentation/reminder_keyboards.py`, `presentation/reminders.py`; add Dispatcher acceptance tests and adapt existing onboarding expectations.

Interfaces: `build_main_menu()` returns the two-section keyboard, `build_prayer_menu()` retains existing actions plus home. Reminder service is injected as `reminder_service`. Dialog state uses `text`, `time`, `schedule`, `date`, `weekday`, `confirm` states. Callback shape is `rem:<rotating_token>:<action>:<value>`; list callbacks bind owner and page.

- [x] Write a real Dispatcher journey with fake Bot session and real SQLite persistence: `/start` → reminders → add → text → time → daily → save → list.
- [x] Add date-calendar and weekly journeys, malformed input, duplicate/stale callbacks, cancellation, group rejection, ownership and pagination tests.
- [x] Run acceptance tests to observe failures before implementing handlers.
- [x] Implement menu routing, FSM prompts, calendar with actual month lengths, fresh token checks on every callback, confirmation, plain text listing and private chat restrictions.
- [x] Adapt tests that intentionally expected `/start` to show the prayer schedule; add explicit schedule requests where that is the journey's intent.
- [x] Run presentation and acceptance tests to green.

## Task 3: Runtime composition and local verification

Files: update `scheduler.py`, `main.py`, README, runtime wiring tests, PostgreSQL integration tests.

- [x] Test application composition exposes the daily prayer job and the reminders job without making network calls.
- [x] Wire one reminder worker to the existing sender/rate limiter; add interval job with coalescing and one active instance.
- [x] Verify new Alembic upgrade/downgrade on isolated local PostgreSQL and concurrent save/claim; never use the application's `.env` database for tests.
- [x] Run `PATH="$PWD/.venv/bin:$PATH" make check` and `git diff --check`.
- [x] Review diff against spec, fix concrete findings with regression tests, then rerun affected checks.
- [x] Update README with menu behavior, migrations, delivery limitations, and test-bot/local-database instructions. Report automated test evidence separately from live Telegram testing.


## Execution record

- Executed directly in the user-selected existing `dev1` checkout; unrelated user changes preserved.
- Domain RED: missing reminder module; GREEN: 20 literal recurrence/validation cases.
- Persistence RED: missing application/repository module; GREEN: SQLite creation, claim, downtime, failure tests.
- UI RED: `/start` still fetched a schedule; GREEN: real Dispatcher private-chat journeys.
- Runtime RED: `personal-reminders` scheduler job absent; GREEN: composition now registers both jobs.
- Unicode list RED: three 1000-emoji reminders exceeded Telegram UTF-16 length; GREEN: lossless per-entry message splitting.
- PostgreSQL migration/concurrency checks: 10 passed, one SQLite-only migration placeholder skipped (PostgreSQL roundtrip passed).
- Fresh independent code review requested before final completion.

- Final reviewer reproduced two important FSM issues; both fixed with failing-first Dispatcher tests: slash commands clear both storage and routing state; historical list callbacks cannot cancel a new draft.
- Final full suite with local PostgreSQL: 157 passed, 1 skipped (SQLite instance of a PostgreSQL-only migration test).
- `make check`: 151 passed, 7 optional PostgreSQL cases skipped without the URL; Ruff, mypy and format checks passed. All six URL-dependent cases passed in the full PostgreSQL run above.
- Runtime job was also invoked through the real application composition using local fake Telegram transport: one due reminder sent once across two job runs.
- Keep `dev1` local per user request. No live Telegram polling, production deployment or push performed.
- Decisions: compose the interval job next to its shared sender in `main.py`; split oversized Unicode list pages into multiple messages without losing text; use the current checkout because the user selected `dev1`. None changes the approved product flow.
- Reviewed delivery uncertainty and blocked-recipient pause behavior remain as documented in the approved spec. No further minor findings were reported.
