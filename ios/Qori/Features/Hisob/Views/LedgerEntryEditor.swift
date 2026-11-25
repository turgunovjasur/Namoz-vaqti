import SwiftUI
import UIKit

struct LedgerEntryEditor: View {
    @EnvironmentObject private var store: LedgerStore
    @Environment(\.dismiss) private var dismiss
    let entry: LedgerEntry?
    let repaymentFor: LedgerEntry?
    @State private var linkedLoanID: UUID?
    @State private var dueDate: Date
    @State private var kind: LedgerKind
    @State private var amount: String
    @State private var categoryID: String
    @State private var note: String
    @State private var date: Date
    @State private var error: String?
    @State private var addingCategory = false
    @State private var choosingCategory = false
    @State private var confirmDelete = false
    @State private var initialized = false
    private enum Field { case amount, note }
    @FocusState private var focusedField: Field?

    init(entry: LedgerEntry?, repaymentFor: LedgerEntry? = nil) {
        self.repaymentFor = repaymentFor
        _linkedLoanID = State(initialValue: repaymentFor?.id ?? entry?.loanID)
        let initialDate = entry.flatMap { LedgerDate.date($0.day) } ?? Date()
        _dueDate = State(initialValue: entry?.dueDay.flatMap(LedgerDate.date) ?? initialDate)
        self.entry = entry
        _kind = State(initialValue: entry?.kind ?? repaymentFor?.kind.opposite ?? .expense)
        _amount = State(initialValue: entry.map { LedgerMoney.text(Decimal($0.amount)) } ?? "")
        _categoryID = State(initialValue: entry?.categoryID ?? repaymentFor?.kind.opposite.loanCategoryID ?? "expense.food")
        _note = State(initialValue: entry?.note ?? repaymentFor?.note ?? "")
        _date = State(initialValue: max(initialDate, repaymentFor.flatMap { LedgerDate.date($0.day) } ?? initialDate))
    }
    private var isLoan: Bool { categoryID == kind.loanCategoryID }
    private var linkedLoan: LedgerEntry? {
        linkedLoanID.flatMap { id in store.state.entries.first { $0.id == id } }
    }
    private var fixedRepayment: Bool { repaymentFor != nil || entry?.loanID != nil }
    // While editing, put this payment back into the available principal.
    private var availablePrincipal: Int64? {
        guard let loan = linkedLoan else { return nil }
        return store.remaining(loan) + (entry?.loanID == loan.id ? entry?.amount ?? 0 : 0)
    }
    private var convertibleLoans: [LedgerEntry] {
        guard let entry, !entry.isLoan, isLoan else { return [] }
        return store.state.entries.filter {
            $0.isLoan && $0.loanID == nil && $0.kind != kind && $0.day <= LedgerDate.key(date) && store.remaining($0) > 0
        }
    }
    private var selectableCategories: [LedgerCategory] {
        store.categories(kind, includeArchived: true).filter {
            !$0.isArchived || ($0.id == entry?.categoryID && $0.kind == entry?.kind)
        }
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if fixedRepayment, let loan = linkedLoan {
                        VStack(alignment: .leading, spacing: 6) {
                            Label(kind == .income ? "Kirim · Qarz qaytimi" : "Chiqim · Qarz qaytimi",
                                  systemImage: kind == .income ? "arrow.down.left" : "arrow.up.right")
                                .font(.subheadline.weight(.semibold)).foregroundStyle(HisobStyle.green)
                                .accessibilityIdentifier("hisob.repaymentDirection")
                            Text(loan.note.isEmpty ? loan.loanTitle : loan.note).font(.title2.bold())
                            if let availablePrincipal {
                                Text((entry == nil ? "Qarz qoldig‘i: " : "Eng ko‘p qaytim: ") + LedgerMoney.text(Decimal(availablePrincipal)) + " so‘m")
                                    .font(.subheadline).foregroundStyle(.secondary)
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(16)
                            .background(HisobStyle.mint, in: RoundedRectangle(cornerRadius: 16))
                    } else {
                        Picker("Yozuv turi", selection: $kind) {
                            ForEach(LedgerKind.allCases) { Text($0.title).tag($0) }
                        }.pickerStyle(.segmented)
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(fixedRepayment ? "Qaytim summasi" : "Summa").font(.subheadline).foregroundStyle(.secondary)
                            Spacer()
                            if let availablePrincipal {
                                Button("Hammasi") { amount = LedgerMoney.text(Decimal(availablePrincipal)) }
                                    .font(.subheadline.weight(.semibold)).frame(minHeight: 44)
                                    .accessibilityLabel("Qolgan summani to‘liq kiritish")
                                    .accessibilityIdentifier("hisob.fullRepayment")
                            }
                        }
                        HStack(spacing: 8) {
                            LedgerAmountField(text: $amount, large: true, label: "Summa, so‘m", identifier: "hisob.amount")
                                .focused($focusedField, equals: .amount)
                                .frame(height: 54)
                            Text("so‘m").font(.headline).foregroundStyle(.secondary)
                        }
                    }.padding(16).background(Palette.card, in: RoundedRectangle(cornerRadius: 16))
                    VStack(spacing: 0) {
                        if !fixedRepayment {
                            Button {
                                dismissKeyboard()
                                choosingCategory = true
                            } label: {
                                HStack {
                                    Label("Kategoriya", systemImage: store.category(categoryID)?.symbol ?? "tag")
                                    Spacer(minLength: 4)
                                    Text(store.category(categoryID)?.displayName ?? "Tanlang").foregroundStyle(HisobStyle.green)
                                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                                }.frame(minHeight: 48).contentShape(Rectangle())
                            }.buttonStyle(.plain)
                                .accessibilityLabel("Kategoriya, " + (store.category(categoryID)?.displayName ?? "Tanlang"))
                                .accessibilityIdentifier("hisob.categoryPicker")
                            Divider()
                        }
                        if !convertibleLoans.isEmpty {
                            Picker("Qarzga bog‘lash", selection: $linkedLoanID) {
                                Text("Yangi qarz").tag(nil as UUID?)
                                ForEach(convertibleLoans) { loan in
                                    Text((loan.note.isEmpty ? loan.loanTitle : loan.note) + " · " + LedgerMoney.text(Decimal(store.remaining(loan))))
                                        .tag(Optional(loan.id))
                                }
                            }.frame(minHeight: 48)
                                .simultaneousGesture(TapGesture().onEnded { dismissKeyboard() })
                            Divider()
                        }
                        if !fixedRepayment, let loan = linkedLoan {
                            Label((loan.note.isEmpty ? loan.loanTitle : loan.note) + " · " +
                                  LedgerMoney.text(Decimal(store.remaining(loan))) + " so‘m", systemImage: "link")
                                .frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 12)
                        }
                        if !fixedRepayment {
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: "pencil").frame(width: 26).padding(.top, 3)
                                TextField("Izoh (ixtiyoriy)", text: $note, prompt: Text("Izoh (ixtiyoriy)").foregroundColor(Palette.mutedInk), axis: .vertical)
                                    .keyboardType(.default)
                                    .focused($focusedField, equals: .note)
                                    .lineLimit(1...4).autocorrectionDisabled(isLoan).accessibilityLabel("Izoh")
                            }.frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.vertical, 13)
                                .contentShape(Rectangle())
                                .simultaneousGesture(TapGesture().onEnded { focusedField = .note })
                            Divider()
                        }
                        LedgerDateRow(title: "Sana", symbol: "calendar", date: $date,
                                      minimum: linkedLoan.flatMap { LedgerDate.date($0.day) } ?? LedgerDate.date("1900-01-01")!,
                                      dismissKeyboard: dismissKeyboard)
                        if isLoan && linkedLoanID == nil {
                            Divider()
                            LedgerDateRow(title: "Qaytarish sanasi", symbol: "calendar.badge.clock", date: $dueDate,
                                          minimum: date, dismissKeyboard: dismissKeyboard)
                            Text("Shu kuni qarz qoldig‘i haqida eslatiladi.").font(.caption).foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading).padding(.bottom, 10)
                        }
                        if !isLoan { Divider(); addCategoryButton }
                    }.padding(.horizontal, 16).background(Palette.card, in: RoundedRectangle(cornerRadius: 16))
                    if let availablePrincipal, let paid = try? LedgerMoney.parse(amount) {
                        let left = availablePrincipal - paid
                        let preview = left < 0 ? "Summa qarz qoldig‘idan oshdi." : left == 0 ? "Saqlanganda qarz yopiladi." : "Qoladi: " + LedgerMoney.text(Decimal(left)) + " so‘m"
                        Label(preview, systemImage: left < 0 ? "exclamationmark.circle" : left == 0 ? "checkmark.circle" : "arrow.turn.down.right")
                            .font(.subheadline.weight(.semibold)).foregroundStyle(left < 0 ? HisobStyle.red : HisobStyle.green)
                            .accessibilityElement(children: .combine).accessibilityIdentifier("hisob.repaymentPreview")
                    }
                    if entry != nil {
                        Button(role: .destructive) { dismissKeyboard(); confirmDelete = true } label: {
                            Label("Yozuvni o‘chirish", systemImage: "trash").frame(maxWidth: .infinity).padding(.vertical, 12)
                        }
                    }
                }.padding(20)
            }.accessibilityIdentifier("hisob.entryScroll").scrollDismissesKeyboard(.interactively).background(Palette.paper)
            .keyboardDismissBar(visible: focusedField != nil, identifier: "hisob.dismissKeyboard", dismiss: dismissKeyboard)
            .navigationDestination(isPresented: $choosingCategory) {
                List(selectableCategories) { category in
                    Button {
                        categoryID = category.id
                        choosingCategory = false
                    } label: {
                        HStack {
                            Label(category.displayName, systemImage: category.symbol)
                            Spacer()
                            if category.id == categoryID { Image(systemName: "checkmark").foregroundStyle(HisobStyle.green) }
                        }.contentShape(Rectangle())
                    }.buttonStyle(.plain)
                        .accessibilityLabel(category.displayName)
                        .accessibilityAddTraits(category.id == categoryID ? .isSelected : [])
                        .listRowBackground(Palette.card)
                }.scrollContentBackground(.hidden).background(Palette.paper)
                    .navigationTitle("Kategoriya").navigationBarTitleDisplayMode(.inline)
            }
            .navigationTitle(repaymentFor != nil ? "Qaytim kiritish" : entry == nil ? "Yangi yozuv" : "Yozuvni tahrirlash").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Bekor qilish") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Saqlash", action: save).bold().disabled(!canSave).accessibilityIdentifier("hisob.save")
                }
            }
            .onAppear {
                guard !initialized else { return }
                if entry == nil && repaymentFor == nil { categoryID = store.defaultCategory(kind)?.id ?? "" }
                initialized = true
                if entry == nil { focusedField = .amount }
            }
            .onChange(of: date) { value in
                if LedgerDate.key(dueDate) < LedgerDate.key(value) { dueDate = value }
            }
            .onChange(of: categoryID) { _ in if !isLoan { linkedLoanID = nil } }
            .onChange(of: kind) { value in
                dismissKeyboard()
                let wasLoan = categoryID == value.opposite.loanCategoryID
                linkedLoanID = nil
                categoryID = wasLoan ? value.loanCategoryID : store.defaultCategory(value)?.id ?? ""
            }
            .onChange(of: store.state.categories) { _ in
                if !selectableCategories.contains(where: { $0.id == categoryID }) {
                    categoryID = store.defaultCategory(kind)?.id ?? ""
                }
            }
            .sheet(isPresented: $addingCategory) {
                LedgerAddCategoryView(kind: kind) { categoryID = $0 }
            }
            .confirmationDialog("Yozuv o‘chirilsinmi?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("O‘chirish", role: .destructive) {
                    if let entry, store.deleteEntry(entry.id) { dismiss() } else { error = store.error }
                }
            } message: { Text("O‘chirgandan keyin 10 soniya ichida qaytarish mumkin.") }
            .ledgerAlert($error).tint(HisobStyle.green)
        }
    }
    private func dismissKeyboard() {
        focusedField = nil
        InputKeyboard.dismiss()
    }

    private var addCategoryButton: some View {
        Button {
            dismissKeyboard()
            addingCategory = true
        } label: {
            Label("Kategoriya qo‘shish", systemImage: "plus.circle")
                .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
        }
    }

    private var canSave: Bool {
        guard store.isAvailable, let value = try? LedgerMoney.parse(amount) else { return false }
        guard let loan = linkedLoan, let availablePrincipal else { return true }
        return value <= availablePrincipal && LedgerDate.key(date) >= loan.day
    }
    private func save() {
        if store.saveEntry(id: entry?.id, kind: kind, amount: amount, categoryID: categoryID, note: note, date: date,
                           dueDate: isLoan && linkedLoanID == nil ? dueDate : nil, loanID: linkedLoanID) {
            dismiss()
        } else { error = store.error }
    }

}

