import SwiftUI

struct PrayerWidgetGalleryView: View {
    let region: PrayerRegion?
    let preferences: PrayerPreferences
    let loadedKey: String
    let today: PrayerDay?
    let tomorrow: PrayerDay?
    @State private var selected = PrayerWidgetStyle.wide
    private func snapshot(at now: Date) -> PrayerWidgetSnapshot {
        let offsets = Dictionary(uniqueKeysWithValues: Prayer.allCases.map { ($0.rawValue, preferences[$0].offset) })
        return PrayerWidgetSnapshot.loaded(date: now, region: region?.name ?? "", slug: region?.slug ?? "",
                                           loadedKey: loadedKey, today: today, tomorrow: tomorrow, offsets: offsets)
    }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Ko‘rinishni oldindan ko‘ring").font(.subheadline).foregroundStyle(.secondary)
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 8) { choices }
                    VStack(alignment: .leading, spacing: 8) { choices }
                }
                TimelineView(.everyMinute) { tick in
                    preview(snapshot: snapshot(at: tick.date)).frame(maxWidth: .infinity)
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text(selected.title).font(.title2.bold())
                    Text(selected.subtitle).foregroundStyle(.secondary)
                }
                VStack(alignment: .leading, spacing: 12) {
                    Label("Ekranga qo‘shish", systemImage: "plus.app").font(.headline)
                    if selected == .lockScreen {
                        Text("1. iPhone qulf ekranini bosib turing va moslashtirishni oching.")
                        Text("2. Vidjetlar joyini bosing va Yordamchini tanlang.")
                        Text("3. To‘rtburchak namoz vidjetini qo‘shing.")
                    } else {
                        Text("1. iPhone bosh ekranidagi bo‘sh joyni bosib turing.")
                        Text("2. Tahrirlash → Vidjet qo‘shish → Yordamchi bo‘limini oching.")
                        Text("3. \(sizeInstruction) ko‘rinishni tanlab, vidjetni qo‘shing.")
                    }
                    Text("Bu yerda oldindan ko‘rinishi berilgan. Vidjet hajmi va joyi iPhone’ning vidjetlar oynasida tanlanadi.")
                        .font(.footnote).foregroundStyle(.secondary)
                }.font(.subheadline).padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.card, in: RoundedRectangle(cornerRadius: 20))
            }.padding()
        }.background(Palette.paper).navigationTitle("Vidjet ko‘rinishi")
            .navigationBarTitleDisplayMode(.inline)
    }
    private var choices: some View {
        ForEach(PrayerWidgetStyle.allCases) { style in
            Button { selected = style } label: {
                Text(style.title).font(.caption.weight(.semibold)).padding(.horizontal, 10).padding(.vertical, 12)
                    .foregroundStyle(selected == style ? .white : Palette.green)
                    .background(selected == style ? Palette.green : Palette.green.opacity(0.07), in: Capsule())
            }.buttonStyle(.plain).accessibilityAddTraits(selected == style ? .isSelected : [])
        }
    }
    private var sizeInstruction: String {
        switch selected {
        case .compact: return "Kichik kvadrat"
        case .wide: return "O‘rta keng"
        case .daily: return "Katta jadval"
        case .lockScreen: return "Qulf ekrani"
        }
    }
    private func preview(snapshot: PrayerWidgetSnapshot) -> some View {
        PrayerWidgetContent(snapshot: snapshot, style: selected)
            .padding(selected == .lockScreen ? 14 : 18)
            .frame(width: selected == .compact ? 164 : nil,
                   height: selected == .compact ? 164 : selected == .daily ? 350 : selected == .lockScreen ? 82 : 164)
            .background(selected == .compact ? PrayerWidgetContent.green : PrayerWidgetContent.paper,
                        in: RoundedRectangle(cornerRadius: 24))
            .overlay(RoundedRectangle(cornerRadius: 24).stroke(Palette.green.opacity(0.12), lineWidth: 1))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 4)
    }
}
