import Foundation
import Security

// The app and widget share only the district and prayer time adjustments.
struct WidgetSettings: Codable, Equatable {
    let regionName: String
    let slug: String
    let offsets: [String: Int]

    init(region: PrayerRegion, preferences: PrayerPreferences) {
        regionName = region.name
        slug = region.slug
        offsets = Dictionary(uniqueKeysWithValues: Prayer.allCases.map { ($0.rawValue, preferences[$0].offset) })
    }

    static let kind = "QoriNextPrayer"

    private static var item: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: kind,
         kSecAttrAccount as String: "settings",
         kSecAttrAccessGroup as String: Bundle.main.object(forInfoDictionaryKey: "WidgetSettingsGroup") as? String ?? ""]
    }

    static func read() -> Self? {
        var query = item
        query[kSecReturnData as String] = true
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return try? JSONDecoder().decode(Self.self, from: data)
    }

    func saveIfChanged() -> Bool {
        guard Self.read() != self, let data = try? JSONEncoder().encode(self) else { return false }
        let update = [kSecValueData as String: data]
        let status = SecItemUpdate(Self.item as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var item = Self.item
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            return SecItemAdd(item as CFDictionary, nil) == errSecSuccess
        }
        return status == errSecSuccess
    }
}
