import SwiftUI
import PDFKit

private enum AdvicePage: Hashable {
    case unread, catalog, saved, settings, advice(String)
}

struct NasihatView: View {
    @EnvironmentObject private var store: NasihatStore
    @EnvironmentObject private var notifications: AdviceNotifications
    @State private var path: [AdvicePage] = []

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if !store.unread.isEmpty { unreadNotice }
                    if let item = store.latest {
                        Label("Eng oxirgi nasihat", systemImage: "text.book.closed")
                            .font(.subheadline.weight(.medium)).foregroundStyle(Palette.green)
                        AdviceCard(advice: item.advice)
                        if item.readAt == nil {
                            Button { store.markRead(id: item.id) } label: {
                                Label("O‘qidim", systemImage: "checkmark").font(.headline)
                                    .frame(maxWidth: .infinity).padding(.vertical, 12)
                            }.buttonStyle(.borderedProminent)
                        } else {
                            Label("O‘qilgan", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(Palette.green).font(.subheadline)
                        }
                    } else {
                        VStack(spacing: 20) {
                            Image(systemName: "books.vertical").font(.system(size: 44)).foregroundStyle(Palette.green)
                            Text(store.state.queue.items.isEmpty ? "Nasihat manbasini tanlang" : "Nasihatlar tayyor")
                                .font(.title2.bold())
                            Text(store.state.queue.items.isEmpty
                                 ? "Kitobni yuklab oling va sozlamalarda nasihat uchun belgilang."
                                 : "Yangi nasihat belgilangan vaqtda keladi.")
                                .multilineTextAlignment(.center).foregroundStyle(.secondary)
                            NavigationLink("Manbalarni ochish", value: AdvicePage.catalog).buttonStyle(.borderedProminent)
                            if !store.downloaded.isEmpty { NavigationLink("Nasihat sozlamalari", value: AdvicePage.settings) }
                        }.padding(28).padding(.top, 40)
                    }
                    if store.state.preferences.notificationsEnabled, let issue = notifications.issue {
                        NavigationLink(value: AdvicePage.settings) {
                            Label(issue, systemImage: "bell.badge").font(.footnote)
                                .frame(maxWidth: .infinity, alignment: .leading).padding(14)
                                .background(Palette.green.opacity(0.06), in: RoundedRectangle(cornerRadius: 14))
                        }
                    }
                }.padding()
            }
            .background(Palette.paper).navigationTitle("Nasihat")
            .navigationDestination(for: AdvicePage.self) { page in
                switch page {
                case .unread: UnreadAdviceView()
                case .catalog: AdviceCatalogView()
                case .saved: SavedAdviceView()
                case .settings: AdviceSettingsView()
                case .advice(let id): AdviceReadView(deliveryID: id)
                }
            }
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    NavigationLink(value: AdvicePage.catalog) {
                        Image(systemName: "books.vertical").frame(minWidth: 36, minHeight: 44)
                    }.accessibilityLabel("Manbalarni tanlash")
                    NavigationLink(value: AdvicePage.saved) {
                        Image(systemName: "bookmark").frame(minWidth: 36, minHeight: 44)
                    }.accessibilityLabel("Saqlangan nasihatlar")
                    NavigationLink(value: AdvicePage.settings) {
                        Image(systemName: "gearshape").frame(minWidth: 36, minHeight: 44)
                    }.accessibilityLabel("Nasihat sozlamalari")
                }
            }
        }
        .onReceive(store.$notificationRoute) { route in
            if let route { path = [.advice(route.deliveryID)] }
        }
        .alert("Nasihat", isPresented: Binding(get: { store.error != nil }, set: { if !$0 { store.error = nil } })) {
            Button("Tushunarli") { store.error = nil }
        } message: { Text(store.error ?? "") }
    }

    private var unreadNotice: some View {
        VStack(alignment: .leading, spacing: 12) {
            if store.state.queue.pausedUntilRead {
                Label {
                    Text("Sizda o‘qilmagan nasihatlar bor. Hammasini o‘qib tasdiqlamaguningizcha yangi nasihat kelmaydi.")
                } icon: { Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange) }
                    .font(.subheadline)
            }
            NavigationLink(value: AdvicePage.unread) {
                HStack {
                    Text("O‘qilmaganlar · \(store.unread.count)").bold()
                    Spacer()
                    Image(systemName: "chevron.right")
                }.padding(.vertical, 4)
            }
        }.padding(16).background(store.state.queue.pausedUntilRead ? Color.orange.opacity(0.12) : Palette.green.opacity(0.07),
                                in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct UnreadAdviceView: View {
    @EnvironmentObject private var store: NasihatStore
    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                if store.unread.isEmpty {
                    Label("Barcha nasihatlarni o‘qidingiz", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(Palette.green).padding(.vertical, 30)
                }
                ForEach(store.unread) { item in
                    NavigationLink(value: AdvicePage.advice(item.id)) {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text("\(item.number)-nasihat").font(.headline)
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption)
                            }
                            Text(item.advice.book.title).font(.subheadline).foregroundStyle(.secondary)
                            Text(item.advice.passage.text).font(.system(.body, design: .serif)).lineLimit(3)
                        }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                            .background(Palette.card, in: RoundedRectangle(cornerRadius: 18))
                    }.buttonStyle(.plain)
                }
            }.padding()
        }.background(Palette.paper).navigationTitle("O‘qilmaganlar")
    }
}

