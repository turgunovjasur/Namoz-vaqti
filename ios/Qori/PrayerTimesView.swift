import SwiftUI

struct PrayerTimesView: View {
    @AppStorage("namoz.region") private var regionID = "Toshkent"
    @AppStorage(PrayerPreferences.key) private var preferenceData = Data()
    @EnvironmentObject private var alerts: PrayerAlerts
    @State private var editingPrayer: Prayer?
    private var preferences: PrayerPreferences { PrayerPreferences(data: preferenceData) }
    @State private var choosingRegion = false
    @State private var retry = 0
    @State private var loadedKey = ""
    @State private var failedKey = ""
    @State private var today: PrayerDay?
    @State private var tomorrow: PrayerDay?
    @State private var tomorrowFailed = false

    private var region: PrayerRegion? {
        PrayerGroup.catalog.lazy.flatMap(\.regions).first { $0.id == regionID } ?? PrayerGroup.catalog.first?.regions.first
    }

    var body: some View {
        NavigationStack {
            TimelineView(.everyMinute) { tick in
                if let region {
                    let now = tick.date
                    let key = region.slug + PrayerClock.day(now)
                    ScrollView {
                        VStack(alignment: .leading, spacing: 16) {
                            Button { choosingRegion = true } label: {
                                HStack {
                                    Image(systemName: "location.fill"); Text(region.name).bold()
                                    Spacer(); Image(systemName: "chevron.down")
                                }.padding(14).background(Palette.green.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                            }
                            if loadedKey == key, let today {
                                let following = PrayerClock.tomorrow(now)
                                let upcoming = today.nextPrayer(on: now, after: now, preferences: preferences)
                                    ?? tomorrow?.nextPrayer(on: following, after: now, preferences: preferences)
                                if let (next, target) = upcoming {
                                    VStack(alignment: .leading, spacing: 12) {
                                        HStack(alignment: .firstTextBaseline, spacing: 16) {
                                            Text(PrayerClock.time(target)).font(.system(size: 64, weight: .bold)).monospacedDigit()
                                                .lineLimit(1).minimumScaleFactor(0.65)
                                            Spacer(minLength: 0)
                                            Text(next.rawValue).font(.title.bold()).lineLimit(1).minimumScaleFactor(0.65)
                                        }
                                        if !PrayerClock.calendar.isDate(now, inSameDayAs: target) {
                                            Text("Ertaga").font(.caption)
                                        }
                                        Label(PrayerClock.remaining(until: target, from: now), systemImage: "clock")
                                            .font(.subheadline).monospacedDigit()
                                    }.frame(maxWidth: .infinity, alignment: .leading).padding(20)
                                        .foregroundStyle(.white).background(Palette.green, in: RoundedRectangle(cornerRadius: 18))
                                } else if tomorrowFailed {
                                    retryButton("Ertangi bomdod vaqtini olishning imkoni bo‘lmadi.")
                                } else { ProgressView("Ertangi jadval yuklanmoqda…") }
                                HStack {
                                    Text("Bugungi jadval").font(.title3.bold())
                                    Spacer(); Text(PrayerClock.day(now)).font(.subheadline).foregroundStyle(.secondary)
                                }
                                VStack(spacing: 0) {
                                    ForEach(Prayer.allCases) { item in
                                        Button { editingPrayer = item } label: {
                                            HStack {
                                                Image(systemName: item.icon).frame(width: 24).foregroundStyle(Palette.green)
                                                Text(item.rawValue)
                                                Spacer()
                                                if preferences[item].reminder > 0 || preferences[item].signal != .off {
                                                    Image(systemName: "bell.fill").font(.caption).foregroundStyle(Palette.green)
                                                }
                                                Text(PrayerClock.time(today.instant(item, on: now, offset: preferences[item].offset)))
                                                    .bold().monospacedDigit()
                                                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                                            }.padding(14).contentShape(Rectangle())
                                        }.buttonStyle(.plain)
                                        if item != .xufton { Divider().padding(.horizontal) }
                                    }
                                }.background(Palette.card, in: RoundedRectangle(cornerRadius: 16))
                                if let issue = alerts.issue {
                                    VStack(alignment: .leading) {
                                        Text(issue).font(.footnote)
                                        Button("Qayta urinish") { alerts.refresh(region: region, data: preferenceData, date: now) }
                                    }
                                }
                                Link("Manba · namoz-vaqti.uz", destination: URL(string: "https://namoz-vaqti.uz/")!)
                                    .font(.footnote)
                            } else if failedKey == key {
                                retryButton("Jadvalni olishning imkoni bo‘lmadi. Internet aloqasini tekshiring.")
                            } else { ProgressView("Jadval yuklanmoqda…") }
                        }.padding()
                    }.task(id: "\(key)/\(retry)") { await load(region: region, date: now, key: key) }
                } else { Text("Hududlar ro‘yxatini ochib bo‘lmadi.") }
            }
            .background(Palette.paper).foregroundStyle(Palette.ink)
            .navigationTitle("Namoz vaqtlari")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink {
                        PrayerWidgetGalleryView(region: region, preferences: preferences, loadedKey: loadedKey, today: today, tomorrow: tomorrow)
                    } label: { Image(systemName: "square.grid.2x2") }
                    .accessibilityLabel("Vidjet ko‘rinishlari")
                }
            }
            .sheet(item: $editingPrayer) { prayer in
                if let today {
                    PrayerOptionsView(prayer: prayer, day: today, date: Date(), original: preferences[prayer]) { value in
                        var updated = preferences
                        updated[prayer] = value
                        preferenceData = try updated.encoded()
                    }
                }
            }
            .sheet(isPresented: $choosingRegion) { RegionPicker(regionID: $regionID) }
        }
    }

    private func retryButton(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(message); Button("Qayta urinish") { retry += 1 }
        }
    }

    @MainActor
    private func load(region: PrayerRegion, date: Date, key: String) async {
        failedKey = ""
        tomorrowFailed = false
        do {
            let month = try await PrayerMonth.load(slug: region.slug, date: date)
            let day = try month.day(date)
            try Task.checkCancellation()
            today = day
            let following = PrayerClock.tomorrow(date)
            tomorrow = try? month.day(following)
            loadedKey = key
            if tomorrow == nil {
                do {
                    let nextMonth = try await PrayerMonth.load(slug: region.slug, date: following)
                    try Task.checkCancellation()
                    tomorrow = try nextMonth.day(following)
                } catch { if !Task.isCancelled { tomorrowFailed = true } }
            }
        } catch { if !Task.isCancelled { failedKey = key; loadedKey = "" } }
    }
}

