# Main Agent V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Foydalanuvchi namoz, eslatma va kirim-chiqim xizmatlarini menyu tanlamasdan matn/ovoz orqali ishlata oladigan asosiy agentni yaratish.

**Architecture:** Bitta Gemini structured extraction, tekshiriladigan request/result protokoli va mavjud application xizmatlarini ishlatadigan adapterlar. Agent sessions/receipts database orqali saqlanadi; yangi yozuv, receipt va session yakuni bitta transactionda bajariladi. Telegram rendering biznes natijasini o‘zgartirmaydi.

**Tech Stack:** Mavjud Python >=3.12, aiogram 3, Pydantic, HTTPX, SQLAlchemy asyncio, Alembic, pytest/respx; yangi dependency yo‘q.

**Spec:** `docs/superpowers/specs/2026-10-13-main-agent-v1-design.md` (foydalanuvchi 2026-10-13 kuni tasdiqlagan).

## Global Constraints

- Protokol versiyasi `1`; action/domain katalogi spec 2-bo‘limida belgilangan.
- Timezone `Asia/Tashkent`; sana `YYYY-MM-DD`, oy `YYYY-MM`, vaqt `HH:MM`.
- Pul butun so‘m; mavjud `AccountingRequest.transaction()` tekshiruvlari saqlanadi.
- Audio maksimal 120 soniya va 5 MiB; maksimal input/transcript 2000 belgi.
- Bitta yangi matn/ovozli so‘rov uchun bitta Gemini extraction chaqiruvi.
- Eslatma faqat joriy revisionga tegishli `✅ Saqlash` tugmasi bilan yoziladi.
- Session TTL 24 soat; tugallangan request receipts TTL 7 kun.
- Logda audio, transcript, pul miqdori, draft va provider payload bo‘lmaydi.
- `MAIN_AGENT_ENABLED=true`; model `GEMINI_MAIN_AGENT_MODEL` yoki `GEMINI_VOICE_MODEL`.
- Gemini timeout connect/read/write/pool: 5/60/15/5 soniya; concurrency 3.
- Mavjud menu, legacy FSM, schedulers va agent o‘chirilgan yo‘llar ishlashi shart.
- Deploy va mavjud bazani migratsiya qilish alohida runtime amallari; ushbu reja avval kod va isolated test bazasini tayyorlaydi.

## Review Focus

- Moliyaviy yozuv bekor qilingandan keyingi eski request replayi uni faol yozuv sifatida qayta hisobga qo‘shmasligi (Task 2 va 4).
- Draft yig‘ilishida yarim tundan o‘tish: avval aytilgan sana saqlanishi, yangi nisbiy sana joriy message vaqtida yechilishi (Task 3).
- Legacy dialog uchun kutilgan matn agentga yutilmasligi; accounting holati yangi aniq namoz so‘rovini yutmasligi (Task 4).
- Saqlash bajarilib Telegram yuborish xato bo‘lsa, retry yozuvni takror yaratmasligi (Task 2 va 4).
- Restartdagi eski callback: user, operation, revision va expiry tekshiruvlari bilan haqiqiy draftgagina ta’sir qilishi (Task 3 va 4).

## Baseline va bajarish tartibi

Branch: `codex/main-agent-v1`; boshlang‘ich commit `0c69df0`.
Baseline: `./.venv/bin/pytest -q` → 380 passed, 43 skipped.
Skip sababi: PostgreSQL test URL yo‘q; buni implementation test natijasi bilan aralashtirmaslik.

Tavsiya etilgan bajarish: shu suhbatda native/inline, chunki vazifalar umumiy
protokol va transactional storega ketma-ket bog‘langan. Mavjud checkoutdagi branch
ishlatilishi mumkin; worktree uchun foydalanuvchining mavjud afzalligi tekshiriladi.
Har task RED → GREEN → verification → scoped commit bilan tugaydi.

---

