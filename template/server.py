"""server.py — Flask HTTP server exposing an inference endpoint.

Usage:
    python server.py

Endpoints:
    GET  /health          Returns {"status": "ok"} if the service is running.
    POST /predict         Accepts JSON and returns model predictions.

Request body for /predict:
    Single sample:  {"features": [<784 floats>]}
    Batch:          {"features": [[<784 floats>], ...]}
"""

import os
import subprocess
import sys

from flask import Flask, request, jsonify
from inference import predict, predict_batch

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/test", methods=["GET"])
def run_tests():
    test_script = os.path.join(os.path.dirname(__file__), "test.py")
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = os.environ.get("SERVER_PORT", "5000")
    server_url = f"http://127.0.0.1:{port}"

    env = {**os.environ, "SERVER_URL": server_url}
    result = subprocess.run(
        [sys.executable, test_script],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=os.path.dirname(__file__),
    )
    output = result.stdout + result.stderr
    passed = result.returncode == 0
    return jsonify({"passed": passed, "returncode": result.returncode, "output": output})


@app.route("/predict", methods=["POST"])
def predict_endpoint():
    body = request.get_json(force=True, silent=True)
    if not body or "features" not in body:
        return jsonify({"error": "Request body must be JSON with a 'features' field."}), 400

    features = body["features"]

    try:
        if features and isinstance(features[0], list):
            predictions = predict_batch(features)
            return jsonify({"predictions": predictions})
        else:
            prediction = predict(features)
            return jsonify({"prediction": prediction})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 422


if __name__ == "__main__":
    import os
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", 5000))
    app.run(host=host, port=port, threaded=True)