private struct RegionPicker: View {
    @Binding var regionID: String
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""
    var body: some View {
        NavigationStack {
            List {
                Section("1. Viloyat yoki shaharni tanlang") {
                    ForEach(PrayerGroup.catalog.filter {
                        search.isEmpty || $0.name.localizedCaseInsensitiveContains(search)
                    }, id: \.name) { group in
                        NavigationLink {
                            DistrictPicker(group: group, regionID: regionID) { region in
                                regionID = region.id
                                dismiss()
                            }
                        } label: {
                            Text(group.name)
                        }
                    }
                }
            }
            .searchable(text: $search, prompt: "Viloyat yoki shahar")
            .navigationTitle("Hududni tanlang")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Yopish") { dismiss() } } }
        }
    }
}

private struct DistrictPicker: View {
    let group: PrayerGroup
    let regionID: String
    let select: (PrayerRegion) -> Void
    @State private var search = ""

    var body: some View {
        List {
            Section("2. Tuman yoki shaharni tanlang") {
                ForEach(group.regions.filter {
                    search.isEmpty || $0.name.localizedCaseInsensitiveContains(search)
                }) { region in
                    Button { select(region) } label: {
                        HStack {
                            Text(region.name).foregroundStyle(Palette.ink)
                            Spacer()
                            if region.id == regionID { Image(systemName: "checkmark") }
                        }.contentShape(Rectangle())
                    }
                }
            }
        }
        .searchable(text: $search, prompt: "Tuman yoki shahar")
        .navigationTitle(group.name)
        .navigationBarTitleDisplayMode(.inline)
    }
}
