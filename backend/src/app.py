"""app.py — Lambda handler for eezy-ml backend API.

All business endpoints were intentionally removed; the file keeps the
startup/boilerplate structure so new routes can be added later.
"""

import json


def handler(event, context):
    # Skeleton handler left in place for future routes.
    return _ok({
        "status": "stub",
        "message": "eezy-ml backend starter ready; no endpoints are active.",
        "input_path": event.get("path", ""),
        "input_method": event.get("httpMethod", "GET"),
    })


def _ok(body, code=200):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def _err(code, message):
    return _ok({"error": message}, code)
