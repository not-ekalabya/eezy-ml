"""app.py - Lambda handler for eezy-ml backend API.

This version exposes project management endpoints backed by DynamoDB.
Only the project-manager routes are enabled; EC2 inference endpoints were
removed.
"""

import json
import re
import time

from utils import (
    create_project,
    auto_create_project,
    auto_delete_project,
    list_projects,
    delete_project,
    modify_project,
    setup_project,
    start_project,
    stop_project,
    update_project,
    get_project_logs,
    get_project_status,
    predict_project,
    fetch_project,
)

_PATH_SETUP = re.compile(r"^/projects/([^/]+)/setup/?$")
_PATH_START = re.compile(r"^/projects/([^/]+)/start/?$")
_PATH_STOP = re.compile(r"^/projects/([^/]+)/stop/?$")
_PATH_UPDATE = re.compile(r"^/projects/([^/]+)/update/?$")
_PATH_LOGS = re.compile(r"^/projects/([^/]+)/logs/?$")
_PATH_STATUS = re.compile(r"^/projects/([^/]+)/status/?$")
_PATH_PREDICT = re.compile(r"^/projects/([^/]+)/predict/?$")
_PATH_GET_PROJECT = re.compile(r"^/projects/([^/]+)/fetch/?$")


def handler(event, context):

    path = event.get("path", "")
    method = event.get("httpMethod", "GET")

    # --- Project manager ---
    if path == "/project-manager/create" and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        return _safe(
            create_project,
            name=body.get("name"),
            repo_url=body.get("repo_url"),
            github_token=body.get("github_token"),
            instance_id=body.get("instance_id"),
            sub_folder=body.get("sub_folder"),
        )

    if path == "/project-manager/auto_create" and method == "POST":
        body = _parse_body(event)

        print(f"Received auto_create request: {body}")  # Debug log

        if body is None:
            return _err(400, "Request body must be valid JSON")
        market_type = body.get("market_type")
        if market_type is None and body.get("isSpotInstance") is True:
            market_type = "spot"
        return _safe(
            auto_create_project,
            name=body.get("name"),
            repo_url=body.get("repo_url"),
            github_token=body.get("github_token"),
            instance_id=body.get("instance_id"),
            ami_id=body.get("ami_id"),
            instance_type=body.get("instance_type"),
            storage_gb=body.get("storage_gb"),
            market_type=market_type,
            sub_folder=body.get("sub_folder"),
        )

    if path == "/project-manager/list" and method == "GET":
        start = time.perf_counter()
        response = _safe(list_projects)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response["headers"]["X-Handler-Time-Ms"] = str(duration_ms)
        return response

    if path == "/project-manager/delete" and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        return _safe(delete_project, name=body.get("name"))

    if path == "/project-manager/auto_delete" and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        return _safe(auto_delete_project, name=body.get("name"))

    if path == "/project-manager/modify" and method == "POST":

        body = _parse_body(event)

        if body is None:
            return _err(400, "Request body must be valid JSON")
        
        print(f"Received modify request: {body}")  # Debug log

        return _safe(
            modify_project,
            name=body.get("name"),
            repo_url=body.get("repo_url"),
            github_token=body.get("github_token"),
            instance_id=body.get("instance_id"),
            sub_folder=body.get("sub_folder"),
        )

    m = _PATH_SETUP.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(setup_project, project_name)

    m = _PATH_START.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(start_project, project_name)

    m = _PATH_STOP.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(stop_project, project_name)

    m = _PATH_UPDATE.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(update_project, project_name)

    m = _PATH_LOGS.match(path)
    if m and method == "GET":
        project_name = m.group(1)
        params = event.get("queryStringParameters") or {}
        command_id = params.get("command_id", "")
        try:
            start_byte = int(params.get("start_byte", 0))
        except (ValueError, TypeError):
            return _err(400, "start_byte must be an integer")
        return _safe(get_project_logs, project_name, command_id, start_byte)

    m = _PATH_STATUS.match(path)
    if m and method == "GET":
        project_name = m.group(1)
        return _safe(get_project_status, project_name)
    
    m = _PATH_GET_PROJECT.match(path)
    if m and method == "GET":
        project_name = m.group(1)
        return _safe(fetch_project, project_name)
    
    m = _PATH_PREDICT.match(path)
    if m and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        project_name = m.group(1)
        return _safe(predict_project, project_name, body)

    return _err(404, "Not found")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
