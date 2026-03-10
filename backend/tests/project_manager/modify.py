import requests

def modify_project(api_url, name, repo_url, github_token, instance_id):
    """
    Create a project via POST request to the project manager API.
    
    Args:
        api_url: Base API URL (e.g., 'https://api.example.com')
        name: Project name
        repo_url: GitHub repository URL
        github_token: GitHub personal access token
        instance_id: AWS instance ID
    
    Returns:
        Response object from the API
    """
    url = f"{api_url}/project-manager/modify"
    
    payload = {
        "name": name,
        "repo_url": repo_url,
        "github_token": github_token,
        "instance_id": instance_id
    }
    
    response = requests.post(url, json=payload)
    return response


# Example usage
if __name__ == "__main__":
    api_url = "http://127.0.0.1:3000"
    response = modify_project(
        api_url=api_url,
        name="demo",
        repo_url="https://github.com/not-ekalabya/eezy-ml",
        github_token="sample_github_token_2",
        instance_id="i-123456789abcdef0"
    )
    print(response.status_code)
    print(response.json())