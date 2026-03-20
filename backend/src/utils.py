"""utils.py - EC2 instance management and DynamoDB project store."""

import os
import re
import json
import time
import urllib.request
import urllib.error
import base64

import boto3
from botocore.exceptions import ClientError

INSTANCE_TAG = "eezy-ml"
SG_NAME = "eezy-ml-sg"
SG_DESCRIPTION = "Security group for eezy-ml deployed instances"

GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+$")
INSTANCE_ID_PATTERN = re.compile(r"^i-[a-f0-9]{8,17}$")
SERVER_RUNNING_HOOK_PATTERN = re.compile(r"=== Server is running \(PID: \d+\) ===")

ALLOWED_INSTANCE_TYPES = {
    "t2.micro", "t2.small", "t2.medium", "t2.large",
    "t3.micro", "t3.small", "t3.medium", "t3.large",
    "t3a.micro", "t3a.small", "t3a.medium", "t3a.large",
    "m5.large", "m5.xlarge",
    "c5.large", "c5.xlarge",
    "g4dn.xlarge",
}

DEFAULT_AUTO_CREATE_AMI_ID = "ami-0a7300e10f97b6153"
DEFAULT_AUTO_CREATE_INSTANCE_TYPE = "g4dn.xlarge"
DEFAULT_AUTO_CREATE_STORAGE_GB = 80
DEFAULT_AUTO_CREATE_MARKET_TYPE = "on-demand"
ALLOWED_MARKET_TYPES = {"on-demand", "spot"}

ec2_client = boto3.client("ec2", region_name="us-east-1")
ssm_client = boto3.client("ssm", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "eezy-ml-projects")
projects_table = dynamodb.Table(PROJECTS_TABLE)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_instance_id(instance_id):
    if not INSTANCE_ID_PATTERN.match(instance_id):
        raise ValueError(f"Invalid instance ID format: {instance_id}")


def validate_repo_url(repo_url):
    if not GITHUB_URL_PATTERN.match(repo_url):
        raise ValueError(
            "repo_url must be a GitHub HTTPS URL like "
            "https://github.com/owner/repo"
        )


def validate_instance_type(instance_type):
    if instance_type not in ALLOWED_INSTANCE_TYPES:
        raise ValueError(
            f"Instance type '{instance_type}' is not allowed. "
            f"Choose from: {', '.join(sorted(ALLOWED_INSTANCE_TYPES))}"
        )


def validate_storage_gb(storage_gb):
    if not isinstance(storage_gb, int):
        raise ValueError("storage_gb must be an integer")
    if storage_gb < 8:
        raise ValueError("storage_gb must be at least 8")


def validate_market_type(market_type):
    if market_type not in ALLOWED_MARKET_TYPES:
        raise ValueError(
            "market_type must be one of: "
            f"{', '.join(sorted(ALLOWED_MARKET_TYPES))}"
        )


def validate_ami_id(ami_id):
    if not isinstance(ami_id, str) or not ami_id.strip():
        raise ValueError("ami_id must be a non-empty string")
    if not ami_id.startswith("ami-"):
        raise ValueError("ami_id must start with 'ami-'")


def validate_project_payload(name, repo_url, github_token, instance_id, require_instance=False):
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")
    if repo_url:
        validate_repo_url(repo_url)
    if github_token is not None and not isinstance(github_token, str):
        raise ValueError("github_token must be a string when provided")
    if instance_id is None:
        if require_instance:
            raise ValueError("instance_id is required")
        return
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("instance_id must be a non-empty string")
    validate_instance_id(instance_id)


# ---------------------------------------------------------------------------
# GitHub token
# ---------------------------------------------------------------------------

