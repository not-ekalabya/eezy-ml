"""app.py — Lambda handler for eezy-ml backend API.

Endpoints
---------
GET  /health                Health check.
POST /deploy                Launch an EC2 instance running a containerised ML model.
GET  /instances             List all eezy-ml instances.
GET  /status/{id}           Instance + service status.
POST /predict/{id}          Proxy an inference request to the instance.
DELETE /terminate/{id}      Terminate an instance.
"""

import json
import re

from utils import (
    deploy_instance,
    get_instance_status,
    list_instances,
    terminate_instance,
    proxy_predict,
)

_PATH_WITH_ID = re.compile(r"^/(status|predict|terminate)/(i-[a-f0-9]{8,17})$")


def handler(event, context):
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")

    # --- Health ---
    if path == "/health" and method == "GET":
        return _ok({"status": "ok"})

    # --- Debug (local dev only) ---
    if path == "/debug/env" and method == "GET":
        import os
        return _ok({
            "AWS_ACCESS_KEY_ID":     "set" if os.environ.get("AWS_ACCESS_KEY_ID") else "missing",
            "AWS_SECRET_ACCESS_KEY": "set" if os.environ.get("AWS_SECRET_ACCESS_KEY") else "missing",
            "AWS_DEFAULT_REGION":    os.environ.get("AWS_DEFAULT_REGION", "missing"),
            "AWS_SESSION_TOKEN":     "set" if os.environ.get("AWS_SESSION_TOKEN") else "missing",
            "GH_PAT":                "set" if os.environ.get("GH_PAT") else "missing",
        })

    # --- Deploy ---
    if path == "/deploy" and method == "POST":
        return _handle_deploy(event)

    # --- List instances ---
    if path == "/instances" and method == "GET":
        return _safe(list_instances)

    # --- Routes with instance_id ---
    m = _PATH_WITH_ID.match(path)
    if m:
        action, instance_id = m.group(1), m.group(2)

        if action == "status" and method == "GET":
            return _safe(get_instance_status, instance_id)

        if action == "predict" and method == "POST":
            body = _parse_body(event)
            if isinstance(body, dict) and "error" not in body:
                return _safe(proxy_predict, instance_id, body)
            return _err(400, "Request body must be valid JSON")

        if action == "terminate" and method == "DELETE":
            return _safe(terminate_instance, instance_id)

    return _err(404, "Not found")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _handle_deploy(event):
    body = _parse_body(event)
    if body is None:
        return _err(400, "Request body must be valid JSON")

    repo_url = body.get("repo_url")
    if not repo_url:
        return _err(400, "repo_url is required")

    instance_type = body.get("instance_type", "t3.medium")

    try:
        result = deploy_instance(repo_url, instance_type)
        return _ok(result)
    except ValueError as e:
        return _err(400, str(e))
    except Exception as e:
        return _err(500, str(e))


def _parse_body(event):
    try:
        return json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None


def _safe(fn, *args, **kwargs):
    try:
        return _ok(fn(*args, **kwargs))
    except ValueError as e:
        return _err(400, str(e))
    except Exception as e:
        return _err(500, str(e))


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