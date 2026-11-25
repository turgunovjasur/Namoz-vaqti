import XCTest
import CoreImage

final class HisobUITests: XCTestCase {
    func testCategorySelectionAfterTypingAmount() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let tab = app.tabBars.buttons["Hisob"]
        if tab.exists { tab.tap() }
        app.buttons["hisob.add"].tap()
        let keyboard = app.keyboards.firstMatch
        XCTAssertTrue(keyboard.waitForExistence(timeout: 5))
        app.typeText("45000")
        let closeKeyboard = app.buttons["hisob.dismissKeyboard"]
        XCTAssertTrue(closeKeyboard.waitForExistence(timeout: 3))
        closeKeyboard.tap()
        XCTAssertTrue(keyboard.waitForNonExistence(timeout: 3))
        app.textFields["hisob.amount"].tap()
        XCTAssertTrue(keyboard.keys["1"].waitForExistence(timeout: 3))
        let picker = app.buttons["hisob.categoryPicker"]
        picker.tap()
        let loan = app.buttons["Qarz"].firstMatch
        XCTAssertTrue(loan.waitForExistence(timeout: 5))
        XCTAssertTrue(keyboard.waitForNonExistence(timeout: 3))
        XCTAssertTrue(loan.isHittable)
        loan.tap()
        XCTAssertTrue(picker.waitForExistence(timeout: 5))
        XCTAssertTrue(picker.label.contains("Qarz"))
        XCTAssertEqual(app.textFields["hisob.amount"].value as? String, "45 000")
        app.buttons["Bekor qilish"].tap()
    }

    func testBalanceAndCategoryKeyboards() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Hisob"].tap()
        app.buttons["Hisob sozlamalari"].tap()
        let keyboard = app.keyboards.firstMatch
        XCTAssertFalse(keyboard.exists)
        let opening = app.textFields["hisob.opening"]
        opening.tap()
        XCTAssertTrue(keyboard.keys["1"].waitForExistence(timeout: 5))
        app.buttons["hisob.settings.dismissKeyboard"].tap()
        XCTAssertTrue(keyboard.waitForNonExistence(timeout: 3))
        opening.tap()
        app.buttons["Kategoriya qo‘shish"].tap()
        let field = app.textFields["Kategoriya nomi"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        app.typeText("Sinov\n")
        XCTAssertTrue(keyboard.waitForNonExistence(timeout: 3))
        XCTAssertEqual(field.value as? String, "Sinov")
        app.buttons["Yopish"].firstMatch.tap()
        XCTAssertTrue(opening.waitForExistence(timeout: 5))
        XCTAssertFalse(keyboard.exists)
    }

    func testEntrySwitchesKeyboardAndClosesCalendarOnDaySelection() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Hisob"].tap()
        app.buttons["hisob.add"].tap()
        let keyboard = app.keyboards.firstMatch
        let amount = app.textFields["hisob.amount"]
        amount.tap()
        XCTAssertTrue(keyboard.keys["1"].waitForExistence(timeout: 5))
        amount.typeText("45000")
        let note = app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "Izoh")).firstMatch
        // The padding above the text is also part of the note row's tap target.
        note.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0))
            .withOffset(CGVector(dx: 0, dy: -5)).tap()
        XCTAssertTrue(keyboard.keys.matching(NSPredicate(format: "label IN %@", ["a", "A"])).firstMatch.waitForExistence(timeout: 3))
        app.typeText("Test")
        XCTAssertEqual(note.value as? String, "Test")
        XCTAssertEqual(amount.value as? String, "45 000")
        let date = app.buttons["Sana"]
        let originalDate = date.value as? String
        date.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 3))
        let nextMonth = app.buttons["DatePicker.NextMonth"]
        let days = app.collectionViews.buttons
        let selected = days.matching(NSPredicate(format: "selected == true")).firstMatch
        XCTAssertTrue(selected.waitForExistence(timeout: 3))
        selected.tap()
        XCTAssertTrue(nextMonth.waitForNonExistence(timeout: 3))
        XCTAssertEqual(date.value as? String, originalDate)
        date.tap()
        nextMonth.tap()
        let monthAndYear = app.buttons["DatePicker.Show"].value as? String
        let twelfth = days.matching(NSPredicate(format: "label CONTAINS %@", ", 12-")).firstMatch
        XCTAssertTrue(twelfth.waitForExistence(timeout: 3))
        twelfth.tap()
        XCTAssertTrue(nextMonth.waitForNonExistence(timeout: 3))
        XCTAssertEqual(date.value as? String, monthAndYear.map { "12 " + $0 })
        XCTAssertEqual(note.value as? String, "Test")
        app.buttons["Bekor qilish"].tap()
    }

    func testHistorySearchOpensAndRestoresList() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let tab = app.tabBars.buttons["Hisob"]
        if tab.exists { tab.tap() }
        app.buttons["Yozuvlar tarixi"].tap()
        let count = app.staticTexts.matching(NSPredicate(format: "label ENDSWITH %@", "ta yozuv · so‘m")).firstMatch
        let originalCount = count.label
        let field = app.textFields["hisob.searchField"]
        XCTAssertFalse(field.exists)
        capture(app, "Yozuvlar-tarixi")
        app.buttons["hisob.search"].tap()
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        let query = UUID().uuidString
        field.typeText(query + "\n")
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 3))
        XCTAssertEqual(field.value as? String, query)
        XCTAssertTrue(app.staticTexts["Yozuv topilmadi"].exists)
        XCTAssertEqual(count.label, "0 ta yozuv · so‘m")
        capture(app, "Yozuvlar-qidiruvi")
        app.buttons["Bekor qilish"].tap()
        XCTAssertFalse(field.exists)
        XCTAssertTrue(app.buttons["hisob.search"].exists)
        XCTAssertEqual(count.label, originalCount)
    }

    func testBookDetailsPreserveSearchWithoutKeyboard() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Nasihat"].tap()
        app.buttons["Manbalarni tanlash"].tap()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        search.typeText("Riyozus")
        let result = app.buttons["Riyozus solihiyn, kitob haqida"]
        result.tap()
        XCTAssertTrue(app.navigationBars["Kitob haqida"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 3))
        app.buttons["Yopish"].tap()
        XCTAssertTrue(result.waitForExistence(timeout: 5))
        XCTAssertEqual(search.value as? String, "Riyozus")
        XCTAssertFalse(app.keyboards.firstMatch.exists)
    }

    func testOpenLoanBalancesAndRepayment() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["-previewOpenLoans"]
        app.launch()
        XCTAssertFalse(app.buttons["hisob.openLoans"].exists)
        app.buttons["Yozuvlar tarixi"].tap()
        capture(app, "00-Yozuvlar-tarixi")
        app.buttons["hisob.openLoans"].tap()
        let ali = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Ali")).firstMatch
        XCTAssertTrue(ali.waitForExistence(timeout: 5))
        XCTAssertTrue(ali.label.contains("150 000 so‘m"))
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Muddati o‘tgan")).firstMatch.exists)
        let workshop = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Ustaxona uchun qarz")).firstMatch
        let dilnoza = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Dilnoza")).firstMatch
        XCTAssertLessThan(ali.frame.minY, workshop.frame.minY)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Bugun")).firstMatch.exists)
        XCTAssertEqual(app.staticTexts["hisob.total.expense"].label, "225 000 so‘m")
        capture(app, "01-Ochiq-qarzlar")
        app.buttons["hisob.search"].tap()
        app.textFields["hisob.searchField"].typeText("Ali")
        XCTAssertTrue(ali.exists)
        XCTAssertFalse(workshop.exists)
        XCTAssertEqual(app.staticTexts["hisob.total.expense"].label, "150 000 so‘m")
        app.buttons["Bekor qilish"].tap()
        app.buttons["hisob.month"].tap()
        let today = Calendar.current.component(.day, from: Date())
        app.buttons["hisob.calendar.day.\(today)"].tap()
        app.buttons["Tayyor"].tap()
        XCTAssertTrue(dilnoza.exists)
        XCTAssertFalse(ali.exists)
        app.buttons["hisob.month"].tap()
        app.buttons["Barcha davrlar"].tap()
        XCTAssertTrue(ali.exists)
        let receivable = app.buttons["hisob.kind.expense"]
        receivable.tap()
        XCTAssertFalse(ali.exists)
        XCTAssertTrue(dilnoza.exists)
        receivable.tap()
        ali.tap()
        XCTAssertTrue(app.buttons["hisob.repay"].waitForExistence(timeout: 5))
        capture(app, "02-Qarz-tafsiloti")
        app.buttons["hisob.repay"].tap()
        XCTAssertTrue(app.textFields["hisob.amount"].waitForExistence(timeout: 5))
        app.typeText("50000")
        XCTAssertEqual(app.descendants(matching: .any)["hisob.repaymentPreview"].firstMatch.label, "Qoladi: 100 000 so‘m")
        capture(app, "03-Qaytim")
        app.buttons["hisob.save"].tap()
        app.buttons["Yopish"].tap()
        XCTAssertTrue(ali.label.contains("100 000 so‘m"))

        for row in [ali, workshop, dilnoza] {
            row.tap()
            app.buttons["hisob.repay"].tap()
            app.buttons["hisob.fullRepayment"].tap()
            app.buttons["hisob.save"].tap()
            XCTAssertFalse(app.buttons["hisob.repay"].exists)
            app.buttons["Yopish"].tap()
            XCTAssertTrue(row.waitForNonExistence(timeout: 3))
        }
        XCTAssertTrue(app.staticTexts["Ochiq qarz yo‘q"].waitForExistence(timeout: 5))
        app.navigationBars["Ochiq qarzlar"].buttons.firstMatch.tap()
        XCTAssertTrue(app.navigationBars["Yozuvlar tarixi"].exists)
        app.buttons["hisob.openLoans"].tap()
        XCTAssertTrue(app.staticTexts["Ochiq qarz yo‘q"].waitForExistence(timeout: 5))
    }

    func testOpenLoansWithLargeText() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["-previewOpenLoans", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        let history = app.buttons["Yozuvlar tarixi"]
        for _ in 0..<6 where !history.isHittable { app.swipeUp() }
        history.tap()
        let open = app.buttons["hisob.openLoans"]
        for _ in 0..<6 where !open.isHittable { app.swipeUp() }
        open.tap()
        let first = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Ali")).firstMatch
        XCTAssertTrue(first.waitForExistence(timeout: 5))
        for _ in 0..<6 where !first.isHittable { app.swipeUp() }
        XCTAssertTrue(first.isHittable)
        capture(app, "04-Katta-matn")
        first.tap()
        XCTAssertTrue(app.buttons["hisob.repay"].isHittable)
    }

    func testLoanRepaymentFromHistory() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Hisob"].tap()
        let add = app.buttons["hisob.add"]
        let save = app.buttons["hisob.save"]
        let amount = app.textFields["hisob.amount"]
        let balance = app.staticTexts["hisob.balance"]
        XCTAssertTrue(balance.waitForExistence(timeout: 5))
        if balance.label == "0 so‘m" {
            add.tap()
            app.buttons["Kirim"].tap()
            amount.tap()
            amount.typeText("1000000")
            save.tap()
        }
        let startingBalance = balance.label
        app.buttons["Yozuvlar tarixi"].tap()
        let expectedIncome = app.staticTexts["hisob.total.income"].label
        let expectedExpense = app.staticTexts["hisob.total.expense"].label
        app.navigationBars.buttons.element(boundBy: 0).tap()
        add.tap()
        amount.tap()
        amount.typeText("200000")
        app.buttons["hisob.categoryPicker"].tap()
        app.buttons["Qarz"].firstMatch.tap()
        let note = app.textFields["Izoh"].exists ? app.textFields["Izoh"] : app.textViews["Izoh"]
        note.tap()
        let name = "Ali"
        note.typeText(name)
        app.buttons["hisob.dismissKeyboard"].tap()
        XCTAssertFalse(app.keyboards.firstMatch.exists)
        capture(app, "Qarz-berish")
        save.tap()
        let permission = XCUIApplication(bundleIdentifier: "com.apple.springboard").alerts.firstMatch
        if permission.waitForExistence(timeout: 3) {
            let allow = permission.buttons["Allow"]
            if allow.exists { allow.tap() }
        }
        app.buttons["Yozuvlar tarixi"].tap()
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", name)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        app.buttons["Oldingi oy"].tap()
        app.buttons["hisob.openLoans"].tap()
        app.buttons.matching(NSPredicate(format: "label CONTAINS %@", name)).firstMatch.tap()
        let repayReady = NSPredicate(format: "hittable == true")
        expectation(for: repayReady, evaluatedWith: app.buttons["hisob.repay"])
        waitForExpectations(timeout: 5)
        capture(app, "Ochiq-qarz-tafsiloti")
        app.buttons["hisob.repay"].tap()
        amount.tap()
        amount.typeText("50000")
        XCTAssertEqual(app.descendants(matching: .any)["hisob.repaymentPreview"].firstMatch.label, "Qoladi: 150 000 so‘m")
        app.buttons["hisob.dismissKeyboard"].tap()
        capture(app, "Qaytim-kiritish")
        save.tap()
        XCTAssertTrue(app.buttons["hisob.repay"].waitForExistence(timeout: 5))
        app.buttons["Yopish"].tap()
        app.navigationBars["Ochiq qarzlar"].buttons.element(boundBy: 0).tap()
        app.buttons["Keyingi oy"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND label CONTAINS %@", name, "Ochiq")).firstMatch.exists)
        XCTAssertEqual(app.staticTexts["hisob.total.income"].label, expectedIncome)
        XCTAssertEqual(app.staticTexts["hisob.total.expense"].label, expectedExpense)
        capture(app, "Qarz-ochiq")
        row.tap()
        app.buttons["hisob.repay"].tap()
        app.buttons["hisob.fullRepayment"].tap()
        XCTAssertEqual(app.descendants(matching: .any)["hisob.repaymentPreview"].firstMatch.label, "Saqlanganda qarz yopiladi.")
        save.tap()
        XCTAssertTrue(app.buttons["Yopish"].waitForExistence(timeout: 5))
        app.buttons["Yopish"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND label CONTAINS %@", name, "Yopilgan")).firstMatch.exists)
        capture(app, "Qarz-yopilgan")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertEqual(balance.label, startingBalance)

        add.tap()
        app.buttons["Kirim"].tap()
        amount.tap()
        amount.typeText("100000")
        app.buttons["hisob.categoryPicker"].tap()
        app.buttons["Qarz"].firstMatch.tap()
        note.tap()
        note.typeText("Vali")
        save.tap()
        app.buttons["Yozuvlar tarixi"].tap()
        app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND label CONTAINS %@", "Vali", "Ochiq")).firstMatch.tap()
        app.buttons["hisob.repay"].tap()
        XCTAssertEqual(app.descendants(matching: .any)["hisob.repaymentDirection"].firstMatch.label, "Chiqim · Qarz qaytimi")
        amount.tap()
        amount.typeText("100000")
        save.tap()
        app.buttons["Yopish"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND label CONTAINS %@", "Vali", "Yopilgan")).firstMatch.exists)
        XCTAssertEqual(app.staticTexts["hisob.total.income"].label, expectedIncome)
        XCTAssertEqual(app.staticTexts["hisob.total.expense"].label, expectedExpense)
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertEqual(balance.label, startingBalance)
    }

    func testEntryFormsFocusFirstInputWhenOpened() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let keyboard = app.keyboards.firstMatch
        func captureKeyboard(_ name: String) {
            XCTAssertTrue(keyboard.keys.firstMatch.waitForExistence(timeout: 5))
            let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        app.tabBars.buttons["Hisob"].tap()
        app.buttons["hisob.add"].tap()
        XCTAssertTrue(keyboard.waitForExistence(timeout: 5))
        let ledgerSave = app.navigationBars.buttons["hisob.save"]
        XCTAssertTrue(ledgerSave.exists)
        XCTAssertFalse(ledgerSave.isEnabled)
        captureKeyboard("Yangi-yozuv-klaviatura")
        app.typeText("0")
        XCTAssertFalse(ledgerSave.isEnabled)
        app.typeText(XCUIKeyboardKey.delete.rawValue + "45000")
        XCTAssertTrue(ledgerSave.isEnabled)
        XCTAssertEqual(app.textFields["hisob.amount"].value as? String, "45 000")
        app.buttons["Bekor qilish"].tap()
        app.buttons["Hisob sozlamalari"].tap()
        app.buttons["Kategoriya qo‘shish"].tap()
        XCTAssertTrue(keyboard.waitForExistence(timeout: 5))
        app.typeText("Kitob")
        XCTAssertEqual(app.textFields["Kategoriya nomi"].value as? String, "Kitob")
        app.navigationBars["Yangi kategoriya"].buttons["Yopish"].tap()
        app.buttons["Yopish"].tap()
        app.tabBars.buttons["Eslatmalar"].tap()
        app.buttons["reminders.add"].tap()
        XCTAssertTrue(keyboard.waitForExistence(timeout: 5))
        let reminderSave = app.navigationBars.buttons["reminders.save"]
        XCTAssertFalse(reminderSave.isEnabled)
        XCTAssertEqual(app.navigationBars.buttons["reminders.editor.close"].label, "Bekor qilish")
        captureKeyboard("Yangi-eslatma-klaviatura")
        app.typeText("Kitob")
        XCTAssertTrue(reminderSave.isEnabled)
        XCTAssertEqual(app.textFields["reminders.title"].value as? String, "Kitob")
        app.buttons["reminders.editor.close"].tap()
    }

    func testAllTimeBalanceBreakdown() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Hisob"].tap()
        let balance = app.staticTexts["hisob.balance"]
        let expected = balance.label
        app.buttons["Oldingi oy"].tap()
        XCTAssertEqual(balance.label, expected)
        app.buttons["Umumiy qoldiq qanday hisoblanadi?"].tap()
        XCTAssertTrue(app.navigationBars["Umumiy qoldiq"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Barcha oylar bo‘yicha"].exists)
        for label in ["Boshlang‘ich qoldiq", "Jami kirim", "Jami chiqim"] {
            XCTAssertTrue(app.staticTexts[label].exists)
        }
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label == %@", expected)).firstMatch.exists)
        capture(app, "Hisob-Umumiy-qoldiq")
        app.buttons["Tayyor"].tap()
        XCTAssertEqual(balance.label, expected)
    }

    func testPeriodFilterAndIndependentHistoryKinds() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Hisob"].tap()
        let period = app.buttons["hisob.month"]
        let currentMonth = period.label
        app.buttons["Oldingi oy"].tap()
        let previousMonth = period.label
        XCTAssertNotEqual(previousMonth, currentMonth)
        app.buttons["Yozuvlar tarixi"].tap()
        XCTAssertTrue(app.navigationBars["Yozuvlar tarixi"].waitForExistence(timeout: 5))
        let singleSelector = NSPredicate { _, _ in app.buttons.matching(identifier: "hisob.month").count == 1 }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: singleSelector, object: app)], timeout: 5), .completed)
        XCTAssertEqual(period.label, previousMonth)
        let income = app.buttons["hisob.kind.income"]
        let expense = app.buttons["hisob.kind.expense"]
        XCTAssertTrue(income.isSelected && expense.isSelected)
        income.tap()
        XCTAssertEqual(income.value as? String, "O‘chiq")
        XCTAssertEqual(expense.value as? String, "Yoqilgan")
        capture(app, "Hisob-Kirim-Chiqim")
        XCTAssertFalse(app.staticTexts["hisob.total.income"].exists)
        XCTAssertTrue(app.staticTexts["hisob.total.expense"].exists)
        income.tap()
        expense.tap()
        XCTAssertTrue(app.staticTexts["hisob.total.income"].exists)
        XCTAssertFalse(app.staticTexts["hisob.total.expense"].exists)
        period.tap()
        XCTAssertTrue(app.buttons["Sana"].isSelected)
        let year = app.buttons["hisob.calendar.year"]
        let yearLabel = year.label
        year.tap()
        app.buttons["Tayyor"].tap()
        XCTAssertEqual(period.label, yearLabel)
        period.tap()
        let month = app.buttons["hisob.calendar.month"]
        let originalMonth = month.label
        app.buttons["hisob.calendar.year.previous"].tap()
        app.buttons["hisob.calendar.year.next"].tap()
        XCTAssertEqual(year.label, yearLabel)
        app.buttons["hisob.calendar.month.next"].tap()
        XCTAssertNotEqual(month.label, originalMonth)
        app.buttons["hisob.calendar.month.previous"].tap()
        XCTAssertEqual(month.label, originalMonth)
        let day = app.buttons["hisob.calendar.day.17"]
        XCTAssertLessThan(year.frame.midY, month.frame.midY)
        XCTAssertLessThan(month.frame.midY, day.frame.midY)
        XCTAssertGreaterThanOrEqual(day.frame.width, 44)
        XCTAssertGreaterThanOrEqual(day.frame.height, 44)
        day.tap()
        app.buttons["Tayyor"].tap()
        XCTAssertTrue(period.label.hasPrefix("17 " + originalMonth.lowercased()))
        period.tap()
        month.tap()
        app.buttons["Tayyor"].tap()
        XCTAssertEqual(period.label, originalMonth + " " + yearLabel)
        period.tap()
        app.buttons["Oraliq"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["hisob.range.start"].firstMatch.exists)
        XCTAssertTrue(app.descendants(matching: .any)["hisob.range.end"].firstMatch.exists)
        app.buttons["Tayyor"].tap()
        XCTAssertFalse(app.buttons["Oldingi oy"].exists)
        XCTAssertTrue(period.label.contains("–"))
        period.tap()
        let clear = app.buttons["Tozalash"]
        if !clear.isHittable { app.swipeUp() }
        clear.tap()
        XCTAssertEqual(period.label, currentMonth)
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertEqual(period.label, currentMonth)
        period.tap()
        XCTAssertTrue(app.buttons["Tozalash"].isHittable)
        capture(app, "Hisob-Sana")
    }

    func testCreateEditUndoHistoryAndReport() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let hisob = app.tabBars.buttons["Hisob"]
        XCTAssertTrue(hisob.waitForExistence(timeout: 15))
        hisob.tap()
        app.buttons["Hisob sozlamalari"].tap()
        XCTAssertFalse(app.segmentedControls["hisob.defaultUnit"].exists)
        app.buttons["Yopish"].tap()
        let add = app.buttons["hisob.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 5))
        add.tap()
        let amount = app.textFields["hisob.amount"]
        XCTAssertTrue(amount.waitForExistence(timeout: 5))
        XCTAssertFalse(app.segmentedControls["hisob.unit"].exists)
        amount.tap(); amount.typeText("24000000")
        XCTAssertEqual(amount.value as? String, "24 000 000")
        amount.coordinate(withNormalizedOffset: CGVector(dx: 0.98, dy: 0.5)).tap()
        amount.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 30) + "45000")
        XCTAssertEqual(amount.value as? String, "45 000")
        let note = app.textFields["Izoh"].exists ? app.textFields["Izoh"] : app.textViews["Izoh"]
        note.tap(); note.typeText("Tushlik — UI sinov")
        XCTAssertFalse(app.buttons["Tayyor"].exists)
        capture(app, "Hisob-entry")
        if app.keyboards.firstMatch.exists { app.scrollViews["hisob.entryScroll"].swipeUp() }
        app.buttons["hisob.save"].tap()
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Tushlik — UI sinov")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        capture(app, "Hisob-main")
        row.tap()
        XCTAssertTrue(amount.waitForExistence(timeout: 5))
        amount.coordinate(withNormalizedOffset: CGVector(dx: 0.98, dy: 0.5)).tap()
        amount.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 20) + "50000")
        XCTAssertFalse(app.buttons["Tayyor"].exists)
        if app.keyboards.firstMatch.exists { app.scrollViews["hisob.entryScroll"].swipeUp() }
        app.buttons["hisob.save"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        XCTAssertTrue(row.label.contains("50 000"), "Edited amount must be visible in the journal")
        row.tap()
        app.buttons["Yozuvni o‘chirish"].tap()
        app.buttons["O‘chirish"].tap()
        let undo = app.buttons["Qaytarish"]
        XCTAssertTrue(undo.waitForExistence(timeout: 3)); undo.tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        app.buttons["Yozuvlar tarixi"].tap()
        XCTAssertTrue(app.navigationBars["Yozuvlar tarixi"].waitForExistence(timeout: 5))
        let search = app.textFields["hisob.searchField"]
        capture(app, "Hisob-history-before-search")
        XCTAssertFalse(search.exists)
        app.buttons["hisob.search"].tap()
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap(); search.typeText("UI sinov")
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        capture(app, "Hisob-history")
        app.buttons["Bekor qilish"].tap()
        app.navigationBars.buttons["BackButton"].tap()
        XCTAssertTrue(app.buttons["Oy hisoboti"].waitForExistence(timeout: 5))
        app.buttons["Oy hisoboti"].tap()
        XCTAssertTrue(app.navigationBars["Oy hisoboti"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Xarajatlar tarkibi"].exists)
        XCTAssertTrue(app.otherElements["hisob.expenseChart"].waitForExistence(timeout: 5))
        capture(app, "Hisob-report")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        row.tap()
        app.buttons["Yozuvni o‘chirish"].tap(); app.buttons["O‘chirish"].tap()
        app.buttons["Hisob sozlamalari"].tap()
        XCTAssertFalse(app.segmentedControls["hisob.defaultUnit"].exists)
        capture(app, "Hisob-unit-settings")
        app.buttons["Yopish"].tap()
        add.tap()
        XCTAssertFalse(app.segmentedControls["hisob.unit"].exists)
        amount.tap(); amount.typeText("25000")
        XCTAssertEqual(amount.value as? String, "25 000")
        note.tap(); note.typeText("Tushlik — UI birlik sinov")
        capture(app, "Hisob-number-entry")
        if app.keyboards.firstMatch.exists { app.scrollViews["hisob.entryScroll"].swipeUp() }
        app.buttons["hisob.save"].tap()
        let scaledRow = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Tushlik — UI birlik sinov")).firstMatch
        XCTAssertTrue(scaledRow.waitForExistence(timeout: 5))
        XCTAssertTrue(scaledRow.label.contains("25 000"))
        capture(app, "Hisob-number-main")
        // Bring the entire row above the bottom inset before reopening it.
        app.scrollViews.firstMatch.swipeUp()
        scaledRow.tap()
        XCTAssertTrue(amount.waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertFalse(app.segmentedControls["hisob.unit"].exists)
        XCTAssertEqual(amount.value as? String, "25 000")
        app.buttons["Yozuvni o‘chirish"].tap(); app.buttons["O‘chirish"].tap()
        app.buttons["Hisob sozlamalari"].tap()
        XCTAssertFalse(app.segmentedControls["hisob.defaultUnit"].exists)
        app.buttons["Yopish"].tap()
        let undoGone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["Qaytarish"])
        XCTAssertEqual(XCTWaiter.wait(for: [undoGone], timeout: 12), .completed)
        XCTAssertTrue(app.staticTexts["hisob.month.exact"].exists)
        add.tap()
        XCTAssertFalse(app.segmentedControls["hisob.unit"].exists)
        app.buttons["Bekor qilish"].tap()
        capture(app, "Hisob-summary-exact-final")
    }
    func testDefaultCategoryAndArchivePreserveHistory() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["Hisob"].waitForExistence(timeout: 15))
        app.tabBars.buttons["Hisob"].tap()
        let categoryName = "UI " + String(UUID().uuidString.prefix(8))
        let noteText = "Arxiv sinovi " + categoryName
        app.buttons["Hisob sozlamalari"].tap()
        app.buttons["Kategoriya qo‘shish"].tap()
        let name = app.textFields["Kategoriya nomi"]
        XCTAssertTrue(name.waitForExistence(timeout: 5))
        name.tap(); name.typeText(categoryName)
        app.buttons["Qo‘shish"].tap()
        let category = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@ AND label CONTAINS %@", "hisob.category.", categoryName)).firstMatch
        for _ in 0..<5 where !category.isHittable { app.swipeUp() }
        XCTAssertTrue(category.isHittable)
        category.tap(); app.buttons["Asosiy qilish"].tap()
        XCTAssertTrue(category.label.contains("Asosiy"))
        capture(app, "Hisob-default-category")
        app.buttons["Yopish"].tap()
        app.terminate(); app.launch()
        app.tabBars.buttons["Hisob"].tap()
        app.buttons["hisob.add"].tap()
        let picker = app.buttons["hisob.categoryPicker"]
        XCTAssertTrue(picker.waitForExistence(timeout: 5))
        XCTAssertTrue(picker.label.contains(categoryName), picker.debugDescription)
        let amount = app.textFields["hisob.amount"]
        amount.tap(); amount.typeText("12500")
        let note = app.textFields["Izoh"].exists ? app.textFields["Izoh"] : app.textViews["Izoh"]
        note.tap(); note.typeText(noteText)
        if app.keyboards.firstMatch.exists { app.scrollViews["hisob.entryScroll"].swipeUp() }
        app.buttons["hisob.save"].tap()
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", noteText)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        app.buttons["Hisob sozlamalari"].tap()
        for _ in 0..<5 where !category.isHittable { app.swipeUp() }
        category.tap(); app.buttons["O‘chirish"].tap()
        capture(app, "Hisob-archive-confirmation")
        app.buttons["O‘chirish"].tap()
        XCTAssertFalse(category.exists)
        app.buttons["Yopish"].tap()
        XCTAssertTrue(row.label.contains(categoryName) && row.label.contains("Arxivlangan"))
        capture(app, "Hisob-archived-history")
        row.tap()
        XCTAssertTrue(picker.label.contains(categoryName))
        app.buttons["hisob.save"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5), "Editing can retain archived category")
        app.buttons["hisob.add"].tap()
        XCTAssertTrue(picker.label.contains("Boshqa"), "Deleted default must fall back")
        picker.tap()
        XCTAssertFalse(app.buttons[categoryName + " · Arxivlangan"].exists, "Archive absent from new entry picker")
        app.buttons["Boshqa"].firstMatch.tap()
        app.buttons["Bekor qilish"].tap()
        row.tap(); app.buttons["Yozuvni o‘chirish"].tap(); app.buttons["O‘chirish"].tap()
        app.buttons["Hisob sozlamalari"].tap()
        let food = app.buttons["hisob.category.expense.food"]
        for _ in 0..<5 where !food.isHittable { app.swipeUp() }
        food.tap(); app.buttons["Asosiy qilish"].tap()
        app.buttons["Yopish"].tap()
    }

    func testDeletingSelectedCategoryInsideDraftUsesFallback() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["Hisob"].waitForExistence(timeout: 15))
        app.tabBars.buttons["Hisob"].tap()
        app.buttons["hisob.add"].tap()
        let initialSelection = app.buttons["hisob.categoryPicker"].label
        app.buttons["Kategoriya qo‘shish"].tap()
        let name = "Draft " + String(UUID().uuidString.prefix(8))
        let field = app.textFields["Kategoriya nomi"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap(); field.typeText(name)
        app.buttons["Qo‘shish"].tap()
        let picker = app.buttons["hisob.categoryPicker"]
        XCTAssertTrue(picker.label.contains(name))
        app.buttons["Kategoriya qo‘shish"].tap()
        let category = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@ AND label CONTAINS %@", "hisob.category.", name)).firstMatch
        for _ in 0..<6 where !category.isHittable { app.swipeUp() }
        category.tap(); app.buttons["O‘chirish"].tap(); app.buttons["O‘chirish"].tap()
        app.navigationBars["Yangi kategoriya"].buttons["Yopish"].tap()
        XCTAssertFalse(picker.label.contains(name), "Removed category cannot remain selected beneath a sheet")
        XCTAssertEqual(picker.label, initialSelection)
        app.buttons["Bekor qilish"].tap()
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}

