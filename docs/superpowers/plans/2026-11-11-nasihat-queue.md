# Nasihat Queue Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Deliver book excerpts in sequence or without-repeat random order, retain unread items, pause at three until all are confirmed read, and open the exact excerpt from a local notification.

**Architecture:** Persist at most three unread/future deliveries before handing their dates and previews to iOS. Reconcile due dates on activation without relying on background execution. A pure queue engine owns selection, used IDs, time windows and the pause latch. Existing PrayerAlerts remains the single notification delegate and routes advice taps.

**Tech Stack:** SwiftUI, Foundation, UserNotifications, current file-backed library.

**Spec:** User-approved three-screen mockup and conversation requirements, 2026-11-11.

## Global Constraints
- Default sequential; random never repeats a reserved/unread/read excerpt until the selected pool is exhausted and unread items are cleared.
- Three due unread items latch a pause. Reading only one or two does not resume. After the last acknowledgement, wait the configured interval and next allowed window.
- Keep existing bookmarks, full source text and due unread items through upgrades/settings changes.
- Notifications show the source title and opening text; tap opens the exact delivery, never marks it read.
- Notification opt-out/denial does not discard queue items. Scope cancellation to `nasihat.` IDs; preserve prayer alerts.
- No paid push service needed: no more than three future/due reservations.

## Review Focus
- App closed for days: exactly three due items, no skipped content or fourth alert.
- Partial acknowledgement after reaching cap: latch survives restart.
- Settings/source/order changes: retain due unread items, replan only future reservations.
- Overnight windows, end-exclusive boundary, time-zone changes and clock rollback.
- Notification launch while on another tab or app closed, permission denial, idempotent read actions, legacy state migration.

### Task 1: Persisted queue engine
Files: create `ios/Qori/AdviceQueue.swift`; modify `NasihatStore.swift`; create `ios/Tests/AdviceQueueChecks.swift`; update `ios/Tests/NasihatChecks.swift`.
- [x] Add failing tests for 3-slot backlog, latch, read-all delay, sequential/random exhaustion, settings and windows.
- [x] Implement `AdviceQueue.reconcile(at:preferences:books:corpora:calendar:)`, `markRead`, and explicit default-compatible decoding.
- [x] Integrate atomic store persistence and legacy migration, then run queue and store checks.

### Task 2: Notification scheduling and routing
Files: create `ios/Qori/AdviceNotifications.swift`; modify `PrayerAlerts.swift`, `QoriApp.swift`, project source references.
- [x] Test generated requests: exact delivery identity, preview/source, configured sound, future-only and max three.
- [x] Schedule local alerts from persisted state; serialize updates and cancel only obsolete advice notifications.
- [x] Route default notification taps through the existing delegate and activate the Nasihat tab/detail.

### Task 3: Approved UI
Files: modify `NasihatView.swift`.
- [x] Show unread queue with count, latched pause message, preview cards and toolbar.
- [x] Detail shows full source, separate Save and explicit Read actions.
- [x] Add order and notification/sound settings, permission feedback; keep source/time controls.

### Task 4: Verify delivery
- [x] Build app, run engine/store/request tests, review changes.
- [x] Install simulator; exercise queue/detail/settings, pause at three and read-all resume; preserve pre-test state.
- [ ] Complete physical-device notification-tap verification. Simulator delivered the alerts, but Device Hub automation did not activate its Open action reliably.
- [x] Record screenshots and report actual validation plus device-only limitations.

## Verification record — 2026-11-11

- `AdviceQueueChecks`: PASS. Sequence, random exhaustion, round-robin sources, latch, restart, last-read interval, source changes, notification opt-out, overnight/end-exclusive windows, clock rollback and time-zone replanning.
- `NasihatChecks` on iOS Simulator: PASS. Real book installation, persistence, saved independence, notification route without read, legacy migration, full long text upgrades and changed-PDF protection.
- `AdviceNotificationChecks` on iOS Simulator: PASS. Exact delivery ID, source title and preview, sound preference, future-only scheduling, opt-out and paused state.
- Final simulator `xcodebuild`: exit 0; installed and launched latest app.
- Native UI: 3 → 2 → 1 remained paused; final Read produced 0 unread, resumed and scheduled next delivery exactly four hours later. Save did not acknowledge. Settings displayed order, alerts, sound, interval and window.
- Real local notifications: three source-backed excerpts delivered while the app process was terminated; source title/opening visible. Existing prayer notifications remained visible. Tap-to-detail implemented and store route tested; OS-level tap could not be completed reliably through Device Hub automation. No claim of physical iPhone validation.
- Independent reviewer found a DST spring-forward edge case for a missing 02:30–03:00 window. Reproduced a failing test; corrected next allowed date search; regression now passes.
- Screenshots: `output/ui/nasihat-queue-main.png`, `nasihat-queue-detail.png`, `nasihat-queue-settings.png`, `nasihat-queue-notification.png`.
- Temporary simulator fixtures were separate from the pre-test state backup; original state restored after verification. No physical-device data changed.

## Runtime boundaries

Local iOS notifications require user permission. Focus/silent settings are controlled by iOS. Future notifications are scheduled with absolute dates and replan to the current time zone when the app next activates; travelling while it remains terminated does not recalculate the local time window until activation.