def get_github_token():
    """Retrieve GitHub token from env var or SSM Parameter Store."""
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    ssm_name = os.environ.get("SSM_GITHUB_TOKEN_NAME", "/eezy-ml/github-token")
    try:
        resp = ssm_client.get_parameter(Name=ssm_name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception as e:
        raise RuntimeError(
            "GitHub token not found. Set GITHUB_TOKEN env var or "
            f"create SSM parameter {ssm_name}: {e}"
        )


# ---------------------------------------------------------------------------
# DynamoDB project store
# ---------------------------------------------------------------------------

def create_project(name, repo_url, github_token, instance_id=None):
    validate_project_payload(name, repo_url, github_token, instance_id, require_instance=True)

    item = {
        "name": name,
        "repo_url": repo_url or "",
        "github_token": github_token or "",
        "instance_id": instance_id or "",
        # keep schema single-instance; legacy instance_ids removed
    }

    try:
        projects_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(#n)",
            ExpressionAttributeNames={"#n": "name"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"Project '{name}' already exists")
        raise

    return {"message": "created", "project": item}


def list_projects():
    resp = projects_table.scan()
    items = []
    for item in resp.get("Items", []):
        # normalize legacy records
        if "instance_ids" in item and not item.get("instance_id"):
            item["instance_id"] = item["instance_ids"][0] if item["instance_ids"] else ""
        item.pop("instance_ids", None)
        if not item.get("instance_id"):
            item["instance_id"] = ""
        items.append(item)
    return {"projects": items}


def delete_project(name):
    if not name:
        raise ValueError("name is required")
    try:
        projects_table.delete_item(
            Key={"name": name},
            ConditionExpression="attribute_exists(#n)",
            ExpressionAttributeNames={"#n": "name"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"Project '{name}' does not exist")
        raise
    return {"message": "deleted", "name": name}


def auto_delete_project(name):
    """Terminate a project's instance and remove the project from DynamoDB."""
    if not name:
        raise ValueError("name is required")

    project = projects_table.get_item(Key={"name": name}).get("Item")
    if not project:
        raise ValueError(f"Project '{name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{name}' has no associated instance_id")
    validate_instance_id(instance_id)

    try:
        ec2_client.terminate_instances(InstanceIds=[instance_id])
    except ClientError as e:
        if e.response["Error"].get("Code") == "InvalidInstanceID.NotFound":
            # Continue deleting project record even when instance is already gone.
            pass
        else:
            raise RuntimeError(f"Failed to terminate instance '{instance_id}': {e}")

    delete_project(name)
    return {
        "message": "auto deleted",
        "name": name,
        "instance_id": instance_id,
        "instance_status": "terminating",
    }


def modify_project(name, repo_url=None, github_token=None, instance_id=None):
    validate_project_payload(name, repo_url, github_token, instance_id)

    update_expr = []
    expr_values = {}
    expr_names = {"#n": "name"}
    remove_expr = ["instance_ids"]

    if repo_url is not None:
        update_expr.append("repo_url = :r")
        expr_values[":r"] = repo_url
    if github_token is not None:
        update_expr.append("github_token = :g")
        expr_values[":g"] = github_token
    if instance_id is not None:
        update_expr.append("instance_id = :i")
        expr_values[":i"] = instance_id

    if not update_expr:
        raise ValueError("Nothing to update")

    update_statement = "SET " + ", ".join(update_expr)
    if remove_expr:
        update_statement = "REMOVE " + ", ".join(remove_expr) + " " + update_statement

    try:
        resp = projects_table.update_item(
            Key={"name": name},
            ConditionExpression="attribute_exists(#n)",
            ExpressionAttributeNames=expr_names,
            UpdateExpression=update_statement,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"Project '{name}' does not exist")
        raise

    return {"message": "updated", "project": resp.get("Attributes", {})}


def auto_create_project(
    name,
    repo_url,
    github_token,
    instance_id=None,
    ami_id=None,
    instance_type=None,
    storage_gb=None,
    market_type=None,
):
    if instance_id is not None:
        raise ValueError("instance_id must not be provided for auto_create")

    validate_project_payload(name, repo_url, github_token, None, require_instance=False)

    ami_id = ami_id or DEFAULT_AUTO_CREATE_AMI_ID
    instance_type = instance_type or DEFAULT_AUTO_CREATE_INSTANCE_TYPE
    storage_gb = storage_gb if storage_gb is not None else DEFAULT_AUTO_CREATE_STORAGE_GB
    market_type = market_type or DEFAULT_AUTO_CREATE_MARKET_TYPE

    validate_ami_id(ami_id)
    validate_instance_type(instance_type)
    validate_storage_gb(storage_gb)
    validate_market_type(market_type)

    # Keep project names unique before provisioning AWS resources.
    existing = projects_table.get_item(Key={"name": name}).get("Item")
    if existing:
        raise ValueError(f"Project '{name}' already exists")

    sg_id = get_or_create_security_group()

    run_args = {
        "ImageId": ami_id,
        "InstanceType": instance_type,
        "MinCount": 1,
        "MaxCount": 1,
        "SecurityGroupIds": [sg_id],
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": storage_gb,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                },
            }
        ],
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": f"eezy-ml-{name}"},
                    {"Key": "Project", "Value": INSTANCE_TAG},
                    {"Key": "ProjectName", "Value": name},
                    {"Key": "RepoUrl", "Value": repo_url or ""},
                ],
            }
        ],
    }
    if market_type == "spot":
        run_args["InstanceMarketOptions"] = {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        }

    try:
        resp = ec2_client.run_instances(**run_args)
    except ClientError as e:
        raise RuntimeError(f"Failed to launch instance: {e}")

    new_instance_id = resp["Instances"][0]["InstanceId"]

    try:
        create_result = create_project(
            name=name,
            repo_url=repo_url,
            github_token=github_token,
            instance_id=new_instance_id,
        )
    except Exception:
        # Best effort cleanup to avoid orphaned instances when project write fails.
        try:
            ec2_client.terminate_instances(InstanceIds=[new_instance_id])
        except ClientError:
            pass
        raise

    return {
        "message": "auto created",
        "project": create_result.get("project", {}),
        "instance": {
            "instance_id": new_instance_id,
            "ami_id": ami_id,
            "instance_type": instance_type,
            "storage_gb": storage_gb,
            "market_type": market_type,
            "status": "launching",
        },
    }


