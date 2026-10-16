# Dynamic agents and skills implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; one whole-feature fresh review at the end.

**Goal:** Deliver admin-created Gemini specialist roles over reusable typed skill plugins, preserving existing behavior and data.
**Architecture:** SQL versioned role catalog -> scoped immutable registry -> per-role Gemini agent factory -> common guarded skill execution. Existing adapters remain compatible; admin forms edit role configuration, not executable code.
**Tech Stack:** Python3.12/SQLAlchemy/PostgreSQL/FastAPI/Gemini, React/TypeScript/Vite.
**Spec:** docs/superpowers/specs/2026-10-16-dynamic-agents-skills.md

## Global Constraints
Preserve all existing role/skill IDs, models, grants and audit data. No example integrations. No hard delete. New role/skill links never auto-grant. All real local activation uses verified TEST credentials only. Preserve unrelated dirty files. Keep current feature branch, no merge/push. Execute natively under the user's continuing delegated authorization.

## Review Focus
- Concurrent catalog/grant/effect updates must share lock order and reject revoked scope; new tests in Task2/3.
- Independent bot/web processes must see changes without leaking snapshots across requests; tests in Task2/4.
- New native skill and new role must work without editing action/domain switches; tests in Task1/4.
- Mutating common rules or model must not silently change already approved work; tests in Task3/4.
- Unsaved forms, malformed payloads, duplicate names/IDs, stale catalog/user editors and disabled role states must remain understandable; HTTP/browser tests Task5.

### Task 1: Typed extensible skill execution
Files: application/skills/{contracts,native}.py; infrastructure/skills/{loader,dependencies}.py; infrastructure/skills/plugins/__init__.py; application/capabilities/{base,registry}.py; domain/workforce/capabilities.py; domain/agent_protocol.py; workforce/execution.py; presentation/result_messages.py; tests/unit/skills/test_native_skills.py; tests/integration/test_native_execution.py.
Interfaces: NativeSkill(spec, execute, render); SkillCall owner-bound context + parameters + idempotency key; build_capability_registry(..., skill_dependencies=None) discovers trusted plugins; capability.prepare_plan/execute_plan bridges both native and legacy.
- [ ] Write native output/input validation, duplicate/discovery and execution tests; run RED for missing SDK.
- [ ] Implement SDK, deterministic trusted loader and generic persisted envelope; keep legacy behavior through adapter methods.
- [ ] Run targeted native and existing workforce execution tests GREEN; commit.

### Task 2: Persisted role catalog and management
Files: domain/workforce/roles.py; application/roles/{catalog,runtime,ports}.py; registry.py; infrastructure/roles/{repository,management}.py; infrastructure/orm.py; migration20261016_01; tests/integration/test_dynamic_roles.py; tests/integration/test_dynamic_role_migration.py.
Interfaces: RoleWrite(name,description,rules,capability_ids,model_id,enabled,expected_revision,expected_model_version); RoleCatalogService create/update/template; SqlRoleCatalog.scope binds immutable RoleRegistry snapshot. Stable generated role IDs, rules template copied at creation.
- [ ] Write migration/grant-preservation, protected role, CRUD, stale/re-add/no-autogrant tests; run RED.
- [ ] Implement SQL tables/seed migration, scoped registry, atomic catalog/model/grant changes and audit; validate external model only when changed.
- [ ] Run SQLite/PostgreSQL tests GREEN; commit.

### Task 3: Authoritative dynamic authorization and delivery
Files: workforce/access.py; infrastructure/workforce/profiles.py; infrastructure/agent_sessions.py; infrastructure/workforce/tasks.py; presentation/middleware.py; application/{broadcasting,daily_schedule,religious_reminders,reminders}.py; tests/integration/test_dynamic_authorization.py.
Interfaces: AccessService.role_scope; available_roles excludes global disabled roles; allowed_any checks role-independent background skill grants; current_grant enforces global catalog membership and task role revision within existing owner-serialized effects.
- [ ] Write refresh/isolation, global-off, pending revision and PostgreSQL revocation race tests; run RED.
- [ ] Wire scoped runtime into bot/background boundaries, preserve legacy standalone tests and fixed-menu compatibility; serialize grant/catalog writes in consistent order.
- [ ] Run dynamic and existing access/delivery tests GREEN; commit.

### Task 4: Separate Gemini specialists and assistant orchestration
Files: infrastructure/ai/{role_agent,agent_factory,role_interpreter}.py; application/capabilities/guidance.py; capability metadata; application/workforce/{planning,assistant,execution}.py; infrastructure/workforce/bootstrap.py; main.py; tests/unit/infrastructure/test_dynamic_role_agents.py; tests/acceptance/test_dynamic_agent_journey.py.
Interfaces: AgentFactory resolves immutable role/model/scoped skill configuration; specialist context limited to its role; new orchestration uses assistant model while historical manager settings remain readable. Generic planning works with native skills without legacy routes.
- [ ] Write two role/model/pending-context isolation and native role end-to-end tests; run RED.
- [ ] Implement factory and modular interpretation, per-skill guidance, shared composition and dynamic model fallback; enforce current role revision before approvals/effects.
- [ ] Run old/new workforce AI and journeys GREEN; commit.

### Task 5: Admin role forms and skill catalog
Files: presentation/admin_web/{role_routes,role_views,schemas,app}.py; web/admin/src/{RoleEditor,RolesPage,RuleTemplateEditor,types,App,HistoryPage,UserEditor}.tsx/ts; CSS; tests/integration/test_dynamic_role_api.py.
Interfaces: GET /api/skills; POST /api/roles; PUT /api/roles/{id}; GET/PUT /api/role-template; existing role response gains revision/rules/enabled/agent identity/model version; old consumers remain compatible.
- [ ] Write authenticated create/update/template/conflict tests using real SQL; run RED.
- [ ] Add modular API and responsive editable role/template forms with fresh catalog refresh, protected-system roles, explicit user-grant separation and audit summaries. Follow existing design, no redesign.
- [ ] Build/type-check/format; browser real synthetic role-create -> assign -> edit -> conflict -> template -> refresh at desktop/mobile; commit.

### Task 6: Documentation, activation and final review
Files: docs/skills-development.md; README.md; docs/superpowers/verification/2026-10-16-dynamic-agents-skills.md.
- [ ] Document one-folder native plugin recipe, I/O/idempotency and role migration/agent behavior; full pytest on isolated PostgreSQL, Ruff/mypy/format, frontend build.
- [ ] One fresh whole-feature read-only review; Important findings get a single RED→GREEN fix pass, minors recorded.
- [ ] Migrate verified TEST database preserving grant/model counts, restart verified TEST services, verify own read-only admin UI. Keep branch, no public deployment.
- [ ] Commit only this feature, record evidence, remove only this plan's scratch workspace.
