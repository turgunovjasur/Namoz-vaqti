import Foundation

struct PrayerWidgetRow: Identifiable {
    let prayer: Prayer
    let day: Date
    let time: Date
    var id: String { "\(PrayerClock.day(day))/\(prayer.rawValue)" }
}

struct PrayerWidgetSnapshot {
    let date: Date
    let region: String
    let rows: [PrayerWidgetRow]
    var today: [PrayerWidgetRow] {
        rows.filter { PrayerClock.calendar.isDate($0.day, inSameDayAs: date) }.sorted { $0.time < $1.time }
    }
    var upcoming: [PrayerWidgetRow] {
        Array(rows.filter { $0.prayer != .quyosh && $0.time > date }.sorted { $0.time < $1.time }.prefix(3))
    }
    static func rows(day: PrayerDay, date: Date, offsets: [String: Int]) -> [PrayerWidgetRow] {
        Prayer.allCases.map {
            PrayerWidgetRow(prayer: $0, day: PrayerClock.calendar.startOfDay(for: date),
                            time: day.instant($0, on: date, offset: offsets[$0.rawValue] ?? 0))
        }
    }
    static func loaded(date: Date, region: String, slug: String, loadedKey: String,
                       today: PrayerDay?, tomorrow: PrayerDay?, offsets: [String: Int]) -> Self {
        guard loadedKey == slug + PrayerClock.day(date) else {
            return Self(date: date, region: region, rows: [])
        }
        var values = today.map { rows(day: $0, date: date, offsets: offsets) } ?? []
        if let tomorrow { values += rows(day: tomorrow, date: PrayerClock.tomorrow(date), offsets: offsets) }
        return Self(date: date, region: region, rows: values)
    }
    // Only used for WidgetKit's placeholder/gallery before real data is available.
    static var example: Self {
        let day = try! PrayerDay(["bomdod":"05:45", "quyosh":"07:06", "peshin":"12:07", "asr":"15:26", "shom":"17:12", "xufton":"18:29"])
        let date = PrayerClock.calendar.startOfDay(for: Date()).addingTimeInterval(14 * 3600)
        return Self(date: date, region: "Toshkent shahri", rows: rows(day: day, date: date, offsets: [:]))
    }
}
