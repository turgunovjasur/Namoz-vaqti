import SwiftUI

enum ScriptStyle: String, CaseIterable { case uthmani = "Usmoniy", simple = "Imloviy" }

struct ReadingPreferences: DynamicProperty {
    @AppStorage("qori.arabicSize") var arabicSize = 30
    @AppStorage("qori.translationSize") var translationSize = 16
    @AppStorage("qori.showTranslation") var showTranslation = true
    @AppStorage("qori.script") var script = ScriptStyle.uthmani
    @AppStorage("qori.reciter") var reciter = Reciter.alafasy
}

struct VerseText: View {
    let verse: Verse
    var preferences = ReadingPreferences()
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(verbatim: preferences.script == .uthmani ? verse.uthmani : verse.simple)
                .font(.custom("AmiriQuranColored-Regular", size: CGFloat(preferences.arabicSize), relativeTo: .body))
                .lineSpacing(7)
                .multilineTextAlignment(.leading)
                .environment(\.layoutDirection, .rightToLeft)
                .frame(maxWidth: .infinity, alignment: .trailing)
            if preferences.showTranslation {
                Text(verbatim: verse.translation)
                    .font(.custom("HelveticaNeue", size: CGFloat(preferences.translationSize), relativeTo: .body))
            }
        }.fixedSize(horizontal: false, vertical: true).foregroundStyle(Palette.ink)
    }
}

struct ReaderView: View {
    let surah: Surah
    let previewVerse: Verse
    private var preferences = ReadingPreferences()
    @StateObject private var audio = RecitationPlayer()
    @State private var settingsOpen = false
    @State private var expandedNotes = Set<Int>()

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 10) {
                Text("\(surah.id)-sura · \(surah.verses.count) oyat")
                    .foregroundStyle(.secondary).font(.subheadline)
                ForEach(surah.verses) { verse in
                    VStack(alignment: .leading, spacing: 4) {
                        VerseText(verse: verse)
                        HStack(spacing: 8) {
                            Button {
                                audio.toggle(surah: surah.id, verse: verse.id, reciter: preferences.reciter)
                            } label: {
                                HStack(spacing: 6) {
                                    Group {
                                        if audio.activeVerse == verse.id && audio.isLoading {
                                            ProgressView().controlSize(.small)
                                        } else {
                                            Image(systemName: audio.activeVerse == verse.id ? "stop.fill" : "play.fill")
                                        }
                                    }.frame(width: 28, height: 28)
                                        .background(Palette.green.opacity(0.09), in: RoundedRectangle(cornerRadius: 8))
                                    Text("\(verse.id)-oyat").font(.subheadline.weight(.semibold))
                                }.frame(minHeight: 44).contentShape(Rectangle())
                            }
                            .accessibilityLabel(audio.activeVerse == verse.id ? "Qiroatni to‘xtatish" : "\(verse.id)-oyatni tinglash")
                            .accessibilityValue(audio.activeVerse == verse.id && audio.isLoading ? "Yuklanmoqda" : "")
                            Spacer()
                            if preferences.showTranslation, verse.note != nil {
                                Button {
                                    if !expandedNotes.insert(verse.id).inserted { expandedNotes.remove(verse.id) }
                                } label: {
                                    HStack(spacing: 4) {
                                        Text("Izoh")
                                        Image(systemName: expandedNotes.contains(verse.id) ? "chevron.down" : "chevron.right")
                                            .font(.caption)
                                    }.frame(minWidth: 44, minHeight: 44)
                                }.accessibilityValue(expandedNotes.contains(verse.id) ? "Ochiq" : "Yopiq")
                            }
                        }.foregroundStyle(Palette.green).buttonStyle(.plain)
                        if preferences.showTranslation, expandedNotes.contains(verse.id), let note = verse.note {
                            Text(verbatim: note)
                                .font(.custom("HelveticaNeue", size: CGFloat(preferences.translationSize), relativeTo: .body))
                        }
                    }.padding(.horizontal, 14).padding(.vertical, 8)
                        .background(Palette.card, in: RoundedRectangle(cornerRadius: 15))
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("Tarjima · Muhammad Sodiq Muhammad Yusuf")
                    Link("Matn manbasi · Tanzil Project", destination: URL(string: "https://tanzil.net")!)
                    Link("Qiroat · EveryAyah", destination: URL(string: "https://everyayah.com/")!)
                }.font(.footnote).padding(.vertical, 8)
            }.padding(.horizontal, 16)
        }
        .background(Palette.paper)
        .navigationTitle(surah.name)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { audio.stop(); settingsOpen = true } label: { Image(systemName: "gearshape") }
                    .accessibilityLabel("O‘qish sozlamalari")
            }
        }
        .sheet(isPresented: $settingsOpen) { ReaderSettings(preview: previewVerse) }
        .onDisappear { audio.stop() }
        .alert("Qiroatni eshitib bo‘lmadi", isPresented: $audio.failed) {
            Button("Yopish") {}
        } message: { Text("Internet aloqasini tekshirib, oyatni yana bosing.") }
    }
}
