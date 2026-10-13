# Voice Conversation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Checkboxes track steps.

**Goal:** Existing bot functions work by voice through main → specialist; only Help is visible.
**Architecture:** Typed actions and session-bound service effects, main confirmation state,
then dedicated text-response conversation UI. Existing V1/disabled legacy UI remains.
**Tech Stack:** Existing Python, aiogram, Pydantic, HTTPX, SQLAlchemy, PostgreSQL/SQLite.
**Spec:** `docs/superpowers/specs/2026-10-13-voice-conversation-design.md`.

## Global Constraints

- Replies are text; no new TTS/dependency/migration.
- Router → one specialist; voice uploaded once; no private content in logs.
- Effects/settings and receipts commit or roll back together; owner isolation remains.
- Help-only reply keyboard and no inline controls in V2.
- Implement native on feature branch; final read-only review, local activation, no push/merge.

## Review Focus

- Yes to incomplete/expired/stale drafts never writes; confirmation cannot change targets.
- Delete/undo selection ambiguity and ordinal/view expiry never guesses or touches another user.
- Preference writes roll back with receipt/session conflicts; relative offset replay is idempotent.
- Old FSM/nav/callbacks cannot reintroduce menus in a V2 conversation.
- Audio confirmation works immediately and specialists receive only their own pending/view metadata.

### Task 1: Typed voice actions and transactional settings

Files: domain/agent_protocol.py, application/agent_sessions.py, application/subscriptions.py,
infrastructure/agent_sessions.py, repositories.py, daily_schedule.py, religious_intervals.py;
new application/conversation_actions.py; tests/integration/test_voice_agent_actions.py.
Interfaces: typed set_daily(time), set_interval(hours), set_region(region),
set_offset(prayer,minutes,mode), reset_offsets; transaction exposes subscription/daily/
interval services bound to the same SQL session. ConversationAdapters.prepare/execute
match existing AgentActionExecutor and reuse existing providers.

- [x] Write invalid-value, preference persistence, cross-user and rollback tests; observe RED.
- [x] Add typed action models; bind repositories/services via existing session_scope; implement
  reversible preference actions and textual current-settings reads. No separate commits inside tx.
- [x] Run integration/unit checks and Ruff/mypy; commit (`4295f72`).

### Task 2: Confirmation, target selection and voice pagination

Files: domain/agent_protocol.py, application/main_agent.py, conversation_actions.py,
infrastructure/agent_sessions.py; tests/integration/test_voice_agent_actions.py.
Interfaces: assistant.confirm; MainAgent.voice_first; get_last_view()->AgentViewState|None;
delete/undo TargetParameters(target_id,text,ordinal); list/history page_step next/previous.

- [x] Write incomplete/complete yes, replay, voice cancellation, deletion/undo owner/ambiguity,
  ordinal latest view and expired view tests; observe RED.
- [x] Generalize confirmation to create/delete/undo, preserve resolved target in draft,
  revalidate owner at execution, and persist receipts atomically. Load only bounded view metadata.
- [x] Run affected suites and static checks; commit (`1908cca`).

### Task 3: Conversation UI, routing prompts and runtime wiring

Files: new presentation/voice_conversation.py, presentation/main_agent.py and middleware.py,
keyboards.py, infrastructure/gemini_menu_agents.py and gemini_main_agent.py,
application/menu_agents.py, main.py, README.md; tests/acceptance/test_voice_conversation.py,
existing V2 journeys/provider schemas.
Interfaces: build_voice_menu(), build_voice_conversation_router(main_agent); V2 defaults to
voice_first=True and ConversationAdapters with scoped helpers. V1 keeps legacy adapters/UI.

- [x] Write actual Telegram voice journeys for every domain, immediate voice followup/yes,
  state recovery, Help-only output, text settings save, no callbacks required; observe RED.
- [x] Narrow/extend prompts and schemas, add router confirmation and pending/view metadata;
  wire V2 conversation router before legacy routers, deterministic text responses and Help menu.
- [x] Update docs, run journeys/provider/V1 regressions and static checks; commit (`901efc2`).

### Task 4: Final verification and activation

- [x] Full configured isolated PostgreSQL suite, Ruff/mypy and diff check.
- [x] Live synthetic router/helper settings and confirmation extraction; no business writes.
- [x] One independent immutable whole-branch review; fix Important/Critical RED→GREEN and full suite.
- [x] Gracefully restart established local test bot; verify V2 startup/polling and record evidence.

Execution follows user's explicit experience requirements and prior native/local workflow.
No additional generic start/permission gate is needed. Base `6974c55`.

## Final review and live extraction evidence

One read-only whole-branch review inspected `6974c55..901efc2`. All seven findings
were addressed: rejected delete/undo target replacements clear the previous draft;
ambiguous ordinal choices retain their exact candidate IDs; list/history reads remain
available during target selection and obsolete open_delete sessions normalize to delete;
clarification blocks every new write action; transaction services retain configured
defaults; nasihat availability is checked before promising delivery; daily delivery
requests route to settings even when the spoken request also mentions namoz.
Regression tests observed RED before the fixes and GREEN afterward.

Additional synthetic live cases exposed and fixed undo versus draft cancellation,
voice confirmation routing and redundant matching view metadata. Only matching
metadata is normalized; conflicting fields are still rejected. A failed interpretation
retains a draft but requires showing its summary again before confirmation can execute.
The live smoke run passed six settings/region/offset/delete/undo text intents, real
synthetic Ogg speech for daily delivery at 07:00 and confirmation, and relative pagination.
No user messages or business data were used, and no business effects were executed.

Review scope rulings: broader speaker/language ASR benchmarking is deferred; concrete
Russian audio cases are verified. Real Telegram transport is covered by the existing
polling startup plus mocked acceptance journeys; local activation is recorded below.
Legacy V1 visual handlers remain available for rollback; the active V2 path uses Help only.

Final fixes committed as `da55c00`. Full suite with the isolated PostgreSQL test database:
**645 passed, 3 expected skips** in 66.53 seconds. The skipped SQLite migration cases
are verified by their PostgreSQL variants. Ruff passed; mypy reported no issues in
63 source files; `git diff --check` passed.

Local activation on 2026-10-13 (Asia/Tashkent): old process `84701` stopped with SIGINT;
launcher verified Alembic head and started process `94481`. Startup at 13:25:20 logged
`main_agent_configured version=2 voice_first=True menus=prayer,nasihat,reminder,accounting,settings`
and polling for `@TestUzNamozTaqvimiBot` (bot ID `8922089476`). Process inventory confirmed
exactly one bot process. No server deployment, push or merge was performed.
