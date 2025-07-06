import base64
import requests
import os
import json
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load API Key from .env
load_dotenv()

app = FastAPI()

CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL")
ORG_ID = os.getenv("ORG_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Your Gemini API Key

@app.get("/process_confluence/")
def process_confluence_page(confluence_url: str = Query(..., description="Full Confluence Page URL")):
    try:
        # Extract page ID from URL
        if "/pages/" not in confluence_url:
            raise HTTPException(status_code=400, detail="Invalid Confluence URL format")

        page_id = confluence_url.split("/pages/")[1].split("/")[0]

        # Step 1: Fetch Confluence Page Content
        api_url = f"https://aicolumbus6.atlassian.net/wiki/rest/api/content/{page_id}?expand=body.storage"

        response = requests.get(api_url, auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
                                headers={"Accept": "application/json"})

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code,
                                detail=f"Failed to fetch Confluence page: {response.text}")

        page_data = response.json()
        html_content = page_data.get("body", {}).get("storage", {}).get("value", "")

        # Step 2: Extract PNG from <ac:image>
        soup = BeautifulSoup(html_content, "html.parser")
        image_tag = soup.find("ac:image")
        attachment_tag = image_tag.find("ri:attachment") if image_tag else None

        if not attachment_tag or not attachment_tag.get("ri:filename", "").lower().endswith(".png"):
            raise HTTPException(status_code=404, detail="No PNG image attachment found on the Confluence page")

        filename = attachment_tag["ri:filename"]

        # Fetch Attachment Metadata
        attachment_api_url = f"https://aicolumbus6.atlassian.net/wiki/rest/api/content/{page_id}/child/attachment?filename={filename}"
        attach_resp = requests.get(attachment_api_url, auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN))

        if attach_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch attachment metadata")

        attachments = attach_resp.json().get("results", [])
        if not attachments:
            raise HTTPException(status_code=404, detail="Attachment not found in Confluence")

        attachment_id = attachments[0]["id"]
        download_api_url = f"https://aicolumbus6.atlassian.net/wiki/rest/api/content/{page_id}/child/attachment/{attachment_id}/download"

        # Download Image with Redirect Handling
        image_response = requests.get(
            download_api_url,
            auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
            headers={"Accept": "*/*"},
            allow_redirects=True
        )

        if image_response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to download image attachment: {image_response.text}")

        content_type = image_response.headers.get("Content-Type", "")
        if "image" not in content_type:
            raise HTTPException(status_code=500, detail="Downloaded content is not an image")

        img_b64 = base64.b64encode(image_response.content).decode()

        # Step 5: Send to Gemini (Your Full Structured Prompt)
        prompt = """
        You are an expert Enterprise Architect. Analyze the provided system architecture diagram. From the diagram, extract the following:

        1. **Mermaid** (The code must follow these specific formatting rules:
        - DO NOT include word Mermaid or ```mermaid or other wrappers in the output. The code block should start with graph TD (instead of Mermaid title)
        - Include a comment line with the group name before each subgraph, e.g., %% Digital Channels.
        - The subgraph name itself must be in double quotes, e.g., subgraph "Digital Channels".
        - Application node definitions must not have double quotes around the title, e.g., PBCP[Private Banking Client Portal].
        - Include a %% Connections comment before listing the relationships.
        - Relationships between systems must be represented in [Source System Code] -->|[Relationship Type]| [Target System Code] format. For example: APP001 -->|API| APP002.
        - Remove any special characters like - or hyphen from the relationship type in [Source System Code] -->|[Relationship Type]| [Target System Code].
        - Exclude <br> or </br> tags from the code.)
        2. **Summary** (max 50 words)
        3. **Description** (max 200 words)
        """

        gemini_resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                        ]
                    }
                ]
            },
        )

        if gemini_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Gemini API Error: {gemini_resp.text}")

        result = gemini_resp.json()
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))