private struct LedgerDateRow: View {
    let title: String
    let symbol: String
    @Binding var date: Date
    let minimum: Date
    let dismissKeyboard: () -> Void
    @State private var showingCalendar = false

    var body: some View {
        Button {
            dismissKeyboard()
            showingCalendar = true
        } label: {
            HStack {
                Label(title, systemImage: symbol)
                Spacer()
                Text(LedgerDate.label(LedgerDate.key(date))).foregroundStyle(HisobStyle.green)
            }.frame(minHeight: 48).contentShape(Rectangle())
        }.buttonStyle(.plain)
            .accessibilityLabel(title)
            .accessibilityValue(LedgerDate.label(LedgerDate.key(date)))
            .sheet(isPresented: $showingCalendar) {
                LedgerDayPicker(date: date, minimum: minimum) { selected in
                    date = selected
                    showingCalendar = false
                }
                .padding()
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
    }
}

private struct LedgerDayPicker: UIViewRepresentable {
    let date: Date
    let minimum: Date
    let onSelect: (Date) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UICalendarView {
        let view = UICalendarView()
        let calendar = LedgerDate.calendar
        view.calendar = calendar
        view.locale = Locale(identifier: "uz_Latn_UZ")
        view.tintColor = UIColor(HisobStyle.green)
        view.availableDateRange = DateInterval(start: calendar.startOfDay(for: minimum), end: LedgerDate.date("9999-12-31")!)
        let components = calendar.dateComponents([.year, .month, .day], from: date)
        view.visibleDateComponents = components
        let selection = UICalendarSelectionSingleDate(delegate: context.coordinator)
        view.selectionBehavior = selection
        selection.setSelected(components, animated: false)
        return view
    }

