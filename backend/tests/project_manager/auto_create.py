import argparse
import requests


def auto_create_project(
    api_url,
    name,
    repo_url,
    github_token,
    ami_id="ami-0a7300e10f97b6153",
    instance_type="g4dn.xlarge",
    storage_gb=80,
    market_type="on-demand",
):
    """Create a project and auto-provision an instance in one call."""
    url = f"{api_url}/project-manager/auto_create"
    payload = {
        "name": name,
        "repo_url": repo_url,
        "github_token": github_token,
        "ami_id": ami_id,
        "instance_type": instance_type,
        "storage_gb": storage_gb,
        "market_type": market_type,
    }
    return requests.post(url, json=payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Auto create project via API")
    parser.add_argument("name", help="Project name")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:3000", help="Base API URL"
    )
    parser.add_argument(
        "--repo-url",
        default="https://github.com/not-ekalabya/eezy-ml",
        help="GitHub repository URL",
    )
    parser.add_argument("--github-token", required=True, help="GitHub PAT")
    parser.add_argument(
        "--ami-id",
        default="ami-0a7300e10f97b6153",
        help="EC2 AMI ID (Ubuntu 24.04 LTS)",
    )
    parser.add_argument(
        "--instance-type", default="g4dn.xlarge", help="EC2 instance type"
    )
    parser.add_argument(
        "--storage-gb", type=int, default=80, help="Root EBS volume size in GB"
    )
    parser.add_argument(
        "--market-type",
        choices=["on-demand", "spot"],
        default="on-demand",
        help="EC2 market type",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    response = auto_create_project(
        api_url=args.api_url,
        name=args.name,
        repo_url=args.repo_url,
        github_token=args.github_token,
        ami_id=args.ami_id,
        instance_type=args.instance_type,
        storage_gb=args.storage_gb,
        market_type=args.market_type,
    )
    print(response.status_code)
    try:
        print(response.json())
    except ValueError:
        print(response.text)
