// Native macOS shell for the tile design console: a single window holding
// the same web/ UI as the local web console, but with no HTTP server. The
// "Export to disk" button's request is bridged straight to a Python
// subprocess (bridge.py, wrapping generate_tiles.generate_batch()) via a
// WKScriptMessageHandlerWithReply -- see exportRequest() in web/app.js for
// the JS side of this branch. web/, generate_tiles.py, and bridge.py are
// bundled into this app's Resources at build time (Scripts/build_app.sh),
// not duplicated here, so both front ends always run identical logic.

import AppKit
import WebKit

enum TileConsoleError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        switch self {
        case .message(let text): return text
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandlerWithReply {
    private var window: NSWindow!
    private var webView: WKWebView!

    private static let timestampFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        return formatter
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let contentController = WKUserContentController()
        contentController.addScriptMessageHandler(self, contentWorld: .page, name: "export")

        let config = WKWebViewConfiguration()
        config.userContentController = contentController

        let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 1100, height: 820), configuration: config)
        self.webView = webView

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1100, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Interlocking Tiles"
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        self.window = window

        NSApp.activate(ignoringOtherApps: true)

        guard let resourceURL = Bundle.main.resourceURL else {
            fatalError("Missing app resources -- was this run from a properly built .app bundle?")
        }
        let indexURL = resourceURL.appendingPathComponent("web/index.html")
        webView.loadFileURL(indexURL, allowingReadAccessTo: resourceURL)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage,
        replyHandler: @escaping (Any?, String?) -> Void
    ) {
        guard message.name == "export" else {
            replyHandler(nil, "unknown message: \(message.name)")
            return
        }
        guard let params = message.body as? [String: Any] else {
            replyHandler(nil, "invalid export payload")
            return
        }
        runExport(params: params, replyHandler: replyHandler)
    }

    /// Shells out to bridge.py (which calls generate_tiles.generate_batch()
    /// unchanged) and relays its JSON result back as the resolved value of
    /// the JS promise from `window.webkit.messageHandlers.export.postMessage(...)`.
    private func runExport(params: [String: Any], replyHandler: @escaping (Any?, String?) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                var effectiveParams = params
                let hasOutputDir = (effectiveParams["output_dir"] as? String).map { !$0.isEmpty } ?? false
                if !hasOutputDir {
                    // The web console defaults to a folder next to the script; there's
                    // no equivalent inside a read-only app bundle, so default to
                    // ~/Documents instead of whatever the process's CWD happens to be.
                    let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
                        ?? FileManager.default.homeDirectoryForCurrentUser
                    let stamp = Self.timestampFormatter.string(from: Date())
                    effectiveParams["output_dir"] = docs.appendingPathComponent("TileConsole/output/\(stamp)").path
                }

                let inputData = try JSONSerialization.data(withJSONObject: effectiveParams)

                guard let resourceURL = Bundle.main.resourceURL else {
                    throw TileConsoleError.message("missing app resources")
                }
                let bridgeURL = resourceURL.appendingPathComponent("bridge.py")

                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
                process.arguments = ["python3", bridgeURL.path]
                process.currentDirectoryURL = resourceURL

                let stdinPipe = Pipe()
                let stdoutPipe = Pipe()
                let stderrPipe = Pipe()
                process.standardInput = stdinPipe
                process.standardOutput = stdoutPipe
                process.standardError = stderrPipe

                try process.run()
                stdinPipe.fileHandleForWriting.write(inputData)
                stdinPipe.fileHandleForWriting.closeFile()

                // Drain stdout/stderr concurrently while waiting for exit --
                // reading them sequentially after waitUntilExit() can deadlock
                // if either pipe's buffer fills before the process exits.
                var stdoutData = Data()
                var stderrData = Data()
                let group = DispatchGroup()
                group.enter()
                DispatchQueue.global(qos: .userInitiated).async {
                    stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
                    group.leave()
                }
                group.enter()
                DispatchQueue.global(qos: .userInitiated).async {
                    stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
                    group.leave()
                }
                process.waitUntilExit()
                group.wait()

                if stdoutData.isEmpty {
                    let errText = String(data: stderrData, encoding: .utf8) ?? "unknown error"
                    throw TileConsoleError.message("export failed: \(errText)")
                }
                let result = try JSONSerialization.jsonObject(with: stdoutData)
                DispatchQueue.main.async { replyHandler(result, nil) }
            } catch {
                DispatchQueue.main.async { replyHandler(nil, error.localizedDescription) }
            }
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
