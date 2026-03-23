#!/usr/bin/env python3
"""
LinkedIn Parasite — Combined Orchestrator
Runs the full pipeline: Init → Scrape → Generate → Post

Usage:
    # Full pipeline (all 4 modules)
    python3 execution/linkedin_parasite.py --keyword "B2B sales" --min-likes 100

    # Skip init (already have creators), just scrape → generate → post
    python3 execution/linkedin_parasite.py --skip-init

    # Generate + post only (already have source posts)
    python3 execution/linkedin_parasite.py --skip-init --skip-scrape

    # Just post the next draft
    python3 execution/linkedin_parasite.py --post-only

    # Dry run (see what would be posted)
    python3 execution/linkedin_parasite.py --post-only --dry-run

    # Full pipeline with custom settings
    python3 execution/linkedin_parasite.py --keyword "outbound" --min-likes 50 --max-results 300 --max-generate 10

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import re
import uuid
import time
import argparse
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from dotenv import load_dotenv

try:
    from apify_client import ApifyClient
    import requests
    from openai import AzureOpenAI
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install apify-client requests openai google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
APIFY_ACTOR_KEYWORD_SEARCH = 'buIWk2uOUzTmcLsuB'
APIFY_ACTOR_PROFILE_SCRAPER = 'A3cAPGpwBEG8RJwse'
SHEET_NAME = 'LinkedIn Parasite System'
LINKEDIN_POST_URL = 'https://api.linkedin.com/rest/posts'
LINKEDIN_API_VERSION = '202601'
MAX_RETRIES = 3
RETRY_BACKOFF = 2

CREATORS_HEADERS = ['linkedin_url', 'name', 'headline', 'sample_post_likes', 'added_date']
SOURCE_POSTS_HEADERS = ['post_id', 'post_url', 'content', 'creator_url', 'posted_at',
                        'image_url_1', 'image_url_2', 'image_url_3', 'scraped_at', 'processed']
DEST_POSTS_HEADERS = ['dest_id', 'source_post_id', 'source_post_url',
                      'generated_content', 'status', 'generated_at', 'published_at']


# ============================================================================
# UTILITIES
# ============================================================================

def sanitize_error(error_str: str) -> str:
    """Remove API keys and sensitive data from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(r'(api[_-]?key["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(apify_api_[a-zA-Z0-9_\-\.]+)', r'[REDACTED_APIFY_KEY]', error_str)
    error_str = re.sub(r'(token["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    return error_str


def get_google_creds():
    """Get Google OAuth credentials (reuse existing token.json)."""
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
                logger.error("credentials.json not found. Cannot access Google Sheets.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds


def update_env(key: str, value: str):
    """Update or add a key in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()
        pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f'{key}={value}', content)
        else:
            content = content.rstrip('\n') + f'\n{key}={value}\n'
        with open(env_path, 'w') as f:
            f.write(content)


def load_tone_examples() -> str:
    """Load tone of voice examples from the directive file."""
    tone_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'directives', 'linkedin_parasite_tone.md'),
        'directives/linkedin_parasite_tone.md',
    ]
    for path in tone_paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if '[REPLACE WITH YOUR POST]' in content:
                return ""
            return content
    return ""


# ============================================================================
# GOOGLE SHEETS HELPERS
# ============================================================================

def get_or_create_spreadsheet(service, drive_service):
    """Get existing spreadsheet or create a new one with all 3 tabs."""
    sheet_id = os.getenv('LINKEDIN_PARASITE_SHEET_ID')

    if sheet_id:
        try:
            service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            return sheet_id
        except HttpError:
            logger.warning("Sheet ID in .env is invalid. Creating new spreadsheet...")

    spreadsheet = service.spreadsheets().create(
        body={'properties': {'title': SHEET_NAME}},
        fields='spreadsheetId,spreadsheetUrl'
    ).execute()

    sheet_id = spreadsheet.get('spreadsheetId')
    sheet_url = spreadsheet.get('spreadsheetUrl')
    logger.info(f"  Created spreadsheet: {sheet_url}")

    # Create tabs
    batch_requests = [
        {"updateSheetProperties": {"properties": {"sheetId": 0, "title": "Creators"}, "fields": "title"}},
        {"addSheet": {"properties": {"title": "Source Posts"}}},
        {"addSheet": {"properties": {"title": "Destination Posts"}}}
    ]
    service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={'requests': batch_requests}).execute()

    # Write headers
    headers_map = {
        'Creators!A1': [CREATORS_HEADERS],
        'Source Posts!A1': [SOURCE_POSTS_HEADERS],
        'Destination Posts!A1': [DEST_POSTS_HEADERS]
    }
    for range_name, values in headers_map.items():
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=range_name,
            valueInputOption='RAW', body={'values': values}
        ).execute()

    # Format headers (bold + freeze + color)
    metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheet_ids = [s['properties']['sheetId'] for s in metadata.get('sheets', [])]

    format_requests = []
    for sid in sheet_ids:
        format_requests.extend([
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
                    }},
                    "fields": "userEnteredFormat(textFormat,backgroundColor)"
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount"
                }
            }
        ])
    service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={'requests': format_requests}).execute()

    # Make publicly viewable
    drive_service.permissions().create(
        fileId=sheet_id, body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    update_env('LINKEDIN_PARASITE_SHEET_ID', sheet_id)
    logger.info(f"  Sheet ID saved to .env")

    return sheet_id


# ============================================================================
# MODULE 1: FIND VIRAL CREATORS
# ============================================================================

def module_1_init(apify_client, service, sheet_id, keyword, min_likes, max_results):
    """Find viral creators via Apify keyword search."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("MODULE 1: Find Viral Creators")
    logger.info("=" * 60)
    logger.info(f"  Keyword: {keyword}")
    logger.info(f"  Min likes: {min_likes}")
    logger.info(f"  Max results: {max_results}")

    # Get existing creators
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range='Creators!A:A'
        ).execute()
        existing_urls = {row[0] for row in result.get('values', [])[1:] if row}
    except HttpError:
        existing_urls = set()

    logger.info(f"  Existing creators: {len(existing_urls)}")

    # Search LinkedIn
    logger.info(f"  Searching LinkedIn for '{keyword}'...")
    run_input = {
        "searchQueries": [keyword],
        "maxPosts": max_results,
        "maxComments": 0, "maxReactions": 0,
        "scrapeComments": False, "scrapeReactions": False,
    }

    try:
        run = apify_client.actor(APIFY_ACTOR_KEYWORD_SEARCH).call(run_input=run_input)
        posts = list(apify_client.dataset(run['defaultDatasetId']).iterate_items())
        logger.info(f"  Retrieved {len(posts)} posts")
    except Exception as e:
        logger.error(f"  Apify search failed: {sanitize_error(str(e))}")
        return 0

    # Filter by engagement and extract unique creators
    posts.sort(key=lambda p: p.get('engagement', {}).get('likes', 0), reverse=True)
    seen_urls = set()
    new_creators = []

    for post in posts:
        likes = post.get('engagement', {}).get('likes', 0)
        if likes < min_likes:
            continue

        author = post.get('author', {})
        profile_url = author.get('linkedinUrl', '')
        if '?' in profile_url:
            profile_url = profile_url.split('?')[0]

        if not profile_url or profile_url in seen_urls or profile_url in existing_urls:
            continue

        seen_urls.add(profile_url)
        new_creators.append([
            profile_url,
            author.get('name', ''),
            author.get('info', ''),
            str(likes),
            datetime.now().strftime('%Y-%m-%d')
        ])

    if new_creators:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range='Creators!A:E',
            valueInputOption='RAW', insertDataOption='INSERT_ROWS',
            body={'values': new_creators}
        ).execute()

    logger.info(f"  Added {len(new_creators)} new creators")
    for c in new_creators[:5]:
        logger.info(f"    {c[1]} — {c[3]} likes")
    if len(new_creators) > 5:
        logger.info(f"    ... and {len(new_creators) - 5} more")

    return len(new_creators)