    func updateUIView(_ view: UICalendarView, context: Context) {}

    final class Coordinator: NSObject, UICalendarSelectionSingleDateDelegate {
        let picker: LedgerDayPicker
        init(_ picker: LedgerDayPicker) { self.picker = picker }

        func dateSelection(_ selection: UICalendarSelectionSingleDate, canSelectDate dateComponents: DateComponents?) -> Bool {
            // UIKit passes nil when the user taps the highlighted day again.
            true
        }

        func dateSelection(_ selection: UICalendarSelectionSingleDate, didSelectDate dateComponents: DateComponents?) {
            picker.onSelect(dateComponents.flatMap { LedgerDate.calendar.date(from: $0) } ?? picker.date)
        }
    }
}

struct LedgerAddCategoryView: View {
    @EnvironmentObject private var store: LedgerStore
    @Environment(\.dismiss) private var dismiss
    let kind: LedgerKind
    var onSave: (String) -> Void = { _ in }
    @State private var name = ""
    @FocusState private var nameFocused: Bool
    @State private var error: String?
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Kategoriya nomi", text: $name).accessibilityLabel("Kategoriya nomi")
                        .focused($nameFocused)
                        .submitLabel(.done).onSubmit { nameFocused = false }
                } header: {
                    Text(kind.title + " kategoriyasi")
                } footer: {
                    Text("Ko‘pi bilan 30 belgi.")
                }
                .listRowBackground(Palette.card)
                LedgerCategorySection(kind: kind, title: "Mavjud kategoriyalar") { EmptyView() }
            }.scrollDismissesKeyboard(.interactively).scrollContentBackground(.hidden).background(Palette.paper)
                .navigationTitle("Yangi kategoriya").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Yopish") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Qo‘shish") {
                            if store.addCategory(name: name, kind: kind) {
                                onSave(store.state.categories.last!.id); dismiss()
                            } else { error = store.error }
                        }.bold().disabled(!(1...30).contains(name.trimmingCharacters(in: .whitespacesAndNewlines).count))
                    }
                }.ledgerAlert($error).tint(HisobStyle.green)
        }.onAppear { nameFocused = true }
            .presentationDetents([.large])
    }
}

