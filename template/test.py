"""test.py — Integration tests for the Qwen inference service.

Run with the server already started in a separate process:
    python server.py &
    python test.py
"""

import os
import sys
import requests

BASE_URL = os.environ.get("SERVER_URL", "http://localhost:5000")
_FAILURES = []

PREDICTION_TIMEOUT = 1e10  # seconds


def _pass(name, detail=""):
    suffix = f" ({detail})" if detail else ""
    print(f"PASS  {name}{suffix}")


def _fail(name, exc):
    print(f"FAIL  {name}: {exc}")
    _FAILURES.append(name)


def test_model_file_exists():
    model_ready = os.path.join(os.path.dirname(__file__), "model", "model.ready")
    model_dir = os.path.join(os.path.dirname(__file__), "model", "qwen3-8b")
    assert os.path.exists(model_ready), f"Model marker not found at '{model_ready}'. Run init.py first."
    assert os.path.isdir(model_dir), f"Model cache not found at '{model_dir}'. Run init.py first."
    _pass("test_model_file_exists")


def test_inference_single():
    from inference import predict
    sample = [{"role": "user", "content": "Respond with exactly one short greeting."}]
    result = predict(sample)
    assert isinstance(result, str) and result.strip(), f"Unexpected result: {result!r}"
    _pass("test_inference_single", f"prediction={result}")


def test_inference_batch():
    from inference import predict_batch
    samples = [
        [{"role": "user", "content": "Return only the word alpha."}],
        [{"role": "user", "content": "Return only the word beta."}],
        [{"role": "user", "content": "Return only the word gamma."}],
        [{"role": "user", "content": "Return only the word delta."}],
    ]
    results = predict_batch(samples)
    assert len(results) == 4
    assert all(isinstance(r, str) and r.strip() for r in results)
    _pass("test_inference_batch", f"predictions={results}")


def test_inference_rejects_invalid_generation_options():
    from inference import predict
    try:
        predict([{"role": "user", "content": "Return the word test."}], options={"top_p": 2})
    except ValueError as exc:
        assert "top_p" in str(exc)
        _pass("test_inference_rejects_invalid_generation_options")
        return
    raise AssertionError("predict accepted invalid generation options")


def test_server_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok - real-time logging <test-6>!"
    _pass("test_server_health")


def test_server_predict_single():
    sample = [{"role": "user", "content": "Answer with one short sentence about deployment."}]
    resp = requests.post(f"{BASE_URL}/predict", json={"features": sample}, timeout=PREDICTION_TIMEOUT)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "prediction" in body and isinstance(body["prediction"], str) and body["prediction"].strip()
    _pass("test_server_predict_single", f"prediction={body['prediction']}")


def test_server_predict_batch():
    samples = [
        [{"role": "user", "content": "Return the word one."}],
        [{"role": "user", "content": "Return the word two."}],
        [{"role": "user", "content": "Return the word three."}],
    ]
    resp = requests.post(f"{BASE_URL}/predict", json={"features": samples}, timeout=PREDICTION_TIMEOUT)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "predictions" in body and len(body["predictions"]) == 3
    assert all(isinstance(r, str) and r.strip() for r in body["predictions"])
    _pass("test_server_predict_batch", f"predictions={body['predictions']}")


def test_server_predict_accepts_generation_options():
    payload = {
        "features": [{"role": "user", "content": "Return one short line about inference."}],
        "max_new_tokens": 24,
        "temperature": 0.2,
        "top_p": 0.8,
        "enable_thinking": False,
    }
    resp = requests.post(f"{BASE_URL}/predict", json=payload, timeout=PREDICTION_TIMEOUT)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "prediction" in body and isinstance(body["prediction"], str) and body["prediction"].strip()
    _pass("test_server_predict_accepts_generation_options", f"prediction={body['prediction']}")


def test_server_bad_request():
    resp = requests.post(f"{BASE_URL}/predict", json={}, timeout=PREDICTION_TIMEOUT)
    assert resp.status_code == 400
    _pass("test_server_bad_request")


if __name__ == "__main__":
    tests = [
        test_model_file_exists,
        test_inference_single,
        test_inference_batch,
        test_inference_rejects_invalid_generation_options,
        test_server_health,
        test_server_predict_single,
        test_server_predict_batch,
        test_server_predict_accepts_generation_options,
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