# ============================================================================
# MODULE 2: SCRAPE SOURCE POSTS
# ============================================================================

def module_2_scrape(apify_client, service, sheet_id, posted_limit, max_posts_per_creator):
    """Scrape recent posts from all tracked creators."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("MODULE 2: Scrape Source Posts")
    logger.info("=" * 60)

    # Read creators
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range='Creators!A:A'
    ).execute()
    creator_urls = [row[0] for row in result.get('values', [])[1:] if row and row[0].startswith('http')]

    if not creator_urls:
        logger.warning("  No creators found. Run Module 1 first.")
        return 0

    logger.info(f"  Scraping posts from {len(creator_urls)} creators...")

    # Read existing post URLs for dedup
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range='Source Posts!B:B'
        ).execute()
        existing_urls = {row[0] for row in result.get('values', [])[1:] if row}
    except HttpError:
        existing_urls = set()

    # Scrape via Apify
    run_input = {
        "targetUrls": creator_urls,
        "maxPosts": max_posts_per_creator,
        "postedLimit": posted_limit,
        "maxComments": 0, "maxReactions": 0,
        "scrapeComments": False, "scrapeReactions": False,
    }

    try:
        run = apify_client.actor(APIFY_ACTOR_PROFILE_SCRAPER).call(run_input=run_input)
        raw_posts = list(apify_client.dataset(run['defaultDatasetId']).iterate_items())
        logger.info(f"  Retrieved {len(raw_posts)} posts from Apify")
    except Exception as e:
        logger.error(f"  Apify scrape failed: {sanitize_error(str(e))}")
        return 0

    # Process posts
    new_rows = []
    for post in raw_posts:
        post_url = post.get('linkedinUrl', '') or post.get('postUrl', '') or ''
        if '?' in post_url:
            post_url = post_url.split('?')[0]

        if not post_url or post_url in existing_urls:
            continue

        content = post.get('content', '') or ''
        if not content.strip():
            continue

        post_id = post.get('id', '')
        if not post_id:
            match = re.search(r'activity-(\d+)', post_url)
            post_id = match.group(1) if match else str(uuid.uuid4())[:8]

        post_images = post.get('postImages', []) or []
        image_urls = []
        for img in post_images[:3]:
            if isinstance(img, dict):
                image_urls.append(img.get('url', ''))
            elif isinstance(img, str):
                image_urls.append(img)
        while len(image_urls) < 3:
            image_urls.append('')

        author = post.get('author', {}) or {}
        creator_url = author.get('linkedinUrl', '') or ''
        if '?' in creator_url:
            creator_url = creator_url.split('?')[0]

        posted_at_data = post.get('postedAt', {}) or {}
        posted_at = ''
        if isinstance(posted_at_data, dict):
            posted_at = posted_at_data.get('date', '') or str(posted_at_data.get('timestamp', ''))
        elif isinstance(posted_at_data, str):
            posted_at = posted_at_data

        new_rows.append([
            post_id, post_url, content[:50000], creator_url, str(posted_at),
            image_urls[0], image_urls[1], image_urls[2],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'no'
        ])
        existing_urls.add(post_url)

    if new_rows:
        # Batch append
        batch_size = 50
        for i in range(0, len(new_rows), batch_size):
            batch = new_rows[i:i + batch_size]
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id, range='Source Posts!A:J',
                valueInputOption='RAW', insertDataOption='INSERT_ROWS',
                body={'values': batch}
            ).execute()

    logger.info(f"  Added {len(new_rows)} new source posts")
    with_images = sum(1 for r in new_rows if r[5])
    logger.info(f"    With images: {with_images}")
    logger.info(f"    Without images: {len(new_rows) - with_images}")

    return len(new_rows)


# ============================================================================
# MODULE 3: AI CONTENT GENERATION
# ============================================================================

def ai_call(client: AzureOpenAI, messages: List[Dict], temperature=0.7,
            max_tokens=2000, model=None) -> Optional[str]:
    """Make an Azure OpenAI call with retry logic."""
    deployment = model or os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=deployment, messages=messages,
                temperature=temperature, max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF ** (attempt + 1)
                logger.warning(f"    AI call failed (attempt {attempt + 1}): {sanitize_error(str(e))}")
                time.sleep(wait)
            else:
                logger.error(f"    AI call failed after {MAX_RETRIES} attempts")
                return None
    return None


def module_3_generate(ai_client, service, sheet_id, max_posts, delay):
    """Generate AI content for unprocessed source posts."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("MODULE 3: AI Content Generation")
    logger.info("=" * 60)

    # Load tone examples
    tone_examples = load_tone_examples()
    if tone_examples:
        logger.info("  Tone of voice examples loaded")
    else:
        logger.info("  No tone examples — using default professional tone")

    # Read unprocessed posts
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range='Source Posts!A:J'
    ).execute()
    values = result.get('values', [])

    if len(values) <= 1:
        logger.info("  No source posts found. Run Module 2 first.")
        return 0

    headers = values[0]
    posts = []
    for row_idx, row in enumerate(values[1:], start=2):
        while len(row) < len(headers):
            row.append('')
        row_dict = dict(zip(headers, row))
        row_dict['_row_number'] = row_idx
        if row_dict.get('processed', '').lower() == 'no':
            posts.append(row_dict)
        if len(posts) >= max_posts:
            break

    if not posts:
        logger.info("  No unprocessed posts. Run Module 2 to scrape more.")
        return 0

    logger.info(f"  Processing {len(posts)} posts...")

    generated = 0
    failed = 0

    for i, post in enumerate(posts):
        post_id = post.get('post_id', f'unknown_{i}')
        content = post.get('content', '')
        image_url = post.get('image_url_1', '')
        row_number = post['_row_number']

        logger.info(f"  [{i + 1}/{len(posts)}] Post {post_id}")
        logger.info(f"    Preview: {content[:80]}...")

        # Step 1: Image analysis (conditional)
        image_description = ""
        if image_url and image_url.startswith('http'):
            logger.info("    Step 1: Analyzing image...")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image comprehensively. What does it show, what text is present, what data or charts are visible?"},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }]
            image_description = ai_call(ai_client, messages, temperature=0.3, max_tokens=1000) or ""
            if image_description:
                logger.info(f"    Image described ({len(image_description)} chars)")
        else:
            logger.info("    Step 1: No image — skipped")

        # Step 2: Generate outline
        logger.info("    Step 2: Generating outline...")
        user_content = f"Create a SHORT outline (3-5 bullet points max) for a new LinkedIn post inspired by (but different from) this source content.\n\nSource post:\n{content}\n"
        if image_description:
            user_content += f"\nImage description:\n{image_description}\n"
        user_content += "\nRules:\n- Keep the core topic but add ONE new angle or personal insight\n- Do NOT copy phrases verbatim from the source\n- Focus on ONE practical takeaway the reader can use today\n- Output as 3-5 short bullet points (not a full essay outline)\n- Focus on B2B/Sales relevance\n- Remember: the final post must be under 1200 characters, so keep the outline tight"

        outline = ai_call(ai_client, [
            {"role": "system", "content": "You're an intelligent writing assistant that takes LinkedIn post content and creates concise, unique outlines for SHORT LinkedIn posts. The final post must be under 1200 characters, so your outline should cover 2-3 key points maximum. You add twists, new perspectives, and practical insights from your knowledge to make the content meaningfully different from the source."},
            {"role": "user", "content": user_content}
        ], temperature=0.7, max_tokens=800)

        if not outline:
            logger.error(f"    Outline failed. Skipping.")
            failed += 1
            continue

        # Step 3: Generate final post
        logger.info("    Step 3: Generating final post...")
        system = """You write LinkedIn posts that sound like a real person talking, not a content creator performing.

Study these example posts carefully. This is EXACTLY how you should write. Match the sentence structure, the rhythm, the level of detail, and the casual-but-smart tone:"""
        if tone_examples:
            system += f"\n\n{tone_examples}"
        system += """

STRICT RULES (violating any of these means failure):
1. HARD LIMIT: 1200 characters maximum. Count carefully. If over, cut ruthlessly.
2. NO hashtags. Zero. Never. Not even one.
3. NO rhetorical questions. Never end a sentence with "?"
4. NO emojis whatsoever.
5. NO em dashes. Use commas, periods, or "and" instead.
6. NO title or headline. Start directly with the first sentence of content.
7. NO generic LinkedIn-speak ("let's connect", "thoughts?", "agree?", "here's why", "hot take")
8. NO bullet point lists longer than 3 items.
9. Write like you're explaining something to a smart friend over coffee.
10. Use contractions naturally (don't, won't, I've, it's, you're).
11. Be specific with numbers, examples, and concrete details.
12. First person. Conversational. Direct. Like you've actually done this stuff.
13. One core idea per post. Go deep on it, don't spread thin across 5 topics."""

        final = ai_call(ai_client, [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Write a LinkedIn post from this outline. Remember: UNDER 1200 characters, NO hashtags, NO questions, NO emojis.\n\n{outline}"}
        ], temperature=0.7, max_tokens=600)

        if not final:
            logger.error(f"    Final post failed. Skipping.")
            failed += 1
            continue

        logger.info(f"    Generated ({len(final)} chars)")

        # Save to Destination Posts
        dest_id = str(uuid.uuid4())[:8]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range='Destination Posts!A:G',
            valueInputOption='RAW', insertDataOption='INSERT_ROWS',
            body={'values': [[
                dest_id, post_id, post.get('post_url', ''),
                final, 'draft',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ''
            ]]}
        ).execute()

        # Mark processed
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f'Source Posts!J{row_number}',
            valueInputOption='RAW', body={'values': [['yes']]}
        ).execute()

        generated += 1
        logger.info(f"    Saved as draft (ID: {dest_id})")

        if i < len(posts) - 1:
            time.sleep(delay)

    logger.info(f"  Generated: {generated} | Failed: {failed}")
    return generated


