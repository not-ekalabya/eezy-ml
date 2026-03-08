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

from flask import Flask, request, jsonify
from inference import predict, predict_batch

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


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
    app.run(host="0.0.0.0", port=5000)
