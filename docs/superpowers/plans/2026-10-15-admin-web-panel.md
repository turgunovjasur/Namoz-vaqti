# Admin web panel implementation

**Goal:** Deliver the delegated admin panel fully connected to existing roles/capabilities/model services.
**Architecture:** React + Vite + TypeScript; same-origin FastAPI; SQLAlchemy auth; shared ProfileService.
**Tech Stack:** Python 3.12, FastAPI, uvicorn, React, Vite, TypeScript.
**Spec:** docs/superpowers/specs/2026-10-15-admin-web-panel.md
**Global Constraints:** Preserve existing dirty files; no real secrets/data in fixtures; TEST DB only for local activation, random isolated schemas for tests; no implicit grants; no public deployment.
**Review Focus:** Magic-link replay/races, session/admin revocation, CSRF and Host/Origin validation, URL token leaks, stale multi-role atomicity, default model consistency, UI stale request/unsaved edits, production build assets, public HTTPS vs local URL behavior.

### Task 1: Shared management foundation
Files: domain/workforce/profiles.py; application/profiles/{ports,service}.py; infrastructure/workforce/profiles.py; infrastructure/workforce/bootstrap.py; main.py; tests/integration/test_admin_management.py.
Interfaces: GrantChange(role_id, enabled, capability_ids, expected_revision); set_assignments(actor_id,user_id,changes) returns ProfileView atomically. Existing set_grants delegates one change. build_profile_service(settings,factory,http) centralizes current model defaults/catalog.
1. Write stale-batch rollback and invalid-capability tests, run RED (missing batch method).
2. Implement shared batch mutation and bootstrap extraction; run tests GREEN.
3. Commit foundation. Expected: targeted SQLite/Postgres tests pass.

### Task 2: Authentication, metadata and API
Files: infrastructure/admin_web/{auth,queries}.py; presentation/admin_web/{app,schemas}.py; admin.py; migration 20261015_04; config.py; middleware.py; tests/integration/test_admin_web.py; tests/unit/test_admin_config.py.
Interfaces: issue_ticket(telegram_id), exchange_ticket(token), authenticate(cookie), revoke(cookie); create_app(settings,factory,profile_service) creates same-origin app. API /api/session, /api/auth/exchange, /api/auth/logout, /api/users, /api/users/{id}, /api/roles, /api/models, /api/history. PUT user assignments and role model with revisions.
1. Write real SQL/HTTP integration tests for one-use expiry, nonadmin, revocation, CSRF, origin, stale batches, search/paging and privacy; run RED.
2. Implement hashed SQL tickets/sessions, migration, trusted identity sync, bounded queries, typed API, secure headers and static build mounting. Install explicit admin dependencies.
3. Run tests GREEN, commit backend. Expected: unauthenticated denied; no writes without same-origin CSRF; no replay; stale edits rollback.

### Task 3: Responsive frontend
Files: web/admin/{package.json,package-lock.json,index.html,vite.config.ts,tsconfig*.json,src/*}; .superdesign/design-system.md.
Interfaces: same-origin JSON API; login fragment exchanged once; session credentials only HttpOnly cookie and in-memory CSRF. Registry-driven roles and capability editor; explicit Save; conflict reload; model errors visible.
1. Generate/inspect concept, define tokens, build UI from accepted self-selected direction.
2. Build and type-check; browser test real API login, searching, role editing/save/cancel/conflict, role catalog, models, history, logout, mobile layout. Expected: real persisted results, no horizontal overflow, clear errors, no mock statistics.
3. Commit frontend. Reversible visual changes verified in browser; meaningful behavior covered by API and browser workflows.

### Task 4: Bot entry, local activation and verification
Files: presentation/admin_web/router.py; main.py; admin.py; README.md; .env.example; tests/acceptance/test_admin_web_entry.py; docs/superpowers/verification/2026-10-15-admin-web-panel.md.
Interfaces: /admin only trusted private admin gets fresh one-use link; CLI --local serve/link uses LocalSettings exclusively. Default bind 127.0.0.1:8088, ADMIN_WEB_URL optional HTTPS/loopback HTTP.
1. Write bot nonadmin/private/link and CLI local-settings tests, run RED.
2. Implement entry/startup/docs; migrate TEST database, start localhost panel, verify own read-only login; restart only verified TEST bot if needed.
3. Run full pytest with isolated PostgreSQL URL, Ruff/mypy and frontend build; one fresh whole-feature review, fix important findings with RED→GREEN, record results. Expected: all checks green; local panel usable.
4. Commit only feature files; preserve unrelated dirty files and do not merge/push.
