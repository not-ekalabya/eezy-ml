import argparse
import requests


def start_project(api_url, project_name):
    """
    Trigger start for a project by hitting /projects/<project-name>/start.

    Args:
        api_url: Base API URL (e.g., "https://api.example.com")
        project_name: Name of the project to start

    Returns:
        Response object from the API
    """
    url = f"{api_url}/projects/{project_name}/start"
    return requests.post(url)


def parse_args():
    parser = argparse.ArgumentParser(description="Call project start endpoint.")
    parser.add_argument("project_name", help="Project name")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:3000", help="Base API URL"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    resp = start_project(args.api_url, args.project_name)
    print(resp.status_code)
    try:
        print(resp.json())
    except ValueError:
        print(resp.text)
