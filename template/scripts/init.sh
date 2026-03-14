#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

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

echo "=== Waiting for server to start ==="
sleep 5

echo "=== Querying /health ==="
curl -s http://localhost:5000/health
echo ""

echo "=== Server is running (PID: $SERVER_PID) ==="
wait $SERVER_PID