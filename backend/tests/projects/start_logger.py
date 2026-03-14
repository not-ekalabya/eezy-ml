import argparse
import json
import os
import re
import time

import boto3
from botocore.exceptions import ClientError

INSTANCE_ID_PATTERN = re.compile(r"^i-[a-f0-9]{8,17}$")
SERVER_RUNNING_HOOK_PATTERN = re.compile(r"=== Server is running \(PID: \d+\) ===")


def validate_instance_id(instance_id):
    if not INSTANCE_ID_PATTERN.match(instance_id):
        raise ValueError(f"Invalid instance ID format: {instance_id}")


def get_clients(region_name):
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    ec2_client = boto3.client("ec2", region_name=region_name)
    ssm_client = boto3.client("ssm", region_name=region_name)
    return dynamodb, ec2_client, ssm_client


def get_project(table, project_name):
    response = table.get_item(Key={"name": project_name})
    project = response.get("Item")
    if not project:
        raise ValueError(f"Project '{project_name}' does not exist")
    return project


def wait_for_instance_running(ec2_client, instance_id, attempts=45, delay_seconds=4):
    for _ in range(attempts):
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        if reservations and reservations[0].get("Instances"):
            state = reservations[0]["Instances"][0]["State"]["Name"]
            if state == "running":
                return
        time.sleep(delay_seconds)
    raise RuntimeError(f"Instance '{instance_id}' did not reach 'running' state")


def wait_for_ssm_online(ssm_client, instance_id, attempts=45, delay_seconds=4):
    for _ in range(attempts):
        response = ssm_client.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        info_list = response.get("InstanceInformationList", [])
        if info_list and info_list[0].get("PingStatus") == "Online":
            return
        time.sleep(delay_seconds)
    raise RuntimeError(f"Instance '{instance_id}' did not come back Online in SSM after start")


def send_start_command(ssm_client, project_name, repo_url, instance_id):
    commands = [
        "set -e",
        f"PROJECT_NAME='{project_name}'",
        "BASE_DIR=/opt/eezy-ml-projects",
        "WORKDIR=\"$BASE_DIR/$PROJECT_NAME\"",
        "if [ ! -d \"$WORKDIR/.git\" ] && [ -d \"$BASE_DIR\" ]; then "
        "for d in \"$BASE_DIR\"/*; do "
        "[ -d \"$d/.git\" ] || continue; "
        "origin=$(git -C \"$d\" remote get-url origin 2>/dev/null || true); "
        "clean_origin=$(printf '%s' \"$origin\" | sed -E 's#https://[^@]+@#https://#'); "
        f"if [ \"$clean_origin\" = \"{repo_url}\" ] || [ \"$clean_origin\" = \"{repo_url}.git\" ]; then WORKDIR=\"$d\"; break; fi; "
        "done; "
        "fi",
        "if [ ! -d \"$WORKDIR/.git\" ] && [ -d /app/.git ]; then WORKDIR=/app; fi",
        "if [ ! -d \"$WORKDIR/.git\" ]; then "
        "echo \"No project checkout found to resume server\" >&2; "
        "exit 20; "
        "fi",
        "cd \"$WORKDIR\"",
        "echo \"Using WORKDIR=$WORKDIR\"",
        "SERVE_SCRIPT=$(find . -maxdepth 5 -type f -path '*/scripts/serve.sh' | sed 's#^./##' | head -n 1)",
        "SETUP_SCRIPT=$(find . -maxdepth 5 -type f -path '*/scripts/setup.sh' | sed 's#^./##' | head -n 1)",
        "if [ -n \"$SERVE_SCRIPT\" ]; then "
        "chmod +x \"$SERVE_SCRIPT\"; "
        "./\"$SERVE_SCRIPT\"; "
        "elif [ -n \"$SETUP_SCRIPT\" ]; then "
        "chmod +x \"$SETUP_SCRIPT\"; "
        "./\"$SETUP_SCRIPT\"; "
        "elif command -v docker >/dev/null 2>&1; then "
        "if docker ps -a --format '{{.Names}}' | grep -qx eezy-ml; then "
        "docker start eezy-ml || docker restart eezy-ml; "
        "else "
        "echo 'No serve.sh/setup.sh and no eezy-ml container found' >&2; exit 127; "
        "fi; "
        "else "
        "echo 'No serve.sh/setup.sh and docker is unavailable' >&2; exit 127; "
        "fi",
        "TAIL_PID=''",
        "if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx eezy-ml; then "
        "docker logs -f --since 0s eezy-ml 2>&1 & "
        "TAIL_PID=$!; "
        "echo \"Tailing eezy-ml container logs (pid=$TAIL_PID)\"; "
        "fi",
        "for i in $(seq 1 30); do "
        "if curl -fsS http://127.0.0.1:5000/health >/dev/null 2>&1; then "
        "if [ -n \"$TAIL_PID\" ]; then kill \"$TAIL_PID\" >/dev/null 2>&1 || true; fi; "
        "echo 'health-ok'; exit 0; "
        "fi; "
        "sleep 2; "
        "done; "
        "if [ -n \"$TAIL_PID\" ]; then kill \"$TAIL_PID\" >/dev/null 2>&1 || true; fi; "
        "echo 'Service did not become healthy on :5000 in time' >&2; exit 124",
    ]

    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
    )
    return response["Command"]["CommandId"]