def setup_project(name):
    """Run scripts/setup.sh on the project's associated instance."""
    if not name:
        raise ValueError("name is required")

    project = projects_table.get_item(Key={"name": name}).get("Item")
    if not project:
        raise ValueError(f"Project '{name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{name}' has no associated instance_id")
    validate_instance_id(instance_id)

    repo_url = project.get("repo_url")
    github_token = project.get("github_token")
    if not repo_url or not github_token:
        raise ValueError("repo_url and github_token are required on the project to run setup")
    validate_repo_url(repo_url)

    # Preflight: instance must exist and be running for SSM RunCommand.
    try:
        inst = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = inst.get("Reservations", [])
        if not reservations or not reservations[0].get("Instances"):
            raise ValueError(f"Instance '{instance_id}' not found")
        state = reservations[0]["Instances"][0]["State"]["Name"]
        if state != "running":
            raise ValueError(
                f"Instance '{instance_id}' is in state '{state}', expected 'running'"
            )
    except ClientError as e:
        raise RuntimeError(f"Failed to check instance state: {e}")

    # Preflight: SSM agent/registration must be healthy.
    try:
        ssm_info = ssm_client.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        info_list = ssm_info.get("InstanceInformationList", [])
        if not info_list:
            raise ValueError(
                f"Instance '{instance_id}' is not registered in SSM. "
                "Attach IAM role AmazonSSMManagedInstanceCore and ensure SSM Agent is running."
            )
        ping = info_list[0].get("PingStatus", "Unknown")
        if ping != "Online":
            raise ValueError(
                f"Instance '{instance_id}' SSM PingStatus is '{ping}', expected 'Online'"
            )
    except ClientError as e:
        raise RuntimeError(f"Failed to check SSM status: {e}")

    # Build repo URL with token for clone
    auth_repo = repo_url.replace("https://", f"https://{github_token}@")
    commands = [
        "set -e",
        "WORKDIR=/tmp/eezy-ml-project",
        "rm -rf \"$WORKDIR\"",
        f"git clone {auth_repo} \"$WORKDIR\"",
        f"cd \"$WORKDIR\" && git remote set-url origin {repo_url}",
        "cd \"$WORKDIR\"",
        "SETUP_SCRIPT=$(find . -maxdepth 6 -type f -path '*/scripts/setup.sh' | sed 's#^./##' | head -n 1)",
        "if [ -z \"$SETUP_SCRIPT\" ]; then "
        "echo 'setup.sh not found under */scripts/setup.sh' >&2; "
        "echo '--- git remote -v ---' >&2; git remote -v >&2 || true; "
        "echo '--- git branch --show-current ---' >&2; git branch --show-current >&2 || true; "
        "echo '--- find . -maxdepth 6 -type f -name setup.sh ---' >&2; "
        "find . -maxdepth 6 -type f -name setup.sh >&2 || true; "
        "exit 127; fi",
        "chmod +x \"$SETUP_SCRIPT\"",
        "./\"$SETUP_SCRIPT\"",
    ]

    try:
        send_resp = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
        )
    except ClientError as e:
        raise RuntimeError(
            f"Failed to start setup command: {e}. "
            "Confirm the instance is managed by SSM and currently Online."
        )

    command_id = send_resp["Command"]["CommandId"]

    # Poll for completion (short window; Lambda timeout is 900s so keep light)
    status = "InProgress"
    stdout = ""
    stderr = ""
    for _ in range(15):
        time.sleep(2)
        try:
            inv = ssm_client.get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )
            status = inv.get("Status")
            stdout = inv.get("StandardOutputContent", "")
            stderr = inv.get("StandardErrorContent", "")
            if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
                break
        except ClientError:
            continue

    return {
        "message": "setup invoked",
        "command_id": command_id,
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "logs": _merge_logs(stdout, stderr),
    }


