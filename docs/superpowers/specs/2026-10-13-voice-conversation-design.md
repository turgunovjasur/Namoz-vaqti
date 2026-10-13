# Ovoz orqali boshqariladigan yagona suhbat

User explicitly requires all existing bot operations by voice, one outward main
agent, content-based dispatch to scoped specialists and a keyboard with only Help.
User clarified that replies remain text. Implement inline in the existing local
bot context; restart after tests and one independent review. No server push/merge.

V2 becomes a conversation UI. It accepts voice/text across old FSM states, replaces
the keyboard on every reply with Help only, and emits no inline menus or required
buttons. V1/disabled legacy modes retain their old handlers for compatibility.
User commands cover prayer schedules/region/offsets, book nasihat and interval
updates/off, reminder create/list/delete, accounting income/expense/balance/report/
history/undo and daily schedule time. Open-settings intents produce textual current
values and voice examples. Existing services remain authoritative; no TTS is needed.

Router transcribes once and selects exactly one domain; original text/transcript is
handed to its specialist. Main owns pending state, clarification, confirmation,
cancel/resume, source IDs and receipts. New assistant.confirm accepts voice yes/save
only for a complete pending confirmation. Partial drafts never execute on yes.
Creation/deletion/undo confirmation is tied to operation and revision; confirmed
targets are owner checked again. IDs and title matching come from owner-scoped
repositories. Duplicate messages and confirmation replay cannot repeat effects.

All persistent setting changes and their receipts share the existing agent SQL
transaction, using session-bound existing repositories/services. New typed values:
daily time HH:MM, interval integer 0..168 (0 off), named region, per-prayer offset
-30..30 (set/add) and reset offsets. Unclear times/regions/targets ask a short question.
Region change retains the existing offset reset rule. No new migration/dependency.

Lists/history retain voice pagination; latest view metadata contains only domain,
action,page,today and owner-derived IDs, not financial amounts or reminder content.
Ordinal selections resolve against that view; explicit IDs remain owner checked.
Cross-domain helpers never receive another domain's draft or view. Router sees only
pending/view metadata. Provider failures preserve drafts. Voice rate limiting must
permit immediate answers within a conversation; existing request-size limits stay.

Tests must verify actual SQL effects/settings and receipt rollback, owner isolation,
voice confirmation/replay/cancel, ambiguous targets, selected-only dispatch/audio
once, all voice commands, state recovery and Help-only output with no inline menus.
Live extraction uses synthetic inputs without business writes; local polling startup
confirms activation. Replies are text; visual command menus are absent in V2.
