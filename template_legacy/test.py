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


def _pass(name, detail=""):
    suffix = f" ({detail})" if detail else ""
    print(f"PASS  {name}{suffix}")


def _fail(name, exc):
    print(f"FAIL  {name}: {exc}")
    _FAILURES.append(name)


def test_inference_single():
    from inference import predict
    sample = [{"role": "user", "content": "Respond with exactly one short greeting."}]
    result = predict(sample, options={"max_new_tokens": 16, "temperature": 1.0})
    assert isinstance(result, str) and result.strip(), f"Unexpected result: {result!r}"
    _pass("test_inference_single", f"prediction={result}")


if __name__ == "__main__":
    tests = [
        test_inference_single,
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