def update_project(name):
    """Pull latest changes for a project repo on instance and re-run setup."""
    if not name:
        raise ValueError("name is required")

    project = projects_table.get_item(Key={"name": name}).get("Item")
    if not project:
        raise ValueError(f"Project '{name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{name}' has no associated instance_id")
    validate_instance_id(instance_id)

    repo_url = project.get("repo_url")
    github_token = project.get("github_token")
    if not repo_url or not github_token:
        raise ValueError("repo_url and github_token are required on the project to run update")
    validate_repo_url(repo_url)

    try:
        inst = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = inst.get("Reservations", [])
        if not reservations or not reservations[0].get("Instances"):
            raise ValueError(f"Instance '{instance_id}' not found")
        state = reservations[0]["Instances"][0]["State"]["Name"]
        if state != "running":
            raise ValueError(
                f"Instance '{instance_id}' is in state '{state}', expected 'running'"
            )
    except ClientError as e:
        raise RuntimeError(f"Failed to check instance state: {e}")

    try:
        ssm_info = ssm_client.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        info_list = ssm_info.get("InstanceInformationList", [])
        if not info_list:
            raise ValueError(
                f"Instance '{instance_id}' is not registered in SSM. "
                "Attach IAM role AmazonSSMManagedInstanceCore and ensure SSM Agent is running."
            )
        ping = info_list[0].get("PingStatus", "Unknown")
        if ping != "Online":
            raise ValueError(
                f"Instance '{instance_id}' SSM PingStatus is '{ping}', expected 'Online'"
            )
    except ClientError as e:
        raise RuntimeError(f"Failed to check SSM status: {e}")

    auth_repo = repo_url.replace("https://", f"https://{github_token}@")

    # Reboot before update to force a clean runtime state.
    try:
        ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": ["sudo reboot"]},
        )
    except ClientError as e:
        raise RuntimeError(f"Failed to trigger reboot before update: {e}")

    # Wait for instance to return online in SSM after reboot.
    online = False
    for _ in range(45):
        time.sleep(4)
        try:
            ssm_info = ssm_client.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            )
            info_list = ssm_info.get("InstanceInformationList", [])
            if info_list and info_list[0].get("PingStatus") == "Online":
                online = True
                break
        except ClientError:
            continue
    if not online:
        raise RuntimeError(
            f"Instance '{instance_id}' did not come back Online in SSM after reboot"
        )

    commands = [
        "set -e",
        f"PROJECT_NAME='{name}'",
        "BASE_DIR=/opt/eezy-ml-projects",
        "WORKDIR=\"$BASE_DIR/$PROJECT_NAME\"",
        # Prefer persistent /opt checkout paths over /app so updates survive reboot.
        # If project-name path is missing, try any /opt checkout with matching origin URL.
        "if [ ! -d \"$WORKDIR/.git\" ] && [ -d \"$BASE_DIR\" ]; then "
        "for d in \"$BASE_DIR\"/*; do "
        "[ -d \"$d/.git\" ] || continue; "
        "origin=$(git -C \"$d\" remote get-url origin 2>/dev/null || true); "
        "clean_origin=$(printf '%s' \"$origin\" | sed -E 's#https://[^@]+@#https://#'); "
        f"if [ \"$clean_origin\" = \"{repo_url}\" ] || [ \"$clean_origin\" = \"{repo_url}.git\" ]; then WORKDIR=\"$d\"; break; fi; "
        "done; "
        "fi",
        "if [ ! -d \"$WORKDIR/.git\" ] && [ -d /app/.git ]; then WORKDIR=/app; fi",
        "mkdir -p \"$BASE_DIR\"",
        "if [ ! -d \"$WORKDIR/.git\" ]; then "
        "rm -rf \"$WORKDIR\"; "
        f"git clone {auth_repo} \"$WORKDIR\"; "
        f"cd \"$WORKDIR\" && git remote set-url origin {repo_url}; "
        "else "
        "cd \"$WORKDIR\"; "
        f"git remote set-url origin {auth_repo}; "
        "git fetch origin --prune; "
        "DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##'); "
        "if [ -z \"$DEFAULT_BRANCH\" ]; then DEFAULT_BRANCH=main; fi; "
        "git checkout \"$DEFAULT_BRANCH\" || git checkout -B \"$DEFAULT_BRANCH\" \"origin/$DEFAULT_BRANCH\"; "
        "git reset --hard \"origin/$DEFAULT_BRANCH\"; "
        "git clean -fdx; "
        f"git remote set-url origin {repo_url}; "
        "fi",
        "cd \"$WORKDIR\"",
        "echo \"Using WORKDIR=$WORKDIR\"",
        "echo \"Commit before setup: $(git rev-parse HEAD)\"",
        "SETUP_SCRIPT=$(find . -maxdepth 5 -type f -path '*/scripts/setup.sh' | sed 's#^./##' | head -n 1)",
        "if [ -z \"$SETUP_SCRIPT\" ]; then "
        "echo 'setup.sh not found under */scripts/setup.sh' >&2; "
        "echo '--- git remote -v ---' >&2; git remote -v >&2 || true; "
        "echo '--- git branch --show-current ---' >&2; git branch --show-current >&2 || true; "
        "echo '--- find . -maxdepth 4 -type f -name setup.sh ---' >&2; "
        "find . -maxdepth 4 -type f -name setup.sh >&2 || true; "
        "exit 127; fi",
        "chmod +x \"$SETUP_SCRIPT\"",
        "./\"$SETUP_SCRIPT\"",
        "echo \"Commit after setup: $(git rev-parse HEAD)\"",
    ]

    try:
        send_resp = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
        )
    except ClientError as e:
        raise RuntimeError(
            f"Failed to start update command: {e}. "
            "Confirm the instance is managed by SSM and currently Online."
        )

    command_id = send_resp["Command"]["CommandId"]

    status = "InProgress"
    stdout = ""
    stderr = ""
    for _ in range(15):
        time.sleep(2)
        try:
            inv = ssm_client.get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )
            status = inv.get("Status")
            stdout = inv.get("StandardOutputContent", "")
            stderr = inv.get("StandardErrorContent", "")
            if status in {"Success", "Failed", "TimedOut", "Cancelled"}:
                break
        except ClientError:
            continue

    return {
        "message": "update invoked",
        "command_id": command_id,
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "logs": _merge_logs(stdout, stderr),
    }