struct LedgerSettingsView: View {
    @EnvironmentObject private var store: LedgerStore
    @Environment(\.dismiss) private var dismiss
    @State private var opening = "0"
    @FocusState private var openingFocused: Bool
    @State private var negative = false
    @State private var error: String?
    @State private var loaded = false
    @State private var kind: LedgerKind = .expense
    @State private var addingCategory = false
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Text("Summa")
                        LedgerAmountField(text: $opening, large: false, label: "Boshlang‘ich qoldiq, so‘m", identifier: "hisob.opening")
                            .focused($openingFocused).frame(minHeight: 44)
                        Text("so‘m").foregroundStyle(.secondary)
                    }
                    Toggle("Manfiy qoldiq", isOn: $negative)
                        .onChange(of: negative) { _ in InputKeyboard.dismiss() }
                } header: { Text("Boshlang‘ich qoldiq") }
                  footer: {
                      Text(negative ? "Boshlang‘ich summa umumiy qoldiqdan ayriladi." : "Hisob yuritishni boshlagan kundagi pulingiz.")
                  }
                  .listRowBackground(Palette.card)
                LedgerCategorySection(kind: kind, title: "Kategoriyalar") {
                    Picker("Turi", selection: $kind) {
                        ForEach(LedgerKind.allCases) { Text($0.title).tag($0) }
                    }.pickerStyle(.segmented).onChange(of: kind) { _ in InputKeyboard.dismiss() }
                    Button {
                        InputKeyboard.dismiss()
                        addingCategory = true
                    } label: { Label("Kategoriya qo‘shish", systemImage: "plus.circle") }
                }
            }.scrollContentBackground(.hidden).background(Palette.paper)
                .keyboardDismissBar(visible: openingFocused, identifier: "hisob.settings.dismissKeyboard") {
                    openingFocused = false
                    InputKeyboard.dismiss()
                }
                .navigationTitle("Hisob sozlamalari").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Yopish") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Saqlash") {
                            if store.setOpeningBalance((negative ? "-" : "") + opening) { dismiss() }
                            else { error = store.error }
                        }.bold().disabled(!loaded || !store.isAvailable)
                    }
                }
                .disabled(!store.isAvailable)
                .onAppear {
                    if !loaded {
                        negative = store.state.openingBalance < 0
                        opening = LedgerMoney.text(abs(Decimal(store.state.openingBalance)))
                        loaded = true
                    }
                }
                .scrollDismissesKeyboard(.interactively)
                .sheet(isPresented: $addingCategory) { LedgerAddCategoryView(kind: kind) }
                .ledgerAlert($error)
                .tint(HisobStyle.green)
        }
    }
}