### Task 1: Protokol va Gemini extraction

**Files:**
- Create: `src/namoz_bot/domain/agent_protocol.py`
- Create: `src/namoz_bot/infrastructure/gemini_main_agent.py`
- Create: `tests/unit/domain/test_agent_protocol.py`
- Create: `tests/unit/infrastructure/test_gemini_main_agent.py`

**Interfaces:**
- Produces: strict Pydantic `AgentContext`, `AgentDecision`, `AgentRequest`, `AgentResult`, `AgentSessionState`.
- `AgentContext`: `bot_id`, `telegram_user_id`, `chat_id`, `user_id`, timezone-aware `message_time`, `timezone`, `language`, `region_code`, `offsets: PrayerOffsets`.
- `AgentDecision`: `domain`, `action`, action-specific typed `parameters`, `transcript`, `clarification`, `multiple_tasks: bool`; untrusted identity fields are forbidden.
- `AgentRequest` and `AgentResult`: exact envelope fields/status/effect from spec sections 3–4. JSON serialization uses Pydantic JSON mode.
- `AgentSessionState`: `operation_id`, `origin_source_key`, `origin_time`, `domain`, `action`, typed `parameters`, `missing_fields`, `revision`, `expires_at`; no raw audio/full chat history.
- `GeminiMainAgentClient.extract(*, text: str | None, audio: bytes | None, mime_type: str, context: AgentContext, pending: AgentSessionState | None) -> AgentDecision`.

- [ ] Write parameterized tests `test_action_catalog_rejects_invalid_pair`, `test_provider_cannot_supply_owner`, `test_result_status_invariants`, `test_domain_parameters_reject_invalid_values`. Assert Pydantic ValidationError for unknown action, extra identity fields, false committed/done states, invalid time/month and noninteger money.
- [ ] Run `./.venv/bin/pytest -q tests/unit/domain/test_agent_protocol.py`; Expected: missing module fails collection.
- [ ] Implement strict protocol models; reuse `AccountingRequest`, `VoiceReminderDraft`, `PrayerKey`, existing region catalog validation and business constraints. Validate IDs/lengths, timezone-aware time and result status invariants.
- [ ] Write provider tests `test_text_extraction_is_one_call`, `test_audio_extraction_is_one_call`, `test_pending_fields_are_only_context`, `test_bad_json_never_becomes_request`, `test_identity_override_is_rejected`, `test_timeout_has_safe_error`, `test_oversized_voice_rejected_before_http`. Inspect actual mocked HTTP body and response parsing, not only mocks of internal methods.
- [ ] Run provider tests; Expected: missing client fails collection.
- [ ] Implement Gemini client using existing HTTPX/structured JSON conventions. Normalize text/audio exactly once, whitelist MIME, reject incomplete candidates and responses larger than 16000 characters, and expose safe `ExternalServiceError` only.
- [ ] Run `./.venv/bin/pytest -q tests/unit/domain/test_agent_protocol.py tests/unit/infrastructure/test_gemini_main_agent.py`; Expected: all pass.
- [ ] Commit protocol, provider and tests: `feat: add main agent protocol and structured extraction`.

### Task 2: Durable sessions, receipts va atomic effects

**Files:**
- Create: `src/namoz_bot/application/agent_sessions.py`
- Create: `src/namoz_bot/infrastructure/agent_sessions.py`
- Create: `src/namoz_bot/infrastructure/session_scope.py`
- Modify: `src/namoz_bot/infrastructure/orm.py`
- Modify: `src/namoz_bot/infrastructure/accounting.py`
- Modify: `src/namoz_bot/infrastructure/reminders.py`
- Create: `alembic/versions/20261013_01_agent_sessions.py`
- Create: `tests/integration/test_agent_sessions.py`
- Modify: `tests/integration/test_accounting.py`, `tests/integration/test_reminder_repository.py`

