import SwiftUI

struct ReaderSettings: View {
    let preview: Verse
    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var typeSize
    private var prefs = ReadingPreferences()

    var body: some View {
        NavigationStack {
            GeometryReader { size in
                if size.size.width > size.size.height && !typeSize.isAccessibilitySize {
                    HStack(alignment: .top, spacing: 14) {
                        ScrollView { sample }.frame(width: size.size.width * 0.4)
                        ScrollView { controls }
                    }
                } else if typeSize.isAccessibilitySize || size.size.height < 440 {
                    VStack(spacing: 10) {
                        ScrollView { sample }.frame(height: size.size.height * 0.45)
                        ScrollView { controls }
                    }
                } else {
                    VStack(spacing: 14) { sample; ScrollView { controls } }
                }
            }
            .padding(.horizontal, 16).padding(.top, 8)
            .background(Palette.paper)
            .navigationTitle("O‘qish sozlamalari")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Tayyor") { dismiss() } } }
        }.tint(Palette.green)
    }

    private var sample: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("FOTIHA · 1-OYAT").font(.caption.bold()).foregroundStyle(.secondary)
            VerseText(verse: preview)
        }.padding(16).background(Palette.card, in: RoundedRectangle(cornerRadius: 15))
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(spacing: 12) {
                Stepper("Arabcha matn · \(prefs.arabicSize)", value: prefs.$arabicSize, in: 24...36, step: 6)
                Divider()
                Stepper("Tarjima kattaligi · \(prefs.translationSize)",
                        onIncrement: prefs.translationSize < 20 ? { prefs.translationSize = prefs.translationSize < 16 ? 16 : 20 } : nil,
                        onDecrement: prefs.translationSize > 13 ? { prefs.translationSize = prefs.translationSize > 16 ? 16 : 13 } : nil)
                    .disabled(!prefs.showTranslation)
                Divider()
                Toggle("Tarjimani ko‘rsatish", isOn: prefs.$showTranslation)
            }.padding().background(Palette.card, in: RoundedRectangle(cornerRadius: 15))
            VStack(alignment: .leading) {
                Text("Arabcha yozuv").font(.headline)
                Picker("Arabcha yozuv", selection: prefs.$script) {
                    ForEach(ScriptStyle.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }.pickerStyle(.segmented)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Qiroat").font(.headline)
                ForEach(Reciter.allCases) { q in
                    Button { prefs.reciter = q } label: {
                        HStack {
                            Text(q.name).foregroundStyle(Palette.ink); Spacer()
                            Image(systemName: prefs.reciter == q ? "largecircle.fill.circle" : "circle")
                        }.frame(minHeight: 44).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                    .accessibilityValue(prefs.reciter == q ? "Tanlangan" : "")
                }
            }.padding().background(Palette.card, in: RoundedRectangle(cornerRadius: 15))
        }.padding(.bottom, 16)
    }
}
