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
- [ ] Full PostgreSQL/static checks; one read-only final review and necessary fixes.
- [ ] Gracefully restart local test bot; verify startup and record evidence. No push/merge.
