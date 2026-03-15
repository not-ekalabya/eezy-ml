import argparse
import json
import time

import requests


TERMINAL_STATUSES = {"Success", "Failed", "TimedOut", "Cancelled"}


def update_project(api_url, project_name):
    """
    Trigger update for a project by hitting /projects/<project-name>/update.

    Args:
        api_url: Base API URL (e.g., "https://api.example.com")
        project_name: Name of the project to update

    Returns:
        Response object from the API
    """
    url = f"{api_url}/projects/{project_name}/update"
    return requests.post(url)


def fetch_project_logs(api_url, project_name, command_id, start_byte):
    """Retrieve a log chunk and command status for a project command."""
    url = f"{api_url}/projects/{project_name}/logs"
    response = requests.get(
        url,
        params={
            "command_id": command_id,
            "start_byte": start_byte,
        },
    )
    response.raise_for_status()
    return response.json()


def stream_update_logs(api_url, project_name, command_id, start_byte=0, poll_seconds=2, timeout_seconds=1800):
    """Stream remote update logs until the command reaches a terminal state."""
    deadline = time.time() + timeout_seconds
    next_byte = start_byte
    last_status = "Pending"
    idle_polls = 0

    while time.time() < deadline:
        payload = fetch_project_logs(api_url, project_name, command_id, next_byte)
        chunk = payload.get("logs", "")
        status = payload.get("command_status", "Pending")

        if chunk:
            print(chunk, end="", flush=True)
            next_byte = payload.get("next_byte", next_byte + len(chunk.encode("utf-8")))
            idle_polls = 0
        else:
            idle_polls += 1

        if status != last_status:
            print(f"\n[command status: {status}]", flush=True)
            last_status = status

        if status in TERMINAL_STATUSES and idle_polls >= 2:
            return {
                "status": status,
                "next_byte": next_byte,
                "command_response_code": payload.get("command_response_code"),
                "command_stderr": payload.get("command_stderr", ""),
            }

        time.sleep(poll_seconds)

    return {
        "status": "TimedOut",
        "next_byte": next_byte,
        "command_response_code": None,
        "command_stderr": "client log stream timed out",
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Call project update endpoint.")
    parser.add_argument("project_name", help="Project name")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:3000", help="Base API URL"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable log streaming and print only the initial API response.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Polling interval in seconds while streaming logs.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="Max seconds to stream logs before client timeout.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    resp = update_project(args.api_url, args.project_name)
    print(resp.status_code)

    try:
        body = resp.json()
    except ValueError:
        print(resp.text)
        raise SystemExit(1)

    print(json.dumps(body, indent=2))

    if args.no_stream:
        raise SystemExit(0)

    command_id = body.get("command_id")
    if not command_id:
        print("No command_id returned by API; cannot stream logs.")
        raise SystemExit(1)

    initial_logs = body.get("logs", "")
    start_byte = 0
    if initial_logs:
        print(initial_logs, end="", flush=True)
        start_byte = len(initial_logs.encode("utf-8"))

    result = stream_update_logs(
        args.api_url,
        args.project_name,
        command_id,
        start_byte=start_byte,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )

    print("\nFinal stream result:")
    print(json.dumps(result, indent=2))

    if result.get("status") != "Success":
        raise SystemExit(1)
