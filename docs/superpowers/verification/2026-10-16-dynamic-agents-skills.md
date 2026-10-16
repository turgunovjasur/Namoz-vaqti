# Dynamic agent roles and skill plugins — verification

## Delivered behavior

Admin can create/edit a role's name, task, Gemini model, common rules, enabled state
and reusable skill links. The template is copied into new roles only. User grants
remain separate and are never added automatically. Seven existing roles and their
identities survive migration; manager settings remain historical, while Yordamchi
coordinates new work. Each specialist has an immutable role/model/skill configuration;
conversation context is passed per owner and role.

Native skills live in trusted backend modules, with typed input/output, explicit
execution context, renderer and durable operation identity. Existing business skills
remain supported through adapters. See [development guide](../../skills-development.md).

## Backend verification

- Full suite before final review: **872 passed, 7 expected skips** on isolated
  PostgreSQL and SQLite. Final post-fix suite: **876 passed, 8 expected skips** (150.55s).
- Ruff, Python formatting, mypy: pass. React/TypeScript production build and
  Prettier checks: pass.
- Migration test upgrades an existing grant/model configuration, checks preservation,
  and downgrades without deleting preexisting grants.
- Global-off/skill removal is authoritative even inside an old request snapshot.
  Removed/re-added skills never restore old user grants.
- PostgreSQL tests serialize catalog/grant/effect edits. Approval and effects reject
  changed role revisions and grant revisions.
- Native discovery, duplicate IDs, identity injection, typed output, task-bound
  receipts, worker recovery, dynamic role planning/execution are covered.
- Real Gemini read-only probes passed for independent integer+nested-object and
  string+nested-object skill schemas, and the existing no-parameter balance skill.
  No business skill was executed by those probes.

## One fresh review and one fix pass

Reviewed immutable range `438d973..4d155db`. Five Important findings accepted,
no Critical findings, no deferred minors, no behaviors declined for judgment.

1. Role/model writer race: both writers now acquire the catalog lock. PostgreSQL
   owner-lock race test reproduced a lost update (RED), then one writer conflicted
   correctly (GREEN).
2. Dynamic manual finance: expense and undo resolve an authorized role and preserve
   it through the transaction. Dynamic-only, operation-only grant journeys RED→GREEN.
3. Skill parameter collisions: complete alternative parameter shapes preserve types,
   nested properties and required fields. Conflicting native schemas RED→GREEN;
   existing no-parameter provider compatibility restored and retested.
4. Stale user catalog: opening/recovering profiles fetches both catalog and profile;
   HTTP400 and409 provide recovery. Browser stale400 recovery RED→GREEN and new role
   appears on reopening without a page reload.
5. Global role disable: existing enabled user assignments can still be revoked;
   new enabling remains disabled. Browser revoke control RED→GREEN.

Relevant regression tests:
`tests/integration/test_dynamic_authorization.py`,
`tests/acceptance/test_dynamic_manual_finance.py`,
`tests/unit/infrastructure/test_dynamic_role_agents.py`,
`tests/unit/infrastructure/test_workforce_ai.py`.

## Browser QA

Environment: synthetic SQLite accounts only, `http://127.0.0.1:8090`, desktop
1440×1000 and mobile390×844. Browser plugin not available; used the available
Playwright tools. The tested flow was authenticated panel → create role → select
model/rules/skill → assign user → edit → conflict recovery → template → reload.

| Check | Result |
|---|---|
| Page identity/title | Pass, Yordamchi Admin panel |
| Meaningful content, blank-page check | Pass |
| Framework overlay | None |
| Console health | No framework errors; expected HTTP400/409 from deliberate stale writes |
| Screenshot evidence | Desktop and mobile visually inspected |
| Interaction proof | Create, assign, edit, conflict, template, stale recovery and global-off revocation pass |
| Responsive overflow | None at tested viewports |

Screenshots outside repository:
`/private/tmp/dynamic-role-final-desktop.png`,
`/private/tmp/dynamic-role-editor-mobile.png`.

Browser/type-script build commands: `npm run build --prefix web/admin`,
`npm run format:check --prefix web/admin`. Python checks:
`.venv/bin/ruff check src tests alembic`,
`.venv/bin/ruff format --check src tests alembic`,
`.venv/bin/mypy src/namoz_bot`.

## Activation

Activated after tests. Target explicitly verified as TEST bot8922089476,
`@TestUzNamozTaqvimiBot`, database `namoz_test_dev1_20260923`.
Migration `20261016_01` seeded seven roles. Every existing user/grant/model,
reminder and ledger record compared identical before/after: 1 user, 5 role
assignments, 25 user skill links, 0 model overrides, 8 reminders, 4 finance entries.
Local polling confirmed the same TEST bot identity; admin served on
`http://127.0.0.1:8088`. Authenticated read-only UI check passed: health=ok, seven roles, 25 skills,
Yordamchi active, manager reserved, no synthetic/custom roles added to the TEST
catalog. The role form opened correctly and the live page console had zero
errors/warnings. Screenshot: `/private/tmp/dynamic-live-admin-role-form.png`.
No production activation, push or merge performed.

## Decisions and limits

- Ruling: plugin discovery belongs to the infrastructure composition root
  (`build_runtime_capabilities`); the application registry accepts injected skills.
  This keeps application code independent of infrastructure. Cost of a missed
  composition hook: that process would not offer the skill; discovery tests and
  shared bot/admin bootstrap cover the configured entrypoints.
- New plugin code requires restarting bot and admin. Ordinary catalog/rule/grant
  edits are loaded on the next request across independent processes.
- Native write idempotency is a developer obligation, including external providers;
  setting a boolean does not create distributed transaction guarantees.
- Language interpretation is provider dependent. Tools remain deny by default and
  canonical skill evidence is preserved; perfect semantic classification is not
  claimed.
- Browser coverage is Chromium at the listed viewports; Safari/Firefox and real
  Telegram microphone interaction were not exercised in this change.
- Existing unrelated menu/settings changes and `output/` were preserved and excluded
  from this feature's commits. Feature remains on `codex/roles-capabilities` as requested.