def poll_command(ssm_client, command_id, instance_id, attempts=20, delay_seconds=2):
    status = "InProgress"
    stdout = ""
    stderr = ""
    for _ in range(attempts):
        time.sleep(delay_seconds)
        try:
            invocation = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except ClientError:
            continue
        status = invocation.get("Status", status)
        stdout = invocation.get("StandardOutputContent", "")
        stderr = invocation.get("StandardErrorContent", "")
        if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
            break
    return {
        "command_id": command_id,
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
    }


def wait_for_command(ssm_client, command_id, instance_id, max_wait_seconds=30, delay_seconds=2):
    start = time.time()
    last_invocation = None
    while time.time() - start < max_wait_seconds:
        try:
            invocation = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except ClientError:
            time.sleep(delay_seconds)
            continue
        last_invocation = invocation
        status = invocation.get("Status", "InProgress")
        if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
            return invocation
        time.sleep(delay_seconds)
    return last_invocation or {
        "Status": "InProgress",
        "StandardOutputContent": "",
        "StandardErrorContent": "",
    }


def stream_command_logs(ssm_client, command_id, instance_id, max_wait_seconds=900, delay_seconds=1):
    start = time.time()
    stdout_len = 0
    stderr_len = 0
    raw_log_offset = 0
    idle_polls = 0
    final_invocation = None

    while time.time() - start < max_wait_seconds:
        try:
            invocation = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except ClientError:
            time.sleep(delay_seconds)
            continue

        final_invocation = invocation
        stdout = invocation.get("StandardOutputContent", "")
        stderr = invocation.get("StandardErrorContent", "")

        stdout_grew = len(stdout) > stdout_len
        stderr_grew = len(stderr) > stderr_len

        if stdout_grew:
            chunk = stdout[stdout_len:]
            stdout_len = len(stdout)
            if chunk.strip():
                print(chunk, end="", flush=True)
                if SERVER_RUNNING_HOOK_PATTERN.search(chunk):
                    return {
                        "command_id": command_id,
                        "status": "Success",
                        "stdout": stdout,
                        "stderr": stderr,
                        "hook_detected": "server_running",
                    }

        if stderr_grew:
            chunk = stderr[stderr_len:]
            stderr_len = len(stderr)
            if chunk.strip():
                print(chunk, end="", file=os.sys.stderr, flush=True)
                if SERVER_RUNNING_HOOK_PATTERN.search(chunk):
                    return {
                        "command_id": command_id,
                        "status": "Success",
                        "stdout": stdout,
                        "stderr": stderr,
                        "hook_detected": "server_running",
                    }

        if stdout_grew or stderr_grew:
            idle_polls = 0
        else:
            idle_polls += 1

        # When get_command_invocation output is delayed, read command-specific SSM log chunks.
        if idle_polls >= 2:
            raw_invocation = read_ssm_log_chunk(ssm_client, instance_id, command_id, raw_log_offset)
            raw_stdout = raw_invocation.get("StandardOutputContent", "")
            raw_status = raw_invocation.get("Status", "")
            raw_code = raw_invocation.get("ResponseCode")

            if raw_status == "Success" and raw_stdout:
                lines = raw_stdout.splitlines()
                payload = ""
                if lines and lines[0].startswith("__LOG_PATH__:"):
                    payload = "\n".join(lines[1:])
                    if raw_stdout.endswith("\n"):
                        payload += "\n"
                if payload:
                    print(payload, end="", flush=True)
                    raw_log_offset += len(payload.encode("utf-8"))
                    idle_polls = 0
                    if SERVER_RUNNING_HOOK_PATTERN.search(payload):
                        return {
                            "command_id": command_id,
                            "status": "Success",
                            "stdout": stdout,
                            "stderr": stderr,
                            "hook_detected": "server_running",
                        }
            elif raw_code == 3:
                # Log file not created yet; keep polling.
                pass

        status = invocation.get("Status", "InProgress")
        if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
            if stdout and not stdout.endswith("\n"):
                print(flush=True)
            if stderr and not stderr.endswith("\n"):
                print(file=os.sys.stderr, flush=True)
            return {
                "command_id": command_id,
                "status": status,
                "stdout": stdout,
                "stderr": stderr,
            }

        time.sleep(delay_seconds)

    return {
        "command_id": command_id,
        "status": (final_invocation or {}).get("Status", "InProgress"),
        "stdout": (final_invocation or {}).get("StandardOutputContent", ""),
        "stderr": (final_invocation or {}).get("StandardErrorContent", ""),
    }


