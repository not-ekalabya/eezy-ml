"""app.py - Lambda handler for eezy-ml backend API.

This version exposes project management endpoints backed by DynamoDB.
Only the project-manager routes are enabled; EC2 inference endpoints were
removed.
"""

import json
import re

from utils import (
    create_project,
    list_projects,
    delete_project,
    modify_project,
    setup_project,
    start_project,
    update_project,
    get_project_logs,
)

_PATH_SETUP = re.compile(r"^/projects/([^/]+)/setup/?$")
_PATH_START = re.compile(r"^/projects/([^/]+)/start/?$")
_PATH_UPDATE = re.compile(r"^/projects/([^/]+)/update/?$")
_PATH_LOGS = re.compile(r"^/projects/([^/]+)/logs/?$")


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
        )

    if path == "/project-manager/list" and method == "GET":
        return _safe(list_projects)

    if path == "/project-manager/delete" and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        return _safe(delete_project, name=body.get("name"))

    if path == "/project-manager/modify" and method == "POST":
        body = _parse_body(event)
        if body is None:
            return _err(400, "Request body must be valid JSON")
        return _safe(
            modify_project,
            name=body.get("name"),
            repo_url=body.get("repo_url"),
            github_token=body.get("github_token"),
            instance_id=body.get("instance_id"),
        )

    m = _PATH_SETUP.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(setup_project, project_name)

    m = _PATH_START.match(path)
    if m and method == "POST":
        project_name = m.group(1)
        return _safe(start_project, project_name)

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
