#!/usr/bin/env python3
"""
LinkedIn Parasite — Module 4: Auto-Post to LinkedIn
Reads the first draft from Destination Posts, publishes to LinkedIn via API,
and marks it as published. Optionally generates an AI image via fal.ai.

Usage:
    python3 execution/linkedin_parasite_post.py
    python3 execution/linkedin_parasite_post.py --dry-run
    python3 execution/linkedin_parasite_post.py --image /path/to/image.jpg
    python3 execution/linkedin_parasite_post.py --generate-image

Prerequisites:
    Run execution/linkedin_auth.py first to set up LinkedIn OAuth tokens.
    For --generate-image: FAL_KEY must be set in .env

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import re
import argparse
import logging
import requests
import tempfile
from datetime import datetime
from dotenv import load_dotenv

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv requests")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
LINKEDIN_POST_URL = 'https://api.linkedin.com/rest/posts'
LINKEDIN_IMAGES_URL = 'https://api.linkedin.com/rest/images'
LINKEDIN_API_VERSION = '202601'


def sanitize_error(error_str: str) -> str:
    """Remove API keys and sensitive data from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(token["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    return error_str


def get_google_creds():
    """Get Google OAuth credentials."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists('credentials.json'):
                logger.error("credentials.json not found")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds


def get_first_draft(service, sheet_id: str) -> dict:
    """Read the first draft post from Destination Posts tab."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='Destination Posts!A:G'
    ).execute()
    values = result.get('values', [])

    if len(values) <= 1:
        return {}

    headers = values[0]

    for row_idx, row in enumerate(values[1:], start=2):
        while len(row) < len(headers):
            row.append('')

        row_dict = dict(zip(headers, row))
        row_dict['_row_number'] = row_idx

        if row_dict.get('status', '').lower() == 'draft':
            return row_dict

    return {}


def count_drafts(service, sheet_id: str) -> int:
    """Count remaining draft posts."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='Destination Posts!E:E'
    ).execute()
    values = result.get('values', [])
    return sum(1 for row in values[1:] if row and row[0].lower() == 'draft')


def generate_image_prompt(post_content: str) -> str:
    """Create an image generation prompt from the LinkedIn post content."""
    # Use Azure OpenAI to create a good image prompt from the post
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')

    if azure_endpoint and azure_key:
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version="2024-12-01-preview"
            )
            deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": (
                        "You create image generation prompts for LinkedIn posts. "
                        "Generate a single, concise prompt for a professional, modern illustration "
                        "that complements the post content. The image should be clean, minimal, "
                        "and suitable for a business audience. No text in the image. "
                        "Output ONLY the prompt, nothing else."
                    )},
                    {"role": "user", "content": f"Create an image prompt for this LinkedIn post:\n\n{post_content}"}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"  AI prompt generation failed: {sanitize_error(str(e))}")

    # Fallback: extract key topic for a generic prompt
    words = post_content[:200].split()[:10]
    topic = ' '.join(words)
    return f"Professional minimalist illustration about {topic}, modern business style, clean design, no text"


def generate_ai_image(post_content: str) -> str:
    """Generate an AI image using fal.ai Flux Pro and return the image URL."""
    fal_key = os.getenv('FAL_KEY')
    if not fal_key:
        logger.error("  FAL_KEY not found in .env")
        return ""

    try:
        import fal_client
    except ImportError:
        logger.error("  fal-client not installed. Run: pip install fal-client")
        return ""

    os.environ['FAL_KEY'] = fal_key

    logger.info("  Generating image prompt from post content...")
    image_prompt = generate_image_prompt(post_content)
    logger.info(f"  Image prompt: {image_prompt[:100]}...")

    logger.info("  Generating image via fal.ai Flux Pro...")
    try:
        result = fal_client.subscribe("fal-ai/flux-pro/v1.1", arguments={
            "prompt": image_prompt,
            "image_size": "landscape_4_3",
            "num_images": 1,
            "output_format": "jpeg",
            "guidance_scale": 3.5,
        })

        if result and 'images' in result and len(result['images']) > 0:
            image_url = result['images'][0]['url']
            logger.info(f"  Image generated: {image_url[:80]}...")
            return image_url
        else:
            logger.error("  fal.ai returned no images")
            return ""
    except Exception as e:
        logger.error(f"  fal.ai image generation failed: {str(e)[:200]}")
        return ""


def download_image(image_source: str) -> str:
    """Download an image from URL or verify local file. Returns local file path."""
    if image_source.startswith('http'):
        logger.info("  Downloading image...")
        response = requests.get(image_source, timeout=30)
        if response.status_code != 200:
            logger.error(f"  Failed to download image: HTTP {response.status_code}")
            return ""

        ext = '.jpg'
        content_type = response.headers.get('content-type', '')
        if 'png' in content_type:
            ext = '.png'

        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(response.content)
        tmp.close()
        logger.info(f"  Downloaded ({len(response.content) / 1024:.0f} KB)")
        return tmp.name
    else:
        if os.path.exists(image_source):
            return image_source
        logger.error(f"  Image file not found: {image_source}")
        return ""


def upload_image_to_linkedin(access_token: str, person_urn: str, image_path: str) -> str:
    """Upload an image to LinkedIn and return the image URN."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'LinkedIn-Version': LINKEDIN_API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }

    # Step 1: Initialize upload
    logger.info("  Initializing LinkedIn image upload...")
    init_body = {
        "initializeUploadRequest": {
            "owner": person_urn
        }
    }

    response = requests.post(
        f"{LINKEDIN_IMAGES_URL}?action=initializeUpload",
        headers=headers,
        json=init_body,
        timeout=30
    )

    if response.status_code != 200:
        error_msg = sanitize_error(response.text)
        logger.error(f"  Image upload init failed: HTTP {response.status_code}: {error_msg}")
        return ""

    data = response.json().get('value', {})
    upload_url = data.get('uploadUrl', '')
    image_urn = data.get('image', '')

    if not upload_url or not image_urn:
        logger.error("  No upload URL returned from LinkedIn")
        return ""

    # Step 2: Upload binary
    logger.info("  Uploading image binary to LinkedIn...")
    with open(image_path, 'rb') as f:
        image_data = f.read()

    upload_headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream',
    }

    response = requests.put(
        upload_url,
        headers=upload_headers,
        data=image_data,
        timeout=60
    )

    if response.status_code in (200, 201):
        logger.info(f"  Image uploaded: {image_urn}")
        return image_urn
    else:
        error_msg = sanitize_error(response.text)
        logger.error(f"  Image binary upload failed: HTTP {response.status_code}: {error_msg}")
        return ""