def read_ssm_log_chunk(ssm_client, instance_id, command_id, start_byte):
    commands = [
        "set -e",
        f"COMMAND_ID='{command_id}'",
        f"START_BYTE={start_byte}",
        "LOG_PATH=$("
        "find /var/lib/amazon/ssm /var/log/amazon/ssm -type f "
        "\\( -name stdout -o -name stderr -o -name '*.log' \\) 2>/dev/null "
        "| grep \"$COMMAND_ID\" "
        "| sort "
        "| tail -n 1"
        ")",
        "if [ -z \"$LOG_PATH\" ] || [ ! -f \"$LOG_PATH\" ]; then "
        "LOG_PATH=$("
        "find /var/lib/amazon/ssm /var/log/amazon/ssm -type f "
        "\\( -name stdout -o -name stderr -o -name '*.log' \\) 2>/dev/null "
        "| grep -i \"$COMMAND_ID\" "
        "| sort "
        "| tail -n 1"
        "); "
        "fi",
        "if [ -z \"$LOG_PATH\" ] || [ ! -f \"$LOG_PATH\" ]; then exit 3; fi",
        "FILE_SIZE=$(wc -c < \"$LOG_PATH\")",
        "if [ \"$START_BYTE\" -ge \"$FILE_SIZE\" ]; then exit 0; fi",
        "echo \"__LOG_PATH__:$LOG_PATH\"",
        "dd if=\"$LOG_PATH\" bs=1 skip=\"$START_BYTE\" status=none",
    ]
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
    )
    invocation = wait_for_command(
        ssm_client,
        response["Command"]["CommandId"],
        instance_id,
        max_wait_seconds=30,
        delay_seconds=1,
    )
    return invocation


def stream_ssm_agent_logs(ssm_client, instance_id, command_id, max_wait_seconds=300, delay_seconds=2):
    print(f"Streaming command-specific SSM logs for {command_id} on {instance_id}...")
    start = time.time()
    offset = 0
    saw_output = False
    idle_polls = 0

    while time.time() - start < max_wait_seconds:
        invocation = read_ssm_log_chunk(ssm_client, instance_id, command_id, offset)
        status = invocation.get("Status", "InProgress")
        stdout = invocation.get("StandardOutputContent", "")
        stderr = invocation.get("StandardErrorContent", "")
        code = invocation.get("ResponseCode")

        if status == "Success":
            lines = stdout.splitlines()
            payload = ""
            if lines and lines[0].startswith("__LOG_PATH__:"):
                payload = "\n".join(lines[1:])
                if stdout.endswith("\n"):
                    payload += "\n"

            if payload:
                saw_output = True
                idle_polls = 0
                offset += len(payload.encode("utf-8"))
                print(payload, end="", flush=True)
            else:
                idle_polls += 1
        elif code == 3:
            idle_polls += 1
        elif stderr:
            print(stderr, end="", file=os.sys.stderr, flush=True)
            idle_polls += 1
        else:
            idle_polls += 1

        if saw_output and idle_polls >= 5:
            break

        time.sleep(delay_seconds)

    if not saw_output:
        print(f"No command-specific SSM log output was produced for {command_id}.")