**Interfaces:**
- Consumes: Task 1 context, request, result and session models.
- Produces: `AgentStore.get_session(user_id: int, now: datetime) -> AgentSessionState | None`, `get_receipt(user_id: int, request_id: str) -> AgentResult | None`, `cleanup(now: datetime) -> None`.
- Produces: async-context-manager `AgentStore.transaction(user_id: int, expected_revision: int | None) -> AsyncIterator[AgentTransaction]`.
- `AgentTransaction` exposes `ledger: LedgerService`, `reminders: ReminderService`, `save_session(state: AgentSessionState | None) -> None`, `save_receipt(result: AgentResult) -> None`; transaction rollback covers all four resources. Revision conflict raises domain `AgentRevisionConflict` before effects.
- Existing ledger/reminder repository constructors accept optional `session: AsyncSession | None = None` after existing factory argument; default behavior unchanged. `session_scope(factory, session, *, write: bool)` reuses supplied session without independently committing; otherwise reproduces existing factory scopes.

- [ ] Write real SQLite tests `test_draft_survives_store_recreation`, `test_other_user_has_no_session_or_receipt`, `test_expired_draft_is_removed`, `test_receipts_expire_after_seven_days`, `test_stale_revision_rolls_back`, `test_write_and_receipt_rollback_together`, `test_duplicate_origin_creates_one_entry`, `test_duplicate_creation_token_creates_one_reminder`, `test_cancelled_entry_is_not_reactivated`. Assert actual table row counts, balances, saved revisions and receipt contents.
- [ ] Run `./.venv/bin/pytest -q tests/integration/test_agent_sessions.py`; Expected: missing store fails collection.
- [ ] Add sessions table keyed by user ID and receipts unique on user/request ID, timezone-aware expiry fields and bounded JSON data. Migration `20261013_01` follows `20261012_01`; preserve existing data.
- [ ] Implement session scope helper and optional bound sessions for ledger/reminder repositories. Reuse existing create/source-key and creation-token conflict handling; avoid copying ledger arithmetic or reminder scheduling into agent store.
- [ ] Implement AgentStore and transaction wrapper; snapshot/check session revision inside transaction, use unique constraints/CAS and rollback, and normalize SQLite naive timestamps to UTC.
- [ ] Run `./.venv/bin/pytest -q tests/integration/test_agent_sessions.py tests/integration/test_accounting.py tests/integration/test_reminder_repository.py`; Expected: SQLite cases pass, pre-existing PostgreSQL cases may skip only with the documented missing URL.
- [ ] Commit storage, migration and tests: `feat: persist agent conversations and atomic operation results`.

### Task 3: Orchestration va mavjud xizmat adapterlari

**Files:**
- Create: `src/namoz_bot/application/main_agent.py`
- Create: `src/namoz_bot/application/agent_adapters.py`
- Create: `tests/unit/application/test_main_agent.py`
- Create: `tests/integration/test_main_agent_operations.py`

**Interfaces:**
- Consumes: Tasks 1–2, existing ScheduleService, ReligiousReminderService and user preferences.
- Produces: `MainAgent.respond(*, context: AgentContext, request_id: str, text: str | None, audio: bytes | None = None, mime_type: str = "audio/ogg") -> AgentResult`.
- Produces: `MainAgent.confirm(*, context: AgentContext, request_id: str, operation_id: str, revision: int) -> AgentResult` and `cancel(*, context: AgentContext, request_id: str, operation_id: str, revision: int) -> AgentResult`.
- Produces: `MainAgent.resume(*, context: AgentContext, request_id: str) -> AgentResult` and `has_pending(user_id: int, now: datetime) -> bool`.
- `AgentExtractor` Protocol matches Task 1 extract signature. `AgentAdapters.prepare(request: AgentRequest) -> AgentResult` handles validation and external reads; `execute(request: AgentRequest, transaction: AgentTransaction) -> AgentResult` handles database operations. No Gemini/network wait while a database effect transaction is open.
- UI navigation result `data` carries validated `view` and its existing handler arguments; Telegram remains outside application.

