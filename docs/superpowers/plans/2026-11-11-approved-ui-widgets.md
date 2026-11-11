# Approved Nasihat and Prayer Widgets Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Implement the approved November 11 mockups and demonstrate the actual app in Simulator.
**Architecture:** Keep persisted advice delivery rules, surface the latest due delivery on home and move backlog to a separate list. Share timer-free widget rendering and schedule selection between widget extension and in-app previews. Native WidgetKit family selection adds the desired size.
**Tech Stack:** SwiftUI, WidgetKit, existing Foundation models and local notifications.
**Spec:** User-approved two images in this chat: latest advice, alert settings, horizontal prayer card, reminder choices, four widget layouts.

## Global Constraints
- Latest due advice remains visible even after read or with three unread; never show future reserved content.
- Pause warning follows existing latch; backlog access remains until all read. Preserve saved excerpts, IDs, timing and notification routing.
- Prayer reminder is configured by Oldindan eslatish; at-time signal stays separate. Time left remains in app but never in widgets.
- Four widget families: small, medium, large, accessory rectangular. Existing kind retained so installed widgets upgrade.
- The in-app chooser is a preview/installation guide, not a claim that an app can add or resize Home/Lock Screen widgets itself.

## Review Focus
- Latest read item must remain home while older unread items are acknowledged.
- No future excerpts shown early, no marking read on entry, no reset of pause.
- Night/midnight prayer roll-over and no stale daily rows on next day.
- Empty/network-failed widget schedule must not show fabricated times.
- Small screens, large text and lock-screen rendering must remain legible without timers.

### Task 1: Nasihat home
- [x] Test latest due delivery selection before implementation, including future exclusion/read preservation.
- [x] Add latest delivery selection; main full card, separate backlog and Read action, clear settings labels.
- [x] Run queue and store checks; inspect main/backlog/settings in Simulator.

### Task 2: Prayer UI
- [x] Reuse existing offset/reminder scheduling; display radio reminder choices and derived reminder time.
- [x] Put time left and prayer name right on one line; remove Keyingi namoz label, retain app countdown.
- [x] Verify existing prayer timing checks and inspect simulator.

### Task 3: Widgets
- [x] Add failing model checks for next-three excluding sunrise, day roll-over and offsets.
- [x] Build shared schedule model and 4 timer-free layouts; extend timeline and families.
- [x] Add preview chooser and accurate native add-widget instructions accessible from prayer page.
- [x] Build both targets, run model tests; inspect actual widget gallery and app previews.

### Task 4: Delivery
- [x] Independent scoped review, fix material findings, run required checks.
- [x] Install and show simulator, capture screenshots; restore any test state.

## Execution record

Ruling: Work in the existing checkout with its untracked iOS project; no broad staging/commit or unrelated edits. Native implementation is already authorized. Review snapshots in /tmp isolate this turn's changes without losing existing work.
Ruling: Native widget family picker owns actual installation/size choice. In-app selection changes the preview and matching instructions; wording makes this explicit.


## Verification and review — 2026-11-11
- AdviceQueueChecks, NasihatChecks and PrayerWidgetChecks passed. Both app and widget targets built successfully for Simulator.
- Independent scoped review found a stale-region/day preview risk. Fixed by validating the loaded schedule key; regression checks passed.
- Simulator verified: latest advice stays visible after acknowledgement, unread count 3 → 2 and pause warning persists, separate backlog shows remaining two. Temporary fixture restored from the original state backup.
- Prayer card shows enlarged time (64 pt) and name on the same baseline. Selecting 10-minute advance reminder for Asr 15:26 displays 15:16; draft discarded after inspection.
- Four in-app widget previews inspected. Actual medium Home Screen widget shows the region and next three prayers, with no timer.
- Empty native widget was traced to an unsigned Simulator build: securityd reported missing shared-Keychain entitlements (-34018). Rebuilt with CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=-, installed and opened app; native widget then displayed real schedule. Documented this build requirement in ios/README.md.
- Screenshots: output/ui/approved-2026-11-11/.
- Limits: physical iPhone not updated in this turn; native lock-screen placement and accessibility-size/device matrix were not exercised. Existing notification scheduling unchanged.
