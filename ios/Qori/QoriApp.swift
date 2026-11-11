import SwiftUI
import WidgetKit

@main
struct QoriApp: App {
    @State private var tab = 0
    @StateObject private var alerts = PrayerAlerts()
    @StateObject private var nasihat = NasihatStore()
    @StateObject private var adviceAlerts = AdviceNotifications()
    @Environment(\.scenePhase) private var phase
    @AppStorage("namoz.region") private var regionID = "Toshkent"
    @AppStorage(PrayerPreferences.key) private var preferences = Data()
    var body: some Scene {
        WindowGroup {
            TabView(selection: $tab) {
                PrayerTimesView().tabItem { Label("Namoz", systemImage: "sunrise") }.tag(0)
                LibraryView().tabItem { Label("Qori", systemImage: "book") }.tag(1)
                NasihatView().tabItem { Label("Nasihat", systemImage: "text.book.closed") }.tag(2)
            }.tint(Palette.green).preferredColorScheme(.light)
            .environmentObject(alerts)
            .environmentObject(nasihat)
            .environmentObject(adviceAlerts)
            .onReceive(alerts.$nasihatNotificationID) { id in
                guard let id else { return }
                tab = 2
                nasihat.openNotification(id: id)
            }
            .onChange(of: nasihat.revision) { _ in adviceAlerts.refresh(state: nasihat.state) }
            .task(id: phase) {
                guard phase == .active else { return }
                while !Task.isCancelled {
                    nasihat.refresh()
                    adviceAlerts.refresh(state: nasihat.state)
                    do { try await Task.sleep(nanoseconds: 15_000_000_000) }
                    catch { return }
                }
            }
            .onOpenURL { url in
                if url.scheme == "qori-namoz", url.host == "times" { tab = 0 }
            }
            .task(id: "\(regionID)/\(preferences.base64EncodedString())/\(phase == .active)") {
                guard phase == .active, let region = PrayerGroup.catalog.lazy.flatMap(\.regions).first(where: { $0.id == regionID }) else { return }
                let settings = WidgetSettings(region: region, preferences: PrayerPreferences(data: preferences))
                if settings.saveIfChanged() {
                    WidgetCenter.shared.reloadTimelines(ofKind: WidgetSettings.kind)
                }
                while !Task.isCancelled {
                    let now = Date()
                    alerts.refresh(region: region, data: preferences, date: now)
                    let midnight = PrayerClock.calendar.startOfDay(for: PrayerClock.tomorrow(now))
                    do { try await Task.sleep(nanoseconds: UInt64(max(1, midnight.timeIntervalSinceNow) * 1_000_000_000)) }
                    catch { return }
                }
            }
        }
    }
}

enum Palette {
    static let paper = Color(red: 0.98, green: 0.97, blue: 0.94)
    static let card = Color(red: 1, green: 0.99, blue: 0.97)
    static let green = Color(red: 0.035, green: 0.40, blue: 0.27)
    static let ink = Color(red: 0.10, green: 0.22, blue: 0.18)
}

struct LibraryView: View {
    @AppStorage("qori.selected") private var savedIDs = ""
    @State private var library: [Surah] = []
    @State private var loadFailed = false
    @State private var adding = false
    private var selected: Set<Int> { Set(savedIDs.split(separator: ",").compactMap { Int($0) }) }

    var body: some View {
        NavigationStack {
            Group {
                if loadFailed {
                    Text("Qur’on matnini ochib bo‘lmadi.")
                } else if library.isEmpty {
                    ProgressView("Suralar yuklanmoqda…")
                } else {
                    VStack(alignment: .leading, spacing: 12) {
                        ViewThatFits(in: .horizontal) {
                            HStack { sectionTitle; Spacer(); addButton }
                            VStack(alignment: .leading, spacing: 8) { sectionTitle; addButton }
                        }
                        .padding(.horizontal)
                        if selected.isEmpty {
                            Text("O‘qishni boshlash uchun sura qo‘shing.")
                                .foregroundStyle(.secondary).padding()
                            Spacer()
                        } else {
                            List(library.filter { selected.contains($0.id) }) { surah in
                                NavigationLink {
                                    ReaderView(surah: surah, previewVerse: library[0].verses[0])
                                } label: { SurahLabel(surah: surah) }
                                .listRowBackground(Palette.card)
                            }
                            .listStyle(.plain).scrollContentBackground(.hidden)
                        }
                    }
                    .padding(.top, 8)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Palette.paper)
            .navigationTitle("Qori")
            .sheet(isPresented: $adding) {
                NavigationStack {
                    List(library) { s in
                        Button {
                            var ids = selected
                            if ids.contains(s.id) { ids.remove(s.id) } else { ids.insert(s.id) }
                            savedIDs = ids.sorted().map(String.init).joined(separator: ",")
                        } label: {
                            HStack {
                                SurahLabel(surah: s)
                                Spacer()
                                if selected.contains(s.id) { Image(systemName: "checkmark").foregroundStyle(Palette.green) }
                            }.contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityValue(selected.contains(s.id) ? "Tanlangan" : "Tanlanmagan")
                        .listRowBackground(Palette.card)
                    }
                    .scrollContentBackground(.hidden).background(Palette.paper)
                    .navigationTitle("Sura qo‘shish")
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Tayyor") { adding = false } } }
                }.tint(Palette.green)
            }
            .task {
                guard library.isEmpty, !loadFailed else { return }
                do {
                    guard let directory = Bundle.main.resourceURL else { throw Quran.LoadError.missingResource("bundle") }
                    library = try await Task.detached { try Quran.load(from: directory) }.value
                } catch { loadFailed = true }
            }
        }
    }
    private var sectionTitle: some View { Text("Tanlangan suralar").font(.title3.bold()) }
    private var addButton: some View {
        Button { adding = true } label: { Label("Sura qo‘shish", systemImage: "plus") }
            .buttonStyle(.borderedProminent)
    }
}

private struct SurahLabel: View {
    let surah: Surah
    var body: some View {
        HStack(spacing: 14) {
            Text(String(format: "%02d", surah.id)).font(.subheadline.monospacedDigit())
                .foregroundStyle(.secondary).frame(minWidth: 32, alignment: .leading)
            Text(surah.name).foregroundStyle(Palette.ink)
        }.padding(.vertical, 6)
    }
}