# ---------------------------------------------------------------------------
# SSM remote log helpers
# ---------------------------------------------------------------------------

def _merge_logs(stdout, stderr):
    """Combine stdout and stderr into a single chronological log string.
    Because SSM returns them as separate blobs (not interleaved), we append
    stderr after stdout with a separator if both are non-empty.
    """
    parts = [p for p in (stdout.strip(), stderr.strip()) if p]
    return "\n".join(parts)

def wait_for_command(command_id, instance_id, max_wait_seconds=30, delay_seconds=2):
    """Poll SSM until a command reaches a terminal status or the time budget is exhausted."""
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
        if invocation.get("Status", "InProgress") in {"Success", "Failed", "TimedOut", "Cancelled"}:
            return invocation
        time.sleep(delay_seconds)
    return last_invocation or {
        "Status": "InProgress",
        "StandardOutputContent": "",
        "StandardErrorContent": "",
    }


def read_ssm_log_chunk(instance_id, command_id, start_byte):
    """Read a chunk of SSM agent log output from the instance starting at start_byte.

    The remote script locates the SSM log file for *command_id* and streams bytes
    starting at *start_byte* via ``dd``.  Returns the raw SSM invocation dict;
    callers inspect ``StandardOutputContent``, ``Status``, and ``ResponseCode``.
    Exit code 3 from the remote script means the log file does not exist yet.
    """
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
    return wait_for_command(
        response["Command"]["CommandId"],
        instance_id,
        max_wait_seconds=30,
        delay_seconds=1,
    )


def _collect_ssm_agent_logs(instance_id, command_id, max_wait_seconds=120, delay_seconds=2):
    """Collect raw SSM log file content for *command_id*; used as a fallback when
    ``get_command_invocation`` returns empty output."""
    start = time.time()
    offset = 0
    accumulated = ""
    idle_polls = 0

    while time.time() - start < max_wait_seconds:
        invocation = read_ssm_log_chunk(instance_id, command_id, offset)
        status = invocation.get("Status", "InProgress")
        raw_stdout = invocation.get("StandardOutputContent", "")
        code = invocation.get("ResponseCode")

        if status == "Success" and raw_stdout:
            lines = raw_stdout.splitlines()
            payload = ""
            if lines and lines[0].startswith("__LOG_PATH__:"):
                payload = "\n".join(lines[1:])
                if raw_stdout.endswith("\n"):
                    payload += "\n"
            if payload:
                offset += len(payload.encode("utf-8"))
                accumulated += payload
                idle_polls = 0
            else:
                idle_polls += 1
        elif code == 3:
            # Log file not created yet; keep waiting.
            idle_polls += 1
        else:
            idle_polls += 1

        if accumulated and idle_polls >= 5:
            break

        time.sleep(delay_seconds)

    return accumulated