final class MenuUITests: XCTestCase {
    func testRegionSearchIncludesDistrictsAndProvinceNames() {
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Namoz"].tap()
        app.buttons["namoz.region"].tap()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        search.typeText("chilonzor")
        XCTAssertTrue(app.buttons["Chilonzor"].waitForExistence(timeout: 3))
        search.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 9) + "Toshkent shahri")
        XCTAssertTrue(app.buttons["Bektemir"].waitForExistence(timeout: 3))
        search.typeText("\n")
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 3))
        XCTAssertEqual(search.value as? String, "Toshkent shahri")
        XCTAssertTrue(app.buttons["Bektemir"].isHittable)
    }

    func testCompactPrayerOptions() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Namoz"].tap()
        for name in ["Quyosh", "Peshin", "Asr", "Shom", "Xufton", "Bomdod"] {
            let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", name)).firstMatch
            XCTAssertTrue(row.waitForExistence(timeout: 8), name)
            row.tap()
            XCTAssertTrue(app.navigationBars[name + " sozlamalari"].waitForExistence(timeout: 5))
            XCTAssertTrue(app.staticTexts[name + " vaqti"].exists)
            let reminder = app.descendants(matching: .any)["prayer.reminder"].firstMatch
            let signal = app.descendants(matching: .any)["prayer.signal"].firstMatch
            XCTAssertTrue(reminder.isHittable && signal.isHittable)
            XCTAssertFalse(app.buttons["1 daqiqadan keyin signalni sinash"].exists)
            if name == "Bomdod" {
                capture(app, "Bomdod-sozlamalari")
                let time = app.staticTexts["prayer.adjustedTime"]
                let originalTime = time.label
                reminder.tap()
                for option in ["O‘chiq", "5 daqiqa oldin", "10 daqiqa oldin", "15 daqiqa oldin", "30 daqiqa oldin"] {
                    XCTAssertTrue(app.buttons[option].firstMatch.exists)
                }
                app.buttons["10 daqiqa oldin"].tap()
                let stepper = app.steppers.firstMatch
                let increment = stepper.buttons.element(boundBy: 1)
                (increment.isEnabled ? increment : stepper.buttons.element(boundBy: 0)).tap()
                XCTAssertNotEqual(time.label, originalTime)
                let parts = time.label.split(separator: ":").compactMap { Int($0) }
                XCTAssertEqual(parts.count, 2)
                let minutes = (parts[0] * 60 + parts[1] + 1440 - 10) % 1440
                let expected = String(format: "Eslatma %02d:%02d da keladi.", minutes / 60, minutes % 60)
                XCTAssertTrue(app.staticTexts[expected].exists)
                signal.tap()
                app.buttons["Qisqa ovoz"].tap()
                XCTAssertTrue(app.buttons["Ovozni tinglash"].isHittable)
                capture(app, "Bomdod-eslatma")
            }
            app.buttons["Yopish"].tap()
        }
    }

    func testModuleSettingsSaveInNavigationBar() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        for section in ["Hisob", "Eslatmalar", "Nasihat"] {
            app.tabBars.buttons[section].tap()
            app.navigationBars.buttons[section + " sozlamalari"].tap()
            let bar = app.navigationBars.firstMatch
            let save = section == "Eslatmalar" ? bar.buttons["reminders.settings.save"] : bar.buttons["Saqlash"]
            XCTAssertTrue(save.waitForExistence(timeout: 5), section)
            XCTAssertTrue(save.isHittable)
            XCTAssertGreaterThan(save.frame.midX, bar.frame.midX)
            if section == "Eslatmalar" {
                let toggle = app.switches["reminders.notifications"]
                let sound = app.switches["reminders.sound"]
                XCTAssertEqual(toggle.label, "Bildirishnomalar")
                XCTAssertEqual(sound.label, "Bildirishnoma ovozi")
                XCTAssertFalse(app.staticTexts["Ruxsat"].exists)
                XCTAssertFalse(app.staticTexts["Oxirgi xabar"].exists)
                let systemSettings = app.buttons["iPhone sozlamalarini ochish"]
                capture(app, section + "-sozlamalari")
                if toggle.value as? String == "1" {
                    XCTAssertEqual(systemSettings.exists, app.staticTexts["Bildirishnomalarga ruxsat berilmagan."].exists)
                    let control = toggle.switches.firstMatch
                    (control.exists ? control : toggle).tap()
                }
                XCTAssertEqual(toggle.value as? String, "0")
                let soundControl = sound.switches.firstMatch
                XCTAssertFalse((soundControl.exists ? soundControl : sound).isEnabled)
                capture(app, "Eslatmalar-ochiq-emas")
                XCTAssertFalse(systemSettings.exists)
                XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Navbatda:'")).firstMatch.exists)
                XCTAssertFalse(app.staticTexts["Shu telefonda saqlanadi"].exists)
            } else { capture(app, section + "-sozlamalari") }
            switch section {
            case "Hisob": save.tap()
            case "Eslatmalar": bar.buttons["reminders.settings.close"].tap()
            default: break
            }
        }
    }

    func testAdviceSettingsScheduleAndNotifications() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["-app.appearance", "dark"]
        app.launch()
        app.tabBars.buttons["Nasihat"].tap()
        let settings = app.navigationBars.buttons["Nasihat sozlamalari"]
        settings.tap()
        let bar = app.navigationBars["Nasihat sozlamalari"]
        let interval = app.buttons["nasihat.interval"]
        let alerts = app.switches["Bildirishnoma yuborish"]
        let sound = app.switches["Ovoz"]
        XCTAssertTrue(interval.waitForExistence(timeout: 8))
        XCTAssertLessThan(interval.frame.maxY, alerts.frame.minY)
        XCTAssertFalse(app.tabBars.firstMatch.exists)
        XCTAssertTrue(app.descendants(matching: .any)["nasihat.schedule.start"].firstMatch.isHittable)
        XCTAssertTrue(app.descendants(matching: .any)["nasihat.schedule.end"].firstMatch.isHittable)
        let originalInterval = interval.value as? String

        let alertSwitch = alerts.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5))
        let wasEnabled = alerts.value as? String == "1"
        if !wasEnabled { alertSwitch.tap() }
        XCTAssertTrue(sound.exists)
        let soundValue = sound.value as? String
        capture(app, "Nasihat-jadval")
        alertSwitch.tap()
        XCTAssertFalse(sound.exists)
        XCTAssertTrue(app.staticTexts["Nasihatlar ilovada jadval bo‘yicha keladi."].exists)
        XCTAssertTrue(interval.isEnabled)
        capture(app, "Nasihat-xabarsiz")
        alertSwitch.tap()
        XCTAssertEqual(sound.value as? String, soundValue)

        interval.tap()
        app.buttons["Har 6 soatda"].tap()
        bar.buttons["BackButton"].tap()
        settings.tap()
        XCTAssertEqual(interval.value as? String, originalInterval)
        XCTAssertEqual(alerts.value as? String == "1", wasEnabled)
        bar.buttons["Saqlash"].tap()
        XCTAssertTrue(settings.waitForExistence(timeout: 8))
        XCTAssertTrue(app.tabBars.buttons["Nasihat"].isHittable)
    }

    func testMainToolbarsPlaceGlobalActionsBeforeSectionSettings() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["-qori.readingLayout", "Oyatma-oyat", "-qori.showTranslation", "YES"]
        app.launch()
        for section in ["Namoz", "Qori", "Nasihat", "Hisob", "Eslatmalar"] {
            app.tabBars.buttons[section].tap()
            let buttons = app.navigationBars.buttons
            let gear = buttons["app.settings"]
            XCTAssertTrue(gear.waitForExistence(timeout: 5), section)
            XCTAssertFalse(buttons["toolbar.widgets"].exists)
            let settings = buttons[section + " sozlamalari"]
            if section == "Namoz" {
                XCTAssertFalse(settings.exists)
            } else {
                XCTAssertTrue(settings.isHittable, section)
                XCTAssertLessThan(gear.frame.midX, settings.frame.midX)
            }
            capture(app, section + "-toolbar")
            if section == "Nasihat" {
                let sources = buttons["Manbalarni tanlash"]
                let saved = buttons["Saqlangan nasihatlar"]
                XCTAssertLessThan(gear.frame.midX, sources.frame.midX)
                XCTAssertLessThan(sources.frame.midX, saved.frame.midX)
                XCTAssertLessThan(saved.frame.midX, settings.frame.midX)
                saved.tap()
                XCTAssertTrue(app.navigationBars["Saqlanganlar"].waitForExistence(timeout: 5))
                app.navigationBars.buttons["BackButton"].tap()
                sources.tap()
                XCTAssertTrue(app.navigationBars["Manbalar"].waitForExistence(timeout: 5))
                app.navigationBars.buttons["BackButton"].tap()
            } else if section == "Hisob" {
                let report = buttons["Oy hisoboti"]
                report.tap()
                XCTAssertTrue(app.navigationBars["Oy hisoboti"].waitForExistence(timeout: 5))
                app.navigationBars.buttons["BackButton"].tap()
            } else if section == "Qori" {
                settings.tap()
                XCTAssertTrue(app.staticTexts["Fotiha · 1-oyat"].waitForExistence(timeout: 8))
                let page = app.scrollViews["qori.settings.page"]
                let translation = page.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Меҳрибон")).firstMatch
                XCTAssertTrue(translation.exists)
                let controls = app.staticTexts["O‘qish ko‘rinishi"]
                XCTAssertLessThanOrEqual(translation.frame.maxY, controls.frame.minY)
                XCTAssertLessThan(controls.frame.minY - translation.frame.maxY, 60)
                let bar = app.navigationBars["O‘qish sozlamalari"]
                XCTAssertLessThan(abs(bar.staticTexts["O‘qish sozlamalari"].frame.midY - bar.buttons["Tayyor"].frame.midY), 8)
                capture(app, "Qori-namuna")
                let before = controls.frame.minY
                let sampleBefore = translation.frame.minY
                page.swipeUp()
                let distance = before - controls.frame.minY
                XCTAssertGreaterThan(distance, 10)
                XCTAssertEqual(sampleBefore - translation.frame.minY, distance, accuracy: 2)
                app.buttons["Tayyor"].tap()
            }
            gear.tap()
            XCTAssertTrue(app.navigationBars["Sozlamalar"].waitForExistence(timeout: 5))
            XCTAssertTrue(app.buttons["app.widgets"].exists)
            XCTAssertFalse(app.buttons["Namoz sozlamalari"].exists)
            app.buttons["Yopish"].tap()
        }
    }

    func testSavedAdviceListOpensFullAdvice() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Nasihat"].tap()
        app.navigationBars.buttons["Saqlangan nasihatlar"].tap()
        XCTAssertTrue(app.buttons["nasihat.sourceFilter"].waitForExistence(timeout: 4))
        let share = app.buttons["Ulashish"].firstMatch
        let remove = app.buttons["Saqlanganlardan olib tashlash"]
        XCTAssertFalse(remove.exists)
        XCTAssertFalse(share.exists)
        let entry = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'nasihat.saved.item.'")).firstMatch
        guard entry.exists else {
            XCTAssertTrue(app.staticTexts["Saqlangan nasihatlar yo‘q"].exists)
            throw XCTSkip("Saqlangan nasihat bo‘lganda to‘liq matn tekshiriladi.")
        }
        capture(app, "Nasihat-Saqlangan-royxat")
        entry.tap()
        for _ in 0..<12 where !share.isHittable { app.scrollViews.firstMatch.swipeUp() }
        XCTAssertTrue(share.isHittable)
        XCTAssertTrue(remove.isHittable)
        capture(app, "Nasihat-Saqlangan-ichida")
    }

    func testRemoveNewBookmarkFromSavedDetail() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Nasihat"].tap()
        let saved = app.navigationBars.buttons["Saqlangan nasihatlar"]
        let back = app.navigationBars.buttons["BackButton"]
        let rows = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'nasihat.saved.item.'"))
        saved.tap()
        let previous = Set(rows.allElementsBoundByIndex.map(\.identifier))
        back.tap()

        let history = app.buttons["nasihat.history"]
        for _ in 0..<12 where !history.isHittable { app.scrollViews.firstMatch.swipeUp() }
        history.tap()
        let entries = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'nasihat.history.item.'"))
        var added = false
        for entry in entries.allElementsBoundByIndex {
            entry.tap()
            let save = app.buttons["Saqlash"]
            if save.exists {
                for _ in 0..<12 where !save.isHittable { app.scrollViews.firstMatch.swipeUp() }
                save.tap()
                added = true
            }
            back.tap()
            if added { break }
        }
        guard added else { throw XCTSkip("Sinov uchun saqlanmagan nasihat kerak.") }
        back.tap()
        saved.tap()
        let newRow = try XCTUnwrap(rows.allElementsBoundByIndex.first { !previous.contains($0.identifier) })
        let identifier = newRow.identifier
        newRow.tap()
        let remove = app.buttons["Saqlanganlardan olib tashlash"]
        for _ in 0..<12 where !remove.isHittable { app.scrollViews.firstMatch.swipeUp() }
        remove.tap()
        if !app.navigationBars["Saqlanganlar"].exists { back.tap() }
        XCTAssertTrue(app.navigationBars["Saqlanganlar"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons[identifier].exists)
        XCTAssertEqual(Set(rows.allElementsBoundByIndex.map(\.identifier)), previous)
    }

    func testNasihatHistoryAndShareWithExistingDeliveries() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Nasihat"].tap()
        let scroll = app.scrollViews.firstMatch
        let read = app.buttons["O‘qidim"]
        let share = app.buttons["Ulashish"].firstMatch
        let history = app.buttons["nasihat.history"]
        XCTAssertTrue(history.waitForExistence(timeout: 8))
        if read.exists {
            for _ in 0..<16 where !read.isHittable { scroll.swipeUp() }
            XCTAssertTrue(share.isHittable)
            let save = app.buttons.matching(NSPredicate(format: "label IN %@", ["Saqlash", "Saqlangan"])).firstMatch
            XCTAssertLessThan(save.frame.midX, share.frame.midX)
            XCTAssertLessThan(share.frame.maxY, read.frame.midY)
            capture(app, "Nasihat-Yangi")
            for _ in 0..<16 where !history.isHittable { scroll.swipeDown() }
        }
        history.tap()
        let filter = app.buttons["nasihat.sourceFilter"]
        XCTAssertTrue(filter.waitForExistence(timeout: 4))
        XCTAssertEqual(filter.value as? String, "Barcha manbalar")
        let entry = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'nasihat.history.item.'")).firstMatch
        guard entry.waitForExistence(timeout: 3) else {
            XCTAssertTrue(app.staticTexts["Hozircha o‘qilgan nasihatlar yo‘q"].exists)
            throw XCTSkip("O‘qilgan nasihat bo‘lganda manba va ulashish tekshiriladi.")
        }
        filter.tap()
        let source = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'nasihat.filter.book.'")).firstMatch
        XCTAssertTrue(source.waitForExistence(timeout: 4))
        let title = source.label
        source.tap()
        XCTAssertEqual(filter.value as? String, title)
        XCTAssertTrue(entry.exists)
        filter.tap()
        app.buttons["Barcha manbalar"].tap()
        XCTAssertEqual(filter.value as? String, "Barcha manbalar")
        XCTAssertFalse(app.navigationBars.buttons["app.settings"].exists)
        XCTAssertFalse(app.navigationBars.buttons["Nasihat sozlamalari"].exists)
        XCTAssertFalse(share.exists)
        capture(app, "Nasihat-Manba-tarixi")
        entry.tap()
        for _ in 0..<12 where !share.isHittable { app.scrollViews.firstMatch.swipeUp() }
        XCTAssertFalse(read.exists)
        XCTAssertTrue(share.isHittable)
        XCTAssertFalse(app.navigationBars.buttons["app.settings"].exists)
        XCTAssertFalse(app.navigationBars.buttons["Nasihat sozlamalari"].exists)
        capture(app, "Nasihat-Oqilgan")
        share.tap()
        let activity = app.otherElements["ActivityListView"]
        XCTAssertTrue(activity.waitForExistence(timeout: 8), app.debugDescription)
        capture(app, "Nasihat-Ulashish")
    }

    func testMenuColumnHeadersAndAppearanceOrder() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        openMenus(app)
        let appearance = app.segmentedControls["settings.appearance"]
        let name = app.staticTexts["Menyu"]
        let primary = app.staticTexts["Asosiy"]
        let enabled = app.staticTexts["Yoqish"]
        let star = app.buttons["menus.primary.option.namoz"]
        let toggle = app.switches["menus.toggle.namoz"].firstMatch
        XCTAssertLessThan(appearance.frame.maxY, app.staticTexts["Mening menyularim"].frame.minY)
        XCTAssertLessThan(name.frame.midX, primary.frame.midX)
        XCTAssertLessThan(primary.frame.maxY, star.frame.minY)
        XCTAssertEqual(primary.frame.midX, star.frame.midX, accuracy: 4)
        XCTAssertEqual(enabled.frame.midX, toggle.frame.midX, accuracy: 4)
        capture(app, "Sozlamalar-ustunlar")
    }

    func testPersonalMenusSaveCancelDefaultAndSingleModule() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        openMenus(app)
        capture(app, "Sozlamalar-asosiy")
        for name in ["namoz", "qori", "nasihat", "hisob", "eslatmalar"] { setToggle(app, name, on: true) }
        let primary = app.buttons["menus.primary.option.hisob"]
        XCTAssertTrue(primary.isHittable)
        primary.tap()
        XCTAssertTrue(primary.isSelected)
        XCTAssertFalse(app.buttons["menus.primary.option.namoz"].isSelected)
        capture(app, "Mening-menyularim-all")
        for name in ["namoz", "qori", "nasihat", "eslatmalar"] { setToggle(app, name, on: false) }
        XCTAssertFalse(app.switches["menus.toggle.hisob"].isEnabled)
        XCTAssertFalse(app.buttons["menus.primary.option.qori"].isEnabled)
        capture(app, "Mening-menyularim-single")
        app.buttons["menus.save"].tap()
        XCTAssertTrue(app.buttons["hisob.add"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.tabBars.firstMatch.exists)
        XCTAssertTrue(app.buttons["app.settings"].exists)
        capture(app, "Hisob-single-menu")
        app.terminate(); app.launch()
        XCTAssertTrue(app.buttons["hisob.add"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.tabBars.firstMatch.exists)
        openMenus(app)
        setToggle(app, "namoz", on: true)
        app.buttons["Yopish"].tap()
        XCTAssertFalse(app.tabBars.firstMatch.exists)
        openMenus(app)
        for name in ["namoz", "qori", "nasihat", "eslatmalar"] { setToggle(app, name, on: true) }
        app.buttons["menus.save"].tap()
        app.terminate(); app.launch()
        XCTAssertTrue(app.buttons["hisob.add"].waitForExistence(timeout: 10), "Chosen primary must open even with all tabs")
        XCTAssertTrue(app.tabBars.buttons["Namoz"].exists)
        for name in ["Namoz", "Qori", "Nasihat", "Hisob", "Eslatmalar"] {
            app.tabBars.buttons[name].tap()
            XCTAssertTrue(app.buttons["app.settings"].waitForExistence(timeout: 4))
        }
        openMenus(app)
        app.buttons["menus.primary.option.namoz"].tap()
        app.buttons["menus.save"].tap()
    }
    func testReorderMenusPersists() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        openMenus(app)
        for name in ["namoz", "qori", "nasihat", "hisob", "eslatmalar"] { setToggle(app, name, on: true) }
        let first = app.cells.containing(.switch, identifier: "menus.toggle.namoz").firstMatch
        let last = app.cells.containing(.switch, identifier: "menus.toggle.hisob").firstMatch
        let handle = last.buttons.matching(NSPredicate(format: "label ENDSWITH %@", "Hisob")).firstMatch
        XCTAssertTrue(handle.isHittable)
        handle.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
            .press(forDuration: 1, thenDragTo: first.coordinate(withNormalizedOffset: CGVector(dx: 0.92, dy: 0.1)),
                   withVelocity: .slow, thenHoldForDuration: 0.5)
        XCTAssertEqual(app.switches.element(boundBy: 0).identifier, "menus.toggle.hisob")
        capture(app, "Menus-reordered")
        app.buttons["menus.save"].tap()
        app.terminate(); app.launch()
        XCTAssertTrue(app.tabBars.buttons["Hisob"].waitForExistence(timeout: 10))
        XCTAssertEqual(app.tabBars.buttons.element(boundBy: 0).label, "Hisob")
        openMenus(app)
        let nowFirst = app.cells.containing(.switch, identifier: "menus.toggle.hisob").firstMatch
        let nowLast = app.cells.containing(.switch, identifier: "menus.toggle.nasihat").firstMatch
        let restoredHandle = nowFirst.buttons.matching(NSPredicate(format: "label ENDSWITH %@", "Hisob")).firstMatch
        XCTAssertTrue(restoredHandle.isHittable)
        restoredHandle.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
            .press(forDuration: 1, thenDragTo: nowLast.coordinate(withNormalizedOffset: CGVector(dx: 0.92, dy: 0.9)),
                   withVelocity: .slow, thenHoldForDuration: 0.5)
        XCTAssertEqual(app.switches.element(boundBy: 0).identifier, "menus.toggle.namoz")
        capture(app, "Mening-menyularim-all")
        app.buttons["menus.save"].tap()
        XCTAssertEqual(app.tabBars.buttons.element(boundBy: 0).label, "Namoz")
    }
    func testWidgetKeepsPrayerAndHidesDisabledModule() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        openMenus(app)
        for name in ["namoz", "qori", "nasihat", "hisob", "eslatmalar"] { setToggle(app, name, on: true) }
        app.buttons["menus.save"].tap()
        XCUIDevice.shared.press(.home)
        let home = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        XCTAssertTrue(home.staticTexts["Namoz"].firstMatch.waitForExistence(timeout: 30), home.debugDescription)
        XCTAssertFalse(home.buttons["Keyingi bo‘lim"].exists)
        capture(home, "Widget-home-prayer")
        let countdown = home.staticTexts["widget.countdown"].firstMatch
        // A freshly cloned simulator starts on page one, with the small widget.
        for _ in 0..<3 where !countdown.exists { home.swipeLeft() }
        XCTAssertTrue(countdown.waitForExistence(timeout: 5))
        let durationPattern = #"^Qoldi: (?:\d+ soat(?: \d+ daqiqa)?|\d+ daqiqa)$"#
        let initial = countdown.label
        XCTAssertTrue(initial.range(of: durationPattern, options: .regularExpression) != nil, initial)
        let changed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != %@", initial), object: countdown)
        XCTAssertEqual(XCTWaiter.wait(for: [changed], timeout: 75), .completed, "Home countdown must change without opening the app")
        let updated = countdown.label
        XCTAssertTrue(updated.range(of: durationPattern, options: .regularExpression) != nil, updated)
        XCTAssertNotEqual(updated, initial)
        // AX text can update before SpringBoard commits its next rendered frame.
        // Keep the evidence screenshot after that frame has had time to draw.
        Thread.sleep(forTimeInterval: 2)
        capture(home, "Widget-home-minute-changed")
        app.activate(); openMenus(app)
        setToggle(app, "namoz", on: false)
        app.buttons["menus.save"].tap()
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(home.staticTexts["Bo‘lim o‘chirilgan"].firstMatch.waitForExistence(timeout: 30))
        capture(home, "Widget-home-disabled")
        app.activate(); openMenus(app)
        setToggle(app, "namoz", on: true)
        app.buttons["menus.save"].tap()
    }
    private func openMenus(_ app: XCUIApplication) {
        let gear = app.buttons["app.settings"]
        XCTAssertTrue(gear.waitForExistence(timeout: 10)); gear.tap()
        XCTAssertTrue(app.switches["menus.toggle.namoz"].waitForExistence(timeout: 4))
        let content = app.scrollViews["settings.content"]
        XCTAssertTrue(content.exists)
        for section in ["Qori", "Nasihat", "Hisob", "Eslatmalar"] {
            XCTAssertFalse(content.buttons[section + " sozlamalari"].exists)
        }
        XCTAssertTrue(app.buttons["menus.save"].waitForExistence(timeout: 4))
    }
    private func setToggle(_ app: XCUIApplication, _ name: String, on: Bool) {
        let item = app.switches["menus.toggle." + name]
        XCTAssertTrue(item.waitForExistence(timeout: 3), app.debugDescription)
        if (item.value as? String == "1") != on {
            // SwiftUI exposes both the full row and its native UISwitch. Tap
            // the actual control so edit-mode row/reorder geometry cannot steal it.
            let control = item.switches.firstMatch
            (control.exists ? control : item).tap()
            let changed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", on ? "1" : "0"), object: item)
            XCTAssertEqual(XCTWaiter.wait(for: [changed], timeout: 4), .completed)
        }
    }
    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}

