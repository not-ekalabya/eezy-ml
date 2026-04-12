#!/bin/sh
set -eu

python /app/backend/src/local_server.py --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
backend_pid="$!"

cleanup() {
  kill "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd /app/client
exec npm run start -- --hostname "$HOSTNAME" --port "$PORT"