private struct LedgerCategorySection<Controls: View>: View {
    @EnvironmentObject private var store: LedgerStore
    let kind: LedgerKind
    let title: String
    @ViewBuilder let controls: () -> Controls
    @State private var deleting: LedgerCategory?
    @State private var error: String?

    var body: some View {
        Section {
            controls()
            ForEach(store.categories(kind)) { category in
                if category.isLoan {
                    Label("Qarz", systemImage: category.symbol)
                } else {
                    Menu {
                        Button {
                            if !store.setDefaultCategory(category.id) { error = store.error }
                        } label: { Label("Asosiy qilish", systemImage: "star") }
                        if !category.isFallback {
                            Button(role: .destructive) { deleting = category } label: {
                                Label("O‘chirish", systemImage: "trash")
                            }
                        }
                    } label: {
                        HStack {
                            Label(category.name, systemImage: category.symbol)
                            Spacer()
                            if store.defaultCategory(kind)?.id == category.id {
                                Label("Asosiy", systemImage: "star.fill").font(.caption)
                            }
                            Image(systemName: "ellipsis").foregroundStyle(.secondary)
                        }.foregroundStyle(HisobStyle.ink)
                    }.simultaneousGesture(TapGesture().onEnded { InputKeyboard.dismiss() })
                        .accessibilityIdentifier("hisob.category." + category.id)
                }
            }
        } header: {
            Text(title)
        } footer: {
            Text("Yangi yozuvda asosiy kategoriya tanlanadi.")
        }
        .listRowBackground(Palette.card)
        .confirmationDialog("«\(deleting?.name ?? "")» kategoriyasi o‘chirilsinmi?",
                            isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }),
                            titleVisibility: .visible, presenting: deleting) { category in
            Button("O‘chirish", role: .destructive) {
                if !store.deleteCategory(category.id) { error = store.error }
                deleting = nil
            }
            Button("Bekor qilish", role: .cancel) { deleting = nil }
        } message: { category in
            if store.categoryHasHistory(category.id) {
                Text("Bu kategoriya arxivlanadi. \(store.categoryUsageCount(category.id)) ta yozuvdagi nomi va summalari saqlanadi, yangi yozuvlarda ko‘rinmaydi.")
            } else {
                Text("Kategoriya ishlatilmagan va butunlay o‘chiriladi.")
            }
        }.ledgerAlert($error)
    }
}

