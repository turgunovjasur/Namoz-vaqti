# Roles, Capabilities and Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Execution is native in this chat, on codex/roles-capabilities. Steps use checkbox syntax for tracking.

**Goal:** Move existing bot functions into reusable capabilities and separately defined AI roles; add admin/user profiles, per-user role/capability grants, role model selection and the approved task/result/correction workflow.

**Architecture:** Keep the domain/application/infrastructure/presentation boundaries. Role definitions reference capability IDs; one shared executor per capability calls existing application services. Trusted SQL grants govern every entry point; durable tasks retain approved parameters, receipts and feedback across restarts.

**Tech Stack:** Python 3.12, aiogram 3, Pydantic, HTTPX, SQLAlchemy async, PostgreSQL, Alembic, APScheduler, pytest/SQLite, Ruff and mypy. Reuse installed dependencies.

**Spec:** [Role workforce design](../../superpowers/specs/2026-10-15-role-workforce-draft.md), commit d4917a2. Read the full spec before execution; the latest per-user capability requirement supersedes role-only grants.

## Global Constraints

- Work in codex/roles-capabilities, starting from d4917a2. Existing implementation stays on codex/voice-conversation.
- Only existing prayer, nasihat, reminder, accounting and settings domains ship; Bankchi/Doctor/Psixolog and external exchange/weather services were examples.
- There are exactly two profile types, admin and user. AI role IDs are independent of profile type.
- Admin assigns whole roles and separately enables capabilities within each assigned role. Missing grants deny access. Role/capability code is shared, never copied per user.
- Assistant and manager are permanent system roles. Specialist roles remain assignable; model settings are per role globally, not per user.
- Preserve persistent menus, voice in every manual state, text replies, exact stored voice approval, rejection without effects and new result messages.
- Keep source protocol V1 through adapters; do not silently reinterpret existing approved drafts. Add MAIN_AGENT_VERSION=3 for the completed orchestration; access checks also cover V1/V2 and disabled-AI/manual paths.
- Role and capability changes take effect at execution/commit and scheduled delivery boundaries. Permission checks use trusted user/bot IDs, never model-supplied identity.
- New users start without specialist grants. Migration explicitly grants existing users their previous roles/capabilities; later capabilities never become implicitly enabled.
- Atomic business effect + receipt; provider/reviewer/outbox retries never repeat a committed write. No secrets, audio, transcripts or financial amounts in logs.
- All timestamps are aware; user-facing time uses Asia/Tashkent. Review TTL remains 15 minutes. Internal answer revision has at most one retry.
- Use native execution and one final independent read-only branch review. Do not dispatch implementation subagents. No push, merge or server deploy.

## Review Focus

- Revoke a capability after its approval card was sent or after its task was claimed: no new effect under the revoked grant (Tasks 3, 5).
- A shared capability is disabled under one role but enabled under another: fresh requests work only through an authorized role, stale tasks never silently switch (Tasks 1, 3, 6).
- Reviewer/provider failure after a committed expense: report the saved result truthfully and never insert a second expense (Tasks 5–7).
- Noisy manual FSM, old callback, group message or V1 fallback: cannot bypass the same owner/grant checks or destroy earlier results (Tasks 3, 4, 6).
- Administrator changes a model while a task is pending: old task uses its frozen model/plan; new task uses the validated new model; invalid model keeps the old setting (Tasks 4–6).

## File ownership

- domain/workforce/: role/capability/profile/task values; no Telegram, SQLAlchemy or HTTP imports.
- application/roles/: seven small definition/instruction files and one registry; no provider/business implementation.
- application/capabilities/: typed interfaces, registry and adapters to existing finance/reminder/prayer/nasihat/settings services.
- application/workforce/: access, planning, execution, review, worker and feedback services.
- application/profiles/: profile views, admin changes and persistence ports.
- infrastructure/ai/: shared Gemini transport and role clients; old client classes become compatibility wrappers.
- infrastructure/workforce/: SQL grants, model settings, task transactions, leases and outbox.
- presentation/profiles/ and presentation/result_messages.py: common metadata/formatting; transport handlers stay thin.
- Add package __init__.py files together with working modules, not empty scaffolding commits.

