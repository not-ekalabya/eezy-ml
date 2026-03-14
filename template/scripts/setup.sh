#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

MODEL_PATH="model/model.joblib"
DATA_DIR="data"

validate_model() {
    if [ ! -f "$MODEL_PATH" ]; then
        return 1
    fi

    python -c "import joblib; m=joblib.load('$MODEL_PATH'); raise SystemExit(0 if m.named_steps['scaler'].n_features_in_ == 784 else 1)"
}

rebuild_model() {
    echo "=== Rebuilding MNIST model ==="
    rm -f "$MODEL_PATH"
    mkdir -p "$DATA_DIR" "$(dirname "$MODEL_PATH")"
    python init.py
}

# If the virtual environment already exists, skip the full system setup and just
# update the installed packages, repair the model if needed, then restart the server.
if [ -d "venv" ]; then
    echo "=== Environment already set up - updating ==="

    echo "=== Activating virtual environment ==="
    source venv/bin/activate

    echo "=== Updating requirements ==="
    pip install --upgrade pip
    pip install -r requirements.txt

    if validate_model; then
        echo "=== Existing model is compatible ==="
    else
        rebuild_model
    fi

    echo "=== Stopping existing server (if running) ==="
    pkill -f "python server.py" || true

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
    exit 0
fi

echo "=== Updating package index ==="
sudo apt-get update

echo "=== Installing Python and pip ==="
sudo apt-get install -y python3 python3-pip python3-venv curl

echo "=== Setting up swap space to prevent OOM kills ==="
if [ ! -f /swapfile ]; then
    # Work in GiB to avoid allocating petabyte-sized swap due to unit mistakes.
    FREE_GB=$(df -B1 / | awk 'NR==2 {printf "%.0f", $4/1024/1024/1024}')
    SWAP_SIZE=$(( FREE_GB * 9 / 10 ))
    # Keep swap within sane bounds: min 1 GiB, max 8 GiB.
    if [ "$SWAP_SIZE" -lt 1 ]; then SWAP_SIZE=1; fi
    if [ "$SWAP_SIZE" -gt 8 ]; then SWAP_SIZE=8; fi

    echo "Free storage: ${FREE_GB}GB, allocating ${SWAP_SIZE}GB for swap (90% capped at 8GB)"
    sudo fallocate -l ${SWAP_SIZE}G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1G count=${SWAP_SIZE}
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab
    echo "Swap space created and enabled"
else
    echo "Swap space already exists"
fi

echo "=== Creating virtual environment ==="
python3 -m venv venv
source venv/bin/activate

echo "=== Installing requirements ==="
pip install --upgrade pip
pip install -r requirements.txt

rebuild_model

echo "=== Starting server in background ==="
nohup python server.py > server.log 2>&1 &
SERVER_PID=$!

echo "=== Waiting for server to start ==="
sleep 5

echo "=== Querying /health ==="
curl -s http://localhost:5000/health
echo ""

echo "=== Querying /test ==="
curl -s http://localhost:5000/test
echo ""

echo "=== Server is running (PID: $SERVER_PID) ==="
wait $SERVER_PID