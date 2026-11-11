import AVFoundation
import Combine

@MainActor
final class RecitationPlayer: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published private(set) var activeVerse: Int?
    @Published private(set) var isLoading = false
    @Published var failed = false
    private var player: AVAudioPlayer?
    private var loading: Task<Void, Never>?
    private var sessionActive = false
    private var playbackFile: URL?

    func toggle(surah: Int, verse: Int, reciter: Reciter) {
        let cancel = activeVerse == verse
        stop()
        guard !cancel else { return }
        failed = false
        activeVerse = verse
        isLoading = true
        let url = reciter.audioURL(surah: surah, verse: verse)
        loading = Task {
            do {
                let (data, response) = try await URLSession.shared.data(from: url)
                try Task.checkCancellation()
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode)
                else { throw URLError(.badServerResponse) }
                let session = AVAudioSession.sharedInstance()
                try session.setCategory(.playback, mode: .spokenAudio)
                try session.setActive(true)
                sessionActive = true
                let audio: AVAudioPlayer
                if Self.needsLeadIn(session.currentRoute.outputs.map(\.portType)) {
                    let file = try await Self.makeHeadphoneAudio(data)
                    guard !Task.isCancelled else {
                        try? FileManager.default.removeItem(at: file)
                        return
                    }
                    playbackFile = file
                    audio = try AVAudioPlayer(contentsOf: file)
                } else {
                    audio = try AVAudioPlayer(data: data)
                }
                player = audio
                audio.delegate = self
                audio.currentTime = 0
                guard audio.prepareToPlay(), audio.play() else { throw URLError(.cannotDecodeContentData) }
                isLoading = false
            } catch {
                guard !Task.isCancelled else { return }
                stop()
                failed = true
            }
        }
    }

    static func needsLeadIn(_ ports: [AVAudioSession.Port]) -> Bool {
        ports.contains { [.headphones, .bluetoothA2DP, .bluetoothHFP, .bluetoothLE, .usbAudio].contains($0) }
    }

    // Silence must reach the headphones through the same stream as the verse:
    // waiting before play() would leave a sleeping audio output idle.
    nonisolated static func makeHeadphoneAudio(_ data: Data) async throws -> URL {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let source = base.appendingPathExtension("mp3")
        let output = base.appendingPathExtension("caf")
        defer { try? FileManager.default.removeItem(at: source) }
        do {
            try Task.checkCancellation()
            try data.write(to: source)
            let input = try AVAudioFile(forReading: source, commonFormat: .pcmFormatFloat32, interleaved: false)
            let format = input.processingFormat
            var diskFormat = format.settings
            diskFormat[AVLinearPCMIsNonInterleaved] = false
            let result = try AVAudioFile(forWriting: output, settings: diskFormat,
                                         commonFormat: .pcmFormatFloat32, interleaved: false)
            let frames = AVAudioFrameCount((format.sampleRate * 1.2).rounded())
            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: max(frames, 8192)),
                  let channels = buffer.floatChannelData else { throw URLError(.cannotDecodeContentData) }
            buffer.frameLength = frames
            for channel in 0..<Int(format.channelCount) {
                memset(channels[channel], 0, Int(frames) * MemoryLayout<Float>.size)
            }
            try result.write(from: buffer)
            while input.framePosition < input.length {
                try Task.checkCancellation()
                let count = AVAudioFrameCount(min(8192, input.length - input.framePosition))
                try input.read(into: buffer, frameCount: count)
                if buffer.frameLength == 0 { break }
                try result.write(from: buffer)
            }
            return output
        } catch {
            try? FileManager.default.removeItem(at: output)
            throw error
        }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ audio: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            guard self.player === audio else { return }
            self.stop()
            self.failed = !flag
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(_ audio: AVAudioPlayer, error: Error?) {
        audioPlayerDidFinishPlaying(audio, successfully: false)
    }

    nonisolated func audioPlayerBeginInterruption(_ audio: AVAudioPlayer) {
        audioPlayerDidFinishPlaying(audio, successfully: true)
    }

    func stop() {
        loading?.cancel()
        loading = nil
        player?.stop()
        player = nil
        if let playbackFile {
            try? FileManager.default.removeItem(at: playbackFile)
            self.playbackFile = nil
        }
        if sessionActive {
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            sessionActive = false
        }
        activeVerse = nil
        isLoading = false
    }
}
