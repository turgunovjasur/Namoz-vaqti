# Admin web panel verification — 2026-10-15

Implemented on `codex/roles-capabilities`, range `fe79910..044a55c` (four feature commits). The user delegated product scope and design. Existing uncommitted menu/settings and journey-test changes were preserved and excluded from feature commits.

## Delivered
- React/Vite/TypeScript Uzbek responsive admin panel: users/search/filter/paging, atomic multi-role capability editing, registry-based role catalog, validated global Gemini model settings, audit history.
- Same-origin FastAPI API, trusted admin-only /admin and profile entry, five-minute one-use login tickets, eight-hour revocable hashed SQL sessions, HttpOnly/SameSite cookies, HTTPS Secure cookie, exact Host/Origin and CSRF validation, no external scripts.
- Trusted Telegram display names/usernames refreshed on updates. No financial entries, reminder content or private conversations exposed.
- Shared ProfileService/model composition, schema revision `20261015_04`, explicit TEST/production CLI, Dockerfile.admin and setup documentation.

## Automated evidence
- Expanded full suite with NAMOZ_TEST_DATABASE_URL pointing to the existing isolated test database: **845 passed, 6 expected skips, 116.04 seconds**. Tests create/drop random schemas, never use the live local bot database.
- Initial feature full run: 838 passed, 6 expected skips. An earlier sandboxed baseline could not open PostgreSQL sockets (3 failures/137 setup errors); rerunning with authorized localhost access resolved those environment failures.
- Ruff check all src/tests/Alembic: passed. Mypy: 132 source files passed. Ruff format: 228 files passed. Prettier format check and TypeScript/Vite production build passed (249.93 kB JS, 77.93 kB gzip).
- New SQL/HTTP tests cover stale batch rollback including audit, exact per-role subsets, disabled grants, invalid/system/duplicate roles, login expiry/replay/concurrent redemption, nonadmin/admin revocation, session expiry/hash storage/logout, CSRF/Origin/Host, non-ASCII malformed CSRF, browser URL origin normalization, escaped name/username/ID search, filtering and registry metadata, failed model validation preserving settings/audit, bot entry/profile link and TEST credential selection.

## Browser evidence
Browser plugin skill was not available. IAB first checked the actual login screen; dedicated Playwright tools then exercised real SQL-backed synthetic accounts at 1440x1000, 768px and 390x844. Verified all four pages, no horizontal overflow, keyboard-native dialog, 44px role switch targets, fixed visible save footer, 20+6 users and 20+7 audit paging, search/role filter/empty state, save and reload, cancel restores selection, role-off preserves capabilities, stale update conflict and explicit refresh, failed Gemini probe leaves current model unchanged, logout returns 401.

No frontend runtime errors or framework overlays. Deliberately triggered 409 and 502 network responses appeared in console and were correctly rendered as user-facing messages.

Final reference comparison: ImageGen concept and final editor screenshots inspected together. White sidebar, teal navigation, restrained table, role pills and right editor match the selected direction. Fictional concept counts were replaced with live server counts; real capability descriptions require vertical scrolling. Synthetic screenshots are in /private/tmp/yordamchi-admin-{desktop,editor,mobile-editor,mobile,models}.png (not committed). Design canvas: https://superdesign.dev/teams/a6424474-f049-4810-aec1-e914c4a4819b/projects/56b46b07-5dc7-49b6-aca4-11a67ec82bfe?node=draft-variant-d03197e8-a19b-4534-b4f3-40f399b43259

## Local activation
Verified LocalSettings TEST database before applying revision 20261015_04; assignment/capability row counts unchanged. Web server bound only to `127.0.0.1:8088` using TEST settings. Own administrator login tested read-only: HTTP200, trusted admin profile, real users loaded, no private records in payload. Only the polling process verified against the TEST token's lock was restarted. Startup confirms the existing TEST bot identity. No production bot, database, role grants, Gemini model, public domain or remote deployment changed.

Use bot `/admin` or **Profil → 🌐 Admin web panel** to get a fresh link. Public HTTPS is required for other devices. Docker recipe was inspected but not built: Docker is not installed on this host. Production HTTPS proxy/deployment and live Gemini model switching were not exercised; the latter's existing service tests and the UI/API rejection path were exercised.

## Fresh final review
Independent read-only review of `fe79910..044a55c` found no Critical or Important issues. Declined to judge: empty. No unresolved rulings.

Deferred minor: an unsaved model dropdown selection is discarded on in-app navigation, or when another row's conflict refresh reloads the models page. Save the selection before leaving; no committed configuration is lost. This improvement was deferred following executing-plans' single-pass/minor policy.