def post_to_linkedin(access_token: str, person_urn: str, content: str,
                     image_urn: str = "") -> dict:
    """Post content to LinkedIn via the REST API, optionally with an image."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'LinkedIn-Version': LINKEDIN_API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }

    body = {
        "author": person_urn,
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED"
    }

    if image_urn:
        body["content"] = {
            "media": {
                "id": image_urn
            }
        }

    response = requests.post(
        LINKEDIN_POST_URL,
        headers=headers,
        json=body,
        timeout=30
    )

    if response.status_code in (200, 201):
        post_urn = response.headers.get('x-restli-id', '')
        return {'success': True, 'post_urn': post_urn}
    else:
        error_msg = sanitize_error(response.text)
        return {'success': False, 'error': f"HTTP {response.status_code}: {error_msg}"}


def mark_as_published(service, sheet_id: str, row_number: int):
    """Update the status to 'published' and set published_at timestamp."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Update status (column E) and published_at (column G)
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            'valueInputOption': 'RAW',
            'data': [
                {
                    'range': f'Destination Posts!E{row_number}',
                    'values': [['published']]
                },
                {
                    'range': f'Destination Posts!G{row_number}',
                    'values': [[now]]
                }
            ]
        }
    ).execute()


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Parasite — Post to LinkedIn')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be posted without actually posting')
    parser.add_argument('--image', type=str, default='',
                        help='Path to a local image file or URL to attach to the post')
    parser.add_argument('--generate-image', action='store_true',
                        help='Auto-generate an AI image via fal.ai that matches the post content')
    args = parser.parse_args()

    # Validate
    sheet_id = os.getenv('LINKEDIN_PARASITE_SHEET_ID')
    if not sheet_id:
        logger.error("LINKEDIN_PARASITE_SHEET_ID not found in .env")
        sys.exit(1)

    access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
    person_urn = os.getenv('LINKEDIN_PERSON_URN')

    if not args.dry_run and (not access_token or not person_urn):
        logger.error("LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN must be set in .env")
        logger.error("Run: python3 execution/linkedin_auth.py")
        sys.exit(1)

    logger.info("LinkedIn Parasite — Module 4: Post to LinkedIn")
    logger.info("=" * 50)

    if args.dry_run:
        logger.info("[DRY RUN MODE — nothing will be posted]")
        logger.info("")

    # Initialize Google Sheets
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)

    # Get first draft
    draft = get_first_draft(service, sheet_id)
    if not draft:
        logger.info("No draft posts available. Run Module 3 to generate content.")
        return

    content = draft.get('generated_content', '')
    dest_id = draft.get('dest_id', '')
    source_url = draft.get('source_post_url', '')
    row_number = draft['_row_number']

    logger.info(f"Draft found: {dest_id}")
    logger.info(f"  Source: {source_url}")
    logger.info(f"  Length: {len(content)} chars")
    logger.info(f"  Preview: {content[:150]}...")
    logger.info("")

    # Handle image generation or provided image
    image_source = args.image
    if args.generate_image and not image_source:
        logger.info("Generating AI image for this post...")
        image_source = generate_ai_image(content)
        if not image_source:
            logger.warning("  Image generation failed. Posting without image.")
        logger.info("")

    if args.dry_run:
        logger.info("Full post content:")
        logger.info("-" * 40)
        logger.info(content)
        logger.info("-" * 40)
        if image_source:
            logger.info(f"\nImage: {image_source}")
        else:
            logger.info("\nNo image attached.")

        remaining = count_drafts(service, sheet_id) - 1
        logger.info(f"\n{remaining} more drafts in queue")
        return

    # Upload image to LinkedIn if provided
    image_urn = ""
    if image_source:
        logger.info("Preparing image for LinkedIn...")
        local_path = download_image(image_source)
        if local_path:
            image_urn = upload_image_to_linkedin(access_token, person_urn, local_path)
            # Clean up temp file if we downloaded it
            if local_path != image_source and os.path.exists(local_path):
                os.unlink(local_path)
            if image_urn:
                logger.info(f"  Image ready: {image_urn}")
            else:
                logger.warning("  Image upload failed. Posting without image.")
        logger.info("")

    # Post to LinkedIn
    logger.info("Posting to LinkedIn...")
    result = post_to_linkedin(access_token, person_urn, content, image_urn)

    if result['success']:
        post_type = "with image" if image_urn else "text only"
        logger.info(f"Posted successfully ({post_type})! URN: {result.get('post_urn', 'N/A')}")

        # Update sheet
        mark_as_published(service, sheet_id, row_number)
        logger.info("Sheet updated: status -> published")

        remaining = count_drafts(service, sheet_id)
        logger.info(f"\n{remaining} drafts remaining in queue")
    else:
        logger.error(f"Failed to post: {result['error']}")
        logger.error("Post was NOT published. Draft remains in queue.")

        # Check for common errors
        if '401' in str(result.get('error', '')):
            logger.error("\nToken may be expired. Re-run: python3 execution/linkedin_auth.py")
        elif '403' in str(result.get('error', '')):
            logger.error("\nMissing permissions. Ensure 'Share on LinkedIn' product is added to your app.")


if __name__ == '__main__':
    main()
