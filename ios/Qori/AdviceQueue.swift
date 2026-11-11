import Foundation

struct AdviceBook: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let author: String
    let translator: String
    let description: String
    let pdf: String
    let corpus: String
}

struct AdvicePassage: Codable, Identifiable, Equatable {
    let id: String
    let text: String
    let pageStart: Int
    let pageEnd: Int
    let reference: String
    enum CodingKeys: String, CodingKey {
        case id, text, reference
        case pageStart = "page_start", pageEnd = "page_end"
    }
    var pages: String { pageStart == pageEnd ? "\(pageStart)" : "\(pageStart)–\(pageEnd)" }
}

struct AdviceCorpus: Codable {
    let title: String
    let author: String
    let translator: String
    let passages: [AdvicePassage]
}

struct SavedAdvice: Codable, Identifiable, Equatable {
    let book: AdviceBook
    let passage: AdvicePassage
    var id: String { "\(book.id)/\(passage.id)" }
}

enum AdviceOrder: String, Codable, CaseIterable {
    case sequential, random
    var title: String { self == .sequential ? "Ketma-ket" : "Tasodifiy" }
}

struct AdvicePreferences: Codable, Equatable {
    var hours = 4
    var startMinute = 8 * 60
    var endMinute = 22 * 60
    var selectedBooks: Set<String> = []
    var order: AdviceOrder = .sequential
    var notificationsEnabled = true
    var soundEnabled = true

    init() {}
    enum CodingKeys: String, CodingKey {
        case hours, startMinute, endMinute, selectedBooks, order, notificationsEnabled, soundEnabled
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hours = min(24, max(1, try c.decodeIfPresent(Int.self, forKey: .hours) ?? 4))
        startMinute = min(1439, max(0, try c.decodeIfPresent(Int.self, forKey: .startMinute) ?? 480))
        endMinute = min(1439, max(0, try c.decodeIfPresent(Int.self, forKey: .endMinute) ?? 1320))
        selectedBooks = try c.decodeIfPresent(Set<String>.self, forKey: .selectedBooks) ?? []
        order = try c.decodeIfPresent(AdviceOrder.self, forKey: .order) ?? .sequential
        notificationsEnabled = try c.decodeIfPresent(Bool.self, forKey: .notificationsEnabled) ?? true
        soundEnabled = try c.decodeIfPresent(Bool.self, forKey: .soundEnabled) ?? true
    }
    var interval: TimeInterval { Double(max(1, hours)) * 3600 }
    func allowsRefresh(at date: Date, calendar: Calendar = .current) -> Bool {
        let minute = calendar.component(.hour, from: date) * 60 + calendar.component(.minute, from: date)
        if startMinute == endMinute { return true }
        if startMinute > endMinute { return minute >= startMinute || minute < endMinute }
        return minute >= startMinute && minute < endMinute
    }
    func nextAllowed(onOrAfter date: Date, calendar: Calendar = .current) -> Date {
        if allowsRefresh(at: date, calendar: calendar) { return date }
        let start = DateComponents(hour: startMinute / 60, minute: startMinute % 60, second: 0)
        var cursor = date.addingTimeInterval(-1)
        while let candidate = calendar.nextDate(after: cursor, matching: start,
                                                matchingPolicy: .nextTime, repeatedTimePolicy: .first) {
            // A spring-forward jump may erase the entire daily window.
            if allowsRefresh(at: candidate, calendar: calendar) { return candidate }
            cursor = candidate
        }
        return date
    }
}

struct AdviceDelivery: Codable, Identifiable, Equatable {
    var id = UUID().uuidString
    var advice: SavedAdvice
    var dueAt: Date
    var readAt: Date?
    var activatedAt: Date?
    var number: Int
    func isDue(at date: Date) -> Bool { activatedAt != nil || dueAt <= date }
}

struct AdviceQueue: Codable, Equatable {
    var items: [AdviceDelivery] = []
    var usedPassageIDs: Set<String> = []
    var pausedUntilRead = false
    var nextDueAt: Date?
    var lastBookID: String?
    var timeZoneID: String?
    var nextNumber = 1

