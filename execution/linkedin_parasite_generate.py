#!/usr/bin/env python3
"""
LinkedIn Parasite — Module 3: AI Content Generation Engine
Processes unprocessed source posts through a 3-step AI pipeline:
  1. Image analysis (conditional) — GPT-4o vision
  2. Unique outline generation — GPT-4.1
  3. Final post in user's tone — GPT-4.1

Usage:
    python3 execution/linkedin_parasite_generate.py
    python3 execution/linkedin_parasite_generate.py --max-posts 5 --delay 3

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import re
import uuid
import time
import argparse
import logging
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

try:
    from openai import AzureOpenAI
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install openai google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, exponential


def sanitize_error(error_str: str) -> str:
    """Remove API keys and sensitive data from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(r'(api[_-]?key["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
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

            # Check if user has replaced placeholder text
            if '[REPLACE WITH YOUR POST]' in content:
                logger.warning("Tone examples not configured yet!")
                logger.warning("Edit directives/linkedin_parasite_tone.md with your LinkedIn posts.")
                return ""

            return content

    logger.warning("directives/linkedin_parasite_tone.md not found. Using default tone.")
    return ""


def read_unprocessed_posts(service, sheet_id: str, max_posts: int) -> List[Dict]:
    """Read source posts where processed = 'no'."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='Source Posts!A:J'
    ).execute()
    values = result.get('values', [])

    if len(values) <= 1:
        return []

    headers = values[0]
    posts = []

    for row_idx, row in enumerate(values[1:], start=2):
        # Pad row to match headers
        while len(row) < len(headers):
            row.append('')

        row_dict = dict(zip(headers, row))
        row_dict['_row_number'] = row_idx  # 1-indexed row in sheet

        if row_dict.get('processed', '').lower() == 'no':
            posts.append(row_dict)

        if len(posts) >= max_posts:
            break

    return posts


def ai_call_with_retry(client: AzureOpenAI, messages: List[Dict],
                       temperature: float = 0.7, max_tokens: int = 2000,
                       model: str = None) -> Optional[str]:
    """Make an Azure OpenAI call with retry logic."""
    deployment = model or os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = sanitize_error(str(e))
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF ** (attempt + 1)
                logger.warning(f"  AI call failed (attempt {attempt + 1}/{MAX_RETRIES}): {error_msg}")
                logger.warning(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"  AI call failed after {MAX_RETRIES} attempts: {error_msg}")
                return None

    return None


def analyze_image(client: AzureOpenAI, image_url: str) -> str:
    """Analyze a post image using GPT-4o vision."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe this image comprehensively. What does it show? What text is present? What data, charts, or diagrams are visible? Be thorough."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url, "detail": "high"}
                }
            ]
        }
    ]

    # Use gpt-4o for vision (gpt-4.1 may not support vision)
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1')
    # If we have a specific GPT-4o deployment, use it; otherwise fall back to default
    vision_model = deployment

    result = ai_call_with_retry(client, messages, temperature=0.3, max_tokens=1000, model=vision_model)
    return result or ""