final class WidgetUITests: XCTestCase {
    func testAllApprovedGallerySizes() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        let settings = app.buttons["app.settings"].firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 15)); settings.tap()
        app.buttons["app.widgets"].tap()
        let examples = app.switches["widgets.examples"]
        XCTAssertTrue(examples.waitForExistence(timeout: 5))
        let control = examples.switches.firstMatch
        (control.exists ? control : examples).tap()
        XCTAssertEqual(examples.value as? String, "1")
        XCTAssertFalse(app.buttons["widgets.module.qori"].exists)
        for module in ["namoz", "hisob", "eslatmalar", "nasihat"] {
            app.buttons["widgets.module." + module].tap()
            let sizes = module == "hisob" ? ["small", "medium"] : ["small", "medium", "large"]
            if module == "hisob" { XCTAssertFalse(app.buttons["widgets.size.large"].exists) }
            for size in sizes {
                app.buttons["widgets.size." + size].tap()
                if module == "namoz" {
                    let preview = app.otherElements["widget.namoz." + size]
                    XCTAssertTrue(preview.waitForExistence(timeout: 5))
                    let countdown = preview.staticTexts["widget.countdown"].firstMatch
                    XCTAssertEqual(countdown.exists, size != "small")
                    XCTAssertFalse(preview.staticTexts["Bugungi jadval"].exists)
                    XCTAssertEqual(preview.staticTexts["Asr"].exists, size == "large")
                    if size != "small" {
                        XCTAssertEqual(countdown.label, "Qoldi: 4 soat 3 daqiqa")
                        let prayerTime = preview.staticTexts["12:07"].firstMatch
                        XCTAssertEqual(countdown.frame.midX, prayerTime.frame.midX, accuracy: 1)
                    }
                }
                if module == "eslatmalar" {
                    XCTAssertEqual(app.staticTexts["10 sahifa mutolaa qiling."].exists, size != "small")
                    XCTAssertFalse(app.buttons["Bajarildi"].exists)
                    if size == "large" { XCTAssertTrue(app.staticTexts["Onamga qo‘ng‘iroq"].exists) }
                }
                if module == "nasihat" && size == "small" { XCTAssertTrue(app.staticTexts["2 ta o‘qilmagan nasihat"].exists) }
                if module == "hisob" {
                    let preview = app.otherElements["widget.hisob." + size]
                    XCTAssertTrue(preview.exists)
                    XCTAssertFalse(preview.staticTexts["Balans"].exists)
                    XCTAssertFalse(preview.staticTexts["Umumiy qoldiq"].exists)
                }
                let shot = XCTAttachment(screenshot: app.screenshot())
                shot.name = "Widget-\(module)-\(size)"; shot.lifetime = .keepAlways; add(shot)
            }
        }
    }
    @available(iOS 16.4, *)
    func testWidgetAddEntryColdAndWarmLinks() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        let url = URL(string: "qori-namoz://hisob/add")!
        app.terminate(); app.open(url)
        XCTAssertTrue(app.textFields["hisob.amount"].waitForExistence(timeout: 15), "Cold widget tap opens a new entry")
        app.buttons["Bekor qilish"].tap()
        app.open(url)
        XCTAssertTrue(app.textFields["hisob.amount"].waitForExistence(timeout: 10), "Repeated widget tap opens a fresh entry")
        app.buttons["Bekor qilish"].tap()
    }
}

