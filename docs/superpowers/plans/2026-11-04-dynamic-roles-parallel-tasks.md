# Dynamic roles and parallel tasks implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Admin-controlled specialist roles with a permanent assistant and independent background tasks.
**Architecture:** SQL role snapshots drive a single agent factory; skills retain server-side validation. Bounded workers refill free slots and publish results through the durable outbox.
**Tech Stack:** Python, SQLAlchemy, aiogram, asyncio, FastAPI, React/TypeScript.
**Spec:** ../specs/2026-11-04-dynamic-roles-parallel-tasks.md

## Global constraints
- Preserve pre-existing workspace changes and database data.
- One protected assistant; no built-in specialist role population on a clean install.
- Dynamic agent permissions are checked at planning, approval and execution.
- Long provider calls must not hold owner SQL locks; committed writes retain atomic receipts.

## Review focus
- Fresh versus migrated catalogs; preserve custom names/models/grants and old saved plans.
- Legacy menus must authorize skills through arbitrary role IDs.
- Archived agents cannot regain grants or execute queued work.
- A slow task must not delay a later task or its result; capacity remains bounded across ticks.
- Duplicate approvals, shutdown and lease recovery must not duplicate business effects.

### Task 1: Database-owned roles
- [x] Add failing tests for assistant-only startup, arbitrary-role legacy dispatch, model snapshots without manager and archive enforcement.
- [x] Remove runtime built-in specialist definitions; move old test data to explicit fixtures. Bootstrap assistant only, persist model defaults, add archive migration/API and UI grouping.
- [x] Verify dynamic roles, authorization, migration and frontend build.

### Task 2: Independent background execution
- [x] Add failing tests for nonblocking/refill worker dispatch and same-user slow preparation alongside a quick task.
- [x] Add configurable worker concurrency, independent outbox scheduling and transaction-free native preparation; preserve receipts and shutdown recovery.
- [x] Verify new inputs preserve accepted jobs and results identify their tasks.

### Task 3: Verification
- [x] Run full test suite, lint/type checks, frontend build and browser interaction smoke tests.
- [x] Obtain an independent code review, fix actionable regressions and record outcomes below.

## Progress / decisions
- Work in the existing checkout because this task extends earlier uncommitted changes; do not commit unrelated edits.
- The user explicitly authorized implementation; proceed without an additional planning approval round.

- Kept legacy menu parsing for saved pre-V3 drafts, but it no longer supplies the live role catalog. Legacy skill dispatch resolves arbitrary assigned database role IDs.
- Fresh installations keep only the assistant; existing specialist definitions, assignments and models survive the migration. Archival keeps historical records and revokes active grants.
- Independent review found one P2 issue: generic failure notifications did not identify concurrent tasks. Added transcript prefixes and task/revision metadata, with three regression cases covering unsaved, saved and committed results. No other concrete findings.
- Browser smoke checks used mocked API responses for frontend behavior: create a specialist, edit assistant name/model, archive a specialist, verify assistant has no archive/disable controls. Desktop 1366px and mobile 390px checked; no horizontal overflow or console errors. Real API behavior is covered by database integration tests.
- Ruff, formatting, mypy (148 files), frontend production build and diff whitespace checks pass. PostgreSQL-specific tests require NAMOZ_TEST_DATABASE_URL and remain unexecuted in this environment.
- No deployment or production database migration was performed. Apply `alembic upgrade head` and restart bot/admin processes when releasing.
- Final full suite after review fixes: **730 passed, 176 skipped**, 82.36 seconds. Targeted worker/failure/profile regression checks: **10 passed, 6 skipped**.
