#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

wait_for_health() {
	local server_pid="$1"
	local timeout_seconds="${HEALTH_CHECK_TIMEOUT_SECONDS:-60}"
	local interval_seconds=2
	local max_attempts=$((timeout_seconds / interval_seconds))

	if [ "$max_attempts" -lt 1 ]; then
		max_attempts=1
	fi

	echo "=== Waiting for server health (timeout: ${timeout_seconds}s) ==="
	local attempt=1
	while [ "$attempt" -le "$max_attempts" ]; do
		if curl -fsS http://127.0.0.1:5000/health > /dev/null; then
			echo "=== Querying /health ==="
			curl -fsS http://127.0.0.1:5000/health
			echo ""
			return 0
		fi

		if ! kill -0 "$server_pid" 2>/dev/null; then
			echo "Server process exited before health check passed." >&2
			echo "=== Last 200 lines of server.log ===" >&2
			tail -n 200 server.log >&2 || true
			return 1
		fi

		sleep "$interval_seconds"
		attempt=$((attempt + 1))
	done

	echo "Health check timed out after ${timeout_seconds}s." >&2
	echo "=== Last 200 lines of server.log ===" >&2
	tail -n 200 server.log >&2 || true
	return 1
}

echo "=== Clearing project model and data directories ==="
rm -f model/model.joblib
mkdir -p data model

echo "=== Activating virtual environment ==="
source venv/bin/activate

echo "=== Stopping existing server (if running) ==="
pkill -f "python server.py" || true

echo "=== Running init.py ==="
nohup python init.py > init.log 2>&1 &
INIT_PID=$!
wait $INIT_PID

echo "=== Starting server in background ==="
nohup python server.py > server.log 2>&1 &
SERVER_PID=$!

wait_for_health "$SERVER_PID"

echo "=== Server is running (PID: $SERVER_PID) ==="
wait $SERVER_PID