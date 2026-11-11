import AlarmKit
import CryptoKit
import SwiftUI
import UserNotifications

private struct AlertProblem: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

private struct PrayerEvent {
    let region: PrayerRegion
    let prayer: Prayer
    let fire: Date
    let preference: PrayerPreference
    let advance: Bool

    var kind: PrayerSignal { advance ? .silent : preference.signal }
    var id: String {
        "namoz.\(region.id).\(prayer.rawValue).\(Int(fire.timeIntervalSince1970)).\(advance ? preference.reminder : 0).\(kind.rawValue)"
    }
    var title: String {
        if advance { return "\(prayer.rawValue)ga \(preference.reminder) daqiqa qoldi" }
        return prayer == .quyosh ? "Quyosh chiqish vaqti" : "\(prayer.rawValue) vaqti"
    }
    var alarmID: UUID {
        let bytes = Array(SHA256.hash(data: Data(id.utf8)).prefix(16))
        return bytes.withUnsafeBufferPointer { NSUUID(uuidBytes: $0.baseAddress!) as UUID }
    }

    func notify(using center: UNUserNotificationCenter) async throws {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = "\(region.name) · \(PrayerClock.time(fire.addingTimeInterval(advance ? Double(preference.reminder * 60) : 0)))"
        if kind == .chime { content.sound = UNNotificationSound(named: UNNotificationSoundName("prayer-chime.wav")) }
        var components = PrayerClock.calendar.dateComponents([.year, .month, .day, .hour, .minute], from: fire)
        components.timeZone = PrayerClock.calendar.timeZone
        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
        try await center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
    }
}

@available(iOS 26, *)
private struct PrayerAlarmMetadata: AlarmMetadata {}

