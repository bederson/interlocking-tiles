#!/usr/bin/env python3
"""Subprocess bridge for the native macOS app.

The web console (server.py) and the native app both need to call
generate_tiles.generate_batch() and get the same JSON summary back; the web
console does that over HTTP, the native app has no server (by design) and
instead runs this script once per export, piping the params in as JSON on
stdin and reading the JSON summary back on stdout.

Usage: python3 bridge.py < params.json > result.json
"""

import json
import sys

import generate_tiles


def main():
    params = json.loads(sys.stdin.read() or "{}")
    try:
        summary = generate_tiles.generate_batch(params)
        response = {"ok": True}
        response.update({k: summary[k] for k in generate_tiles.EXPORT_RESPONSE_FIELDS})
    except Exception as exc:  # surface the error to the app UI, don't crash
        response = {"ok": False, "error": str(exc)}
    json.dump(response, sys.stdout)


if __name__ == "__main__":
    main()
