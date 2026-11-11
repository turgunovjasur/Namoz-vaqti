import AVFAudio
import SwiftUI

struct PrayerOptionsView: View {
    let prayer: Prayer
    let day: PrayerDay
    let date: Date
    let original: PrayerPreference
    let save: (PrayerPreference) throws -> Void

    @State private var draft: PrayerPreference
    #if DEBUG
    @EnvironmentObject private var alerts: PrayerAlerts
    @State private var testTime: Date?
    #endif
    @State private var saving = false
    @State private var error: String?
    @State private var player: AVAudioPlayer?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    init(prayer: Prayer, day: PrayerDay, date: Date, original: PrayerPreference,
         save: @escaping (PrayerPreference) throws -> Void) {
        self.prayer = prayer
        self.day = day
        self.date = date
        self.original = original
        self.save = save
        _draft = State(initialValue: original)
    }

    var body: some View {
        let time = day.instant(prayer, on: date, offset: draft.offset)
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Siz sozlagan vaqt").font(.subheadline)
                        Text(PrayerClock.time(time)).font(.system(size: 40, weight: .bold)).monospacedDigit()
                            .foregroundStyle(Palette.green)
                        Text("Jadval bo‘yicha \(day.times[prayer] ?? "")").font(.footnote).foregroundStyle(.secondary)
                    }.padding(.vertical, 4)
                    Stepper(value: $draft.offset, in: -30...30) {
                        Text("Vaqt farqi   \(draft.offset > 0 ? "+" : "")\(draft.offset) daq")
                    }
                }
                Section("Oldindan eslatish") {
                    ForEach([0, 5, 10, 15, 30], id: \.self) { minutes in
                        Button { draft.reminder = minutes } label: {
                            HStack(spacing: 12) {
                                Image(systemName: draft.reminder == minutes ? "largecircle.fill.circle" : "circle")
                                    .foregroundStyle(draft.reminder == minutes ? Palette.green : .secondary)
                                Text(minutes == 0 ? "O‘chirilgan" : "\(minutes) daqiqa oldin")
                                    .foregroundStyle(Palette.ink)
                            }.frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                        }.buttonStyle(.plain)
                            .accessibilityAddTraits(draft.reminder == minutes ? .isSelected : [])
                    }
                    if draft.reminder > 0 {
                        Label("Eslatma \(PrayerClock.time(time.addingTimeInterval(Double(-60 * draft.reminder)))) da keladi.", systemImage: "bell")
                            .font(.subheadline).foregroundStyle(Palette.green)
                    }
                }
                Section {
                    Picker("Signal", selection: $draft.signal) {
                        ForEach(PrayerSignal.allCases, id: \.self) { signal in
                            if signal != .alarm || PrayerAlerts.supportsAlarms {
                                Text(signal.title).tag(signal)
                            }
                        }
                    }
                    if draft.signal == .chime {
                        Button { preview() } label: { Label("Ovozni tinglash", systemImage: "play.circle") }
                    }
                } header: { Text("Namoz vaqtidagi signal") }
                  footer: { Text("Oldindan eslatishdan alohida sozlanadi.") }
                #if DEBUG
                if #available(iOS 26, *) {
                    Section("Telefonda tekshirish") {
                        Button("1 daqiqadan keyin signalni sinash") {
                            Task { @MainActor in
                                guard !saving else { return }
                                saving = true
                                defer { saving = false }
                                do {
                                    testTime = try await alerts.testAlarm(for: prayer)
                                    error = nil
                                } catch { self.error = error.localizedDescription }
                            }
                        }
                        if let testTime {
                            Text("Sinov vaqti: \(testTime.formatted(date: .omitted, time: .standard)). Ekranni qulflab kuting.")
                                .font(.footnote)
                        }
                    }
                }
                #endif
                if let error {
                    Section {
                        Text(error).foregroundStyle(.red)
                        Button("iPhone sozlamalarini ochish") { openURL(URL(string: UIApplication.openSettingsURLString)!) }
                    }
                }
            }
            .scrollContentBackground(.hidden).background(Palette.paper)
            .navigationTitle("\(prayer.rawValue) sozlamalari").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Yopish") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Saqlash") { Task { await commit() } } }
            }
            .disabled(saving).interactiveDismissDisabled(saving)
        }
    }

    private func preview() {
        guard let url = Bundle.main.url(forResource: "prayer-chime", withExtension: "wav") else { return }
        player = try? AVAudioPlayer(contentsOf: url)
        player?.play()
    }

    @MainActor private func commit() async {
        guard !saving else { return }
        saving = true
        defer { saving = false }
        do {
            try await PrayerAlerts.authorize(draft, replacing: original)
            try save(draft)
            dismiss()
        } catch { self.error = error.localizedDescription }
    }
}