## Task 1: Role and capability contracts with existing-service adapters

**Files:**
- Create domain/workforce/{roles,capabilities,profiles}.py.
- Create application/roles/{base,registry,assistant,manager,accountant,planner,prayer_calendar,adviser,settings}.py.
- Create application/capabilities/{base,registry,finance,reminders,prayer,nasihat,settings,preferences}.py.
- Modify application/menu_agents.py and application/conversation_actions.py for compatibility delegation.
- Test tests/unit/workforce/test_registry.py and tests/integration/test_capability_adapters.py.

**Interfaces:**
- CapabilitySpec: id, name, description, parameters_model, result_model, effect, entrypoints. Effects are read/write/generate; entrypoints are conversation/background.
- RoleDefinition: id, name, description, instruction, capability_ids, system_role. Retain specialist IDs prayer/nasihat/reminder/accounting/settings; add manager; assistant retains its system ID.
- CapabilitySelection: role_id, capability_id, validated parameters. No user ID supplied by the model.
- CapabilityRegistry.get(capability_id: str) -> Capability; RoleRegistry.get(role_id: str) -> RoleDefinition; validate unknown/duplicate references on construction.
- Capability.prepare(request: AgentRequest) -> AgentResult; Capability.execute(request: AgentRequest, transaction: AgentTransaction) -> AgentResult. Existing request data stays behind the bridge until Task 6.
- CapabilityDispatcher.prepare/execute satisfy the existing AgentActionExecutor port and dispatch by a single legacy domain/action/view -> capability mapping.

- [x] RED: registry tests reject duplicate IDs, unknown capability references and a model-selected action outside its role. Shared preferences.region_view/preferences.offsets_view resolve to the same executor for prayer and settings.
- [x] RED: adapter tests prove existing expense, reminder, prayer and nasihat calls preserve parameters, owner and receipt/source keys.
- [x] Run ./.venv/bin/pytest -q tests/unit/workforce/test_registry.py tests/integration/test_capability_adapters.py; confirm failures target missing contracts/adapters.
- [x] Implement the seven role files as metadata plus instructions. Extract common instruction text once. Keep new example roles/providers out of the catalog.
- [x] Implement one executor per capability using existing services, with a single compatibility mapping. Register new IDs finance.correct and reminder.update only when Task 7 supplies their working implementations; the frozen legacy migration list excludes them.
- [x] Separate background capability IDs settings.deliver_daily, nasihat.deliver and reminder.deliver from conversation invocation. Register them in owner roles but exclude them from the model's callable schema.
- [x] GREEN: run the new tests plus tests/unit/application/test_menu_agents.py, tests/integration/test_voice_agent_actions.py and tests/acceptance/test_menu_agent_journey.py.
- [x] Commit feat: define reusable role and capability registries.

## Task 2: Shared Gemini transport and common result presentation

**Files:**
- Create infrastructure/ai/gemini_client.py and presentation/result_messages.py.
- Modify infrastructure/{gemini,gemini_main_agent,gemini_menu_agents,gemini_accounting,gemini_voice}.py.
- Modify presentation/main_agent.py, presentation/voice_conversation.py and presentation/voice_approval.py.
- Test tests/unit/infrastructure/test_gemini_transport.py and tests/unit/presentation/test_result_messages.py; retain existing Gemini tests.

**Interfaces:**
- GeminiClient.generate_json(*, model: str, instruction: str, schema: dict[str, JsonValue], parts: list[dict[str, JsonValue]], max_output_tokens: int) -> dict[str, JsonValue].
- render_result(result: AgentResult) -> str and render_interpretation(transcript: str, selection: CapabilitySelection, registry: CapabilityRegistry) -> str. Telegram keyboards remain separate from business formatting.
- Each old client keeps its public extract/generate signature and strict domain validation, delegating HTTP/parsing to GeminiClient.