final class AppearanceUITests: XCTestCase {
    func testAppearanceSelectionPersistsAcrossRelaunch() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let settings = app.buttons["app.settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 15))
        settings.tap()
        let picker = app.segmentedControls["settings.appearance"]
        XCTAssertTrue(picker.waitForExistence(timeout: 5))
        let original = ["Tizim", "Yorug‘", "Qorong‘i"].first { picker.buttons[$0].isSelected } ?? "Tizim"
        defer {
            if !picker.exists { app.buttons["app.settings"].tap() }
            picker.buttons[original].tap()
            app.buttons["Yopish"].tap()
        }
        picker.buttons["Qorong‘i"].tap()
        XCTAssertTrue(picker.buttons["Qorong‘i"].isSelected)
        assertAppearance(app, dark: true)
        capture(app, "Appearance-dark-settings")
        app.buttons["Yopish"].tap()
        for title in ["Namoz", "Qori", "Nasihat", "Hisob", "Eslatmalar"] {
            let tab = app.tabBars.buttons[title]
            if tab.exists { tab.tap(); capture(app, "Appearance-dark-" + title) }
        }
        app.terminate()
        app.launch()
        XCTAssertTrue(settings.waitForExistence(timeout: 15))
        settings.tap()
        XCTAssertTrue(picker.waitForExistence(timeout: 5))
        XCTAssertTrue(picker.buttons["Qorong‘i"].isSelected, "Appearance must persist after relaunch")
        picker.buttons["Yorug‘"].tap()
        XCTAssertTrue(picker.buttons["Yorug‘"].isSelected)
        assertAppearance(app, dark: false)
        capture(app, "Appearance-light-settings")
        app.buttons["Yopish"].tap()
        for title in ["Namoz", "Qori", "Nasihat", "Hisob", "Eslatmalar"] {
            let tab = app.tabBars.buttons[title]
            if tab.exists { tab.tap(); capture(app, "Appearance-light-" + title) }
        }
        app.buttons["app.settings"].tap()
        picker.buttons["Tizim"].tap()
        XCTAssertTrue(picker.buttons["Tizim"].isSelected)
    }

