# Voice Accounting Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Run local voice income/expense records and reports in a new bot section.
**Architecture:** Strict extracted intent -> owner-scoped integer ledger -> SQL aggregates.
**Tech Stack:** Python 3.12, aiogram, HTTPX/Gemini, SQLAlchemy, Alembic, PostgreSQL.
**Spec:** docs/superpowers/specs/2026-10-12-accounting-design.md

## Global Constraints
- UZS whole integers, maximum 1,000,000,000,000,000; audio 120 seconds/5 MiB.
- Balance carries forward; per-user isolation; no logs of financial input.
- Local checkout contains unrelated work: preserve it, no commits/push/deployment.

## Review Focus
- Month-only input must not silently acquire an exact day.
- Duplicate messages must not double balance or resurrect cancelled records.
- Cancelling old records must remain owner-scoped and idempotent.
- Finance mode must not intercept reminders after navigation away.
- Provider malformed/ambiguous output must never mutate the ledger.

### Task 1: Ledger and extraction contracts
Files: domain/accounting.py, application/accounting.py, infrastructure/accounting.py,
infrastructure/orm.py, alembic/versions/20261012_01_finance_entries.py.
Interface: AccountingRequest; LedgerService.record(user_id, request, source_key, now),
summary(user_id, month), balance(user_id), history(user_id,page), cancel(user_id,id).
- [x] Write/run failing repository tests for 10,000,000 income minus 120,000 expense,
  month salary filters, rollover, duplicates, cancellation, and ownership.
- [x] Implement strict request validation, bounded whole amounts, persisted journal,
  SQL aggregates, and additive migration. Run repository tests until green.

### Task 2: Voice/text accounting UI
Files: infrastructure/gemini_accounting.py, presentation/accounting.py,
presentation/keyboards.py, presentation/reminders.py, main.py.
Interface: GeminiAccountingClient.extract(text,audio,mime_type,now)->AccountingRequest.
- [x] Write/run failing acceptance journeys for section entry, transactions,
  reports/history/undo, malformed input and navigation away.
- [x] Add one structured Gemini request per input and a private accounting FSM router
  ahead of reminder voice routing. Keep existing reminder workflows intact.
- [x] Update intentional main-menu expectations, then run complete suite/Ruff/mypy.

### Task 3: Local delivery
Files: README.md; local test database only.
- [x] Review feature, fix findings, verify synthetic real audio extraction.
- [x] Stop the identified local test polling process, run local migration/startup,
  confirm only one process polls, and provide test commands to the user.

## Verification record

Inline execution in the existing local checkout as requested. No commits or push.
Final independent review found no actionable findings. Full suite with local PostgreSQL
using isolated temporary schemas: 420 passed, 3 SQLite-only migration variants skipped.
Ruff and mypy passed. Live synthetic OGG income/expense plus Uzbek salary query passed.
Local test database migrated to 20261012_01 and @TestUzNamozTaqvimiBot polling started.
