#!/usr/bin/env bash
set -euo pipefail

# Builds "Interlocking Tiles.app": compiles the Swift executable, then assembles a
# standard macOS app bundle and copies in the CURRENT web/, generate_tiles.py,
# and bridge.py from the repo root as bundled resources. This copy step is
# the "copy on build" mechanism that keeps the native app's UI and generator
# logic identical to the primary web/CLI source -- there is no hand-
# maintained duplicate of that code inside macos/ to drift out of sync.

# Bundled Python runtime (so the app works on a Mac with no Python
# installed) -- a small standalone CPython build from astral-sh/
# python-build-standalone, the smallest ("install_only_stripped") variant.
# Set SKIP_PYTHON_BUNDLE=1 to skip this for a faster dev-only build (the
# app then falls back to the system python3 at run time, see main.swift).
PYTHON_BUILD_TAG="20260901"
PYTHON_VERSION="3.12.14"
PYTHON_ARCHIVE="cpython-${PYTHON_VERSION}+${PYTHON_BUILD_TAG}-aarch64-apple-darwin-install_only_stripped.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD_TAG}/${PYTHON_ARCHIVE}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACOS_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$MACOS_DIR")"
BUILD_DIR="$MACOS_DIR/build"
CACHE_DIR="$MACOS_DIR/.cache"
APP_NAME="Interlocking Tiles.app"
APP_DIR="$BUILD_DIR/$APP_NAME"

echo "Building Swift executable (release)..."
(cd "$MACOS_DIR" && swift build -c release)

BIN_PATH="$MACOS_DIR/.build/release/InterlockingTiles"

echo "Assembling $APP_NAME..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/InterlockingTiles"
cp "$MACOS_DIR/Info.plist" "$APP_DIR/Contents/Info.plist"
if [ -f "$MACOS_DIR/Resources/AppIcon.icns" ]; then
    cp "$MACOS_DIR/Resources/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
fi

echo "Copying shared web/ + generator sources from $REPO_ROOT into Resources..."
cp -R "$REPO_ROOT/web" "$APP_DIR/Contents/Resources/web"
cp "$REPO_ROOT/generate_tiles.py" "$APP_DIR/Contents/Resources/generate_tiles.py"
cp "$REPO_ROOT/bridge.py" "$APP_DIR/Contents/Resources/bridge.py"

if [ "${SKIP_PYTHON_BUNDLE:-0}" = "1" ]; then
    echo "SKIP_PYTHON_BUNDLE=1 set -- not bundling Python (will use system python3 at run time)."
else
    mkdir -p "$CACHE_DIR"
    if [ ! -f "$CACHE_DIR/$PYTHON_ARCHIVE" ]; then
        echo "Downloading bundled Python runtime ($PYTHON_ARCHIVE, ~25MB)..."
        curl -fsSL -o "$CACHE_DIR/$PYTHON_ARCHIVE.tmp" "$PYTHON_URL"
        mv "$CACHE_DIR/$PYTHON_ARCHIVE.tmp" "$CACHE_DIR/$PYTHON_ARCHIVE"
    fi
    echo "Bundling Python runtime into Resources/python..."
    tar xzf "$CACHE_DIR/$PYTHON_ARCHIVE" -C "$APP_DIR/Contents/Resources"
fi

echo ""
echo "Built: $APP_DIR"
echo "Run with: open \"$APP_DIR\""
