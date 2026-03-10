import sys
import requests

def delete_project(api_url, name):
    """
    Delete a project via POST request to the project manager API.
    
    Args:
        api_url: Base API URL (e.g., 'https://api.example.com')
        name: Project name
    
    Returns:
        Response object from the API
    """
    url = f"{api_url}/project-manager/delete"
    
    payload = {
        "name": name,
    }
    
    response = requests.post(url, json=payload)
    return response


# Example usage
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete.py <project_name>")
        sys.exit(1)
    
    api_url = "http://127.0.0.1:3000"
    project_name = sys.argv[1]
    
    response = delete_project(
        api_url=api_url,
        name=project_name,
    )
    print(response.status_code)
    print(response.json())