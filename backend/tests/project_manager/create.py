import argparse
import requests


def create_project(api_url, name, repo_url, github_token, instance_id):
    """
    Create a project via POST request to the project manager API.

    Args:
        api_url: Base API URL (e.g., "https://api.example.com")
        name: Project name
        repo_url: GitHub repository URL
        github_token: GitHub personal access token
        instance_id: AWS instance ID

    Returns:
        Response object from the API
    """
    url = f"{api_url}/project-manager/create"

    payload = {
        "name": name,
        "repo_url": repo_url,
        "github_token": github_token,
        "instance_id": instance_id,
    }

    return requests.post(url, json=payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Create a project via API")
    parser.add_argument("name", help="Project name")
    parser.add_argument("instance_id", help="Associated EC2 instance ID")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:3000", help="Base API URL"
    )
    parser.add_argument(
        "--repo-url",
        default="https://github.com/not-ekalabya/eezy-ml",
        help="GitHub repository URL",
    )
    parser.add_argument("--github-token", required=True, help="GitHub PAT")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    response = create_project(
        api_url=args.api_url,
        name=args.name,
        repo_url=args.repo_url,
        github_token=args.github_token,
        instance_id=args.instance_id,
    )
    print(response.status_code)
    try:
        print(response.json())
    except ValueError:
        print(response.text)