- [ ] Write tests `test_followup_preserves_date_and_text`, `test_new_relative_date_uses_current_message_time`, `test_domain_switch_keeps_old_draft`, `test_multiple_tasks_do_not_execute`, `test_plain_yes_cannot_save`, `test_confirmation_revalidates_past_time`, `test_stale_confirmation_cannot_commit`, `test_error_keeps_previous_draft`, `test_audio_uses_one_extractor_call`, `test_replayed_update_skips_extraction`.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_main_agent.py`; Expected: missing MainAgent fails collection.
- [ ] Implement operation/source-key lifecycle, pending merge, 24-hour expiry, cancel/resume, revision-aware confirmation and domain switching. For multiple tasks return clarification without executing. For a new domain while pending, ask user to cancel or resume instead of silently discarding or running the new command.
- [ ] Implement action adapters: provider-backed schedule/date/prayer extraction with offsets; existing religious excerpt provider; database reminder list/create; LedgerService balance/report/history/income/expense; validated navigation for settings/delete panels; assistant help/clarify/cancel/resume.
- [ ] Write real-repository tests `test_finance_followup_commits_once`, `test_report_never_creates_entry`, `test_reminder_confirmation_commits_once`, `test_whole_som_and_future_rules_preserved`, `test_prayer_uses_region_date_and_offsets`. Assert persisted records, source keys, receipt statuses/effects and exact provider-derived times/totals.
- [ ] Run `./.venv/bin/pytest -q tests/unit/application/test_main_agent.py tests/integration/test_main_agent_operations.py`; Expected: all pass.
- [ ] Commit orchestration and tests: `feat: route conversational requests to existing bot services`.

### Task 4: Telegram kirishi, callbacks, fallback va regressiya

**Files:**
- Create: `src/namoz_bot/presentation/main_agent.py`
- Modify: `src/namoz_bot/main.py`, `src/namoz_bot/config.py`
- Modify: `src/namoz_bot/presentation/middleware.py`, `handlers.py`, `reminder_panel.py`
- Modify: `src/namoz_bot/presentation/accounting.py`, `reminders.py`
- Create: `tests/acceptance/test_main_agent_journey.py`
- Modify: legacy Gemini/voice/accounting acceptance fixture files, `tests/unit/test_config.py`, `tests/unit/test_main.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: MainAgent methods and Task 1 result models.
- Produces: `build_main_agent_router() -> Router`; DI name `main_agent: MainAgent | None`.
- `receive_agent_message(message: Message, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent) -> None` verifies private chat, downloads bounded audio once, creates trusted context and renders result.
- `agent_callback(callback: CallbackQuery, state: FSMContext, handler_services: HandlerServices, main_agent: MainAgent) -> None` verifies owner/operation/revision/expiry and only then calls confirm/cancel/resume.
- `render_agent_result(message: Message, state: FSMContext, result: AgentResult) -> None` uses deterministic formatting and inline callbacks <=64 bytes. Opaque callback token is stored/resolved against owner/operation/revision; model never generates callback authorization.
- New Settings: `main_agent_enabled: bool = True`, `gemini_main_agent_model: str | None = None`; getter/factory fallback to existing voice model.

