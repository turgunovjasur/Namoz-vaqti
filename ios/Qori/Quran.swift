import Foundation

struct Verse: Identifiable {
    let id: Int
    let uthmani: String
    let simple: String
    let translation: String
    let note: String?

    init(id: Int, uthmani: String, simple: String, translated: String) {
        self.id = id
        self.uthmani = uthmani
        self.simple = simple
        // Separate only a complete trailing commentary. Keep parenthetical words
        // within the translation itself (for example, in Fotiha 1:7).
        if translated.last == ")" {
            var depth = 0
            for i in translated.indices.reversed() {
                if translated[i] == ")" { depth += 1 }
                if translated[i] == "(" { depth -= 1 }
                if depth == 0, i > translated.startIndex,
                   translated[translated.index(before: i)] == " " {
                    translation = String(translated[..<translated.index(before: i)])
                    note = String(translated[translated.index(after: i)..<translated.index(before: translated.endIndex)])
                    return
                }
                if depth <= 0 { break }
            }
        }
        translation = translated
        note = nil
    }
}

struct Surah: Identifiable {
    let id: Int
    let name: String
    let verses: [Verse]
}

enum Quran {
    enum LoadError: Error { case missingResource(String), invalidCorpus }

    static func load(from directory: URL) throws -> [Surah] {
        func read(_ filename: String) throws -> String {
            let url = directory.appendingPathComponent(filename)
            return try String(contentsOf: url, encoding: .utf8)
        }
        func chapters(_ filename: String) throws -> [[String]] {
            var result = Array(repeating: [String](), count: 114)
            for line in try read(filename).split(whereSeparator: \.isNewline) where !line.hasPrefix("#") {
                let fields = line.split(separator: "|", maxSplits: 2)
                guard fields.count == 3, let chapter = Int(fields[0]), (1...114).contains(chapter),
                      let number = Int(fields[1]), number == result[chapter - 1].count + 1 else {
                    throw LoadError.invalidCorpus
                }
                result[chapter - 1].append(String(fields[2]))
            }
            return result
        }
        let names = try read("surah-names.txt").split(whereSeparator: \.isNewline)
        let uthmani = try chapters("quran-uthmani.txt")
        let simple = try chapters("quran-simple.txt")
        let translated = try chapters("uz-sodik.txt")
        guard names.count == 114, uthmani.allSatisfy({ !$0.isEmpty }),
              uthmani.map(\.count) == simple.map(\.count), uthmani.map(\.count) == translated.map(\.count),
              uthmani.reduce(0, { $0 + $1.count }) == 6236 else { throw LoadError.invalidCorpus }
        return names.indices.map { i in
            Surah(id: i + 1, name: String(names[i]), verses: uthmani[i].indices.map { j in
                Verse(id: j + 1, uthmani: uthmani[i][j], simple: simple[i][j], translated: translated[i][j])
            })
        }
    }
}

enum Reciter: String, CaseIterable, Identifiable {
    case alafasy = "Alafasy_128kbps"
    case husary = "Husary_128kbps"
    var id: Self { self }
    var name: String { self == .alafasy ? "Mishari Alafasiy" : "Mahmud Xalil Husariy" }

    func audioURL(surah: Int, verse: Int) -> URL {
        let file = String(format: "%03d%03d.mp3", surah, verse)
        return URL(string: "https://everyayah.com/data/")!.appendingPathComponent(rawValue).appendingPathComponent(file)
    }
}
