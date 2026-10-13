# Menu Agents V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Main agent yo‘naltiradigan, o‘z prompt/model/action vakolatiga ega yordamchi agentlarni implement qilish.
**Architecture:** Routing/interpretation pipeline va typed handoff; har domain agent xizmat adapterining o‘z vakolatdagi amallarini ishlatadi. V1 persistence/UI reuse.
**Tech Stack:** Mavjud Python/Pydantic/HTTPX/aiogram/SQLAlchemy; yangi dependency yo‘q.
**Spec:** `docs/superpowers/specs/2026-10-13-menu-agents-v2-design.md`.

## Global Constraints

- Protokol versiyasi 1, MAIN_AGENT_VERSION=2 default, V1 fallback bor.
- Bitta router → bitta selected helper; audio faqat routerga yuboriladi.
- User/operation/request IDs trusted application tomonidan beriladi.
- Har helper o‘z domain/actionidan tashqarida effekt bajara olmaydi.
- Settings faqat mavjud oynalarni ochadi; assistant controls main agentda qoladi.
- V1 owner/revision/confirmation/receipt/source-key/TTL/transaction qoidalari saqlanadi.
- Default model mavjud konfiguratsiyadan; new SDK/dependency/migration yo‘q.
- Loglarga private input/parameters chiqmaydi.

## Review Focus

- Router transkripti text qiymatini o‘zgartirsa, helperga asl matn uzatilishi.
- V1 dan qolgan qoralama V2 helperiga to‘g‘ri domain bo‘yicha yetib borishi.
- Boshqa domaining pending mazmuni selected helperga oshkor bo‘lmasligi.
- Wrong-domain/correlation reply yoki helper timeout hech qanday yozuv qilmasligi.
- Router-only help/multi-task va helper scope shartlari real HTTP bodylar bilan tekshirilishi.

### Task 1: Typed handoff va menu-agent chegaralari

**Files:** domain/agent_protocol.py, application/menu_agents.py, application/main_agent.py;
tests/unit/application/test_menu_agents.py.
**Interfaces:** AgentRoutingDecision, AgentHandoff, AgentHandoffReply; operation_id_for(context,request_id);
MenuAgent.interpret(handoff)->AgentHandoffReply, prepare(request)->AgentResult,
execute(request,transaction)->AgentResult; RoutedAgentExtractor.extract(...,request_id=None)->AgentDecision;
MenuAgentDispatcher.prepare/execute. MainAgent optional extractor request_id va executor Protocol.

- [ ] Write tests for selected-only dispatch, untouched text, assistant/multi-task, cross-domain pending isolation, wrong reply IDs/domain, capability guard; run and observe missing module failure.
- [ ] Implement protocol models/ports, PrayerAgent/ReminderAgent/AccountingAgent/SettingsAgent and fixed registry dispatcher; retain V1 methods.
- [ ] Run focused tests, Ruff/mypy; commit `feat: add typed menu agent handoffs and capabilities`.

### Task 2: Gemini routing va per-domain interpreterlar

**Files:** infrastructure/gemini_main_agent.py, infrastructure/gemini_menu_agents.py;
tests/unit/infrastructure/test_gemini_menu_agents.py.
**Interfaces:** GeminiRoutingClient.route(text/audio/context/pending)->AgentRoutingDecision;
GeminiMainAgentClient configurable instruction/schema for reuse; Gemini menu client
interpret(handoff)->AgentDecision with domain-specific schema and system instruction.

- [ ] Write real mocked-HTTP tests for narrow router schema, single audio upload, specialist prompts/action schema, cross-domain output rejection and safe provider failures; observe RED.
- [ ] Reuse shared HTTP/response parsing via configurable V1 client and small routing client; provide four narrow profiles with strict action-specific normalization.
- [ ] Run V1/V2 provider tests, Ruff/mypy; commit `feat: add isolated Gemini router and menu interpreters`.

### Task 3: Runtime wiring, compatibility va journey tests

**Files:** config.py, main.py, README.md; V1 test fixture, new tests/acceptance/test_menu_agent_journey.py,
tests/unit/test_config.py; tests/integration/test_main_agent_operations.py where needed.
**Interfaces:** MAIN_AGENT_VERSION 1/2, per-domain model overrides; existing MainAgent/UI/service DI.

- [ ] Write V2 text/audio journeys using distinct router/helper model URLs and real SQLite repositories; assert selected helper only, correct finance effects, reminder followup/save, helper failure preserves draft, replay skips both models, V1 draft survives V2 switch and wrong domain never writes. Observe RED.
- [ ] Wire registry/pipeline/dispatcher for V2; preserve V1 and legacy fallbacks. Set V1-specific fixture version=1, add explicit V2 coverage.
- [ ] Update README examples/config/protocol flow and two-call behavior.
- [ ] Run focused journeys and existing suite; commit `feat: enable V2 menu agents with V1 compatibility`.

### Task 4: Verification, review va local activation

**Files:** regression fixes/tests only; docs verification notes.

- [ ] Full pytest with existing isolated PostgreSQL test DB, Ruff, mypy and git diff check.
- [ ] Live synthetic router/helper/followup check without real user data or DB writes.
- [ ] One independent read-only whole-branch review; fix important findings RED→GREEN, rerun affected/full checks after code changes.
- [ ] Commit verified fixes, restart existing local test bot gracefully with its existing run script, and verify startup/config/logs without leaking keys. No new migration needed.
- [ ] Record final evidence and branch status; no server deploy, merge or push.

## Execution authorization

Foydalanuvchi oldindan ta’riflangan V2 oqimini «v2 implement qil» deb aniq so‘radi.
Bu bosqich native bajariladi; yana umumiy start/permission savoli berilmaydi.
