# Yordamchi admin web panel

The user delegates scope and design: “admin web panel qilib ber, nimalar bolishi kerakligini ozing hal qil”. Deliver a real, responsive Uzbek interface backed by the existing bot database and ProfileService.

## Product
- Users: factual counts, name/username/Telegram ID search, role filter, keyset paging, user inspector. Show account identity and role assignments, never financial entries or private messages.
- Edit multiple specialist roles and their individual capabilities together. One explicit Save commits all changes atomically; stale revisions reject the entire edit. System roles are explained and cannot be disabled. Disabling a role preserves its selected capabilities. Never grant capabilities implicitly.
- Roles: readable responsibilities and reusable capability descriptions from the registries.
- AI models: current global model per role, configured choices, real Gemini validation before saving, optimistic concurrency, honest error feedback. Clearly explain global scope and potential API usage during validation.
- History: server audit records, timestamps, actor/target and meaningful change summaries, paging.
- Loading, empty, error, expired login, unsaved changes, save success and conflict states. Desktop sidebar/table and mobile sheet/checklist.

## Architecture and authentication
React/Vite/TypeScript frontend, FastAPI API/static server, existing SQLAlchemy PostgreSQL database. Separate admin modules for auth, queries, API, bootstrap and CLI; share role/model composition and existing ProfileService authorization/model validation.

A configured admin requests /admin in the private bot chat and receives a short-lived, one-use login link. Token is 256-bit random, stored only as SHA256, expires after five minutes, consumed atomically, transported in URL fragment and removed before exchange. Local trusted CLI can issue the same link for an explicitly configured administrator. No password, user-ID impersonation, public registration, mock/demo login or browser localStorage credentials. Eight-hour opaque, hashed SQL sessions; HttpOnly SameSite=Strict cookie, Secure on HTTPS, localhost-only HTTP. Exact Origin plus CSRF header required for writes; authenticated reads recheck the configured administrator list. Logout revokes the session. No third-party scripts or Telegram SDK required. Configured public HTTPS URL enables remote access; default localhost remains private.

Migration adds optional Telegram display name/username metadata and auth tables, preserving all grants and data. Bot middleware refreshes identity from trusted Telegram updates. No private .env values or real account identities in source, screenshots or design prompts.

## Delivery
Keep existing dirty menu/settings/tests untouched. Continue on the existing user-requested feature branch. Build and run locally against TEST_DATABASE_URL only, document production HTTPS setup, verify API/security/concurrency on SQLite and isolated PostgreSQL schemas, verify responsive browser flows. Commit only this feature. Never merge/push/publish automatically.