- [x] RED: parameterized transport tests cover HTTP/timeout errors, malformed/truncated/multiple text parts, thought exclusion, oversize response and secrets absent from errors. Assert request body/schema/temperature/timeouts match existing contracts.
- [x] RED: existing finance/reminder/prayer result examples render the same facts in both legacy and conversation paths; nasihat original quotation/source remains unchanged.
- [x] Run ./.venv/bin/pytest -q tests/unit/infrastructure/test_gemini_transport.py tests/unit/presentation/test_result_messages.py and inspect expected failures.
- [x] Implement shared transport and formatter; remove copied HTTP/JSON/error bodies from callers. Preserve per-client response validation and cooldown behavior.
- [x] GREEN: run tests/unit/infrastructure/ plus tests/acceptance/test_voice_conversation.py and tests/acceptance/test_voice_approval.py.
- [x] Commit refactor: share Gemini transport and result rendering.

## Task 3: SQL profiles, grants and one access policy across every entry point

**Files:**
- Create application/profiles/ports.py, application/workforce/access.py and infrastructure/workforce/profiles.py.
- Modify infrastructure/orm.py, infrastructure/session_scope.py and config.py.
- Add alembic/versions/20261015_01_profiles_roles.py after 20261013_01.
- Modify presentation/middleware.py, application/reminders.py, application/daily_schedule.py, application/religious_reminders.py and main.py wiring.
- Create tests/helpers/workforce.py; adapt existing SQL journey setup to explicitly grant its synthetic users legacy access.
- Test tests/integration/test_workforce_access.py, tests/integration/test_workforce_migrations.py and tests/acceptance/test_access_boundaries.py.

**Interfaces:**
- PermissionSnapshot: user_id, role_id, capability_id, assignment_revision. It cannot grant identity or access by itself.
- AccessService.allowed(user_id: int, role_id: str, capability_id: str) -> bool; available_roles(user_id: int) -> tuple[RoleDefinition, ...]. Available descriptions/schemas contain only enabled capabilities.
- AccessService.effect_scope(user_id: int, role_id: str, capability_id: str) -> AsyncContextManager[AgentTransaction]. Lock the owner row and recheck grants in the same session as business effects; admin updates lock that row too.
- PermissionTransaction extends AgentTransaction with current_grant(user_id: int, role_id: str, capability_id: str) -> PermissionSnapshot|None. AccessService.require_in(transaction: PermissionTransaction, user_id: int, role_id: str, capability_id: str) -> PermissionSnapshot reuses the same policy inside an already opened business transaction.
- ProfileRepository.get_profile(user_id: int) -> ProfileView; set_grants(*, actor_id: int, user_id: int, role_id: str, enabled: bool, capability_ids: frozenset[str], expected_revision: int) -> ProfileView. Validate actor admin status server-side.
- ADMIN_TELEGRAM_IDS is a validated set of Telegram integer IDs from trusted server settings; missing configuration promotes nobody. Sync the stored profile type from this source; a stale database flag cannot retain admin access after its trusted configuration is removed. Ordinary users cannot edit profile_type.
- Tables: profiles, user_role_assignments, user_role_capabilities, role_model_settings and admin_audit. Unique grant key is user_id/role_id/capability_id; absent grant denies.

- [ ] RED: SQLite/PostgreSQL tests assign different capabilities to two users under one role. Assert unassigned capability, wrong owner, non-admin change and unknown capability all deny; role toggle preserves but suspends its selected capabilities.
- [ ] RED: commit/revoke race test serializes on the same user lock; a revocation completed before execution prevents the effect. Disabling a shared capability under prayer leaves an independently enabled settings grant working.
- [ ] RED: upgrade a populated pre-profile database; existing five roles/current capabilities are explicitly granted, later capabilities and fresh users have no implicit grants. Downgrade removes only workforce tables.
- [ ] RED: manual menus, group messages, legacy callbacks and V1/disabled-AI paths cannot bypass access. Only test fixtures may seed synthetic assigned users; production /start never grants specialist access automatically.
- [ ] RED: daily/nasihat/reminder delivery pauses when its owner role/capability is disabled, keeps underlying data and resumes future schedules without a backlog flood.
- [ ] Run the three new suites; verify failures are caused by absent grants/persistence/gates.
- [ ] Implement SQL migration with a frozen legacy grant list; do not import a mutable runtime registry from migrations. Add one AccessService policy and thin boundary calls, not copied authorization conditions in each handler.
- [ ] Use the existing session binding mechanism for transaction-scoped business repositories. Do not hold SQL locks across Gemini or Telegram requests. Invalidate grant caches by assignment revision on every admin change.
- [ ] GREEN: run new suites, tests/integration/test_postgres_claims.py, test_agent_migrations.py and affected scheduler/manual acceptance journeys.
- [ ] Commit feat: persist profiles and enforce role capability grants.

