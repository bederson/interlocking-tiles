# Interlocking Tiles — native macOS app

A native macOS wrapper around the same design console as the web version —
one window, no local web server, a standard double-clickable `.app`. It
uses the identical `web/` HTML/CSS/JS and the identical `generate_tiles.py`
generator as the web console; nothing here is a hand-maintained duplicate.

## How it works

- `Sources/InterlockingTiles/main.swift` is a small AppKit app that opens one
  `WKWebView` loading `web/index.html` straight off disk (`file://`, no
  server).
- The web UI's "Export design" button already knows how to call either a
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
- The output folder isn't user-set in the UI at all (see the web console's
  own "Export design" button/subtitle) — `generate_tiles.py`'s own
  `default_output_dir()` resolves to `~/Documents/Interlocking Tile
  Output/<timestamp>`, a fixed, writable location, unlike the read-only
  app bundle.
- `Sources/InterlockingTiles/main.swift` builds a minimal app menu by hand (no
  `.xib`/storyboard) so Cmd+Q and the menu-bar Quit item work normally.

## Building

```
./Scripts/build_app.sh
```

This compiles the Swift executable (`swift build -c release`) and then
assembles `"build/Interlocking Tiles.app"`, copying:

- the **current** `web/`, `generate_tiles.py`, and `bridge.py` from the
  repo root into the bundle's `Contents/Resources/` — this copy step is
  the "sync" mechanism: edit the shared web/Python source, rerun this
  script, and the app picks up the change. There's no separate copy of
  that logic checked in under `macos/`.
- `Resources/AppIcon.icns` (checked into this directory) as the app icon.
- a small standalone Python runtime into `Contents/Resources/python/`
  (downloaded once from
  [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  and cached in `.cache/`, ~25MB), so the app works even on a Mac with no
  Python installed. `main.swift` prefers this bundled interpreter and
  falls back to the system `python3` if it's missing. Set
  `SKIP_PYTHON_BUNDLE=1 ./Scripts/build_app.sh` to skip downloading it for
  a faster dev-only build.

Run it with:

```
open "build/Interlocking Tiles.app"
```

## Requirements

- Xcode/Swift toolchain (for building) — tested with Swift 6.
- Network access the first time you build (to download the bundled Python
  runtime; cached after that). Not needed at all with
  `SKIP_PYTHON_BUNDLE=1`, as long as the target Mac has its own `python3`.
- macOS 12+.
- The bundled Python runtime is built for Apple Silicon (arm64) Macs. On
  an Intel Mac, `SKIP_PYTHON_BUNDLE=1` and rely on the system `python3`
  instead, or swap `PYTHON_ARCHIVE` in `Scripts/build_app.sh` for an
  `x86_64-apple-darwin` build.

## What's not done

- No code signing / notarization — this is a local dev build, not a
  distributable release.
