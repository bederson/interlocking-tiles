#!/usr/bin/env bash
# Start the tile design console server and open it in the browser.
# Usage: ./run.sh [port]

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${1:-8765}"
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}/"

python3 server.py --port "$PORT" --host "$HOST" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' EXIT

# Wait for the server to come up before opening the browser.
for _ in $(seq 1 50); do
  if curl -s -o /dev/null "$URL"; then
    break
  fi
  sleep 0.1
done

if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
else
  echo "Open $URL in your browser."
fi

wait "$SERVER_PID"
