import SwiftUI

enum PrayerWidgetStyle: String, CaseIterable, Identifiable {
    case compact, wide, daily, lockScreen
    var id: Self { self }
    var title: String {
        switch self {
        case .compact: return "Ixcham"
        case .wide: return "Keng"
        case .daily: return "Kunlik jadval"
        case .lockScreen: return "Qulf ekrani"
        }
    }
    var subtitle: String {
        switch self {
        case .compact: return "Bitta namoz vaqti"
        case .wide: return "Yaqin namozlar"
        case .daily: return "Barcha namoz vaqtlari"
        case .lockScreen: return "Sodda va kichik"
        }
    }
}

struct PrayerWidgetContent: View {
    let snapshot: PrayerWidgetSnapshot
    let style: PrayerWidgetStyle
    static let green = Color(red: 0.035, green: 0.36, blue: 0.25)
    static let paper = Color(red: 0.98, green: 0.97, blue: 0.94)
    private var next: PrayerWidgetRow? { snapshot.upcoming.first }
    private var isDark: Bool { style == .compact }

    var body: some View {
        Group {
            if style == .lockScreen { lockScreen }
            else if next == nil && (style != .daily || snapshot.today.isEmpty) { empty }
            else {
                switch style {
                case .compact: compact
                case .wide: wide
                case .daily: daily
                case .lockScreen: lockScreen
                }
            }
        }
        .foregroundStyle(style == .lockScreen ? Color.primary : isDark ? .white : Self.green)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private var compact: some View {
        VStack(alignment: .leading, spacing: 5) {
            Label("Yordamchi", systemImage: "sunrise").font(.caption2)
            Spacer(minLength: 0)
            if let next {
                Text(next.prayer.rawValue).font(.headline)
                Text(PrayerClock.time(next.time)).font(.system(size: 38, weight: .bold)).monospacedDigit()
                    .lineLimit(1).minimumScaleFactor(0.6)
                if !PrayerClock.calendar.isDate(snapshot.date, inSameDayAs: next.day) {
                    Text("Ertaga").font(.caption2)
                }
            }
            Spacer(minLength: 0)
            Text(snapshot.region).font(.caption2).lineLimit(1).minimumScaleFactor(0.7)
        }
    }
    private var wide: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Yordamchi").font(.caption.bold())
                Spacer(minLength: 4)
                Text(snapshot.region).font(.caption2).lineLimit(1).minimumScaleFactor(0.6)
            }
            HStack(spacing: 8) {
                ForEach(snapshot.upcoming) { item in
                    VStack(spacing: 5) {
                        Text(item.prayer.rawValue).font(.subheadline.bold())
                        Text(PrayerClock.time(item.time)).font(.system(size: 23, weight: .bold)).monospacedDigit()
                            .lineLimit(1).minimumScaleFactor(0.7)
                        if !PrayerClock.calendar.isDate(snapshot.date, inSameDayAs: item.day) {
                            Text("Ertaga").font(.caption2)
                        }
                    }.frame(maxWidth: .infinity, maxHeight: .infinity).padding(.vertical, 6)
                        .foregroundStyle(item.id == next?.id ? .white : Self.green)
                        .background(item.id == next?.id ? Self.green : Self.green.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
    private var daily: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Bugungi namozlar").font(.headline)
            Text(snapshot.region).font(.caption).lineLimit(1)
            if snapshot.today.isEmpty {
                Text("Bugungi jadval topilmadi. Ilovani oching.").font(.caption)
            } else {
                ForEach(snapshot.today) { item in
                    HStack {
                        Text(item.prayer.rawValue)
                        Spacer()
                        Text(PrayerClock.time(item.time)).monospacedDigit().bold()
                    }.font(.subheadline).padding(.horizontal, 10).frame(maxHeight: .infinity)
                        .foregroundStyle(item.id == next?.id ? .white : Self.green)
                        .background(item.id == next?.id ? Self.green : Color.clear, in: RoundedRectangle(cornerRadius: 8))
                }
            }
        }
    }
    private var lockScreen: some View {
        HStack(spacing: 8) {
            Image(systemName: next?.prayer.icon ?? "sunrise").font(.title3)
            VStack(alignment: .leading, spacing: 2) {
                if let next {
                    Text("\(next.prayer.rawValue) · \(PrayerClock.time(next.time))").font(.headline).monospacedDigit()
                        .lineLimit(1).minimumScaleFactor(0.7)
                    Text(PrayerClock.calendar.isDate(snapshot.date, inSameDayAs: next.day) ? snapshot.region : "Ertaga")
                        .font(.caption2).lineLimit(1)
                } else { Text("Jadvalni oching").font(.caption) }
            }
        }
    }
    private var empty: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: "sunrise")
            Text("Namoz vaqtlari").font(.headline)
            Text("Jadvalni ko‘rish uchun Yordamchini oching.").font(.caption)
        }
    }
}
