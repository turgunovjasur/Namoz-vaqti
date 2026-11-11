import Foundation

@main struct QueueChecks {
    static func main() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        func date(_ day: Int, _ hour: Int, _ minute: Int = 0) -> Date {
            calendar.date(from: DateComponents(year: 2026, month: 11, day: day, hour: hour, minute: minute))!
        }
        let book = AdviceBook(id: "book", title: "Manba", author: "Muallif", translator: "", description: "", pdf: "book.pdf", corpus: "book.json")
        let other = AdviceBook(id: "other", title: "Boshqa", author: "Muallif", translator: "", description: "", pdf: "other.pdf", corpus: "other.json")
        func corpus(_ count: Int) -> AdviceCorpus {
            AdviceCorpus(title: "Manba", author: "Muallif", translator: "", passages: (1...count).map {
                AdvicePassage(id: "p\($0)", text: "Asl to‘liq nasihat \($0)", pageStart: 1, pageEnd: 1, reference: "\($0)")
            })
        }
        let sources = ["book": corpus(7), "other": corpus(3)]
        var prefs = AdvicePreferences()
        prefs.selectedBooks = [book.id]
        precondition(prefs.order == .sequential)
        var q = AdviceQueue()
        func reconcile(_ queue: inout AdviceQueue, _ time: Date, _ settings: AdvicePreferences? = nil) {
            queue.reconcile(at: time, preferences: settings ?? prefs, books: [book, other], corpora: sources, calendar: calendar)
        }
        reconcile(&q, date(11, 8))
        precondition(q.items.map(\.advice.passage.id) == ["p1", "p2", "p3"])
        precondition(q.items.map(\.dueAt) == [date(11, 8), date(11, 12), date(11, 16)])
        precondition(q.unread(at: date(11, 8)).count == 1)
        reconcile(&q, date(13, 18))
        precondition(q.unread(at: date(13, 18)).count == 3 && q.pausedUntilRead)
        let IDs = q.items.map(\.id)
        q.markRead(id: IDs[1], at: date(13, 18), preferences: prefs, calendar: calendar)
        reconcile(&q, date(13, 19))
        precondition(q.items.count == 3 && q.pausedUntilRead)
        q = try JSONDecoder().decode(AdviceQueue.self, from: JSONEncoder().encode(q))
        q.markRead(id: IDs[0], at: date(13, 19), preferences: prefs, calendar: calendar)
        reconcile(&q, date(13, 19))
        precondition(q.items.count == 3 && q.pausedUntilRead)
        q.markRead(id: IDs[2], at: date(13, 19), preferences: prefs, calendar: calendar)
        reconcile(&q, date(13, 19))
        precondition(!q.pausedUntilRead && q.unread(at: date(13, 19)).isEmpty)
        let future = q.items.filter { $0.readAt == nil }
        precondition(future.first?.dueAt == date(14, 8))
        precondition(future.map(\.advice.passage.id) == ["p4", "p5", "p6"])
        let snapshot = q
        q.markRead(id: IDs[2], at: date(14, 10), preferences: prefs, calendar: calendar)
        precondition(q == snapshot, "Repeated read must not change timer")
        q.markRead(id: future[0].id, at: date(13, 20), preferences: prefs, calendar: calendar)
        precondition(q == snapshot, "Future advice cannot be marked read")

        var randomPrefs = prefs; randomPrefs.order = .random
        var random = AdviceQueue()
        var read: [String] = []
        var now = date(11, 8)
        while read.count < 7 {
            reconcile(&random, now, randomPrefs)
            for item in random.unread(at: now) {
                read.append(item.advice.passage.id)
                random.markRead(id: item.id, at: now, preferences: randomPrefs, calendar: calendar)
            }
            now = now.addingTimeInterval(4 * 3600)
        }
        precondition(Set(read).count == 7 && read.count == 7, "Random must exhaust pool before repeating")

        var changed = AdviceQueue()
        reconcile(&changed, date(11, 8))
        let first = changed.items[0]
        var selectedOther = prefs; selectedOther.selectedBooks = ["other"]
        changed.reconfigure(at: date(11, 9), old: prefs, new: selectedOther, calendar: calendar)
        reconcile(&changed, date(11, 9), selectedOther)
        precondition(changed.items[0] == first, "Source change must keep due unread item")
        precondition(changed.items.filter { $0.dueAt > date(11, 9) }.allSatisfy { $0.advice.book.id == "other" })
        var disabled = prefs; disabled.notificationsEnabled = false
        var quiet = AdviceQueue(); reconcile(&quiet, date(11, 8), disabled)
        reconcile(&quiet, date(13, 18), disabled)
        precondition(quiet.unread(at: date(13, 18)).count == 3 && quiet.pausedUntilRead)

