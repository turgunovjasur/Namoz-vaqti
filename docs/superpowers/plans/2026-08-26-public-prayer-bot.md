# Public Prayer Times Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready public Telegram bot that sends each subscriber the full next-day prayer schedule for their selected Uzbekistan region every day at 21:00 Asia/Tashkent.

**Architecture:** A single async Python service uses aiogram for Telegram, HTTPX for IslomAPI, SQLAlchemy/PostgreSQL for persistence, and APScheduler for the daily trigger. Domain models and application services remain independent of aiogram, HTTPX, and SQLAlchemy so integrations can change without rewriting business rules.

**Tech Stack:** Python 3.12, aiogram 3, HTTPX, Pydantic Settings, SQLAlchemy 2 async, asyncpg, Alembic, APScheduler 3, pytest, pytest-asyncio, Ruff, mypy, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-26-namoz-bot-design.md`

## Global Constraints

- Use `Asia/Tashkent`; the daily broadcast time is exactly `21:00`.
- Default region is exactly `Toshkent`.
- First-stage UI copy is Uzbek Latin.
- Only supported Uzbekistan locations appear in the UI; users cannot submit arbitrary region text.
- A successful daily delivery is unique by user, schedule date, and delivery type.
- Secrets come from environment variables and `.env` is never committed.
- Domain and application modules must not import aiogram, HTTPX, or SQLAlchemy.
- Reuse formatter, validation, and region lookup functions; do not duplicate field mapping or message construction.
- Write a failing test before each behavior, implement the minimum passing code, then refactor while green.

## File Map

```text
src/namoz_bot/
  config.py                   environment configuration
  domain/                     models, errors, immutable region catalog
  application/                ports and framework-free use cases
  infrastructure/             IslomAPI and SQLAlchemy adapters
  presentation/               Telegram keyboards, middleware, handlers
  scheduler.py                APScheduler wiring only
  main.py                     composition root and lifecycle
alembic/                      database migrations
tests/unit/                   pure domain/application tests
tests/integration/            HTTP/DB adapter tests
tests/acceptance/             complete user journeys with fake ports
```

---

### Task 1: Foundation, configuration, and domain types

**Files:** Create `pyproject.toml`, `.gitignore`, `.env.example`, `src/namoz_bot/config.py`, `src/namoz_bot/domain/models.py`, `src/namoz_bot/domain/errors.py`; test in `tests/unit/test_config.py` and `tests/unit/domain/test_models.py`.

**Interfaces:** Produce immutable `PrayerTimes`, `PrayerSchedule`, `UserSubscription`, and `Settings`. `PrayerSchedule(date: date, region_code: str, region_name: str, times: PrayerTimes)` is canonical across layers.

- [ ] Write failing tests that invalid `25:00` raises `ScheduleValidationError`, valid times preserve order, and settings default to `Asia/Tashkent` plus `21:00`.
- [ ] Run `pytest tests/unit/test_config.py tests/unit/domain/test_models.py -q`; expect missing-module failures.
- [ ] Implement packaging, Pydantic settings aliases, immutable models, `HH:MM` validation, semantic ordering, and secret-safe `.gitignore`.
- [ ] Run `pytest tests/unit/test_config.py tests/unit/domain/test_models.py -q && ruff check src tests`; expect PASS.
- [ ] Commit with `chore: establish modular bot foundation`.

Test shape:

```python
def test_prayer_times_reject_invalid_clock_value():
    with pytest.raises(ScheduleValidationError):
        PrayerTimes("25:00", "06:00", "12:00", "16:00", "18:00", "20:00")
