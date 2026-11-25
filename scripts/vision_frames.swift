// Apple Vision on still frames: face boxes + on-screen text, one JSON line per image.
// Usage: swift scripts/vision_frames.swift a.jpg b.jpg ...
import Foundation
import Vision

for path in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: path)
    let faces = VNDetectFaceRectanglesRequest()
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.usesLanguageCorrection = false  // handles like @mike_dalton_art must stay literal
    var out: [String: Any] = ["path": path]
    do {
        try VNImageRequestHandler(url: url).perform([faces, text])
        // Vision boxes are normalized with origin bottom-left; flip y to top-left.
        out["faces"] = (faces.results ?? []).map { f in
            let b = f.boundingBox
            return [b.minX, 1 - b.maxY, b.width, b.height].map { ($0 * 1000).rounded() / 1000 }
        }
        out["text"] = (text.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    } catch {
        out["error"] = "\(error)"
    }
    let data = try! JSONSerialization.data(withJSONObject: out)
    print(String(data: data, encoding: .utf8)!)
}
