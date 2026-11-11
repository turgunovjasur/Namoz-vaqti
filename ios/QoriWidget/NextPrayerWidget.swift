import SwiftUI
import WidgetKit

private struct Entry: TimelineEntry {
    let date: Date
    let snapshot: PrayerWidgetSnapshot
    static var example: Self { Self(date: Date(), snapshot: .example) }
}

private struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry { .example }
    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        if context.isPreview { completion(.example); return }
        Task { completion(await timeline().entries[0]) }
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        Task { completion(await timeline()) }
    }
    private func timeline() async -> Timeline<Entry> {
        let now = Date()
        let settings = WidgetSettings.read()
        var rows: [PrayerWidgetRow] = []
        var boundaries: Set<Date> = [now]
        var month: PrayerMonth?
        var day = now
        if let settings {
            for _ in 0..<3 {
                do {
                    if month?.meta.ym != PrayerClock.month(day) {
                        month = try await PrayerMonth.load(slug: settings.slug, date: day)
                    }
                    guard let schedule = try month?.day(day) else { break }
                    rows += PrayerWidgetSnapshot.rows(day: schedule, date: day, offsets: settings.offsets)
                    day = PrayerClock.tomorrow(day)
                    boundaries.insert(PrayerClock.calendar.startOfDay(for: day))
                } catch { break }
            }
        }
        for row in rows where row.time > now { boundaries.insert(row.time) }
        let entries = boundaries.sorted().map { date in
            Entry(date: date, snapshot: PrayerWidgetSnapshot(date: date, region: settings?.regionName ?? "", rows: rows))
        }
        return Timeline(entries: entries, policy: .after(now.addingTimeInterval(rows.isEmpty ? 900 : 21600)))
    }
}

private struct PrayerWidgetView: View {
    let entry: Entry
    @Environment(\.widgetFamily) private var family
    private var style: PrayerWidgetStyle {
        switch family {
        case .systemMedium: return .wide
        case .systemLarge: return .daily
        case .accessoryRectangular: return .lockScreen
        default: return .compact
        }
    }
    @ViewBuilder var body: some View {
        if #available(iOS 17, *) {
            PrayerWidgetContent(snapshot: entry.snapshot, style: style)
                .containerBackground(for: .widget) {
                    if style != .lockScreen {
                        style == .compact ? PrayerWidgetContent.green : PrayerWidgetContent.paper
                    }
                }
        } else if style == .lockScreen {
            PrayerWidgetContent(snapshot: entry.snapshot, style: style)
        } else {
            PrayerWidgetContent(snapshot: entry.snapshot, style: style).padding()
                .background(style == .compact ? PrayerWidgetContent.green : PrayerWidgetContent.paper)
        }
    }
}

@main
struct NextPrayerWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: WidgetSettings.kind, provider: Provider()) { entry in
            PrayerWidgetView(entry: entry).widgetURL(URL(string: "qori-namoz://times"))
        }
        .configurationDisplayName("Namoz vaqtlari")
        .description("Ixcham, keng, kunlik jadval va qulf ekrani. Namoz nomi va boshlanish vaqti.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular])
    }
}
