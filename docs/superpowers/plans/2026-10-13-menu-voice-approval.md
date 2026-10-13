# Menu and voice approval

User now requires visible menus alongside voice at all times, a main-agent interpretation
preview for every voice message with Ha/Yo‘q buttons, execution only after Ha, cancellation
on Yo‘q and the result as a new message. Replies remain text. This supersedes Help-only
and hidden-menu mode. The existing /menu shortcut remains available.

Implementation uses existing agent-session JSON and SQL transactions, without migrations
or dependencies. A typed review stores the parsed decision, source context and prior draft.
Preview invokes extraction only, never business preparation/execution. Approval checks owner,
bot, operation, revision and expiry, then applies the exact parsed decision without a second
model call. Business effects, new draft state and callback receipt commit atomically. Rejection
restores the prior draft. New voice supersedes the previous review; stale/duplicate callbacks
never repeat effects. Complete create/delete/undo can execute after that approval; ambiguous
or partial commands continue by requesting missing information. Interpretation is shown with
human action/field labels, not raw internal protocol names.

- [x] RED: real SQL voice-gate tests, no effects before approval, yes/no, reads, expiry,
  duplicate/stale/foreign callbacks, prior-draft followups and restart persistence.
- [x] Implement typed review and main-agent apply/approve methods; verify affected suites.
- [x] Keep menus visible through voice/manual journeys; Ha/Yo‘q callbacks send a fresh result,
  retire buttons, and preserve manual menu functionality. Adapt superseded UI expectations.
- [x] Full PostgreSQL/static checks; one read-only final review and necessary fixes.
- [x] Gracefully restart local test bot; verify startup and record evidence. No push/merge.

Final review covered immutable 9351d40..bb49f6a and requested four corrections:
uncertain assistant confirmations must retain clarification/multiple-task flags and cannot
execute a prior draft; completed reminder/accounting results must survive later navigation;
failed or oversized replacement voices must retire earlier approvals; offset calendar
navigation must append results. Each reproduction failed before the fixes. Regressions also
cover uncertain resume, duration rejection and suspension of prior confirmation until its
summary is shown again. The fixes preserve existing V1 behavior.

Review scope rulings: no live Telegram messages or real business actions are sent during
validation. Existing synthetic speech extraction evidence applies because model routing is
unchanged. Scheduler delivery is unchanged. PostgreSQL locking is covered by the full
configured integration suite. Activation is checked separately below. Importing individual
spoken fields into legacy manual FSM drafts and downgrading V2 pending reviews into V1 are
outside this change: a voice input from any manual step reaches the main agent, while manual
field entry remains available through its original flow. No further review round is required.

Final verification after review fixes: 698 passed, 3 expected SQLite-only migration skips,
46.29 seconds with PostgreSQL integration enabled. Ruff passed; mypy passed for all 65 source
files; git diff --check passed. No schema or dependency changes.

Local activation: implementation bb49f6a and review fixes 5a48469. Old PID2368 received
SIGINT and stopped polling at 16:01:27 Asia/Tashkent. New PID9878 started at 16:01:39;
16:01:41 startup confirmed version2, voice_approval=True, persistent_menu=True and all five
service domains. Polling confirmed @TestUzNamozTaqvimiBot, ID8922089476 at 16:01:42.
Exactly one bot process was found; PTY78172 remains running. No push, merge or server deploy.