// Format synchronously in the native input delegate so fast typing cannot be
// overwritten by a later SwiftUI onChange, and preserve the caret when spaces move.
private struct LedgerAmountField: UIViewRepresentable {
    @Binding var text: String
    let large: Bool
    let label: String
    let identifier: String

    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.delegate = context.coordinator
        field.keyboardType = .decimalPad
        field.textAlignment = large ? .natural : .right
        field.attributedPlaceholder = NSAttributedString(string: "0", attributes: [.foregroundColor: UIColor(Palette.mutedInk)])
        field.font = UIFontMetrics(forTextStyle: large ? .largeTitle : .body)
            .scaledFont(for: .systemFont(ofSize: large ? 42 : 17, weight: large ? .semibold : .regular))
        field.adjustsFontSizeToFitWidth = true
        field.minimumFontSize = large ? 20 : 12
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        field.accessibilityLabel = label
        field.accessibilityIdentifier = identifier
        return field
    }
    func updateUIView(_ field: UITextField, context: Context) {
        context.coordinator.parent = self
        field.accessibilityLabel = label
        if field.text != text { field.text = text }
    }
    final class Coordinator: NSObject, UITextFieldDelegate {
        var parent: LedgerAmountField
        init(_ parent: LedgerAmountField) { self.parent = parent }
        func textField(_ field: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
            let current = (field.text ?? "") as NSString
            guard range.location + range.length <= current.length else { return false }
            var editRange = range
            // Backspacing over an inserted space also removes the preceding digit.
            if string.isEmpty, range.length == 1, range.location > 0, current.substring(with: range) == " " {
                editRange = NSRange(location: range.location - 1, length: 2)
            }
            let proposed = current.replacingCharacters(in: editRange, with: string)
            let prefix = (proposed as NSString).substring(to: editRange.location + (string as NSString).length)
            let significantCount = prefix.filter { !$0.isWhitespace }.count
            let formatted = LedgerMoney.groupedInput(proposed)
            field.text = formatted
            parent.text = formatted
            var offset = 0
            var significant = 0
            for character in formatted {
                if significant >= significantCount { break }
                offset += String(character).utf16.count
                if !character.isWhitespace { significant += 1 }
            }
            if let position = field.position(from: field.beginningOfDocument, offset: offset) {
                field.selectedTextRange = field.textRange(from: position, to: position)
            }
            return false
        }
    }
}