# ============================================================================
# MODULE 4: POST TO LINKEDIN
# ============================================================================

def generate_ai_image_for_post(content: str) -> str:
    """Generate an AI image using fal.ai Flux Pro. Returns image URL or empty string."""
    import tempfile
    fal_key = os.getenv('FAL_KEY')
    if not fal_key:
        logger.warning("  FAL_KEY not found in .env. Skipping image generation.")
        return ""

    try:
        import fal_client
    except ImportError:
        logger.warning("  fal-client not installed. Run: pip install fal-client")
        return ""

    os.environ['FAL_KEY'] = fal_key

    # Generate image prompt using Azure OpenAI
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    image_prompt = ""
    if azure_endpoint and azure_key:
        try:
            ai_client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version="2024-12-01-preview"
            )
            deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')
            response = ai_client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": (
                        "You create image generation prompts for LinkedIn posts. "
                        "Generate a single, concise prompt for a professional, modern illustration "
                        "that complements the post content. The image should be clean, minimal, "
                        "and suitable for a business audience. No text in the image. "
                        "Output ONLY the prompt, nothing else."
                    )},
                    {"role": "user", "content": f"Create an image prompt for this LinkedIn post:\n\n{content}"}
                ],
                temperature=0.7,
                max_tokens=200
            )
            image_prompt = response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"  AI prompt generation failed: {sanitize_error(str(e))}")

    if not image_prompt:
        words = content[:200].split()[:10]
        image_prompt = f"Professional minimalist illustration about {' '.join(words)}, modern business style, clean design, no text"

    logger.info(f"  Image prompt: {image_prompt[:100]}...")
    logger.info("  Generating image via fal.ai...")

    try:
        result = fal_client.subscribe("fal-ai/flux-pro/v1.1", arguments={
            "prompt": image_prompt,
            "image_size": "landscape_4_3",
            "num_images": 1,
            "output_format": "jpeg",
            "guidance_scale": 3.5,
        })
        if result and 'images' in result and len(result['images']) > 0:
            url = result['images'][0]['url']
            logger.info(f"  Image generated: {url[:80]}...")
            return url
    except Exception as e:
        logger.error(f"  fal.ai failed: {str(e)[:200]}")
    return ""


