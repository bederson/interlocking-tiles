#!/usr/bin/env bash
set -euo pipefail

# Builds TileConsole.app: compiles the Swift executable, then assembles a
# standard macOS app bundle and copies in the CURRENT web/, generate_tiles.py,
# and bridge.py from the repo root as bundled resources. This copy step is
# the "copy on build" mechanism that keeps the native app's UI and generator
# logic identical to the primary web/CLI source -- there is no hand-
# maintained duplicate of that code inside macos/ to drift out of sync.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACOS_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$MACOS_DIR")"
BUILD_DIR="$MACOS_DIR/build"
APP_NAME="TileConsole.app"
APP_DIR="$BUILD_DIR/$APP_NAME"

echo "Building Swift executable (release)..."
(cd "$MACOS_DIR" && swift build -c release)

BIN_PATH="$MACOS_DIR/.build/release/TileConsole"

echo "Assembling $APP_NAME..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/TileConsole"
cp "$MACOS_DIR/Info.plist" "$APP_DIR/Contents/Info.plist"

echo "Copying shared web/ + generator sources from $REPO_ROOT into Resources..."
cp -R "$REPO_ROOT/web" "$APP_DIR/Contents/Resources/web"
cp "$REPO_ROOT/generate_tiles.py" "$APP_DIR/Contents/Resources/generate_tiles.py"
cp "$REPO_ROOT/bridge.py" "$APP_DIR/Contents/Resources/bridge.py"

echo ""
echo "Built: $APP_DIR"
echo "Run with: open \"$APP_DIR\""