/// Opening a loan in history keeps all repayments attached to its original entry.
struct LedgerEntrySheet: View {
    @EnvironmentObject private var store: LedgerStore
    let entry: LedgerEntry?
    var body: some View {
        if let entry, let loan = store.loan(for: entry) {
            LedgerLoanDetail(loanID: loan.id)
        } else {
            LedgerEntryEditor(entry: entry)
        }
    }
}

private struct LedgerLoanDetail: View {
    @EnvironmentObject private var store: LedgerStore
    @Environment(\.dismiss) private var dismiss
    let loanID: UUID
    @State private var editing: LedgerEditorRoute?
    @State private var paying = false

    var body: some View {
        NavigationStack {
            if let loan = store.state.entries.first(where: { $0.id == loanID }) {
                let remaining = store.remaining(loan)
                let payments = store.state.entries.filter { $0.loanID == loanID }
                    .sorted { ($0.day, $0.createdAt) > ($1.day, $1.createdAt) }
                List {
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            LedgerLoanStatus(remaining: remaining)
                            Text(loan.note.isEmpty ? loan.loanTitle : loan.note).font(.title2.bold())
                            Text(loan.kind == .expense ? "Menga qaytariladigan qoldiq" : "Men qaytaradigan qoldiq")
                                .font(.subheadline).foregroundStyle(.secondary)
                            Text(LedgerMoney.text(Decimal(remaining)) + " so‘m")
                                .font(.title.bold()).monospacedDigit().foregroundStyle(HisobStyle.ink)
                        }.padding(.vertical, 6)
                    }.listRowBackground(HisobStyle.mint)
                    Section {
                        LabeledContent(loan.loanTitle, value: LedgerMoney.text(Decimal(loan.amount)) + " so‘m")
                        if remaining < loan.amount {
                            LabeledContent("Qaytarilgan", value: LedgerMoney.text(Decimal(loan.amount - remaining)) + " so‘m")
                        }
                        LabeledContent("Qarz sanasi", value: LedgerDate.label(loan.day))
                        if let due = loan.dueDay { LabeledContent("Qaytarish sanasi", value: LedgerDate.label(due)) }
                    }.listRowBackground(Palette.card)
                    if !payments.isEmpty {
                        Section("Qaytimlar") {
                            ForEach(payments) { payment in
                                Button { editing = .init(entry: payment) } label: {
                                    LabeledContent(LedgerDate.label(payment.day), value: LedgerMoney.text(Decimal(payment.amount)) + " so‘m")
                                }
                            }
                        }.listRowBackground(Palette.card)
                    }
                }.scrollContentBackground(.hidden).background(Palette.paper)
                    .safeAreaInset(edge: .bottom) {
                        if remaining > 0 {
                            Button { paying = true } label: {
                                Label("Qaytim kiritish", systemImage: "arrow.left.arrow.right")
                                    .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 16)
                            }.buttonStyle(LedgerPrimaryButton()).accessibilityIdentifier("hisob.repay")
                                .padding(.horizontal, 20).padding(.vertical, 8).background(Palette.paper)
                        }
                    }
                    .navigationTitle("Qarz").navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) { Button("Yopish") { dismiss() } }
                        ToolbarItem(placement: .confirmationAction) { Button("Tahrirlash") { editing = .init(entry: loan) } }
                    }
                    .sheet(isPresented: $paying) { LedgerEntryEditor(entry: nil, repaymentFor: loan) }
                    .sheet(item: $editing) { LedgerEntryEditor(entry: $0.entry) }
            } else {
                Color.clear.onAppear { dismiss() }
            }
        }.tint(HisobStyle.green)
    }
}
