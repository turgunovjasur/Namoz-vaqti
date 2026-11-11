import Foundation

@main struct PrayerWidgetChecks {
    static func main() throws {
        let day = try PrayerDay(["bomdod":"05:45", "quyosh":"07:06", "peshin":"12:07", "asr":"15:26", "shom":"17:12", "xufton":"18:29"])
        let base = PrayerClock.calendar.date(from: DateComponents(year: 2026, month: 11, day: 11))!
        let tomorrow = PrayerClock.tomorrow(base)
        let rows = PrayerWidgetSnapshot.rows(day: day, date: base, offsets: ["Asr": 10])
            + PrayerWidgetSnapshot.rows(day: day, date: tomorrow, offsets: ["Asr": 10])
        let at = base.addingTimeInterval(14 * 3600)
        let snapshot = PrayerWidgetSnapshot(date: at, region: "Sinov", rows: rows)
        precondition(snapshot.upcoming.map(\.prayer) == [.asr, .shom, .xufton])
        precondition(PrayerClock.time(snapshot.upcoming[0].time) == "15:36")
        precondition(snapshot.today.count == 6 && snapshot.today[1].prayer == .quyosh)
        let morning = PrayerWidgetSnapshot(date: base.addingTimeInterval(6 * 3600), region: "Sinov", rows: rows)
        precondition(morning.upcoming.first?.prayer == .peshin, "Sunrise is in daily schedule but not next-prayer selection")
        let night = PrayerWidgetSnapshot(date: base.addingTimeInterval(23 * 3600), region: "Sinov", rows: rows)
        precondition(night.upcoming.first?.prayer == .bomdod)
        precondition(night.today.allSatisfy { PrayerClock.calendar.isDate($0.day, inSameDayAs: base) })
        let midnight = PrayerWidgetSnapshot(date: tomorrow, region: "Sinov", rows: rows)
        precondition(midnight.today.allSatisfy { PrayerClock.calendar.isDate($0.day, inSameDayAs: tomorrow) })
        precondition(PrayerWidgetSnapshot(date: at, region: "", rows: []).upcoming.isEmpty)
        let loadedKey = "old-region" + PrayerClock.day(base)
        let wrongRegion = PrayerWidgetSnapshot.loaded(date: at, region: "New", slug: "new-region", loadedKey: loadedKey,
                                                     today: day, tomorrow: day, offsets: [:])
        precondition(wrongRegion.rows.isEmpty, "Old region schedule must not be relabeled as new region")
        let wrongDay = PrayerWidgetSnapshot.loaded(date: tomorrow, region: "Old", slug: "old-region", loadedKey: loadedKey,
                                                  today: day, tomorrow: day, offsets: [:])
        precondition(wrongDay.rows.isEmpty, "Yesterday's schedule must not be relabeled as today")
        let valid = PrayerWidgetSnapshot.loaded(date: at, region: "Old", slug: "old-region", loadedKey: loadedKey,
                                               today: day, tomorrow: day, offsets: [:])
        precondition(valid.today.count == 6 && valid.upcoming.count == 3)
        print("PASS: widget next-three, sunrise exclusion, offsets, midnight, empty data")
    }
}