private struct AdviceReadView: View {
    @EnvironmentObject private var store: NasihatStore
    @Environment(\.dismiss) private var dismiss
    let deliveryID: String
    var body: some View {
        ScrollView {
            if let item = store.delivery(id: deliveryID) {
                VStack(alignment: .leading, spacing: 18) {
                    Text("\(item.number)-nasihat · \(item.readAt == nil ? "O‘qilmagan" : "O‘qilgan")")
                        .font(.subheadline).foregroundStyle(.secondary)
                    AdviceCard(advice: item.advice)
                    if item.readAt == nil {
                        Button {
                            if store.markRead(id: item.id) { dismiss() }
                        } label: {
                            Label("O‘qidim", systemImage: "checkmark").font(.headline)
                                .frame(maxWidth: .infinity).padding(.vertical, 12)
                        }.buttonStyle(.borderedProminent)
                        Text("Faqat tasdiqlasangiz o‘qilgan hisoblanadi.")
                            .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                    }
                }.padding()
            } else { Text("Nasihat topilmadi.").padding() }
        }.background(Palette.paper).navigationTitle("Nasihat").navigationBarTitleDisplayMode(.inline)
    }
}

private struct AdviceCard: View {
    @EnvironmentObject private var store: NasihatStore
    let advice: SavedAdvice
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text(advice.passage.text)
                .font(.system(.title3, design: .serif)).lineSpacing(7)
                .foregroundStyle(Palette.ink).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            Divider()
            VStack(alignment: .leading, spacing: 8) {
                Label(advice.book.title, systemImage: "book").font(.headline)
                Text(advice.book.author).font(.subheadline).foregroundStyle(.secondary)
                Text("PDF sahifasi: \(advice.passage.pages) · \(advice.passage.reference)")
                    .font(.footnote).foregroundStyle(.secondary)
                NavigationLink {
                    AdvicePDFView(book: advice.book, page: advice.passage.pageStart)
                } label: { Label("Manbani ochish", systemImage: "arrow.up.right") }
            }
            Button { store.toggleSaved(advice) } label: {
                Label(store.isSaved(advice) ? "Saqlangan" : "Saqlash",
                      systemImage: store.isSaved(advice) ? "bookmark.fill" : "bookmark")
                    .frame(maxWidth: .infinity).padding(.vertical, 8)
            }.buttonStyle(.bordered)
        }
        .padding(22).background(Palette.card, in: RoundedRectangle(cornerRadius: 22))
    }
}