def collect_command_logs(command_id, instance_id, max_wait_seconds=900, delay_seconds=1):
    """Collect command output via ``get_command_invocation``, falling back to reading
    raw SSM log files when the API output is delayed.  Returns a result dict with
    keys ``command_id``, ``status``, ``stdout``, ``stderr``, and optionally
    ``hook_detected``.
    """
    start = time.time()
    stdout_len = 0
    stderr_len = 0
    raw_log_offset = 0
    idle_polls = 0
    accumulated_stdout = ""
    accumulated_stderr = ""
    hook_detected = None
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
            accumulated_stdout += chunk
            if SERVER_RUNNING_HOOK_PATTERN.search(chunk):
                hook_detected = "server_running"

        if stderr_grew:
            chunk = stderr[stderr_len:]
            stderr_len = len(stderr)
            accumulated_stderr += chunk
            if SERVER_RUNNING_HOOK_PATTERN.search(chunk):
                hook_detected = "server_running"

        if stdout_grew or stderr_grew:
            idle_polls = 0
        else:
            idle_polls += 1

        # When get_command_invocation output is delayed, read raw SSM log chunks.
        if idle_polls >= 2:
            raw_inv = read_ssm_log_chunk(instance_id, command_id, raw_log_offset)
            raw_stdout = raw_inv.get("StandardOutputContent", "")
            raw_status = raw_inv.get("Status", "")
            raw_code = raw_inv.get("ResponseCode")

            if raw_status == "Success" and raw_stdout:
                lines = raw_stdout.splitlines()
                payload = ""
                if lines and lines[0].startswith("__LOG_PATH__:"):
                    payload = "\n".join(lines[1:])
                    if raw_stdout.endswith("\n"):
                        payload += "\n"
                if payload:
                    accumulated_stdout += payload
                    raw_log_offset += len(payload.encode("utf-8"))
                    idle_polls = 0
                    if SERVER_RUNNING_HOOK_PATTERN.search(payload):
                        hook_detected = "server_running"
            elif raw_code == 3:
                pass  # log file not yet created; keep polling

        status = invocation.get("Status", "InProgress")
        if hook_detected == "server_running" or status in {"Success", "Failed", "TimedOut", "Cancelled"}:
            result = {
                "command_id": command_id,
                "status": status,
                "stdout": accumulated_stdout or stdout,
                "stderr": accumulated_stderr or stderr,
            }
            if hook_detected:
                result["hook_detected"] = hook_detected
            return result

        time.sleep(delay_seconds)

    inv = final_invocation or {}
    return {
        "command_id": command_id,
        "status": inv.get("Status", "InProgress"),
        "stdout": accumulated_stdout or inv.get("StandardOutputContent", ""),
        "stderr": accumulated_stderr or inv.get("StandardErrorContent", ""),
    }


def get_project_logs(name, command_id, start_byte=0):
    """Retrieve a chunk of SSM log output for a running command on the project's instance.

    This is intended for polling from the API after a ``start`` or ``update`` call
    returns a ``command_id``.
    """
    if not name:
        raise ValueError("name is required")
    if not command_id:
        raise ValueError("command_id is required")

    project = projects_table.get_item(Key={"name": name}).get("Item")
    if not project:
        raise ValueError(f"Project '{name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{name}' has no associated instance_id")
    validate_instance_id(instance_id)

    invocation = read_ssm_log_chunk(instance_id, command_id, start_byte)
    raw_stdout = invocation.get("StandardOutputContent", "")
    status = invocation.get("Status", "")
    code = invocation.get("ResponseCode")

    command_status = "Pending"
    command_response_code = None
    command_stderr = ""
    try:
        command_invocation = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        command_status = command_invocation.get("Status", "Pending")
        command_response_code = command_invocation.get("ResponseCode")
        command_stderr = command_invocation.get("StandardErrorContent", "")
    except ClientError:
        # Keep defaults while the invocation record is not yet readable.
        pass

    payload = ""
    if status == "Success" and raw_stdout:
        lines = raw_stdout.splitlines()
        if lines and lines[0].startswith("__LOG_PATH__:"):
            payload = "\n".join(lines[1:])
            if raw_stdout.endswith("\n"):
                payload += "\n"

    return {
        "logs": payload,
        "start_byte": start_byte,
        "next_byte": start_byte + len(payload.encode("utf-8")),
        "log_file_not_found": code == 3,
        "command_status": command_status,
        "command_response_code": command_response_code,
        "command_stderr": command_stderr,
    }


