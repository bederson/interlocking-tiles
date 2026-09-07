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

enum InterlockingTilesError: LocalizedError {
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

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = Self.buildMainMenu()

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

        // WKWebView's default data store persists its disk/memory cache of
        // file:// resources on disk across separate app launches (keyed by
        // this app's bundle identifier), so a rebuilt app can otherwise
        // still serve stale HTML/CSS/JS from a previous run at the same
        // on-disk path. Clear just those caches -- not localStorage, which
        // intentionally persists control panel values across launches (see
        // web/app.js's PERSISTED_FIELD_IDS) -- before every load. The
        // bigger risk in practice is a *still-running* previous instance,
        // which "open" just re-activates instead of launching a fresh
        // process at all -- see build_app.sh's pkill step for that case.
        let cacheTypes: Set<String> = [
            WKWebsiteDataTypeDiskCache,
            WKWebsiteDataTypeMemoryCache,
            WKWebsiteDataTypeOfflineWebApplicationCache,
        ]
        webView.configuration.websiteDataStore.removeData(ofTypes: cacheTypes, modifiedSince: .distantPast) {
            webView.loadFileURL(indexURL, allowingReadAccessTo: resourceURL)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    /// A minimal app menu (no .xib/storyboard here) so Cmd+Q -- and the
    /// dock/menu-bar Quit item -- work like any normal Mac app.
    private static func buildMainMenu() -> NSMenu {
        let mainMenu = NSMenu()

        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)
        let appMenu = NSMenu()
        appMenuItem.submenu = appMenu

        let appName = Bundle.main.infoDictionary?["CFBundleName"] as? String ?? "Interlocking Tiles"
        let quitItem = NSMenuItem(
            title: "Quit \(appName)",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        quitItem.target = NSApp
        appMenu.addItem(quitItem)

        return mainMenu
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
                // No output_dir override needed here: generate_tiles.py's own
                // default_output_dir() already resolves to a fixed, writable
                // ~/Documents location when the UI leaves it blank.
                let inputData = try JSONSerialization.data(withJSONObject: params)

                guard let resourceURL = Bundle.main.resourceURL else {
                    throw InterlockingTilesError.message("missing app resources")
                }
                let bridgeURL = resourceURL.appendingPathComponent("bridge.py")

                // Prefer the Python runtime bundled by Scripts/build_app.sh
                // (so the app works out of the box on a Mac with no Python
                // installed); fall back to the system python3 if the bundle
                // was built without it (e.g. a quick dev build).
                let bundledPython = resourceURL.appendingPathComponent("python/bin/python3")
                let process = Process()
                if FileManager.default.isExecutableFile(atPath: bundledPython.path) {
                    process.executableURL = bundledPython
                    process.arguments = [bridgeURL.path]
                } else {
                    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
                    process.arguments = ["python3", bridgeURL.path]
                }
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
                    throw InterlockingTilesError.message("export failed: \(errText)")
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
