"""
LinkedIn Parasite — Daily Auto-Poster (Modal Serverless)
Posts one draft from Google Sheets to LinkedIn with an AI-generated image.

Schedule: Daily at 10 AM ICT (3 AM UTC)

Deploy:
    python3 -m modal deploy modal_workflows/linkedin_parasite_daily.py

Test manually:
    python3 -m modal run modal_workflows/linkedin_parasite_daily.py

View logs:
    python3 -m modal app logs linkedin-parasite --follow
"""

import modal

app = modal.App("linkedin-parasite")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "requests",
        "openai",
        "fal-client",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
    )
)

LINKEDIN_POST_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_IMAGES_URL = "https://api.linkedin.com/rest/images"
LINKEDIN_API_VERSION = "202601"


@app.function(
    image=image,
    schedule=modal.Cron("0 3 * * *"),  # 3 AM UTC = 10 AM ICT (UTC+7)
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=300,  # 5 minutes max
)
def post_linkedin_daily():
    """Post one draft to LinkedIn with an AI-generated image."""
    import os
    import re
    import json
    import tempfile
    import requests
    from datetime import datetime
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    print(f"LinkedIn Parasite — Daily Post")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    # Load config from Modal secrets
    sheet_id = os.environ.get("LINKEDIN_PARASITE_SHEET_ID")
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    person_urn = os.environ.get("LINKEDIN_PERSON_URN")
    fal_key = os.environ.get("FAL_KEY")
    token_json_str = os.environ.get("GMAIL_TOKEN_JSON")

    if not all([sheet_id, access_token, person_urn, token_json_str]):
        missing = []
        if not sheet_id: missing.append("LINKEDIN_PARASITE_SHEET_ID")
        if not access_token: missing.append("LINKEDIN_ACCESS_TOKEN")
        if not person_urn: missing.append("LINKEDIN_PERSON_URN")
        if not token_json_str: missing.append("GMAIL_TOKEN_JSON")
        print(f"Missing secrets: {', '.join(missing)}")
        return {"status": "error", "error": f"Missing secrets: {', '.join(missing)}"}

    # Initialize Google Sheets
    print("Connecting to Google Sheets...")
    token_data = json.loads(token_json_str)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        print("Refreshing Google token...")
        creds.refresh(Request())

    service = build("sheets", "v4", credentials=creds)

    # Get first draft
    print("Reading first draft from Destination Posts...")
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Destination Posts!A:G"
    ).execute()
    values = result.get("values", [])

    draft = {}
    if len(values) > 1:
        headers = values[0]
        for row_idx, row in enumerate(values[1:], start=2):
            while len(row) < len(headers):
                row.append("")
            row_dict = dict(zip(headers, row))
            row_dict["_row_number"] = row_idx
            if row_dict.get("status", "").lower() == "draft":
                draft = row_dict
                break

    if not draft:
        print("No draft posts available. Nothing to post.")
        return {"status": "no_drafts"}

    content = draft.get("generated_content", "")
    dest_id = draft.get("dest_id", "")
    row_number = draft["_row_number"]

    print(f"Draft found: {dest_id}")
    print(f"  Length: {len(content)} chars")
    print(f"  Preview: {content[:120]}...")

    # Generate AI image
    image_urn = ""
    if fal_key:
        print("\nGenerating AI image...")
        image_url = _generate_ai_image(content, fal_key)
        if image_url:
            print(f"  Image generated: {image_url[:80]}...")
            image_urn = _upload_image_to_linkedin(
                access_token, person_urn, image_url
            )
            if image_urn:
                print(f"  Image uploaded: {image_urn}")
            else:
                print("  Image upload to LinkedIn failed. Posting without image.")
        else:
            print("  Image generation failed. Posting without image.")
    else:
        print("FAL_KEY not set. Posting without image.")

    # Post to LinkedIn
    print("\nPosting to LinkedIn...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    body = {
        "author": person_urn,
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
    }

    if image_urn:
        body["content"] = {"media": {"id": image_urn}}

    response = requests.post(
        LINKEDIN_POST_URL, headers=headers, json=body, timeout=30
    )

    if response.status_code in (200, 201):
        post_urn = response.headers.get("x-restli-id", "")
        post_type = "with image" if image_urn else "text only"
        print(f"Posted successfully ({post_type})! URN: {post_urn}")

        # Mark as published
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"Destination Posts!E{row_number}", "values": [["published"]]},
                    {"range": f"Destination Posts!G{row_number}", "values": [[now]]},
                ],
            },
        ).execute()
        print("Sheet updated: status -> published")

        # Count remaining
        remaining_result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="Destination Posts!E:E"
        ).execute()
        remaining_values = remaining_result.get("values", [])
        remaining = sum(1 for row in remaining_values[1:] if row and row[0].lower() == "draft")
        print(f"\n{remaining} drafts remaining in queue")

        return {
            "status": "success",
            "post_urn": post_urn,
            "post_type": post_type,
            "dest_id": dest_id,
            "remaining_drafts": remaining,
            "timestamp": now,
        }
    else:
        error_text = re.sub(
            r'(bearer\s+)[a-zA-Z0-9_\-\.]+',
            r'\1[REDACTED]',
            response.text,
            flags=re.IGNORECASE,
        )
        print(f"Failed to post: HTTP {response.status_code}: {error_text}")

        if response.status_code == 401:
            print("Token may be expired. Re-run linkedin_auth.py and update Modal secrets.")
        elif response.status_code == 403:
            print("Missing permissions. Ensure 'Share on LinkedIn' product is added to your app.")

        return {
            "status": "error",
            "error": f"HTTP {response.status_code}",
            "dest_id": dest_id,
        }