- [ ] Write real application journey tests for text and voice in all three domains. Mock actual Gemini/Telegram HTTP/session, use SQLite tables, and assert one extraction call per new request plus actual balances/records.
- [ ] Write journey tests `test_plain_finance_without_menu`, `test_prayer_while_accounting_open`, `test_legacy_time_input_not_consumed`, `test_start_offers_pending_resume`, `test_menu_does_not_discard_agent_draft`, `test_restart_resumes_draft`, `test_old_or_foreign_callback_cannot_save`, `test_duplicate_save_after_restart_creates_one_row`, `test_send_failure_then_replay_has_one_entry`, `test_replay_after_undo_stays_cancelled`, `test_missing_key_and_disabled_agent_preserve_legacy_flow`, `test_group_chat_is_not_processed`, `test_provider_error_preserves_draft`.
- [ ] Run `./.venv/bin/pytest -q tests/acceptance/test_main_agent_journey.py`; Expected: router/DI or new behavior fails before integration.
- [ ] Implement agent wiring, cooldown/concurrency, private-chat input, deterministic response formatting and bounded callbacks. Reuse/refactor existing accounting rendering/history/undo helpers; keep old callbacks owner-scoped. For navigation reuse existing settings/reminder presentation functions.
- [ ] Integrate command/menu priority and pending-draft guard before destructive legacy state clears. Active manual reminder/settings input retains existing FSM behavior. Agent enabled catches accounting/free-text and voice before broad legacy handlers; agent disabled or key absent restores the original router paths.
- [ ] Set `MAIN_AGENT_ENABLED=false` explicitly in legacy AI-specific test fixtures so they continue testing the old extractor contract. Add enabled-agent tests for equivalent menu/voice paths rather than weakening assertions.
- [ ] Update `/start` and README with examples, settings, confirmation, cancel/resume, TTL, one-task rule, protocol location and migration instructions. Avoid exposing protocol internals in Telegram product text.
- [ ] Run `./.venv/bin/pytest -q tests/acceptance tests/unit/test_config.py tests/unit/test_main.py`; Expected: all pass.
- [ ] Commit UI, wiring, README and tests: `feat: enable the main agent for text and voice conversations`.

### Task 5: Migration, umumiy tekshiruv va yakuniy review

**Files:**
- Create: `tests/integration/test_agent_migrations.py`
- Modify only files needed for verified regression fixes.

**Interfaces:**
- Consumes: complete V1 implementation and migration `20261013_01`.
- Produces: tested branch, exact verification results and known limitations.

- [ ] Write migration test `test_agent_migration_roundtrip_preserves_existing_records` using an isolated PostgreSQL test URL, never production/local bot database. Create pre-migration user/finance/reminder data, upgrade, create agent session/receipt, downgrade only the new revision, and assert old data retained.
- [ ] Run the migration test against code before migration implementation if Task 2 has not yet supplied it; otherwise verify its failure by running against the previous migration head first, then current head. No assertion-only mirror tests.
- [ ] Use project integration fixture patterns for isolated database setup. If PostgreSQL URL is unavailable, record explicit unverified migration status; do not count a skip as passing migration verification or silently edit `.env`.
- [ ] Run `./.venv/bin/pytest -q`; Expected: all configured tests pass, skips individually explained.
- [ ] Run `./.venv/bin/ruff check src tests alembic`; Expected: no lint errors.
- [ ] Run `./.venv/bin/mypy src/namoz_bot`; Expected: no type errors.
- [ ] Run `git diff --check`; Expected: no whitespace errors.
- [ ] Review the complete diff against spec, Review Focus and observed test evidence; independently inspect ownership, callbacks, recovery and transaction boundaries. Use requesting-code-review workflow, following user/skill authorization rules for a fresh reviewer.
- [ ] Fix confirmed important findings through reproducing tests (RED → GREEN); rerun affected checks and full suite when implementation changes.
- [ ] Commit only verified final fixes/tests. Report code completion separately from deployment/restart; include any PostgreSQL/live-provider verification limitation.

## Self-review and traceability

Spec 1–4 → Task 1 and 3; spec 5–6 → Task 2 and 3; spec 7–8 → Task 1 and 4;
spec 9 → Task 2/4/5; spec 10–11 → all tasks and final verification.
Each later task consumes the exact signatures defined above; no V2 helper-agent
implementation or new framework is required. Authoritative business rules remain
in existing domain/application code. Plan review precedes runtime implementation.