@MainActor
final class PrayerAlerts: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    @Published var issue: String?
    @Published var nasihatNotificationID: String?
    private var queue: Task<Void, Never>?
    private let center = UNUserNotificationCenter.current()
    static var supportsAlarms: Bool {
        if #available(iOS 26, *) { return true }
        return false
    }
    override init() {
        super.init()
        center.delegate = self
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                             withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                             withCompletionHandler completionHandler: @escaping () -> Void) {
        guard response.actionIdentifier == UNNotificationDefaultActionIdentifier,
              let id = response.notification.request.content.userInfo["adviceDeliveryID"] as? String else {
            completionHandler()
            return
        }
        Task { @MainActor in
            // This delegate also owns prayer presentation; tapping never confirms reading.
            nasihatNotificationID = id
            completionHandler()
        }
    }

    static func authorize(_ value: PrayerPreference, replacing old: PrayerPreference) async throws {
        if value.usesNotifications && (!old.usesNotifications || old.signal != value.signal || old.reminder != value.reminder) {
            guard try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) else {
                throw AlertProblem(message: "Bildirishnomalarga ruxsat berish uchun iPhone sozlamalarini oching.")
            }
        }
        if value.signal == .alarm && old.signal != .alarm {
            if #available(iOS 26, *), try await AlarmManager.shared.requestAuthorization() == .authorized { return }
            throw AlertProblem(message: "Uyg‘otuvchi signal uchun iPhone sozlamalarida ruxsat bering.")
        }
    }

    func refresh(region: PrayerRegion, data: Data, date: Date) {
        let previous = queue
        previous?.cancel()
        queue = Task {
            await previous?.value
            guard !Task.isCancelled else { return }
            do {
                try await reconcile(region: region, data: data, date: date)
                if !Task.isCancelled { issue = nil }
            } catch {
                if !Task.isCancelled { issue = error.localizedDescription }
            }
        }
    }

    private func reconcile(region: PrayerRegion, data: Data, date: Date) async throws {
        let preferences = PrayerPreferences(data: data)
        // Invalidate the old town's or old preferences' alerts even when the new timetable is offline.
        let signature = region.id + data.base64EncodedString()
        let changed = UserDefaults.standard.string(forKey: "namoz.alertPlan") != signature
        if changed {
            try await apply([])
            UserDefaults.standard.set(signature, forKey: "namoz.alertPlan")
        }
        guard preferences.hasAlerts else { return }
        var events: [PrayerEvent] = []
        var month: PrayerMonth?
        var incomplete = false
        for shift in 0..<5 {
            let day = PrayerClock.calendar.date(byAdding: .day, value: shift, to: date)!
            if month?.meta.ym != PrayerClock.month(day) {
                do { month = try await PrayerMonth.load(slug: region.slug, date: day) }
                catch { incomplete = true; break }
            }
            guard let schedule = try? month?.day(day) else { incomplete = true; break }
            for prayer in Prayer.allCases {
                let pref = preferences[prayer]
                let target = schedule.instant(prayer, on: day, offset: pref.offset)
                if pref.signal != .off && target > Date() {
                    events.append(PrayerEvent(region: region, prayer: prayer, fire: target, preference: pref, advance: false))
                }
                let early = target.addingTimeInterval(Double(-pref.reminder * 60))
                if pref.reminder > 0 && early > Date() {
                    events.append(PrayerEvent(region: region, prayer: prayer, fire: early, preference: pref, advance: true))
                }
            }
        }
        try Task.checkCancellation()
        if !incomplete || !events.isEmpty { try await apply(events, prune: !incomplete) }
        if incomplete { throw AlertProblem(message: "Eslatmalar jadvalini to‘liq yuklab bo‘lmadi.") }
    }

    private func apply(_ events: [PrayerEvent], prune: Bool = true) async throws {
        let notifications = events.filter { $0.kind != .alarm }
        let existing = Set((await center.pendingNotificationRequests()).map(\.identifier).filter { $0.hasPrefix("namoz.") })
        try Task.checkCancellation()
        if prune { center.removePendingNotificationRequests(withIdentifiers: Array(existing.subtracting(notifications.map(\.id)))) }
        var errors: [String] = []
        if !notifications.isEmpty {
            let settings = await center.notificationSettings()
            if settings.authorizationStatus == .denied {
                errors.append("Bildirishnomalar uchun iPhone sozlamalarida ruxsat bering.")
            } else {
                for event in notifications where !existing.contains(event.id) {
                    try Task.checkCancellation()
                    do { try await event.notify(using: center) }
                    catch { errors.append("Bildirishnomani rejalashtirib bo‘lmadi."); break }
                }
            }
        }
        if #available(iOS 26, *) {
            do { try await updateAlarms(events.filter { $0.kind == .alarm }, prune: prune) }
            catch { errors.append(error.localizedDescription) }
        }
        if !errors.isEmpty { throw AlertProblem(message: errors.joined(separator: " ")) }
    }

    @available(iOS 26, *)
    private func updateAlarms(_ events: [PrayerEvent], prune: Bool) async throws {
        let manager = AlarmManager.shared
        guard manager.authorizationState == .authorized else {
            if events.isEmpty { return }
            throw AlertProblem(message: "Uyg‘otuvchi signal uchun iPhone sozlamalarida ruxsat bering.")
        }
        var existing = Set(try manager.alarms.map(\.id))
        #if DEBUG
        existing.remove(Self.testID)
        #endif
        if prune {
            for id in existing.subtracting(events.map(\.alarmID)) { try manager.cancel(id: id) }
        }
        for event in events where !existing.contains(event.alarmID) {
            try Task.checkCancellation()
            try await scheduleAlarm(id: event.alarmID, date: event.fire, name: event.title)
        }
    }

    @available(iOS 26, *)
    private static func makeAlert(title: LocalizedStringResource) -> AlarmPresentation.Alert {
        if #available(iOS 26.1, *) { return .init(title: title) }
        return .init(title: title, stopButton: AlarmButton(text: "To‘xtatish", textColor: .white, systemImageName: "stop.fill"))
    }

    @available(iOS 26, *)
    private func scheduleAlarm(id: UUID, date: Date, name: String) async throws {
        let alert = Self.makeAlert(title: "\(name)")
        let attributes = AlarmAttributes<PrayerAlarmMetadata>(presentation: .init(alert: alert), tintColor: Palette.green)
        _ = try await AlarmManager.shared.schedule(id: id, configuration: .alarm(schedule: .fixed(date), attributes: attributes))
    }

    #if DEBUG
    private static let testID = UUID(uuidString: "BCED0C83-1351-4387-836E-78D305D9FE2A")!

    @available(iOS 26, *)
    func testAlarm(for prayer: Prayer) async throws -> Date {
        let manager = AlarmManager.shared
        guard try await manager.requestAuthorization() == .authorized else {
            throw AlertProblem(message: "Uyg‘otuvchi signal uchun iPhone sozlamalarida ruxsat bering.")
        }
        if try manager.alarms.contains(where: { $0.id == Self.testID }) {
            try manager.cancel(id: Self.testID)
        }
        let date = Date().addingTimeInterval(60)
        try await scheduleAlarm(id: Self.testID, date: date, name: "\(prayer.rawValue) · Sinov signali")
        return date
    }
    #endif
}