```

### Task 2: Supported Uzbekistan region catalog

**Files:** Create `src/namoz_bot/domain/regions.py`; test `tests/unit/domain/test_regions.py`.

**Interfaces:** Produce `Region(code, display_name)`, `UZBEKISTAN_REGIONS`, `DEFAULT_REGION_CODE`, `get_region(code)`, and `list_regions()`. Store `code`; show `display_name`.

- [ ] Write failing tests for Toshkent default, unique codes/labels, and rejection of an unsupported name.
- [ ] Run `pytest tests/unit/domain/test_regions.py -q`; expect FAIL.
- [ ] Implement an immutable Uzbekistan-only catalog from IslomAPI’s published `regions.json`, preserving exact API Unicode while normalizing labels.
- [ ] Run the focused test; expect PASS.
- [ ] Commit with `feat: add supported Uzbekistan region catalog`.

### Task 3: IslomAPI adapter and schedule formatting

**Files:** Create `src/namoz_bot/application/ports.py`, `src/namoz_bot/application/schedules.py`, `src/namoz_bot/infrastructure/islom_api.py`; test `tests/unit/application/test_schedules.py` and `tests/integration/test_islom_api.py`.

**Interfaces:** `PrayerScheduleProvider.get_for_date(region_code: str, target_date: date) -> PrayerSchedule`; `ScheduleService.get_schedule(...)`; `format_schedule(schedule, relative_label) -> str`.

- [ ] Write failing tests for wrong-date rejection, exact Uzbek message format, exact endpoint/query parameters, and malformed API payloads.
- [ ] Run focused tests; expect FAIL.
- [ ] Implement the port, validation service, shared formatter, and HTTPX adapter. Map `tong_saharlik`, `quyosh`, `peshin`, `asr`, `shom_iftor`, `hufton` once only.
- [ ] Retry only timeout/connection/429/5xx with bounded exponential backoff; never retry 400/404.
- [ ] Run focused tests; expect PASS, then commit `feat: integrate validated IslomAPI schedules`.

Formatter assertion:

```python
text = format_schedule(make_schedule(date(2026, 8, 27)), "Ertaga")
assert text.startswith("📅 Ertaga — 27-avgust, Toshkent")
assert text.endswith("Manba: islomapi.uz")
```

### Task 4: Persistence and subscription use cases

**Files:** Create `src/namoz_bot/infrastructure/db.py`, `orm.py`, `repositories.py`, `src/namoz_bot/application/subscriptions.py`, `alembic.ini`, `alembic/env.py`, and initial migration; test unit subscription behavior and integration repositories.

**Interfaces:** Add `SubscriptionRepository` and `DeliveryRepository` Protocols. Produce `SubscriptionService.start(...) -> StartResult`, `change_region(...)`, and `set_active(...)`.

- [ ] Write failing tests that `/start` creates one active Toshkent record and a returning user keeps the saved region and is reactivated.
- [ ] Write failing repository tests for unique Telegram user and `(user_id, schedule_date, delivery_type)` constraints.
- [ ] Implement SQLAlchemy async tables/adapters and Alembic migration without leaking ORM types into application code.
- [ ] Run focused unit/integration tests; expect PASS.
- [ ] Commit `feat: persist subscriptions and delivery state`.

Critical assertion:

```python
first = await service.start(7, 9)
second = await service.start(7, 9)
assert first.created is True and second.created is False
assert second.subscription.region_code == "Toshkent"
```

### Task 5: Telegram menus and thin handlers

**Files:** Create `src/namoz_bot/presentation/keyboards.py`, `handlers.py`, `middleware.py`; test `tests/unit/presentation/`.

**Interfaces:** Produce `build_main_menu(is_active)`, `build_region_keyboard(page)`, and aiogram `router`. Inject application services; never instantiate repositories or HTTP clients in handlers.

- [ ] Write failing tests for paginated catalog-only buttons, `/start`, `/today`, `/settings`, `/help`, region callback validation, and notification toggle.
- [ ] Run `pytest tests/unit/presentation -q`; expect FAIL.
- [ ] Implement reusable keyboards and thin handler adapters. Callback payload is `region:<page>:<catalog-index>`; always answer callbacks.
- [ ] Run presentation tests; expect PASS.
- [ ] Commit `feat: add Telegram onboarding and settings UI`.

### Task 6: Grouped idempotent daily broadcaster

**Files:** Create `src/namoz_bot/application/broadcasting.py`, `src/namoz_bot/scheduler.py`; test broadcaster and scheduler units.

**Interfaces:** `BroadcastService.send_next_day(target_date: date) -> BroadcastReport`. Consume subscriptions grouped by region, `ScheduleService`, `DeliveryRepository`, and `MessageSender` port.

- [ ] Write a failing test proving two Toshkent users cause one API fetch, each user receives once across repeated runs, and a Samarqand failure does not stop Toshkent.
- [ ] Write a failing test proving a blocked chat is deactivated while the batch continues.
- [ ] Implement grouping, delivery reservation, Telegram rate-limit handling, and report counts.
- [ ] Wire an APScheduler cron trigger for hour 21/minute 0 in `Asia/Tashkent`, calculating tomorrow from timezone-aware local time.
- [ ] Run focused tests; expect PASS, then commit `feat: schedule idempotent daily broadcasts`.

### Task 7: Composition root, deployment, and documentation

**Files:** Create `src/namoz_bot/logging.py`, `src/namoz_bot/main.py`, `Dockerfile`, `docker-compose.yml`, `Makefile`; modify `README.md`; test lifecycle in `tests/unit/test_main.py`.

**Interfaces:** `create_application(settings) -> ApplicationResources` owns Bot, HTTPX client, engine, dispatcher, and scheduler; `close()` releases all resources.

- [ ] Write a failing lifecycle test that shutdown closes the client, engine, bot session, and scheduler.
- [ ] Implement dependency composition, polling lifecycle, graceful signals, and token-safe structured logging.
- [ ] Document BotFather token, `.env`, migrations, local run, Docker, commands, supported regions, and 21:00 behavior.
- [ ] Run `pytest -q && ruff check src tests && ruff format --check src tests && mypy src`; expect all exit 0.
- [ ] Commit `feat: compose deployable prayer bot service`.

### Task 8: Acceptance and release workflow

**Files:** Create `tests/acceptance/test_user_journey.py`, `tests/acceptance/test_daily_delivery.py`; refine README only if verified commands differ.

**Interfaces:** Use production application services with fake external ports; introduce no new production interface.

- [ ] Write acceptance tests: `/start` immediately sends today’s Toshkent schedule, region changes to Samarqand, and the 21:00 job sends tomorrow’s Samarqand schedule once.
- [ ] Run acceptance tests and verify RED before the harness is complete.
- [ ] Add a reusable harness that replaces only external ports and does not duplicate production formatting/region/scheduler logic.
- [ ] Run `pytest -q && ruff check src tests && ruff format --check src tests && mypy src && git diff --check`; expect all exit 0.
- [ ] Commit `test: verify complete public bot journey`.

Acceptance assertion:

```python
await harness.send_command(user_id=7, command="/start")
assert "Bugun" in harness.last_message(7) and "Toshkent" in harness.last_message(7)
await harness.select_region(7, "Samarqand")
await harness.run_daily_job("2026-08-26T21:00:00+05:00")
assert "Ertaga — 27-avgust, Samarqand" in harness.last_message(7)
```

## Final Branch Workflow

1. Push tested `dev1` and verify its remote commit.
2. Merge `dev1` into local `main` non-interactively.
3. Re-run the full quality gate on `main`.
4. Push `main` to `origin` and report exact hashes plus deployment-only secrets still needed.