private struct SavedAdviceView: View {
    @EnvironmentObject private var store: NasihatStore
    @State private var filter = "all"
    private var sources: [AdviceBook] {
        Dictionary(grouping: store.state.saved, by: { $0.book.id }).values
            .compactMap { $0.first?.book }.sorted { $0.title < $1.title }
    }
    var body: some View {
        List {
            Section {
                Picker("Manba", selection: $filter) {
                    Text("Barcha manbalar").tag("all")
                    ForEach(sources) { Text($0.title).tag($0.id) }
                }
            }.listRowBackground(Palette.card)
            if store.state.saved.isEmpty {
                Section {
                    VStack(spacing: 12) {
                        Image(systemName: "bookmark").font(.largeTitle)
                        Text("Saqlangan nasihatlar yo‘q").font(.headline)
                        Text("Yoqtirgan nasihatingizdagi «Saqlash» tugmasini bosing.")
                            .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }.frame(maxWidth: .infinity).padding(.vertical, 30)
                }.listRowBackground(Palette.card)
            }
            ForEach(sources.filter { filter == "all" || $0.id == filter }) { book in
                Section(book.title) {
                    ForEach(store.state.saved.filter { $0.book.id == book.id }) { advice in
                        HStack(alignment: .top, spacing: 10) {
                            NavigationLink {
                                ScrollView { AdviceCard(advice: advice).padding() }
                                    .background(Palette.paper).navigationTitle("Nasihat")
                                    .navigationBarTitleDisplayMode(.inline)
                            } label: {
                                VStack(alignment: .leading, spacing: 10) {
                                    Text(advice.passage.text).lineSpacing(3)
                                        .fixedSize(horizontal: false, vertical: true)
                                    Text("PDF sahifasi: \(advice.passage.pages)")
                                        .font(.caption).foregroundStyle(.secondary)
                                }.padding(.vertical, 8)
                            }
                            Button { store.toggleSaved(advice) } label: {
                                Image(systemName: "trash").frame(width: 44, height: 44)
                            }
                            .buttonStyle(.borderless).foregroundStyle(.secondary)
                            .accessibilityLabel("Saqlanganlardan olib tashlash")
                        }
                        .swipeActions {
                            Button("Olib tashlash", role: .destructive) { store.toggleSaved(advice) }
                        }
                    }.listRowBackground(Palette.card)
                }
            }
        }
        .scrollContentBackground(.hidden).background(Palette.paper)
        .navigationTitle("Saqlanganlar")
        .onChange(of: sources.map(\.id)) { ids in
            if filter != "all", !ids.contains(filter) { filter = "all" }
        }
    }
}

