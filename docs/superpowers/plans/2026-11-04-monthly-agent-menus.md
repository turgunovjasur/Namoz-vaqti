# Monthly accounting and agent menus implementation plan

> Use superpowers:executing-plans; implement in this existing checkout.

**Goal:** Monthly accounting and database-named Telegram agent menus.
**Architecture:** Optional SQL month filters and explicit receipt month totals; request-scoped agent menu catalog and capability-based UI adapters.
**Tech Stack:** Python, SQLAlchemy, aiogram, pytest.
**Spec:** ../specs/2026-11-04-monthly-agent-menus.md

## Constraints and review focus
- Preserve old data, arbitrary role IDs/names and user grants. Menus cannot confer permissions.
- Month/year boundaries, viewing old months then writing today, old receipts, revoked role/capability callbacks, mixed/custom skills and navigation from active forms.

## Task 1: Monthly accounting
- [x] RED: month-filtered balance/history, monthly view excluding carryover, month navigation and write date isolation.
- [x] Extend LedgerRepository/Service balance and history with optional month; preserve defaults for existing internal callers. Add finance history month schema and receipt monthly totals.
- [x] Implement monthly panel, explicit overall balance, picker and month-filtered pagination; update truthful result rendering.
- [x] Verify accounting tests and existing receipts.

## Task 2: Agent menus
- [x] RED: custom role names, renames, only granted actions, old callbacks after revocation.
- [x] Build request-scoped role/capability menu metadata and generic menu router before conversational routers. Reuse authorized forms by capability, not role ID.
- [x] Verify dynamic roles, accounting and existing Telegram journeys.

## Task 3: Validation
- [x] Full pytest, ruff/mypy, independent reviewer and fix any actionable regressions.

## Decisions
- User already approved the inline design and asked for implementation. No repeat approval needed. Work remains uncommitted alongside prior changes.
- Shared interface: Task 2 invokes Task 1 accounting handlers with role-specific menu context; finance permissions and period state must survive internal form resets.
- Existing role assignments are preserved. A separately configured settings agent remains visible; admins can bind its skills to another agent from the panel.
- Monthly display does not remove stored entries or change internal all-time balance defaults. No schema migration is needed for this feature.

## Review and verification record
- Independent reviewer found two actionable issues: a fallback skill retained an active reminder form, and backdated AI receipts did not select the receipt month for subsequent buttons. Both reproduced with failing acceptance tests and passed after fixes.
- Additional regression tests cover a cancelled receipt's refreshed monthly balance and an excerpt-only agent retaining only its granted actions after use.
- Seven new menu/month navigation acceptance cases pass. Provider calls are faked at the external boundary; database, authorization, FSM and Telegram dispatch paths are real.
- Ruff passes; mypy passes for 152 source files. Final full pytest: 743 passed, 177 skipped in 89.72 seconds (`/tmp/namoz-month-menu-final.log`).
- No deployment or live Telegram messages. PostgreSQL-only tests require a configured test database; SQLite integration coverage runs locally.