def _generate_ai_image(post_content: str, fal_key: str) -> str:
    """Generate an AI image using fal.ai Flux Pro."""
    import os

    # Generate image prompt using Azure OpenAI
    image_prompt = _create_image_prompt(post_content)
    print(f"  Image prompt: {image_prompt[:100]}...")

    os.environ["FAL_KEY"] = fal_key

    try:
        import fal_client

        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": image_prompt,
                "image_size": "landscape_4_3",
                "num_images": 1,
                "output_format": "jpeg",
                "guidance_scale": 3.5,
            },
        )

        if result and "images" in result and len(result["images"]) > 0:
            return result["images"][0]["url"]
        return ""
    except Exception as e:
        print(f"  fal.ai error: {str(e)[:200]}")
        return ""


def _create_image_prompt(post_content: str) -> str:
    """Create an image generation prompt from post content."""
    import os

    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    azure_key = os.environ.get("AZURE_OPENAI_API_KEY")

    if azure_endpoint and azure_key:
        try:
            from openai import AzureOpenAI

            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version="2024-12-01-preview",
            )
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You create image generation prompts for LinkedIn posts. "
                            "Generate a single, concise prompt for a professional, modern illustration "
                            "that complements the post content. The image should be clean, minimal, "
                            "and suitable for a business audience. No text in the image. "
                            "Output ONLY the prompt, nothing else."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Create an image prompt for this LinkedIn post:\n\n{post_content}",
                    },
                ],
                temperature=0.7,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  AI prompt generation failed: {str(e)[:100]}")

    # Fallback
    words = post_content[:200].split()[:10]
    topic = " ".join(words)
    return f"Professional minimalist illustration about {topic}, modern business style, clean design, no text"


def _upload_image_to_linkedin(access_token: str, person_urn: str, image_url: str) -> str:
    """Download image, upload to LinkedIn, return image URN."""
    import requests
    import tempfile

    # Download image
    try:
        resp = requests.get(image_url, timeout=30)
        if resp.status_code != 200:
            print(f"  Failed to download image: HTTP {resp.status_code}")
            return ""
    except Exception as e:
        print(f"  Image download error: {str(e)[:100]}")
        return ""

    image_data = resp.content
    print(f"  Downloaded ({len(image_data) / 1024:.0f} KB)")

    # Initialize LinkedIn upload
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    init_body = {"initializeUploadRequest": {"owner": person_urn}}
    response = requests.post(
        f"{LINKEDIN_IMAGES_URL}?action=initializeUpload",
        headers=headers,
        json=init_body,
        timeout=30,
    )

    if response.status_code != 200:
        print(f"  Image upload init failed: HTTP {response.status_code}")
        return ""

    data = response.json().get("value", {})
    upload_url = data.get("uploadUrl", "")
    image_urn = data.get("image", "")

    if not upload_url or not image_urn:
        print("  No upload URL returned from LinkedIn")
        return ""

    # Upload binary
    upload_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
    }
    response = requests.put(
        upload_url, headers=upload_headers, data=image_data, timeout=60
    )

    if response.status_code in (200, 201):
        return image_urn
    else:
        print(f"  Image binary upload failed: HTTP {response.status_code}")
        return ""


@app.local_entrypoint()
def main():
    """
    Run manually: python3 -m modal run modal_workflows/linkedin_parasite_daily.py
    """
    print("Manual trigger — LinkedIn Parasite Daily Post")
    result = post_linkedin_daily.remote()
    print(f"\nResult: {result}")