## Task 4: Admin/user profile screens and per-role model settings

**Files:**
- Create application/profiles/service.py, presentation/profiles/{router,views,keyboards}.py and infrastructure/ai/model_catalog.py.
- Modify presentation/keyboards.py, config.py and main.py.
- Test tests/acceptance/test_profile_journey.py and tests/integration/test_role_model_settings.py.

**Interfaces:**
- ProfileService.self_view(actor_id: int) -> ProfileView; user_view(actor_id: int, user_id: int) -> ProfileView; list_users(actor_id: int, *, after_id: int, limit: int) -> UserPage.
- ProfileService.set_grants uses Task 3's signature. Persist role toggle and selected capabilities atomically; optimistic revision rejects old cards.
- RoleModelSetting: role_id, model_id, version. ProfileService.set_model(*, actor_id: int, role_id: str, model_id: str, expected_version: int) -> RoleModelSetting.
- ModelCatalog.list_for_role(role_id: str) -> tuple[ModelOption, ...]; validate(model_id: str, role: RoleDefinition) -> None. Use configured model allowlist plus provider capability/structured-output probe; no business service is invoked.
- Profile views render names/descriptions/capabilities from the same registries. No copied role information in Telegram callbacks or UI strings.

- [ ] RED: admin selects a user, enables a role and a capability subset, saves and sees it after restart; user sees only its own enabled roles/capabilities. A user with zero selected capabilities sees that state and receives no business route.
- [ ] RED: forged admin callbacks, another user's profile ID and stale save revision cannot change grants; changing grants never reveals user financial records to the administrator.
- [ ] RED: callback data remains at most 64 bytes, including long user/model/capability IDs. Use an opaque compact token with trusted owner-bound UI state for nested selection, never embed an entire grant payload in callback data.
- [ ] RED: model changes apply globally to future tasks for the selected role only; invalid/unsupported models or a failed provider probe leave the last valid setting. No API key appears in profile views or logs.
- [ ] Run ./.venv/bin/pytest -q tests/acceptance/test_profile_journey.py tests/integration/test_role_model_settings.py; inspect RED failures.
- [ ] Implement persistent Profil/Yordam entry points, admin user/role/capability navigation and role catalog/model card. Hide admin controls for ordinary users and verify every mutation in the service, not only the keyboard.
- [ ] GREEN: run new suites and tests/unit/presentation/test_keyboards.py plus tests/acceptance/test_hidden_menu.py and tests/acceptance/test_voice_approval.py.
- [ ] Commit feat: add admin and user role management profiles.

## Task 5: Durable tasks, atomic execution, leases and result outbox

**Files:**
- Create domain/workforce/tasks.py, application/workforce/{ports,execution,worker}.py and infrastructure/workforce/{tasks,queue,outbox}.py.
- Add alembic/versions/20261015_02_workforce_tasks.py after Task 3's migration; extend infrastructure/orm.py.
- Modify main.py startup/shutdown wiring and infrastructure/telegram.py for outbox delivery.
- Test tests/integration/test_workforce_tasks.py, tests/integration/test_workforce_worker.py and tests/integration/test_workforce_outbox.py.

