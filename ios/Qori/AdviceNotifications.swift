import Foundation
import Combine
import UserNotifications

@MainActor
final class AdviceNotifications: ObservableObject {
    @Published private(set) var status: UNAuthorizationStatus = .notDetermined
    @Published private(set) var issue: String?
    private let center = UNUserNotificationCenter.current()
    private var task: Task<Void, Never>?

    nonisolated static func requests(for state: AdviceState, at date: Date) -> [UNNotificationRequest] {
        guard state.preferences.notificationsEnabled, !state.queue.pausedUntilRead else { return [] }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        return state.queue.items.filter { $0.readAt == nil && !$0.isDue(at: date) }.prefix(3).map { item in
            let content = UNMutableNotificationContent()
            content.title = item.advice.book.title
            let text = item.advice.passage.text
            content.body = String(text.prefix(220)) + (text.count > 220 ? "…" : "")
            content.threadIdentifier = "nasihat"
            content.userInfo = ["adviceDeliveryID": item.id]
            if state.preferences.soundEnabled { content.sound = .default }
            var components = calendar.dateComponents([.year, .month, .day, .hour, .minute, .second], from: item.dueAt)
            components.timeZone = calendar.timeZone
            return UNNotificationRequest(identifier: "nasihat.\(item.id)", content: content,
                                         trigger: UNCalendarNotificationTrigger(dateMatching: components, repeats: false))
        }
    }

    func requestPermission() async {
        do {
            _ = try await center.requestAuthorization(options: [.alert, .sound])
            status = await center.notificationSettings().authorizationStatus
            issue = status == .denied ? "Bildirishnomalarga ruxsat berish uchun iPhone sozlamalarini oching." : nil
        } catch { issue = "Bildirishnoma ruxsatini tekshirib bo‘lmadi. \(error.localizedDescription)" }
    }

    func refresh(state: AdviceState) {
        let previous = task
        previous?.cancel()
        task = Task {
            await previous?.value
            guard !Task.isCancelled else { return }
            do { try await reconcile(state) }
            catch {
                if !Task.isCancelled { issue = "Nasihat bildirishnomasi rejalashtirilmadi. \(error.localizedDescription)" }
            }
        }
    }

    private func reconcile(_ state: AdviceState) async throws {
        let pending = await center.pendingNotificationRequests().filter { $0.identifier.hasPrefix("nasihat.") }
        let settings = await center.notificationSettings()
        try Task.checkCancellation()
        status = settings.authorizationStatus
        let desired = Self.requests(for: state, at: Date())
        let desiredIDs = Set(desired.map(\.identifier))
        center.removePendingNotificationRequests(withIdentifiers: pending.map(\.identifier).filter { !desiredIDs.contains($0) })
        center.removeDeliveredNotifications(withIdentifiers: state.queue.items.filter { $0.readAt != nil }.map { "nasihat.\($0.id)" })
        guard state.preferences.notificationsEnabled else { issue = nil; return }
        guard [.authorized, .provisional, .ephemeral].contains(status) else {
            issue = status == .denied ? "Bildirishnomalar uchun iPhone sozlamalarida ruxsat bering." : "Nasihat bildirishnomalariga ruxsat bering."
            return
        }
        for request in desired {
            try Task.checkCancellation()
            let previous = pending.first { $0.identifier == request.identifier }
            if previous?.content == request.content && previous?.trigger == request.trigger { continue }
            try await center.add(request)
        }
        try Task.checkCancellation()
        issue = nil
    }
}