        var night = prefs; night.startMinute = 22*60; night.endMinute = 6*60
        precondition(night.nextAllowed(onOrAfter: date(11, 12), calendar: calendar) == date(11, 22))
        precondition(night.nextAllowed(onOrAfter: date(12, 5), calendar: calendar) == date(12, 5))
        precondition(night.nextAllowed(onOrAfter: date(12, 6), calendar: calendar) == date(12, 22))
        night.startMinute = 0; night.endMinute = 0
        precondition(night.nextAllowed(onOrAfter: date(12, 6), calendar: calendar) == date(12, 6))
        var two = prefs; two.selectedBooks = ["book", "other"]
        var interleaved = AdviceQueue(); reconcile(&interleaved, date(11, 8), two)
        precondition(interleaved.items.map(\.advice.book.id) == ["book", "other", "book"])
        let oldJSON = Data(#"{"hours":6,"startMinute":480,"endMinute":1200,"selectedBooks":["book"]}"#.utf8)
        let old = try JSONDecoder().decode(AdvicePreferences.self, from: oldJSON)
        precondition(old.hours == 6 && old.order == .sequential && old.selectedBooks == ["book"])
        var short = AdviceQueue()
        short.reconcile(at: date(11, 8), preferences: prefs, books: [book], corpora: ["book": corpus(1)], calendar: calendar)
        short.markRead(id: short.items[0].id, at: date(13, 8), preferences: prefs, calendar: calendar)
        short.reconcile(at: date(13, 8), preferences: prefs, books: [book], corpora: ["book": corpus(1)], calendar: calendar)
        precondition(short.unread(at: date(13, 8)).isEmpty, "An exhausted book must not replay missed intervals")
        precondition(short.items.last?.dueAt == date(13, 12))
        var newYork = Calendar(identifier: .gregorian)
        newYork.timeZone = TimeZone(identifier: "America/New_York")!
        var dst = prefs; dst.startMinute = 150; dst.endMinute = 180
        let spring = newYork.date(from: DateComponents(year: 2027, month: 3, day: 14, hour: 1, minute: 59))!
        let allowed = dst.nextAllowed(onOrAfter: spring, calendar: newYork)
        precondition(dst.allowsRefresh(at: allowed, calendar: newYork), "DST must not escape the allowed window")
        precondition(newYork.component(.day, from: allowed) == 15)
        var travel = AdviceQueue(); reconcile(&travel, date(11, 8))
        let shownID = travel.unread(at: date(11, 8))[0].id
        reconcile(&travel, date(11, 7))
        precondition(travel.unread(at: date(11, 7)).first?.id == shownID, "Clock rollback must retain an already due excerpt")
        travel.reconcile(at: date(11, 9), preferences: prefs, books: [book], corpora: sources, calendar: newYork)
        precondition(travel.unread(at: date(11, 9)).first?.id == shownID)
        precondition(travel.items.filter { !$0.isDue(at: date(11, 9)) }.allSatisfy { prefs.allowsRefresh(at: $0.dueAt, calendar: newYork) })
        var home = AdviceQueue()
        let start = date(11, 8)
        let homeAdvice = SavedAdvice(book: book, passage: sources[book.id]!.passages[0])
        let oldDelivery = AdviceDelivery(advice: homeAdvice, dueAt: start, number: 1)
        var latestDelivery = AdviceDelivery(advice: homeAdvice, dueAt: start.addingTimeInterval(10), number: 2)
        latestDelivery.readAt = start.addingTimeInterval(20)
        home.items = [oldDelivery, latestDelivery, AdviceDelivery(advice: homeAdvice, dueAt: start.addingTimeInterval(100), number: 3)]
        precondition(home.latestDelivered(at: start.addingTimeInterval(30))?.id == latestDelivery.id,
                     "Home must retain latest read advice while older advice is unread, excluding future reservations")
        precondition(home.latestDelivered(at: start.addingTimeInterval(-1)) == nil)
        print("PASS: queue rules and latest due advice remains visible after acknowledgement")
    }
}