def upload_image_to_linkedin_api(access_token: str, person_urn: str, image_url: str) -> str:
    """Download image from URL and upload to LinkedIn. Returns image URN or empty string."""
    import tempfile

    # Download image
    logger.info("  Downloading generated image...")
    try:
        resp = requests.get(image_url, timeout=30)
        if resp.status_code != 200:
            logger.error(f"  Image download failed: HTTP {resp.status_code}")
            return ""
    except Exception as e:
        logger.error(f"  Image download failed: {str(e)[:100]}")
        return ""

    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp.write(resp.content)
    tmp.close()
    logger.info(f"  Downloaded ({len(resp.content) / 1024:.0f} KB)")

    headers_req = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'LinkedIn-Version': LINKEDIN_API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }

    # Initialize upload
    logger.info("  Initializing LinkedIn image upload...")
    init_resp = requests.post(
        'https://api.linkedin.com/rest/images?action=initializeUpload',
        headers=headers_req,
        json={"initializeUploadRequest": {"owner": person_urn}},
        timeout=30
    )

    if init_resp.status_code != 200:
        logger.error(f"  Image init failed: HTTP {init_resp.status_code}: {sanitize_error(init_resp.text)}")
        os.unlink(tmp.name)
        return ""

    data = init_resp.json().get('value', {})
    upload_url = data.get('uploadUrl', '')
    image_urn = data.get('image', '')

    if not upload_url or not image_urn:
        logger.error("  No upload URL from LinkedIn")
        os.unlink(tmp.name)
        return ""

    # Upload binary
    logger.info("  Uploading image to LinkedIn...")
    with open(tmp.name, 'rb') as f:
        image_data = f.read()

    upload_resp = requests.put(
        upload_url,
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/octet-stream'},
        data=image_data,
        timeout=60
    )

    os.unlink(tmp.name)

    if upload_resp.status_code in (200, 201):
        logger.info(f"  Image uploaded: {image_urn}")
        return image_urn
    else:
        logger.error(f"  Image upload failed: HTTP {upload_resp.status_code}")
        return ""


