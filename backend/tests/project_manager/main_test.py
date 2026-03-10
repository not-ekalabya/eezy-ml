import argparse
import json
import logging
from pathlib import Path

from create import create_project
from modify import modify_project
from delete import delete_project


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def log_response(step: str, response) -> tuple[int, object]:
    try:
        body = response.json()
    except ValueError:
        body = response.text

    logging.info("%s → status=%s body=%s", step, response.status_code, body)
    return response.status_code, body


def status_ok(status: int) -> bool:
    return status in (200, 201, 202)


def run_flow(
    api_url: str,
    name: str,
    create_repo_url: str,
    modify_repo_url: str,
    github_token: str,
    instance_id: str,
) -> None:
    results = {}

    # Create
    create_resp = create_project(api_url, name, create_repo_url, github_token, instance_id)
    results["create"] = log_response("create", create_resp)
    if not status_ok(results["create"][0]):
        raise SystemExit("Create failed; aborting remaining steps.")

    # Modify (can point to a different repo)
    modify_resp = modify_project(api_url, name, modify_repo_url, github_token, instance_id)
    results["modify"] = log_response("modify", modify_resp)
    if not status_ok(results["modify"][0]):
        raise SystemExit("Modify failed; aborting remaining steps.")

    # Delete
    delete_resp = delete_project(api_url, name)
    results["delete"] = log_response("delete", delete_resp)
    if not status_ok(results["delete"][0]):
        raise SystemExit("Delete failed.")

    # Human-friendly summary
    summary = {
        step: {"status": status, "body": body}
        for step, (status, body) in results.items()
    }
    logging.info("Test flow summary: %s", json.dumps(summary, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run project manager flow: create -> modify -> delete."
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:3000", help="Base API URL.")
    parser.add_argument("--name", default="demo", help="Project name for the test run.")
    parser.add_argument(
        "--repo-url",
        default="https://github.com/not-ekalabya/eezy-ml",
        help="GitHub repository URL for creation.",
    )
    parser.add_argument(
        "--modify-repo-url",
        default="https://github.com/not-ekalabya/eezy-ml",
        help="GitHub repository URL to use during modify step.",
    )
    parser.add_argument("--github-token", default="sample_github_token", help="GitHub token.")
    parser.add_argument(
        "--instance-id",
        default="i-123456789abcdef0",
        help="AWS instance ID used by the API.",
    )
    parser.add_argument(
        "--log-file",
        default="logs/test_run.log",
        help="Path to write the flow log.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    setup_logging(Path(args.log_file))
    run_flow(
        api_url=args.api_url,
        name=args.name,
        create_repo_url=args.repo_url,
        modify_repo_url=args.modify_repo_url,
        github_token=args.github_token,
        instance_id=args.instance_id,
    )
