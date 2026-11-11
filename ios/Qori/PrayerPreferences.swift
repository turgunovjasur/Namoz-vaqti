import Foundation

enum PrayerSignal: String, CaseIterable, Codable {
    case off, silent, chime, alarm
    var title: String {
        switch self {
        case .off: return "O‘chiq"
        case .silent: return "Ovozsiz xabar"
        case .chime: return "Qisqa ovoz"
        case .alarm: return "Uyg‘otuvchi signal"
        }
    }
}

struct PrayerPreference: Codable, Equatable {
    var offset = 0
    var reminder = 0
    var signal = PrayerSignal.off
    var usesNotifications: Bool { reminder > 0 || signal == .silent || signal == .chime }
}

struct PrayerPreferences {
    static let key = "namoz.prayerPreferences"
    private var values: [String: PrayerPreference]

    init(data: Data) {
        values = (try? JSONDecoder().decode([String: PrayerPreference].self, from: data)) ?? [:]
    }
    subscript(_ prayer: Prayer) -> PrayerPreference {
        get { values[prayer.rawValue] ?? PrayerPreference() }
        set { values[prayer.rawValue] = newValue }
    }
    func encoded() throws -> Data { try JSONEncoder().encode(values) }
    var hasAlerts: Bool { values.values.contains { $0.reminder > 0 || $0.signal != .off } }
}

extension PrayerClock {
    static func time(_ date: Date) -> String {
        String(format: "%02d:%02d", calendar.component(.hour, from: date), calendar.component(.minute, from: date))
    }

    static func remaining(until target: Date, from now: Date) -> String {
        let minutes = max(0, Int(ceil(target.timeIntervalSince(now) / 60)))
        let hours = minutes / 60
        if hours == 0 { return "\(minutes) daqiqa qoldi" }
        if minutes % 60 == 0 { return "\(hours) soat qoldi" }
        return "\(hours) soat \(minutes % 60) daqiqa qoldi"
    }
}

extension PrayerDay {
    func instant(_ prayer: Prayer, on day: Date, offset: Int) -> Date {
        // PrayerDay validates that all six times are present in HH:mm format.
        let parts = times[prayer]!.split(separator: ":")
        let minutes = Int(parts[0])! * 60 + Int(parts[1])! + offset
        return PrayerClock.calendar.startOfDay(for: day).addingTimeInterval(Double(minutes * 60))
    }

    func nextPrayer(on day: Date, after now: Date, preferences: PrayerPreferences) -> (Prayer, Date)? {
        Prayer.allCases.filter { $0 != .quyosh }.map {
            ($0, instant($0, on: day, offset: preferences[$0].offset))
        }.filter { $0.1 > now }.min { $0.1 < $1.1 }
    }
}