def start_project(project_name, region_name, table_name):
    dynamodb, ec2_client, ssm_client = get_clients(region_name)
    table = dynamodb.Table(table_name)
    project = get_project(table, project_name)

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{project_name}' has no associated instance_id")
    validate_instance_id(instance_id)

    repo_url = project.get("repo_url")
    if not repo_url:
        raise ValueError(f"Project '{project_name}' has no repo_url")

    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    reservations = response.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        raise ValueError(f"Instance '{instance_id}' not found")
    state = reservations[0]["Instances"][0]["State"]["Name"]

    if state == "stopped":
        ec2_client.start_instances(InstanceIds=[instance_id])
    elif state not in {"running", "pending"}:
        raise ValueError(
            f"Instance '{instance_id}' is in state '{state}', expected 'stopped' or 'running'"
        )

    wait_for_instance_running(ec2_client, instance_id)
    wait_for_ssm_online(ssm_client, instance_id)
    command_id = send_start_command(ssm_client, project_name, repo_url, instance_id)
    print(f"Streaming SSM logs for command {command_id} on {instance_id}...")
    result = stream_command_logs(ssm_client, command_id, instance_id)
    if not (result.get("stdout", "").strip() or result.get("stderr", "").strip()):
        stream_ssm_agent_logs(ssm_client, instance_id, command_id)
    if result.get("status") == "InProgress" and result.get("hook_detected") != "server_running":
        print("Start command still running; waiting for final SSM status...", flush=True)
        final_invocation = wait_for_command(
            ssm_client,
            command_id,
            instance_id,
            max_wait_seconds=1800,
            delay_seconds=2,
        )
        result = {
            "command_id": command_id,
            "status": final_invocation.get("Status", "InProgress"),
            "stdout": final_invocation.get("StandardOutputContent", ""),
            "stderr": final_invocation.get("StandardErrorContent", ""),
        }
    result["message"] = "start invoked"
    result["instance_id"] = instance_id
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Start an eezy-ml project directly through AWS without the SAM API."
    )
    parser.add_argument("project_name", help="Project name stored in DynamoDB")
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        help="AWS region for DynamoDB, EC2, and SSM",
    )
    parser.add_argument(
        "--projects-table",
        default=os.environ.get("PROJECTS_TABLE", "eezy-ml-projects"),
        help="DynamoDB table containing project records",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable live SSM log streaming and only print the final result.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.no_stream:
        dynamodb, ec2_client, ssm_client = get_clients(args.region)
        table = dynamodb.Table(args.projects_table)
        project = get_project(table, args.project_name)
        instance_id = project.get("instance_id")
        if not instance_id:
            raise ValueError(f"Project '{args.project_name}' has no associated instance_id")
        validate_instance_id(instance_id)
        repo_url = project.get("repo_url")
        if not repo_url:
            raise ValueError(f"Project '{args.project_name}' has no repo_url")
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        if not reservations or not reservations[0].get("Instances"):
            raise ValueError(f"Instance '{instance_id}' not found")
        state = reservations[0]["Instances"][0]["State"]["Name"]
        if state == "stopped":
            ec2_client.start_instances(InstanceIds=[instance_id])
        elif state not in {"running", "pending"}:
            raise ValueError(
                f"Instance '{instance_id}' is in state '{state}', expected 'stopped' or 'running'"
            )
        wait_for_instance_running(ec2_client, instance_id)
        wait_for_ssm_online(ssm_client, instance_id)
        command_id = send_start_command(ssm_client, args.project_name, repo_url, instance_id)
        result = poll_command(ssm_client, command_id, instance_id)
        result["message"] = "start invoked"
        result["instance_id"] = instance_id
    else:
        result = start_project(args.project_name, args.region, args.projects_table)
    print(json.dumps(result, indent=2))
