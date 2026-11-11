import Foundation
import Combine
import PDFKit

struct AdviceNotificationRoute: Equatable {
    let requestID = UUID()
    let deliveryID: String
}

@MainActor
final class NasihatStore: ObservableObject {
    @Published private(set) var books: [AdviceBook] = []
    @Published private(set) var state = AdviceState()
    @Published private(set) var downloaded: Set<String> = []
    @Published private(set) var downloading: Set<String> = []
    @Published var error: String?
    @Published private(set) var revision = 0
    @Published private(set) var now = Date()
    @Published private(set) var notificationRoute: AdviceNotificationRoute?
    private let clock: () -> Date
    var unread: [AdviceDelivery] { state.queue.unread(at: now) }
    var latest: AdviceDelivery? { state.queue.latestDelivered(at: now) }
    func delivery(id: String) -> AdviceDelivery? { state.queue.items.first { $0.id == id } }
    private var corpora: [String: AdviceCorpus] = [:]
    private let root: URL
    private let catalogRoot: URL
    private var stateFile: URL { root.appendingPathComponent("state.json") }

    init(root: URL? = nil, catalogRoot: URL? = nil, clock: @escaping () -> Date = { Date() }) {
        self.clock = clock
        self.now = clock()
        self.root = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Nasihat", isDirectory: true)
        self.catalogRoot = catalogRoot ?? Bundle.main.resourceURL!.appendingPathComponent("NasihatBooks", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: self.root, withIntermediateDirectories: true)
            books = try JSONDecoder().decode([AdviceBook].self, from: Data(contentsOf: self.catalogRoot.appendingPathComponent("catalog.json")))
            if FileManager.default.fileExists(atPath: stateFile.path) {
                state = try JSONDecoder().decode(AdviceState.self, from: Data(contentsOf: stateFile))
            }
            for book in books {
                let directory = self.root.appendingPathComponent(book.id)
                if FileManager.default.fileExists(atPath: directory.path) {
                    let corpus = try Self.updateInstalledCorpus(book: book, directory: directory, catalog: self.catalogRoot)
                    corpora[book.id] = corpus
                    downloaded.insert(book.id)
                }
            }
            var next = state
            next.saved = state.saved.map(updatedSnapshot)
            for index in next.queue.items.indices {
                next.queue.items[index].advice = updatedSnapshot(next.queue.items[index].advice)
            }
            if let old = state.current, next.queue.items.isEmpty {
                let advice = updatedSnapshot(old)
                next.queue.items = [AdviceDelivery(advice: advice, dueAt: state.shownAt ?? now, activatedAt: now, number: 1)]
                next.queue.usedPassageIDs.insert(advice.id)
                next.queue.nextNumber = 2
                next.queue.nextDueAt = next.preferences.nextAllowed(onOrAfter: now.addingTimeInterval(next.preferences.interval))
            }
            next.current = nil
            next.shownAt = nil
            if next.saved != state.saved || next.queue != state.queue || state.current != nil { try commit(next) }
            refresh()
        } catch { self.error = "Nasihat ma’lumotlarini ochib bo‘lmadi. \(error.localizedDescription)" }
    }

    func bundledPDF(_ book: AdviceBook) -> URL { catalogRoot.appendingPathComponent(book.pdf) }
    func localPDF(_ book: AdviceBook) -> URL { root.appendingPathComponent(book.id).appendingPathComponent(book.pdf) }
    func isSaved(_ advice: SavedAdvice) -> Bool { state.saved.contains { $0.id == advice.id } }

    private func updatedSnapshot(_ advice: SavedAdvice) -> SavedAdvice {
        guard let book = books.first(where: { $0.id == advice.book.id }),
              let passage = corpora[book.id]?.passages.first(where: {
                  $0.id == advice.passage.id && $0.reference == advice.passage.reference
              }) else { return advice }
        return SavedAdvice(book: book, passage: passage)
    }

    nonisolated private static func updateInstalledCorpus(book: AdviceBook, directory: URL, catalog: URL) throws -> AdviceCorpus {
        let installed = try loadCorpus(book: book, directory: directory)
        let installedURL = directory.appendingPathComponent(book.corpus)
        let bundledURL = catalog.appendingPathComponent(book.corpus)
        let newData = try Data(contentsOf: bundledURL)
        guard newData != (try Data(contentsOf: installedURL)) else { return installed }
        // Only expand/reprocess an identical source PDF. A different edition
        // must not silently change the pages behind existing saved excerpts.
        guard try Data(contentsOf: directory.appendingPathComponent(book.pdf)) ==
                Data(contentsOf: catalog.appendingPathComponent(book.pdf)) else { return installed }
        let updated = try loadCorpus(book: book, directory: catalog)
        try newData.write(to: installedURL, options: .atomic)
        return updated
    }

    private func commit(_ next: AdviceState) throws {
        try JSONEncoder().encode(next).write(to: stateFile, options: .atomic)
        state = next
        revision += 1
    }

    func savePreferences(_ preferences: AdvicePreferences) -> Bool {
        var next = state
        let date = clock()
        next.queue.reconfigure(at: date, old: state.preferences, new: preferences)
        next.preferences = preferences
        next.queue.reconcile(at: date, preferences: preferences, books: books, corpora: corpora)
        do {
            try commit(next)
            refresh()
            return true
        } catch {
            self.error = "Sozlamalar saqlanmadi. \(error.localizedDescription)"
            return false
        }
    }

    func toggleSaved(_ advice: SavedAdvice) {
        var next = state
        if isSaved(advice) { next.saved.removeAll { $0.id == advice.id } }
        else { next.saved.insert(advice, at: 0) }
        do { try commit(next) }
        catch { self.error = "Nasihatni saqlab bo‘lmadi. \(error.localizedDescription)" }
    }

    func refresh(at date: Date? = nil, calendar: Calendar = .current) {
        let instant = date ?? clock()
        now = instant
        var next = state
        next.queue.reconcile(at: instant, preferences: next.preferences, books: books, corpora: corpora, calendar: calendar)
        guard next.queue != state.queue else { return }
        do { try commit(next) }
        catch { self.error = "Nasihat navbati saqlanmadi. \(error.localizedDescription)" }
    }

    @discardableResult
    func markRead(id: String) -> Bool {
        let instant = clock()
        now = instant
        var next = state
        next.queue.markRead(id: id, at: instant, preferences: next.preferences)
        guard next.queue != state.queue else { return false }
        next.queue.reconcile(at: instant, preferences: next.preferences, books: books, corpora: corpora)
        do { try commit(next); return true }
        catch { self.error = "O‘qilganlik tasdig‘i saqlanmadi. \(error.localizedDescription)"; return false }
    }

    func openNotification(id: String) {
        refresh()
        guard let item = delivery(id: id), item.isDue(at: now) else { return }
        notificationRoute = AdviceNotificationRoute(deliveryID: id)
    }

    func download(_ book: AdviceBook) async {
        guard !downloading.contains(book.id), !downloaded.contains(book.id) else { return }
        downloading.insert(book.id)
        defer { downloading.remove(book.id) }
        let source = catalogRoot
        let destination = root.appendingPathComponent(book.id, isDirectory: true)
        do {
            // This first admin catalogue ships with the app; installing a book makes
            // its PDF and source-preserving corpus available in the offline library.
            let corpus = try await Task.detached(priority: .userInitiated) {
                let staging = destination.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
                try FileManager.default.createDirectory(at: staging, withIntermediateDirectories: true)
                defer { try? FileManager.default.removeItem(at: staging) }
                for name in [book.pdf, book.corpus] {
                    try FileManager.default.copyItem(at: source.appendingPathComponent(name), to: staging.appendingPathComponent(name))
                }
                let corpus = try Self.loadCorpus(book: book, directory: staging)
                try FileManager.default.moveItem(at: staging, to: destination)
                return corpus
            }.value
            corpora[book.id] = corpus
            downloaded.insert(book.id)
            refresh()
        } catch { self.error = "Kitob yuklanmadi. \(error.localizedDescription)" }
    }

    nonisolated private static func loadCorpus(book: AdviceBook, directory: URL) throws -> AdviceCorpus {
        let corpus = try JSONDecoder().decode(AdviceCorpus.self, from: Data(contentsOf: directory.appendingPathComponent(book.corpus)))
        guard let pdf = PDFDocument(url: directory.appendingPathComponent(book.pdf)),
              !corpus.passages.isEmpty,
              Set(corpus.passages.map(\.id)).count == corpus.passages.count,
              corpus.passages.allSatisfy({ !$0.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && $0.pageStart > 0 && $0.pageEnd >= $0.pageStart && $0.pageEnd <= pdf.pageCount }) else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return corpus
    }
}