private struct AdviceSettingsView: View {
    @EnvironmentObject private var store: NasihatStore
    @EnvironmentObject private var notifications: AdviceNotifications
    @Environment(\.dismiss) private var dismiss
    @State private var draft = AdvicePreferences()
    @State private var loaded = false
    @State private var saving = false
    var body: some View {
        Form {
            Section("Nasihat tartibi") {
                Picker("Tartib", selection: $draft.order) {
                    ForEach(AdviceOrder.allCases, id: \.self) { Text($0.title).tag($0) }
                }.pickerStyle(.segmented)
                Text(draft.order == .sequential ? "Har kitob boshidan ketma-ket o‘qiladi." : "Barcha parchalar o‘qilmaguncha takrorlanmaydi.")
                    .font(.footnote).foregroundStyle(.secondary)
            }.listRowBackground(Palette.card)
            Section {
                Toggle(isOn: $draft.notificationsEnabled) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Nasihat bildirishnomasi")
                        Text("Telefon ekraniga xabar chiqaradi").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if draft.notificationsEnabled {
                    Toggle(isOn: $draft.soundEnabled) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Bildirishnoma ovozi")
                            Text("Xabar kelganda tovush chalinadi").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    if notifications.status == .denied {
                        Link("iPhone sozlamalarini ochish", destination: URL(string: UIApplication.openSettingsURLString)!)
                        Text("Bildirishnomalarga ruxsat berilmagan.").font(.footnote).foregroundStyle(.secondary)
                    } else if notifications.status == .notDetermined {
                        Button("Bildirishnomalarga ruxsat berish") { Task { await notifications.requestPermission() } }
                    }
                }
            } header: { Text("Bildirishnomalar") }
              footer: { Text("Nasihatning boshlanishi ko‘rinadi. Bosilganda to‘liq matn ochiladi. Bildirishnomalar o‘chiq bo‘lsa ham nasihatlar navbatga yig‘iladi.") }
              .listRowBackground(Palette.card)
            Section("Yangi nasihat oralig‘i") {
                Picker("Yangi nasihat", selection: $draft.hours) {
                    ForEach([1, 2, 4, 6, 8, 12, 24], id: \.self) { Text("Har \($0) soatda").tag($0) }
                }
            }.listRowBackground(Palette.card)
            Section {
                DatePicker("Boshlanishi", selection: timeBinding(\.startMinute), displayedComponents: .hourAndMinute)
                    .environment(\.locale, Locale(identifier: "en_GB"))
                DatePicker("Tugashi", selection: timeBinding(\.endMinute), displayedComponents: .hourAndMinute)
                    .environment(\.locale, Locale(identifier: "en_GB"))
                if draft.startMinute == draft.endMinute {
                    Text("Kun davomida").font(.footnote).foregroundStyle(.secondary)
                } else if draft.startMinute > draft.endMinute {
                    Text("Oraliq keyingi kuni tugaydi.").font(.footnote).foregroundStyle(.secondary)
                }
            } header: { Text("Kun davomidagi vaqt") }
              footer: { Text("Yangi nasihatlar shu oraliqda keladi. 3 ta o‘qilmagan nasihat yig‘ilsa, hammasi tasdiqlanguncha yuborish to‘xtaydi.") }
              .listRowBackground(Palette.card)
            Section {
                ForEach(store.books.filter { store.downloaded.contains($0.id) }) { book in
                    Toggle(isOn: Binding(get: { draft.selectedBooks.contains(book.id) }, set: { selected in
                        if selected { draft.selectedBooks.insert(book.id) }
                        else { draft.selectedBooks.remove(book.id) }
                    })) { Label(book.title, systemImage: "book") }
                }
                if store.downloaded.isEmpty {
                    Text("Avval manbalar bo‘limidan kitob yuklab oling.").foregroundStyle(.secondary)
                }
                NavigationLink("Manbalarni ochish") { AdviceCatalogView() }
            } header: { Text("Nasihat manbalari") }
              footer: { Text("Kitoblar navbatlashadi. Har bir kitob uchun o‘qish tartibi alohida saqlanadi.") }
              .listRowBackground(Palette.card)
            Section {
                Button {
                    saving = true
                    Task {
                        if draft.notificationsEnabled { await notifications.requestPermission() }
                        if store.savePreferences(draft) { dismiss() }
                        saving = false
                    }
                } label: { Text("Saqlash").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6) }
                    .buttonStyle(.borderedProminent)
                    .disabled(saving)
            }.listRowBackground(Color.clear)
        }
        .scrollContentBackground(.hidden).background(Palette.paper)
        .navigationTitle("Nasihat sozlamalari").navigationBarTitleDisplayMode(.inline)
        .onAppear { if !loaded { draft = store.state.preferences; loaded = true } }
    }
    private func timeBinding(_ key: WritableKeyPath<AdvicePreferences, Int>) -> Binding<Date> {
        Binding(get: {
            let minute = draft[keyPath: key]
            return Calendar.current.date(bySettingHour: minute / 60, minute: minute % 60, second: 0, of: Date()) ?? Date()
        }, set: { date in
            let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
            draft[keyPath: key] = (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
        })
    }
}

