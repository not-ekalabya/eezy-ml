import argparse
import requests


def auto_delete_project(api_url, name):
    """Terminate project instance and remove project record in one call."""
    url = f"{api_url}/project-manager/auto_delete"
    payload = {"name": name}
    return requests.post(url, json=payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Auto delete a project via API")
    parser.add_argument("name", help="Project name")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:3000", help="Base API URL"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    response = auto_delete_project(args.api_url, args.name)
    print(response.status_code)
    try:
        print(response.json())
    except ValueError:
        print(response.text)
