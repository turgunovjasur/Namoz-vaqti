import Foundation
@main struct Check {
    @MainActor static func main() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("nasihat-check-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: root) }
        let catalog = URL(fileURLWithPath: CommandLine.arguments[1])
        let now = Date()
        let store = NasihatStore(root: root, catalogRoot: catalog, clock: { now })
        precondition(store.error == nil && store.books.count == 1 && store.unread.isEmpty)
        let book = store.books[0]
        await store.download(book)
        await store.download(book)
        precondition(store.error == nil && store.downloaded.contains(book.id))
        var selected = AdvicePreferences(); selected.selectedBooks = [book.id]
        selected.startMinute = 0; selected.endMinute = 0
        precondition(store.savePreferences(selected))
        precondition(store.unread.count == 1 && store.state.queue.items.count == 3)
        let first = store.unread[0]
        store.toggleSaved(first.advice)
        store.openNotification(id: first.id)
        precondition(store.unread.count == 1 && store.notificationRoute?.deliveryID == first.id)
        let later = now.addingTimeInterval(2 * 86400)
        let restored = NasihatStore(root: root, catalogRoot: catalog, clock: { later })
        precondition(restored.error == nil && restored.state.saved == [first.advice])
        precondition(restored.unread.count == 3 && restored.state.queue.pausedUntilRead)
        precondition(restored.markRead(id: first.id))
        precondition(restored.unread.count == 2 && restored.state.queue.pausedUntilRead)
        selected.selectedBooks = []
        precondition(restored.savePreferences(selected))
        precondition(restored.unread.count == 2, "Deselecting source must not discard unread advice")
        let twice = NasihatStore(root: root, catalogRoot: catalog, clock: { later })
        precondition(twice.unread.count == 2 && twice.state.queue.pausedUntilRead)
        precondition(twice.state.saved == [first.advice])

        // Simulate an old installation: a single current excerpt and bookmarks.
        let full = try JSONDecoder().decode(AdviceCorpus.self, from: Data(contentsOf: catalog.appendingPathComponent(book.corpus)))
        let original = full.passages[1]
        let prior = SavedAdvice(book: book, passage: original)
        let oldData = try JSONSerialization.jsonObject(with: JSONEncoder().encode(prior))
        let legacy: [String: Any] = [
            "preferences": ["hours": 4, "startMinute": 0, "endMinute": 0, "selectedBooks": [book.id]],
            "saved": [oldData], "current": oldData, "shownAt": now.timeIntervalSinceReferenceDate
        ]
        try JSONSerialization.data(withJSONObject: legacy).write(to: root.appendingPathComponent("state.json"))
        let longText = String(repeating: "To‘liq asl matn. ", count: 1000) + "OXIRI."
        let expanded = AdvicePassage(id: original.id, text: longText, pageStart: original.pageStart,
                                     pageEnd: original.pageEnd, reference: original.reference)
        let updatedCatalog = root.appendingPathComponent("updated-catalog")
        try FileManager.default.copyItem(at: catalog, to: updatedCatalog)
        let update = AdviceCorpus(title: full.title, author: full.author, translator: full.translator,
                                  passages: full.passages.map { $0.id == expanded.id ? expanded : $0 })
        try JSONEncoder().encode(update).write(to: updatedCatalog.appendingPathComponent(book.corpus))
        let upgraded = NasihatStore(root: root, catalogRoot: updatedCatalog, clock: { later })
        precondition(upgraded.error == nil)
        precondition(upgraded.unread.count == 1 && upgraded.unread[0].advice.passage.text == longText)
        precondition(upgraded.state.saved.first?.id == prior.id && upgraded.state.saved.first?.passage.text == longText)
        precondition(upgraded.state.preferences.order == .sequential && upgraded.state.current == nil)
        let upgradedAgain = NasihatStore(root: root, catalogRoot: updatedCatalog, clock: { later })
        precondition(upgradedAgain.state.queue == upgraded.state.queue)
        try Data("different PDF".utf8).write(to: updatedCatalog.appendingPathComponent(book.pdf))
        try JSONEncoder().encode(full).write(to: updatedCatalog.appendingPathComponent(book.corpus))
        let changedPDF = NasihatStore(root: root, catalogRoot: updatedCatalog, clock: { later })
        precondition(changedPDF.error == nil && changedPDF.state.saved == upgraded.state.saved)
        print("PASS: install, duplicate install, queue persistence, tap not read, saved independent, partial pause, source deselection, legacy migration, full long text update, changed-PDF protection")
    }
}
