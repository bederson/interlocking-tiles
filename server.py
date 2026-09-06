#!/usr/bin/env python3
"""Local web server for the tile design console.

Serves the static page in web/ and exposes POST /api/export, which calls
generate_tiles.generate_batch() -- the exact same code path the CLI uses --
so files written from the browser are identical in behavior to the CLI.

Usage: python3 server.py [--port 8765] [--host 127.0.0.1]
"""

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import generate_tiles

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console quiet; errors are still sent to the client

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
        path = path.split("?", 1)[0]
        file_path = (WEB_DIR / path).resolve()

        if WEB_DIR not in file_path.parents and file_path != WEB_DIR:
            self.send_error(403, "Forbidden")
            return
        if not file_path.is_file():
            self.send_error(404, "Not found")
            return

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/export":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            params = json.loads(self.rfile.read(length) or b"{}")
            summary = generate_tiles.generate_batch(params)
            response = {"ok": True}
            response.update({k: summary[k] for k in generate_tiles.EXPORT_RESPONSE_FIELDS})
            self._send_json(200, response)
        except Exception as exc:  # local dev tool: surface the error to the browser, don't crash the server
            self._send_json(400, {"ok": False, "error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    os.chdir(BASE_DIR)  # so relative --output-dir / "output" lands next to the script, like the CLI
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Tile design console: http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