    private func assertAppearance(_ app: XCUIApplication, dark: Bool) {
        // Average rendered pixels verifies that the sheet actually changes,
        // independently of the selected label or stored preference.
        let screenshot = CIImage(cgImage: app.screenshot().image.cgImage!)
        let average = screenshot.applyingFilter("CIAreaAverage", parameters: [kCIInputExtentKey: CIVector(cgRect: screenshot.extent)])
        var pixel = [UInt8](repeating: 0, count: 4)
        CIContext().render(average, toBitmap: &pixel, rowBytes: 4,
                           bounds: CGRect(x: 0, y: 0, width: 1, height: 1), format: .RGBA8,
                           colorSpace: CGColorSpaceCreateDeviceRGB())
        let brightness = Double(Int(pixel[0]) + Int(pixel[1]) + Int(pixel[2])) / (3 * 255)
        if dark { XCTAssertLessThan(brightness, 0.45, "Settings must render dark") }
        else { XCTAssertGreaterThan(brightness, 0.65, "Settings must render light") }
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}

final class RuntimeUITests: XCTestCase {
    func testIdleForegroundAndBackgroundResume() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.buttons["app.settings"].waitForExistence(timeout: 15))
        print("RUNTIME_SAMPLE foreground_start \(Date().timeIntervalSince1970)")
        // Span the minute refresh boundary so a restarted task loop is observable
        // in the companion CPU/notification trace, rather than only at launch.
        waitWhileIdle(seconds: 70)
        XCTAssertEqual(app.state, .runningForeground)
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(app.wait(for: .runningBackground, timeout: 10))
        print("RUNTIME_SAMPLE background_start \(Date().timeIntervalSince1970)")
        waitWhileIdle(seconds: 75)
        print("RUNTIME_SAMPLE background_state \(app.state.rawValue)")
        XCTAssertTrue([XCUIApplication.State.runningBackground, .runningBackgroundSuspended].contains(app.state))
        print("RUNTIME_SAMPLE background_end \(Date().timeIntervalSince1970)")
        app.activate()
        XCTAssertTrue(app.buttons["app.settings"].waitForExistence(timeout: 10))
    }

    private func waitWhileIdle(seconds: TimeInterval) {
        // Keep the test runner's run loop free to receive application-state updates.
        let elapsed = expectation(description: "Idle observation window")
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { elapsed.fulfill() }
        wait(for: [elapsed], timeout: seconds + 5)
    }
}