**Interfaces:**
- TaskPlan: protocol_version=2, task_id, revision, trusted AgentContext, PermissionSnapshot, role definition/instruction version, RoleModelSetting snapshot, CapabilitySelection, transcript, expires_at. Freeze the approved arguments and model; do not call the model to reconstruct them at approval.
- TaskStatus: draft/needs_input/awaiting_approval/queued/running/reviewing/awaiting_feedback/awaiting_correction/done/cancelled/failed.
- TaskRevision: task_id, revision, parent_revision, plan, status, service_result: AgentResult|None, review: ReviewVerdict|None, feedback: str|None. ReviewVerdict has decision=accept|revise|clarify and bounded issues, not hidden reasoning.
- TaskStore.save_plan(plan: TaskPlan, *, expected_revision: int|None) -> TaskRevision; get_owned(task_id: str, context: AgentContext) -> TaskRevision; approve(task_id: str, revision: int, context: AgentContext, request_id: str, accept: bool) -> TaskRevision.
- TaskStore.effect_scope(task_id: str, revision: int, lease_token: str) -> AsyncContextManager[TaskTransaction]. TaskTransaction extends PermissionTransaction with save_result(result: AgentResult) -> None, saving receipt/task state/outbox in the same SQL transaction. Call AccessService.require_in on this transaction; never nest an independently committing effect_scope.
- Queue.claim(*, now: datetime, limit: int, lease_seconds: int) -> list[ClaimedTask]; heartbeat(task_id: str, token: str, now: datetime) -> bool. Outbox.send_due(sender: MessageSender) -> None never runs a business capability.
- Worker.run_once(now: datetime) -> None. Claim at most 3 tasks; lease 180 seconds, heartbeat every 30 seconds; existing APScheduler polls every second with max_instances=1. Shutdown cancels workers and closes sessions cleanly.

- [ ] RED: approval atomically queues the exact saved plan and one acceptance notification; rejection leaves zero business rows. Foreign user/bot, old revision, expired 15-minute review and duplicate update never queue another effect.
- [ ] RED: two PostgreSQL workers cannot commit the same expense; revoke capability between approval and claim prevents writing. Revoke/commit uses Task 3's same owner lock.
- [ ] RED: simulate crashes before commit, after commit/before review and after Telegram send/before delivery acknowledgement. Business receipt remains exactly once; restart resumes review/delivery from stored state.
- [ ] RED: model changes after approval do not mutate the pending task. A lost lease cannot commit effects or overwrite another worker's result.
- [ ] Run the new integration suites against SQLite and configured PostgreSQL; confirm RED failures address missing durable transitions/locks.
- [ ] Implement tables for task revisions, business receipts, claims and outbox. Keep provider/Telegram awaits outside effect transactions. Store one effect key per task/revision and a unique outbox key per notification type/revision.
- [ ] Preserve safe external-delivery semantics: Telegram can receive a retry after an ambiguous network acknowledgement; never claim exactly-once remote delivery and never retry the business effect for that reason.
- [ ] GREEN: run new suites plus tests/integration/test_agent_sessions.py, test_main_agent_operations.py and test_postgres_claims.py.
- [ ] Commit feat: execute approved tasks durably with receipts and outbox.

## Task 6: Assistant, manager and specialists over the shared runtime

**Files:**
- Create application/workforce/{planning,manager,review}.py and infrastructure/ai/{transcription,role_interpreter,result_reviewer}.py.
- Modify application/roles/{assistant,manager}.py, application/main_agent.py, application/voice_approval.py, presentation/voice_conversation.py, config.py and main.py.
- Test tests/unit/workforce/test_manager.py, tests/unit/infrastructure/test_workforce_ai.py and tests/acceptance/test_workforce_journey.py.

**Interfaces:**
- Transcriber.transcribe(audio: bytes, mime_type: str) -> str; RoleInterpreter.interpret(*, text: str, context: AgentContext, role: RoleDefinition, capabilities: tuple[CapabilitySpec, ...], pending: TaskRevision|None) -> CapabilitySelection.
- Manager.plan(*, context: AgentContext, request_id: str, text: str, pending: TaskRevision|None) -> TaskPlan. The manager routes using only Task 3's allowed role/capability descriptions; programmatic replies receive the same strict validation as provider JSON.
- ResultReviewer.review(plan: TaskPlan, result: AgentResult) -> ReviewVerdict. Validate allowed verdict and bounded issues; source evidence remains the canonical result data.
- Manager.review_result(task: TaskRevision) -> TaskRevision. At most one additional read/render attempt with unchanged approved parameters. Writes never repeat; changed parameters require a new plan/approval.
- AssistantService.receive(context: AgentContext, request_id: str, *, text: str|None, audio: bytes|None, mime_type: str) -> ConversationReply. Reply contains text, persistent menu and typed approval/feedback callback descriptors; Telegram-specific classes stay in presentation.
- MAIN_AGENT_VERSION accepts 1/2/3; retain default 2 until Task 8 activation. Version 3 uses this runtime; versions 1/2 retain their parsers behind the common access policy.