def start_project(name):
    """Start a stopped project's instance and bring the server back up."""
    if not name:
        raise ValueError("name is required")

    project = projects_table.get_item(Key={"name": name}).get("Item")
    if not project:
        raise ValueError(f"Project '{name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{name}' has no associated instance_id")
    validate_instance_id(instance_id)

    repo_url = project.get("repo_url")
    if not repo_url:
        raise ValueError("repo_url is required on the project to run start")
    validate_repo_url(repo_url)

    try:
        inst = ec2_client.describe_instances(InstanceIds=[instance_id])
        reservations = inst.get("Reservations", [])
        if not reservations or not reservations[0].get("Instances"):
            raise ValueError(f"Instance '{instance_id}' not found")
        state = reservations[0]["Instances"][0]["State"]["Name"]
    except ClientError as e:
        raise RuntimeError(f"Failed to check instance state: {e}")

    if state == "stopped":
        try:
            ec2_client.start_instances(InstanceIds=[instance_id])
        except ClientError as e:
            raise RuntimeError(f"Failed to start instance '{instance_id}': {e}")
    elif state in {"running", "pending"}:
        pass
    else:
        raise ValueError(
            f"Instance '{instance_id}' is in state '{state}', expected 'stopped' or 'running'"
        )

    # Wait until EC2 reports running.
    running = False
    for _ in range(45):
        time.sleep(4)
        try:
            inst = ec2_client.describe_instances(InstanceIds=[instance_id])
            reservations = inst.get("Reservations", [])
            if reservations and reservations[0].get("Instances"):
                current_state = reservations[0]["Instances"][0]["State"]["Name"]
                if current_state == "running":
                    running = True
                    break
        except ClientError:
            continue
    if not running:
        raise RuntimeError(f"Instance '{instance_id}' did not reach 'running' state")

    # Wait for SSM to become Online.
    online = False
    for _ in range(45):
        time.sleep(4)
        try:
            ssm_info = ssm_client.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            )
            info_list = ssm_info.get("InstanceInformationList", [])
            if info_list and info_list[0].get("PingStatus") == "Online":
                online = True
                break
        except ClientError:
            continue
    if not online:
        raise RuntimeError(
            f"Instance '{instance_id}' did not come back Online in SSM after start"
        )

    commands = [
        "set -e",
        f"PROJECT_NAME='{name}'",
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

    try:
        send_resp = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
        )
    except ClientError as e:
        raise RuntimeError(
            f"Failed to start server command: {e}. "
            "Confirm the instance is managed by SSM and currently Online."
        )

    command_id = send_resp["Command"]["CommandId"]

    result = collect_command_logs(command_id, instance_id)
    if not (result.get("stdout", "").strip() or result.get("stderr", "").strip()):
        raw_logs = _collect_ssm_agent_logs(instance_id, command_id)
        if raw_logs:
            result["stdout"] = raw_logs
    if result.get("status") == "InProgress" and result.get("hook_detected") != "server_running":
        final_inv = wait_for_command(command_id, instance_id, max_wait_seconds=1800, delay_seconds=2)
        result = {
            "command_id": command_id,
            "status": final_inv.get("Status", "InProgress"),
            "stdout": final_inv.get("StandardOutputContent", ""),
            "stderr": final_inv.get("StandardErrorContent", ""),
        }
    result["message"] = "start invoked"
    result["instance_id"] = instance_id
    result.setdefault("logs", _merge_logs(result.get("stdout", ""), result.get("stderr", "")))
    return result


# ---------------------------------------------------------------------------
# AWS helpers
# ---------------------------------------------------------------------------

def get_default_vpc_id():
    vpcs = ec2_client.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )
    if not vpcs["Vpcs"]:
        raise RuntimeError("No default VPC found.")
    return vpcs["Vpcs"][0]["VpcId"]


def get_or_create_security_group():
    """Return the eezy-ml security group ID, creating it if necessary."""
    try:
        resp = ec2_client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )
        if resp["SecurityGroups"]:
            return resp["SecurityGroups"][0]["GroupId"]
    except ClientError:
        pass

    vpc_id = get_default_vpc_id()
    resp = ec2_client.create_security_group(
        GroupName=SG_NAME,
        Description=SG_DESCRIPTION,
        VpcId=vpc_id,
    )
    sg_id = resp["GroupId"]

    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 5000,
                "ToPort": 5000,
                "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Flask server"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH access"}],
            },
        ],
    )

    ec2_client.create_tags(
        Resources=[sg_id],
        Tags=[
            {"Key": "Name", "Value": SG_NAME},
            {"Key": "Project", "Value": INSTANCE_TAG},
        ],
    )
    return sg_id


def get_latest_ami():
    """Get the latest Amazon Linux 2023 x86_64 AMI ID."""
    resp = ssm_client.get_parameter(
        Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    )
    return resp["Parameter"]["Value"]


# ---------------------------------------------------------------------------
# EC2 lifecycle
# ---------------------------------------------------------------------------

def _build_user_data(repo_url, github_token):
    """Build a cloud-init script that clones, builds and runs the container."""
    # Authenticated clone URL (token stripped from remote afterwards)
    auth_url = repo_url.replace("https://", f"https://{github_token}@")
    if not auth_url.endswith(".git"):
        auth_url += ".git"
    clean_url = repo_url if repo_url.endswith(".git") else repo_url + ".git"

    script = f"""#!/bin/bash
set -ex
exec > >(tee /var/log/user-data.log) 2>&1

echo "=== eezy-ml: bootstrapping ==="

# Install Docker & Git
dnf update -y
dnf install -y docker git

systemctl start docker
systemctl enable docker

# Clone private repo
git clone {auth_url} /app
cd /app
git remote set-url origin {clean_url}

# Build & run
docker build -t eezy-ml-model .
docker run -d -p 5000:5000 --restart unless-stopped --name eezy-ml eezy-ml-model

echo "=== eezy-ml: deployment complete ==="
"""
    return base64.b64encode(script.encode()).decode()