def module_4_post(service, sheet_id, dry_run=False, generate_image=False, image_path=""):
    """Post the first draft to LinkedIn, optionally with an AI-generated or provided image."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("MODULE 4: Post to LinkedIn")
    logger.info("=" * 60)

    if dry_run:
        logger.info("  [DRY RUN — nothing will be posted]")

    access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
    person_urn = os.getenv('LINKEDIN_PERSON_URN')

    if not dry_run and (not access_token or not person_urn):
        logger.error("  LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN not set.")
        logger.error("  Run: python3 execution/linkedin_auth.py")
        return False

    # Get first draft
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range='Destination Posts!A:G'
    ).execute()
    values = result.get('values', [])

    draft = None
    for row_idx, row in enumerate(values[1:], start=2):
        headers = values[0]
        while len(row) < len(headers):
            row.append('')
        row_dict = dict(zip(headers, row))
        row_dict['_row_number'] = row_idx
        if row_dict.get('status', '').lower() == 'draft':
            draft = row_dict
            break

    if not draft:
        logger.info("  No draft posts available.")
        return False

    content = draft.get('generated_content', '')
    dest_id = draft.get('dest_id', '')
    row_number = draft['_row_number']

    logger.info(f"  Draft: {dest_id}")
    logger.info(f"  Length: {len(content)} chars")
    logger.info(f"  Preview: {content[:150]}...")

    # Handle image
    image_source = image_path
    if generate_image and not image_source:
        logger.info("")
        logger.info("  Generating AI image for this post...")
        image_source = generate_ai_image_for_post(content)
        if not image_source:
            logger.warning("  Image generation failed. Continuing without image.")

    if dry_run:
        logger.info("")
        logger.info("  Full content:")
        logger.info("  " + "-" * 40)
        for line in content.split('\n'):
            logger.info(f"  {line}")
        logger.info("  " + "-" * 40)
        if image_source:
            logger.info(f"\n  Image: {image_source}")
        return True

    # Upload image to LinkedIn if we have one
    image_urn = ""
    if image_source:
        image_urn = upload_image_to_linkedin_api(access_token, person_urn, image_source)
        if not image_urn:
            logger.warning("  Image upload failed. Posting without image.")

    # Post to LinkedIn
    logger.info("  Posting to LinkedIn...")
    headers_req = {
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
        body["content"] = {"media": {"id": image_urn}}

    response = requests.post(LINKEDIN_POST_URL, headers=headers_req, json=body, timeout=30)

    if response.status_code in (200, 201):
        post_urn = response.headers.get('x-restli-id', '')
        post_type = "with image" if image_urn else "text only"
        logger.info(f"  Posted successfully ({post_type})! URN: {post_urn}")

        # Update sheet
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={'valueInputOption': 'RAW', 'data': [
                {'range': f'Destination Posts!E{row_number}', 'values': [['published']]},
                {'range': f'Destination Posts!G{row_number}', 'values': [[now]]}
            ]}
        ).execute()

        # Count remaining
        remaining = sum(1 for row in values[1:] if len(row) >= 5 and row[4].lower() == 'draft') - 1
        logger.info(f"  {remaining} drafts remaining in queue")
        return True
    else:
        error_msg = sanitize_error(response.text)
        logger.error(f"  Failed: HTTP {response.status_code}: {error_msg}")
        if '401' in str(response.status_code):
            logger.error("  Token expired. Re-run: python3 execution/linkedin_auth.py")
        return False


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LinkedIn Parasite — Full Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Full pipeline:    python3 execution/linkedin_parasite.py --keyword "B2B sales"
  Scrape+Gen+Post:  python3 execution/linkedin_parasite.py --skip-init
  Generate+Post:    python3 execution/linkedin_parasite.py --skip-init --skip-scrape
  Post only:        python3 execution/linkedin_parasite.py --post-only
  Dry run:          python3 execution/linkedin_parasite.py --post-only --dry-run
        """
    )

    # Module control
    parser.add_argument('--skip-init', action='store_true', help='Skip Module 1 (use existing creators)')
    parser.add_argument('--skip-scrape', action='store_true', help='Skip Module 2 (use existing source posts)')
    parser.add_argument('--skip-generate', action='store_true', help='Skip Module 3 (use existing drafts)')
    parser.add_argument('--post-only', action='store_true', help='Only run Module 4 (post next draft)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be posted without posting')
    parser.add_argument('--generate-image', action='store_true', help='Generate AI image via fal.ai for the post')
    parser.add_argument('--image', type=str, default='', help='Path or URL to image to attach to the post')

    # Module 1 settings
    parser.add_argument('--keyword', type=str, default=os.getenv('LINKEDIN_SEARCH_KEYWORD', 'B2B sales'))
    parser.add_argument('--min-likes', type=int, default=int(os.getenv('LINKEDIN_MIN_LIKES', '100')))
    parser.add_argument('--max-results', type=int, default=200)

    # Module 2 settings
    parser.add_argument('--posted-limit', type=str, default='week', choices=['day', 'week', 'month'])
    parser.add_argument('--max-posts-per-creator', type=int, default=10)

    # Module 3 settings
    parser.add_argument('--max-generate', type=int, default=5, help='Max posts to generate per run')
    parser.add_argument('--delay', type=int, default=3, help='Delay between AI generations (seconds)')

    args = parser.parse_args()

    # Validate essentials
    apify_key = os.getenv('APIFY_API_KEY')
    if not apify_key:
        logger.error("APIFY_API_KEY not found in .env")
        sys.exit(1)

    logger.info("")
    logger.info("LinkedIn Parasite System")
    logger.info("=" * 60)
    logger.info(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Determine which modules to run
    if args.post_only:
        run_init = run_scrape = run_generate = False
        run_post = True
    else:
        run_init = not args.skip_init
        run_scrape = not args.skip_scrape
        run_generate = not args.skip_generate
        run_post = True

    modules = []
    if run_init:
        modules.append("1:Init")
    if run_scrape:
        modules.append("2:Scrape")
    if run_generate:
        modules.append("3:Generate")
    if run_post:
        modules.append("4:Post")
    logger.info(f"  Modules: {' → '.join(modules)}")

    # Initialize shared clients
    apify_client = ApifyClient(apify_key)
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # Get or create spreadsheet
    sheet_id = get_or_create_spreadsheet(service, drive_service)

    # Run pipeline
    if run_init:
        module_1_init(apify_client, service, sheet_id, args.keyword, args.min_likes, args.max_results)

    if run_scrape:
        module_2_scrape(apify_client, service, sheet_id, args.posted_limit, args.max_posts_per_creator)

    if run_generate:
        azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        azure_key = os.getenv('AZURE_OPENAI_API_KEY')
        if not azure_endpoint or not azure_key:
            logger.error("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in .env")
            sys.exit(1)

        ai_client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version="2024-12-01-preview"
        )
        module_3_generate(ai_client, service, sheet_id, args.max_generate, args.delay)

    if run_post:
        module_4_post(service, sheet_id, args.dry_run, args.generate_image, args.image)

    # Final summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"  Google Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == '__main__':
    main()