- [ ] RED: voice -> one transcription -> manager -> only selected specialist -> stored Eshitdim/Tushundim card. Before Ha, no business read/write. After Ha, queue acknowledgement and result arrive as new messages.
- [ ] RED: a user granted only finance.report cannot trigger finance.expense through a misleading prompt, another role name or forged model output. Shared preferences capability uses the explicitly named permitted role; ambiguity asks a question.
- [ ] RED: user speaks from a manual FSM; menus stay visible, current result history survives and only the new voice approval may execute. Failed download/oversize/new provider error retires the previous approval.
- [ ] RED: reviewer rejects wrong month/currency/category; only safe re-read/render occurs. A provider failure after expense commit produces a truthful saved receipt plus incomplete-review notice, not a second expense or a false failure-to-save claim.
- [ ] RED: current V1/V2 drafts resume through adapters after upgrade; no cached approval is silently converted into a different operation or model decision.
- [ ] Run the three new suites, inspect relevant missing-runtime failures and preserve existing manual/voice assertions.
- [ ] Implement transcription separately from routing. Generate role descriptions and output schemas from the narrowed registries; do not maintain new parallel role lists or ACTION_LABELS tables.
- [ ] Render data facts with Task 2's formatter. Reviewer can identify issues and request safe work; it cannot invent totals, prayer times, quotation text or source references.
- [ ] Wire version 3 into create_application with existing event isolation. Route task-bound approvals by owner/bot/revision; keep legacy vr/ag callbacks through their compatibility handlers.
- [ ] GREEN: run new suites plus tests/acceptance/test_voice_approval.py, test_voice_conversation.py, test_menu_agent_journey.py and test_hidden_menu.py.
- [ ] Commit feat: separate assistant manager and specialist execution.

## Task 7: Result feedback and corrections linked to original records

**Files:**
- Create application/workforce/feedback.py and domain/workforce/corrections.py.
- Modify application/capabilities/{finance,reminders,settings}.py, application/{accounting,reminders}.py and infrastructure/{accounting,reminders,orm}.py.
- Add alembic/versions/20261015_03_workforce_corrections.py after Task 5's migration.
- Modify presentation/result_messages.py and presentation/voice_conversation.py.
- Test tests/integration/test_workforce_corrections.py and tests/acceptance/test_workforce_feedback.py.

**Interfaces:**
- FeedbackService.rate(*, context: AgentContext, task_id: str, revision: int, accepted: bool, request_id: str) -> ConversationReply.
- FeedbackService.correct(*, context: AgentContext, task_id: str, revision: int, text: str, request_id: str) -> TaskPlan. Voice corrections first pass Task 6's transcriber and then the same exact-plan approval.
- FinanceCorrection: original_entry_id, expected_record_revision, replacement: AccountingRequest. LedgerService.correct(user_id: int, correction: FinanceCorrection, source_key: str, now: datetime) -> LedgerEntry.
- ReminderCorrection: original_reminder_id, expected_record_revision, replacement: ReminderSpec. ReminderService.update(user_id: int, correction: ReminderCorrection, source_key: str) -> Reminder.
- LedgerService.summary(user_id: int, month: date, *, category: Category|None = None) -> LedgerSummary; preserve existing calls when category is omitted. Filter the requested category totals and label them explicitly; account opening/closing balance remains the actual whole-ledger balance. Never present a category subtotal as the account balance.
- New capability IDs finance.correct and reminder.update require explicit grants; migration does not automatically grant newly added capabilities. Settings corrections reuse their existing update capability after a new approval.

