# Interlocking Tiles — native macOS app

A native macOS wrapper around the same design console as the web version —
one window, no local web server, a standard double-clickable `.app`. It
uses the identical `web/` HTML/CSS/JS and the identical `generate_tiles.py`
generator as the web console; nothing here is a hand-maintained duplicate.

## How it works

- `Sources/TileConsole/main.swift` is a small AppKit app that opens one
  `WKWebView` loading `web/index.html` straight off disk (`file://`, no
  server).
- The web UI's "Export to disk" button already knows how to call either a
  local HTTP server or a native bridge (see `exportRequest()` in
  `web/app.js`) — in this app, `window.webkit.messageHandlers.export` is
  registered as a `WKScriptMessageHandlerWithReply`, so the same
  `await exportRequest(payload)` call in the shared JS resolves here
  without ever doing a network request.
- On the Swift side, that message runs `bridge.py` (repo root) as a
  subprocess, piping the export params in as JSON on stdin and reading the
  JSON result back on stdout. `bridge.py` just calls
  `generate_tiles.generate_batch()` — the exact same function the CLI and
  the web server call — so behavior is identical across all three front
  ends.
- If no output folder was set in the UI, the app defaults to
  `~/Documents/TileConsole/output/<timestamp>` instead of a path relative
  to the app bundle (which is read-only once built).

## Building

```
./Scripts/build_app.sh
```

This compiles the Swift executable (`swift build -c release`) and then
assembles `build/TileConsole.app`, copying the **current** `web/`,
`generate_tiles.py`, and `bridge.py` from the repo root into the bundle's
`Contents/Resources/` — this copy step is the "sync" mechanism: edit the
shared web/Python source, rerun this script, and the app picks up the
change. There's no separate copy of that logic checked in under `macos/`.

Run it with:

```
open build/TileConsole.app
```

## Requirements

- Xcode/Swift toolchain (for building) — tested with Swift 6.
- A `python3` on the machine's `PATH` at runtime (the app shells out to
  it; nothing bundles its own Python interpreter). Fine for local/personal
  use; a distributable build for other people's Macs would need to embed a
  Python runtime instead of relying on the system one.
- macOS 12+.

## What's not done

- No code signing / notarization — this is a local dev build, not a
  distributable release.
- No app icon.
- No embedded Python — see "Requirements" above.