def deploy_instance(repo_url, instance_type="t3.medium"):
    """Launch an EC2 instance and deploy the ML container from *repo_url*."""
    validate_repo_url(repo_url)
    validate_instance_type(instance_type)

    github_token = get_github_token()
    sg_id = get_or_create_security_group()
    ami_id = get_latest_ami()
    user_data = _build_user_data(repo_url, github_token)

    resp = ec2_client.run_instances(
        ImageId=ami_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        UserData=user_data,
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "VolumeSize": 30,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                },
            }
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": f"eezy-ml-{repo_url.rstrip('/').split('/')[-1]}"},
                    {"Key": "Project", "Value": INSTANCE_TAG},
                    {"Key": "RepoUrl", "Value": repo_url},
                ],
            }
        ],
    )

    instance_id = resp["Instances"][0]["InstanceId"]
    return {
        "instance_id": instance_id,
        "status": "launching",
        "message": f"Instance is launching. Poll GET /status/{instance_id} until service_status is 'ready'.",
    }


def get_instance_info(instance_id):
    validate_instance_id(instance_id)
    resp = ec2_client.describe_instances(InstanceIds=[instance_id])
    if not resp["Reservations"] or not resp["Reservations"][0]["Instances"]:
        raise ValueError(f"Instance {instance_id} not found")
    return resp["Reservations"][0]["Instances"][0]


def get_instance_status(instance_id):
    instance = get_instance_info(instance_id)
    state = instance["State"]["Name"]
    public_ip = instance.get("PublicIpAddress")

    result = {
        "instance_id": instance_id,
        "state": state,
        "public_ip": public_ip,
        "instance_type": instance.get("InstanceType"),
    }

    if state == "running" and public_ip:
        try:
            req = urllib.request.Request(
                f"http://{public_ip}:5000/health", method="GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                result["service_status"] = "ready" if resp.status == 200 else "starting"
                result["inference_url"] = f"http://{public_ip}:5000/predict"
        except (urllib.error.URLError, OSError):
            result["service_status"] = "starting"
    elif state == "pending":
        result["service_status"] = "launching"
    else:
        result["service_status"] = state

    return result


def list_instances():
    resp = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Project", "Values": [INSTANCE_TAG]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "running", "stopping", "stopped"],
            },
        ]
    )

    instances = []
    for reservation in resp["Reservations"]:
        for inst in reservation["Instances"]:
            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
            instances.append(
                {
                    "instance_id": inst["InstanceId"],
                    "state": inst["State"]["Name"],
                    "public_ip": inst.get("PublicIpAddress"),
                    "instance_type": inst.get("InstanceType"),
                    "name": tags.get("Name", ""),
                    "repo_url": tags.get("RepoUrl", ""),
                    "launch_time": inst["LaunchTime"].isoformat(),
                }
            )

    return {"instances": instances}


def terminate_instance(instance_id):
    instance = get_instance_info(instance_id)
    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
    if tags.get("Project") != INSTANCE_TAG:
        raise ValueError(f"Instance {instance_id} is not an eezy-ml instance")

    ec2_client.terminate_instances(InstanceIds=[instance_id])
    return {
        "instance_id": instance_id,
        "status": "terminating",
        "message": f"Instance {instance_id} is being terminated.",
    }


def proxy_predict(instance_id, payload):
    """Forward a prediction request to the Flask server on the EC2 instance."""
    instance = get_instance_info(instance_id)
    state = instance["State"]["Name"]
    public_ip = instance.get("PublicIpAddress")

    if state != "running":
        raise RuntimeError(f"Instance is not running (state={state})")
    if not public_ip:
        raise RuntimeError("Instance has no public IP address")

    url = f"http://{public_ip}:5000/predict"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"Prediction failed ({e.code}): {error_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach instance: {e.reason}")


def get_project_status(project_name):
    """Get the status of a project's instance, including public IP and inference URL."""
    if not project_name:
        raise ValueError("project_name is required")

    project = projects_table.get_item(Key={"name": project_name}).get("Item")
    if not project:
        raise ValueError(f"Project '{project_name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{project_name}' has no associated instance_id")

    status = get_instance_status(instance_id)
    return {
        "project_name": project_name,
        "instance_id": instance_id,
        "state": status.get("state"),
        "public_ip": status.get("public_ip"),
        "instance_type": status.get("instance_type"),
        "service_status": status.get("service_status"),
        "inference_url": status.get("inference_url"),
    }


def predict_project(project_name, features):
    """Run one inference call for a project by resolving its instance first."""
    if not project_name:
        raise ValueError("project_name is required")
    if not isinstance(features, str) or not features.strip():
        raise ValueError("features is required and must be a non-empty string")

    project = projects_table.get_item(Key={"name": project_name}).get("Item")
    if not project:
        raise ValueError(f"Project '{project_name}' does not exist")

    instance_id = project.get("instance_id")
    if not instance_id:
        raise ValueError(f"Project '{project_name}' has no associated instance_id")

    result = proxy_predict(instance_id, {"features": features})
    return {
        "project_name": project_name,
        "instance_id": instance_id,
        "result": result,
    }