- [ ] RED: result Ha ends the task; result Yo‘q only asks for the error and changes no business data. Correction text uses original task/parameters/evidence and creates a new revision; unrelated request creates a different task.
- [ ] RED: voice correction shows Eshitdim/Tushundim before rerunning; result and feedback buttons are new messages. Old revision/foreign callbacks cannot rate or alter the latest result.
- [ ] RED: “only food expenses” changes the report filter and returns only that category. No existing ledger entries are inserted/changed by report correction.
- [ ] RED: correct an expense amount: cancel/supersede original + linked replacement + audit + receipt commit together; failure rolls back all parts, retry returns the same result, concurrent target change requests fresh confirmation.
- [ ] RED: edit an existing reminder time without creating a duplicate reminder; recompute pending delivery safely. Delivered messages remain historical, expired old claim cannot send a superseded occurrence.
- [ ] RED: revoked capability, another user's record, cancelled target or unsupported correction cannot execute; a saved original expense is never recreated merely because result feedback is negative.
- [ ] Run new suites against SQLite/PostgreSQL and inspect the expected missing correction/feedback failures.
- [ ] Implement correction revision/audit fields and atomic methods using the existing transaction. Preserve old source/receipt identity and ledger history; use one new effect key for the correction revision.
- [ ] Implement feedback prefixes separate from execution approval. Payloads contain compact task ID/revision/action, remain within Telegram's 64-byte limit and carry no model-supplied owner identity.
- [ ] GREEN: run new suites plus tests/integration/test_accounting.py, test_reminder_repository.py and prior voice-approval acceptance tests.
- [ ] Commit feat: review task results and apply confirmed corrections safely.

## Task 8: Whole-branch verification, one review and local activation

**Files:**
- Modify README.md, config.py and the spec/plan completion evidence.
- Test existing full tests/ plus all new workforce suites.

- [ ] Run ./.venv/bin/ruff check src tests alembic, ./.venv/bin/mypy src/namoz_bot and git diff --check. Fix source/type issues before claiming success.
- [ ] Run the full suite with NAMOZ_TEST_DATABASE_URL pointing to an isolated test database; all SQL integration fixtures must create/drop their own random schemas, not operate on the running bot's data. Record actual counts and expected skips.
- [ ] Commit the complete source. Request one independent read-only immutable review of d4917a2..HEAD, covering role/capability ACLs, reused capability execution, provider facts, restart/rollback and manual/V1 compatibility. No implementation subagents or repeated review loops.
- [ ] Reproduce each accepted finding RED, fix it GREEN, then run affected tests and one final full suite/static check. Record declined-scope rulings explicitly.
- [ ] Set default MAIN_AGENT_VERSION=3 only with the completed runtime. Update examples for ADMIN_TELEGRAM_IDS/model allowlist without inserting real keys or IDs into tracked files.
- [ ] Verify the real administrator ID is already supplied by trusted local settings; if it is missing, finish code/tests and ask for that single value before activating admin access. Never guess a production/local user identity from unrelated records.
- [ ] Gracefully stop the verified old local bot, apply approved local migrations and start the new test bot. Confirm one process, version 3, enabled role/capability checks and expected test bot identity without printing private chat content.
- [ ] Use synthetic provider/Telegram journeys for behavior verification. A live extraction-only smoke can use synthetic input; do not send real user messages or create real financial records as a test.
- [ ] Commit documentation with actual test and activation evidence. Report the new branch, final commit, tests and any required input; no push/merge/server deploy.

## Self-review and handoff

- Registry, capability adapter, access, profiles and model ports are defined before their consumers.
- Existing business services remain the data source; example external capabilities are out of scope.
- All five review-focus failure classes have RED/GREEN coverage in their owning tasks.
- No user-specific role implementation or capability executor is duplicated. Test fixtures grant synthetic users explicitly; defaults do not weaken production authorization.
- Design accepted by the request to preserve current code and do the new logic on a separate branch. This implementation plan is the next reviewable artifact; do not begin product code until its review is received.
