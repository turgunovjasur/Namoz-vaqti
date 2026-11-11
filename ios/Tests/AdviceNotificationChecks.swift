import Foundation
import UserNotifications

@main struct NotificationChecks {
    static func main() throws {
        let now = Date()
        let book = AdviceBook(id: "b", title: "Kitob nomi", author: "Muallif", translator: "", description: "", pdf: "b.pdf", corpus: "b.json")
        let advice = SavedAdvice(book: book, passage: AdvicePassage(id: "p", text: String(repeating: "Asl matn. ", count: 80), pageStart: 1, pageEnd: 1, reference: "1"))
        var state = AdviceState()
        state.queue.items = [
            AdviceDelivery(advice: advice, dueAt: now.addingTimeInterval(-100), number: 1),
            AdviceDelivery(advice: advice, dueAt: now.addingTimeInterval(100), number: 2),
            AdviceDelivery(advice: advice, dueAt: now.addingTimeInterval(200), number: 3)
        ]
        let plan = AdviceNotifications.requests(for: state, at: now)
        precondition(plan.count == 2)
        let target = state.queue.items[1]
        precondition(plan[0].identifier == "nasihat.\(target.id)")
        precondition(plan[0].content.title == book.title)
        precondition(plan[0].content.body.hasPrefix("Asl matn."))
        precondition(plan[0].content.body.count <= 221 && plan[0].content.body.hasSuffix("…"))
        precondition(plan[0].content.userInfo["adviceDeliveryID"] as? String == target.id)
        precondition(plan[0].content.sound != nil)
        precondition(abs((plan[0].trigger as! UNCalendarNotificationTrigger).nextTriggerDate()!.timeIntervalSince(target.dueAt)) < 1)
        state.preferences.soundEnabled = false
        precondition(AdviceNotifications.requests(for: state, at: now).allSatisfy { $0.content.sound == nil })
        state.preferences.notificationsEnabled = false
        precondition(AdviceNotifications.requests(for: state, at: now).isEmpty)
        state.preferences.notificationsEnabled = true
        state.queue.pausedUntilRead = true
        precondition(AdviceNotifications.requests(for: state, at: now).isEmpty)
        print("PASS: notification source/preview, future-only, exact delivery route, sound, opt-out, pause")
    }
}
