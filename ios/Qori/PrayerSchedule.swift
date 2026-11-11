import Foundation

struct PrayerRegion: Decodable, Identifiable {
    let id, name, slug: String
}

struct PrayerGroup: Decodable {
    let name: String
    let regions: [PrayerRegion]

    static let catalog: [Self] = {
        guard let url = Bundle.main.url(forResource: "prayer-regions", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return [] }
        return (try? JSONDecoder().decode([Self].self, from: data)) ?? []
    }()
}

enum Prayer: String, CaseIterable, Identifiable {
    case bomdod = "Bomdod", quyosh = "Quyosh", peshin = "Peshin", asr = "Asr", shom = "Shom", xufton = "Xufton"
    var id: Self { self }
    var icon: String {
        switch self {
        case .bomdod: return "sun.haze"
        case .quyosh: return "sunrise"
        case .peshin: return "sun.max"
        case .asr: return "sun.min"
        case .shom: return "sunset"
        case .xufton: return "moon.stars"
        }
    }
}

enum PrayerClock {
    static let calendar: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tashkent")!
        return calendar
    }()
    static func month(_ date: Date) -> String {
        String(format: "%04d-%02d", calendar.component(.year, from: date), calendar.component(.month, from: date))
    }
    static func day(_ date: Date) -> String {
        String(format: "%02d.%02d.%04d", calendar.component(.day, from: date),
               calendar.component(.month, from: date), calendar.component(.year, from: date))
    }
    static func tomorrow(_ date: Date) -> Date { calendar.date(byAdding: .day, value: 1, to: date)! }
}

struct PrayerDay {
    let times: [Prayer: String]
    init(_ data: [String: String]) throws {
        var result: [Prayer: String] = [:]
        var previous = -1
        for prayer in Prayer.allCases {
            guard let text = data[prayer.rawValue.lowercased()],
                  text.range(of: #"^([01][0-9]|2[0-3]):[0-5][0-9]$"#, options: .regularExpression) != nil,
                  let hour = Int(text.prefix(2)), let minute = Int(text.suffix(2)), hour * 60 + minute > previous
            else { throw URLError(.cannotParseResponse) }
            previous = hour * 60 + minute
            result[prayer] = text
        }
        times = result
    }

    func next(at date: Date) -> Prayer? {
        let now = String(format: "%02d:%02d", PrayerClock.calendar.component(.hour, from: date),
                         PrayerClock.calendar.component(.minute, from: date))
        return Prayer.allCases.first { $0 != .quyosh && (times[$0] ?? "") > now }
    }
}

struct PrayerMonth: Decodable {
    struct Meta: Decodable {
        struct Region: Decodable { let slug: String }
        let region: Region
        let ym: String
    }
    struct Row: Decodable { let date: String; let times: [String: String] }
    let meta: Meta
    let period_table: [Row]

    func day(_ date: Date) throws -> PrayerDay {
        guard let row = period_table.first(where: { $0.date == PrayerClock.day(date) })
        else { throw URLError(.cannotParseResponse) }
        return try PrayerDay(row.times)
    }

    static func load(slug: String, date: Date) async throws -> Self {
        let period = PrayerClock.month(date)
        var url = URLComponents(string: "https://namoz-vaqti.uz/")!
        url.queryItems = ["region": slug, "lang": "lotin", "period": period, "format": "json"]
            .map { URLQueryItem(name: $0.key, value: $0.value) }
        let cacheKey = "namoz.month." + slug
        func decode(_ data: Data) throws -> Self {
            let value = try JSONDecoder().decode(Self.self, from: data)
            guard value.meta.region.slug == slug, value.meta.ym == period else { throw URLError(.badServerResponse) }
            _ = try value.day(date)
            return value
        }
        do {
            let (data, response) = try await URLSession.shared.data(for: URLRequest(url: url.url!, timeoutInterval: 12))
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
            let value = try decode(data)
            UserDefaults.standard.set(data, forKey: cacheKey + "." + period.suffix(2))
            return value
        } catch {
            try Task.checkCancellation()
            if let data = UserDefaults.standard.data(forKey: cacheKey + "." + period.suffix(2)),
               let value = try? decode(data) { return value }
            throw error
        }
    }
}