private struct AdviceCatalogView: View {
    @EnvironmentObject private var store: NasihatStore
    @State private var search = ""
    @State private var detail: AdviceBook?
    private var books: [AdviceBook] {
        store.books.filter { search.isEmpty || "\($0.title) \($0.author)".localizedCaseInsensitiveContains(search) }
    }
    var body: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(books) { book in
                    VStack(alignment: .leading, spacing: 12) {
                        Button { detail = book } label: {
                            HStack(alignment: .top, spacing: 18) {
                                AdviceCover(book: book)
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(book.title).font(.title3.bold()).foregroundStyle(Palette.ink)
                                    Text(book.author).foregroundStyle(.secondary)
                                    Text("Tarjima: \(book.translator)").font(.footnote).foregroundStyle(.secondary)
                                    Text("PDF").font(.caption.weight(.medium)).foregroundStyle(.secondary)
                                    Label("Kitob haqida", systemImage: "info.circle").font(.subheadline)
                                }.frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }.buttonStyle(.plain).accessibilityLabel("\(book.title), kitob haqida")
                        AdviceDownloadButton(book: book)
                    }.padding(18).background(Palette.card, in: RoundedRectangle(cornerRadius: 20))
                }
                if books.isEmpty {
                    Text("Kitob topilmadi").foregroundStyle(.secondary).padding(40)
                }
            }.padding()
        }
        .background(Palette.paper).navigationTitle("Manbalar")
        .searchable(text: $search, prompt: "Kitob izlash")
        .sheet(item: $detail) { book in
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        HStack(alignment: .top, spacing: 20) {
                            AdviceCover(book: book)
                            VStack(alignment: .leading, spacing: 8) {
                                Text(book.title).font(.title2.bold())
                                Text(book.author)
                                Text("Tarjima: \(book.translator)").font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                        Text("Kitob haqida").font(.headline)
                        Text(book.description).lineSpacing(5)
                        AdviceDownloadButton(book: book)
                    }.padding(24)
                }
                .background(Palette.paper).navigationTitle("Kitob haqida").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Yopish") { detail = nil } } }
            }.presentationDetents([.large]).environmentObject(store)
        }
    }
}

private struct AdviceDownloadButton: View {
    @EnvironmentObject private var store: NasihatStore
    let book: AdviceBook
    var body: some View {
        if store.downloading.contains(book.id) {
            ProgressView("Yuklanmoqda…").frame(maxWidth: .infinity, minHeight: 44)
        } else if store.downloaded.contains(book.id) {
            VStack(alignment: .leading, spacing: 10) {
                Label("Yuklab olingan", systemImage: "checkmark.circle.fill").font(.subheadline).foregroundStyle(Palette.green)
                NavigationLink { AdviceSettingsView() } label: {
                    Text("Nasihat uchun tanlash").frame(maxWidth: .infinity).padding(.vertical, 6)
                }.buttonStyle(.bordered)
            }
        } else {
            Button { Task { await store.download(book) } } label: {
                Label("Yuklab olish", systemImage: "arrow.down.to.line")
                    .frame(maxWidth: .infinity).padding(.vertical, 6)
            }.buttonStyle(.borderedProminent)
        }
    }
}

private struct AdviceCover: View {
    @EnvironmentObject private var store: NasihatStore
    let book: AdviceBook
    @State private var cover: UIImage?
    var body: some View {
        Group {
            if let cover { Image(uiImage: cover).resizable().scaledToFit() }
            else { Image(systemName: "book.closed").font(.largeTitle).foregroundStyle(Palette.green) }
        }
        .frame(width: 94, height: 132).background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(.black.opacity(0.08)))
        .accessibilityLabel("\(book.title) kitobining birinchi sahifasi")
        .task(id: book.id) {
            let url = store.bundledPDF(book)
            cover = await Task.detached(priority: .utility) {
                PDFDocument(url: url)?.page(at: 0)?.thumbnail(of: CGSize(width: 188, height: 264), for: .mediaBox)
            }.value
        }
    }
}

private struct AdvicePDFView: View {
    @EnvironmentObject private var store: NasihatStore
    let book: AdviceBook
    let page: Int
    var body: some View {
        PDFReader(url: store.localPDF(book), page: page)
            .navigationTitle(book.title).navigationBarTitleDisplayMode(.inline)
    }
}

private struct PDFReader: UIViewControllerRepresentable {
    let url: URL
    let page: Int
    func makeUIViewController(context: Context) -> AdvicePDFController {
        AdvicePDFController(url: url, page: page)
    }
    func updateUIViewController(_ controller: AdvicePDFController, context: Context) {}
}

private final class AdvicePDFController: UIViewController {
    private let url: URL
    private let page: Int
    private var positioned = false

    init(url: URL, page: Int) {
        self.url = url
        self.page = page
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("Use init(url:page:)") }

    override func loadView() {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.displayDirection = .vertical
        view.document = PDFDocument(url: url)
        self.view = view
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !positioned, let pdf = view as? PDFView,
              let destination = pdf.document?.page(at: page - 1) else { return }
        // PDFKit resets an early destination while its first layout is calculated.
        pdf.go(to: destination)
        positioned = true
    }
}