def generate_outline(client: AzureOpenAI, content: str, image_description: str = "") -> str:
    """Generate a unique outline from source content + image description."""
    system_prompt = (
        "You're an intelligent writing assistant that takes LinkedIn post content and creates "
        "concise, unique outlines for SHORT LinkedIn posts. The final post must be under 1200 characters, "
        "so your outline should cover 2-3 key points maximum. You add twists, new perspectives, and "
        "practical insights from your knowledge to make the content meaningfully different from the source."
    )

    user_content = f"""Create a SHORT outline (3-5 bullet points max) for a new LinkedIn post inspired by (but different from) this source content.

Source post:
{content}
"""

    if image_description:
        user_content += f"""
Image description:
{image_description}
"""

    user_content += """
Rules:
- Keep the core topic but add ONE new angle or personal insight
- Do NOT copy phrases verbatim from the source
- Focus on ONE practical takeaway the reader can use today
- Output as 3-5 short bullet points (not a full essay outline)
- Focus on B2B/Sales relevance
- Remember: the final post must be under 1200 characters, so keep the outline tight"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    result = ai_call_with_retry(client, messages, temperature=0.7, max_tokens=800)
    return result or ""


def generate_final_post(client: AzureOpenAI, outline: str, tone_examples: str) -> str:
    """Generate the final LinkedIn post from an outline in the user's tone."""
    system_prompt = """You write LinkedIn posts that sound like a real person talking, not a content creator performing.

Study these example posts carefully. This is EXACTLY how you should write. Match the sentence structure, the rhythm, the level of detail, and the casual-but-smart tone:"""

    if tone_examples:
        system_prompt += f"""

{tone_examples}"""

    system_prompt += """

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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Write a LinkedIn post from this outline. Remember: UNDER 1200 characters, NO hashtags, NO questions, NO emojis.\n\n{outline}"}
    ]

    result = ai_call_with_retry(client, messages, temperature=0.7, max_tokens=600)
    return result or ""


def append_destination_post(service, sheet_id: str, dest_post: Dict):
    """Append a generated post to the Destination Posts tab."""
    row = [
        dest_post['dest_id'],
        dest_post['source_post_id'],
        dest_post['source_post_url'],
        dest_post['generated_content'],
        dest_post['status'],
        dest_post['generated_at'],
        dest_post['published_at']
    ]

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range='Destination Posts!A:G',
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': [row]}
    ).execute()


def mark_post_processed(service, sheet_id: str, row_number: int):
    """Update a source post's 'processed' column to 'yes'."""
    # Column J (index 10) is 'processed'
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f'Source Posts!J{row_number}',
        valueInputOption='RAW',
        body={'values': [['yes']]}
    ).execute()


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Parasite — AI Content Generation')
    parser.add_argument('--max-posts', type=int, default=5,
                        help='Max posts to process per run (default: 5)')
    parser.add_argument('--delay', type=int, default=3,
                        help='Delay between posts in seconds (default: 3)')
    args = parser.parse_args()

    # Validate
    sheet_id = os.getenv('LINKEDIN_PARASITE_SHEET_ID')
    if not sheet_id:
        logger.error("LINKEDIN_PARASITE_SHEET_ID not found in .env")
        logger.error("Run Module 1 first.")
        sys.exit(1)

    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    if not azure_endpoint or not azure_key:
        logger.error("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in .env")
        sys.exit(1)

    logger.info("LinkedIn Parasite — Module 3: AI Content Generation")
    logger.info("=" * 50)

    # Initialize Azure OpenAI
    ai_client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=azure_key,
        api_version="2024-12-01-preview"
    )

    # Initialize Google Sheets
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)

    # Load tone examples
    tone_examples = load_tone_examples()
    if tone_examples:
        logger.info("Tone of voice examples loaded")
    else:
        logger.info("No tone examples — using default professional tone")

    # Read unprocessed posts
    posts = read_unprocessed_posts(service, sheet_id, args.max_posts)
    if not posts:
        logger.info("No unprocessed posts found. Run Module 2 first.")
        return

    logger.info(f"Processing {len(posts)} posts...")
    logger.info("")

    generated_count = 0
    failed_count = 0

    for i, post in enumerate(posts):
        post_id = post.get('post_id', f'unknown_{i}')
        content = post.get('content', '')
        image_url = post.get('image_url_1', '')
        row_number = post['_row_number']

        logger.info(f"[{i + 1}/{len(posts)}] Processing post {post_id}...")
        logger.info(f"  Content preview: {content[:80]}...")

        # Step 1: Image analysis (conditional)
        image_description = ""
        if image_url and image_url.startswith('http'):
            logger.info("  Step 1: Analyzing image...")
            image_description = analyze_image(ai_client, image_url)
            if image_description:
                logger.info(f"  Image described ({len(image_description)} chars)")
            else:
                logger.warning("  Image analysis failed, continuing without it")
        else:
            logger.info("  Step 1: No image — skipping")

        # Step 2: Generate outline
        logger.info("  Step 2: Generating unique outline...")
        outline = generate_outline(ai_client, content, image_description)
        if not outline:
            logger.error(f"  Outline generation failed for post {post_id}. Skipping.")
            failed_count += 1
            continue
        logger.info(f"  Outline generated ({len(outline)} chars)")

        # Step 3: Generate final post
        logger.info("  Step 3: Generating final LinkedIn post...")
        final_post = generate_final_post(ai_client, outline, tone_examples)
        if not final_post:
            logger.error(f"  Final post generation failed for post {post_id}. Skipping.")
            failed_count += 1
            continue
        logger.info(f"  Final post generated ({len(final_post)} chars)")

        # Save to Destination Posts
        dest_post = {
            'dest_id': str(uuid.uuid4())[:8],
            'source_post_id': post_id,
            'source_post_url': post.get('post_url', ''),
            'generated_content': final_post,
            'status': 'draft',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'published_at': ''
        }

        append_destination_post(service, sheet_id, dest_post)
        mark_post_processed(service, sheet_id, row_number)

        generated_count += 1
        logger.info(f"  Saved as draft (ID: {dest_post['dest_id']})")

        # Rate limit delay
        if i < len(posts) - 1:
            logger.info(f"  Waiting {args.delay}s before next post...")
            time.sleep(args.delay)

        logger.info("")

    # Summary
    logger.info("=" * 50)
    logger.info(f"Generated: {generated_count} posts")
    if failed_count:
        logger.info(f"Failed: {failed_count} posts")
    logger.info("All generated posts saved as drafts in Destination Posts tab.")


if __name__ == '__main__':
    main()