    func unread(at date: Date) -> [AdviceDelivery] {
        items.filter { $0.readAt == nil && $0.isDue(at: date) }
    }
    func latestDelivered(at date: Date) -> AdviceDelivery? {
        items.filter { $0.isDue(at: date) }.max { $0.number < $1.number }
    }
    private mutating func activate(at date: Date) {
        for index in items.indices where items[index].activatedAt == nil && items[index].dueAt <= date {
            items[index].activatedAt = items[index].dueAt
        }
        if unread(at: date).count >= 3 { pausedUntilRead = true }
    }
    mutating func markRead(id: String, at date: Date, preferences: AdvicePreferences, calendar: Calendar = .current) {
        guard let index = items.firstIndex(where: { $0.id == id && $0.readAt == nil && $0.isDue(at: date) }) else { return }
        activate(at: date)
        items[index].readAt = date
        if pausedUntilRead && unread(at: date).isEmpty {
            pausedUntilRead = false
            nextDueAt = preferences.nextAllowed(onOrAfter: date.addingTimeInterval(preferences.interval), calendar: calendar)
        }
    }
    mutating func reconfigure(at date: Date, old: AdvicePreferences, new: AdvicePreferences, calendar: Calendar = .current) {
        activate(at: date)
        guard old.hours != new.hours || old.startMinute != new.startMinute || old.endMinute != new.endMinute ||
                old.order != new.order || old.selectedBooks != new.selectedBooks else { return }
        releaseFuture(at: date)
        nextDueAt = new.nextAllowed(onOrAfter: items.isEmpty ? date : date.addingTimeInterval(new.interval), calendar: calendar)
    }
    private mutating func releaseFuture(at date: Date) {
        let future = items.filter { $0.readAt == nil && !$0.isDue(at: date) }
        usedPassageIDs.subtract(future.map(\.advice.id))
        items.removeAll { $0.readAt == nil && !$0.isDue(at: date) }
        lastBookID = items.last?.advice.book.id
        nextNumber = (items.map(\.number).max() ?? 0) + 1
    }
    mutating func reconcile(at date: Date, preferences: AdvicePreferences, books: [AdviceBook],
                            corpora: [String: AdviceCorpus], calendar: Calendar = .current) {
        activate(at: date)
        if let zone = timeZoneID, zone != calendar.timeZone.identifier {
            releaseFuture(at: date)
            nextDueAt = preferences.nextAllowed(onOrAfter: date.addingTimeInterval(preferences.interval), calendar: calendar)
        }
        timeZoneID = calendar.timeZone.identifier
        guard !pausedUntilRead else { return }
        let selected = books.filter { preferences.selectedBooks.contains($0.id) && corpora[$0.id] != nil }
        guard !selected.isEmpty else { return }
        while items.filter({ $0.readAt == nil }).count < 3 {
            func remaining(_ book: AdviceBook) -> [AdvicePassage] {
                (corpora[book.id]?.passages ?? []).filter { !usedPassageIDs.contains("\(book.id)/\($0.id)") }
            }
            if selected.allSatisfy({ remaining($0).isEmpty }) {
                // Never start another cycle while a previous delivery remains unread/future.
                guard !items.contains(where: { $0.readAt == nil }) else { break }
                nextDueAt = max(nextDueAt ?? date, date.addingTimeInterval(preferences.interval))
                for book in selected {
                    for passage in corpora[book.id]?.passages ?? [] { usedPassageIDs.remove("\(book.id)/\(passage.id)") }
                }
            }
            let start = lastBookID.flatMap { last in selected.firstIndex { $0.id == last } }.map { ($0 + 1) % selected.count } ?? 0
            let rotated = Array(selected[start...]) + Array(selected[..<start])
            guard let book = rotated.first(where: { !remaining($0).isEmpty }) else { break }
            let candidates = remaining(book)
            guard let passage = preferences.order == .sequential ? candidates.first : candidates.randomElement() else { break }
            let due = preferences.nextAllowed(onOrAfter: nextDueAt ?? date, calendar: calendar)
            let advice = SavedAdvice(book: book, passage: passage)
            items.append(AdviceDelivery(advice: advice, dueAt: due, number: nextNumber))
            nextNumber += 1
            usedPassageIDs.insert(advice.id)
            lastBookID = book.id
            nextDueAt = preferences.nextAllowed(onOrAfter: due.addingTimeInterval(preferences.interval), calendar: calendar)
        }
        activate(at: date)
    }
}

struct AdviceState: Codable {
    var preferences = AdvicePreferences()
    var saved: [SavedAdvice] = []
    var queue = AdviceQueue()
    // Decoded only to migrate pre-queue installations without losing their current excerpt.
    var current: SavedAdvice?
    var shownAt: Date?
    init() {}
    enum CodingKeys: String, CodingKey { case preferences, saved, queue, current, shownAt }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        preferences = try c.decodeIfPresent(AdvicePreferences.self, forKey: .preferences) ?? AdvicePreferences()
        saved = try c.decodeIfPresent([SavedAdvice].self, forKey: .saved) ?? []
        queue = try c.decodeIfPresent(AdviceQueue.self, forKey: .queue) ?? AdviceQueue()
        current = try c.decodeIfPresent(SavedAdvice.self, forKey: .current)
        shownAt = try c.decodeIfPresent(Date.self, forKey: .shownAt)
    }
}
