import base64
import requests
import os

# Load image and encode as base64
def load_image_as_base64(image_path):
    with open(image_path, 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_image

# Send image to Claude Sonnet for summarization
def summarize_image_with_claude(image_base64, anthropic_api_key):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-3-5-sonnet-latest",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": "Please summarize the contents of this image."
                    }
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()['content'][0]['text']

# Save summary to file
def save_summary_to_file(summary, filename):
    with open(filename, 'w') as f:
        f.write(summary)

# Push file to GitHub
def push_to_github(repo_owner, repo_name, file_path, commit_message, github_token):
    with open(file_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode('utf-8')

    file_name = os.path.basename(file_path)
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents/architecture_repository/diagram_to_code/{file_name}'

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Check if file exists
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json()['sha']
        data = {
            "message": commit_message,
            "content": content,
            "sha": sha
        }
    else:
        data = {
            "message": commit_message,
            "content": content
        }

    put_response = requests.put(url, headers=headers, json=data)
    if put_response.status_code in [200, 201]:
        print("File successfully committed to GitHub.")
    else:
        print("GitHub commit failed:", put_response.json())

# Main logic
if __name__ == '__main__':
    image_path = r'C:\Users\sourav\Downloads\Sample_Migration_Diagram_v2.drawio.png'
    github_token = ''
    anthropic_api_key = 'your_anthropic_api_key_here'

    image_base64 = load_image_as_base64(image_path)
    summary = summarize_image_with_claude(image_base64, anthropic_api_key)

    summary_filename = 'image_summary.txt'
    save_summary_to_file(summary, summary_filename)

    push_to_github(
        repo_owner='eilsvad',
        repo_name='GenAI',
        file_path=summary_filename,
        commit_message='Add image summary from Claude Sonnet',
        github_token=github_token
    )
