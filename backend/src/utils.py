"""utils.py — EC2 instance management for eezy-ml deployments."""

import os
import re
import json
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

ALLOWED_INSTANCE_TYPES = {
    "t2.micro", "t2.small", "t2.medium", "t2.large",
    "t3.micro", "t3.small", "t3.medium", "t3.large",
    "t3a.micro", "t3a.small", "t3a.medium", "t3a.large",
    "m5.large", "m5.xlarge",
    "c5.large", "c5.xlarge",
}

ec2_client = boto3.client("ec2", region_name="us-east-1")
ssm_client = boto3.client("ssm", region_name="us-east-1")


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