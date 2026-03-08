"""test.py — Integration tests for the MNIST ML service.

Run with the server already started in a separate process:
    python server.py &
    python test.py
"""

import os
import sys
import numpy as np
import requests

BASE_URL = os.environ.get("SERVER_URL", "http://localhost:5000")
_FAILURES = []


def _pass(name, detail=""):
    suffix = f" ({detail})" if detail else ""
    print(f"PASS  {name}{suffix}")


def _fail(name, exc):
    print(f"FAIL  {name}: {exc}")
    _FAILURES.append(name)


def test_model_file_exists():
    model_path = os.path.join(os.path.dirname(__file__), "model", "model.joblib")
    assert os.path.exists(model_path), f"Model not found at '{model_path}'. Run init.py first."
    _pass("test_model_file_exists")


def test_inference_single():
    from inference import predict
    sample = np.zeros(784).tolist()
    result = predict(sample)
    assert result.isdigit() and 0 <= int(result) <= 9, f"Unexpected result: {result!r}"
    _pass("test_inference_single", f"prediction={result}")


def test_inference_batch():
    from inference import predict_batch
    samples = [np.zeros(784).tolist() for _ in range(4)]
    results = predict_batch(samples)
    assert len(results) == 4
    assert all(r.isdigit() for r in results)
    _pass("test_inference_batch", f"predictions={results}")


def test_server_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    _pass("test_server_health")


def test_server_predict_single():
    sample = np.zeros(784).tolist()
    resp = requests.post(f"{BASE_URL}/predict", json={"features": sample}, timeout=5)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "prediction" in body and body["prediction"].isdigit()
    _pass("test_server_predict_single", f"prediction={body['prediction']}")


def test_server_predict_batch():
    samples = [np.zeros(784).tolist() for _ in range(3)]
    resp = requests.post(f"{BASE_URL}/predict", json={"features": samples}, timeout=5)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "predictions" in body and len(body["predictions"]) == 3
    _pass("test_server_predict_batch", f"predictions={body['predictions']}")


def test_server_bad_request():
    resp = requests.post(f"{BASE_URL}/predict", json={}, timeout=5)
    assert resp.status_code == 400
    _pass("test_server_bad_request")


if __name__ == "__main__":
    tests = [
        test_model_file_exists,
        test_inference_single,
        test_inference_batch,
        test_server_health,
        test_server_predict_single,
        test_server_predict_batch,
        test_server_bad_request,
    ]

    print(f"Running {len(tests)} tests against {BASE_URL}\n")
    for t in tests:
        try:
            t()
        except Exception as exc:
            _fail(t.__name__, exc)

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)}/{len(tests)} tests FAILED: {', '.join(_FAILURES)}")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed.")
