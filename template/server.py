"""server.py — Flask HTTP server exposing an inference endpoint.

Usage:
    python server.py

Endpoints:
    GET  /health          Returns {"status": "ok"} if the service is running.
    POST /predict         Accepts JSON and returns model predictions.

Request body for /predict:
    Message list:   {"features": [{"role": "user", "content": "prompt"}], "max_new_tokens": 96}
    Batch list:     {"features": [[{"role": "user", "content": "prompt 1"}], [{"role": "user", "content": "prompt 2"}]], "temperature": 0.7}
"""

import os
import subprocess
import sys

from flask import Flask, request, jsonify
from inference import load_model, predict, predict_batch

app = Flask(__name__)


def _is_batch_payload(features):
    if not isinstance(features, list) or not features:
        return False
    if all(isinstance(item, dict) for item in features):
        return False
    return any(isinstance(item, list) for item in features)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok - real-time logging <test-6>!"})


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
    options = {
        key: body[key]
        for key in ("max_new_tokens", "temperature", "top_p", "enable_thinking")
        if key in body
    }

    try:
        if _is_batch_payload(features):
            predictions = predict_batch(features, options=options)
            return jsonify({"predictions": predictions})
        else:
            prediction = predict(features, options=options)
            return jsonify({"prediction": prediction})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 422


if __name__ == "__main__":
    try:
        load_model()
    except FileNotFoundError:
        pass

    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", 5000))
    app.run(host=host, port=port, threaded=True)
