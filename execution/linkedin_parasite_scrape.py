#!/usr/bin/env python3
"""
LinkedIn Parasite — Module 2: Scrape Source Posts
Reads creators from Google Sheets, scrapes their recent posts via Apify,
and stores them in the Source Posts tab.

Usage:
    python3 execution/linkedin_parasite_scrape.py
    python3 execution/linkedin_parasite_scrape.py --posted-limit week --max-posts 10

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import re
import argparse
import logging
from typing import List, Dict, Set
from datetime import datetime
from dotenv import load_dotenv

try:
    from apify_client import ApifyClient
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install apify-client google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
APIFY_ACTOR_PROFILE_SCRAPER = 'A3cAPGpwBEG8RJwse'


def sanitize_error(error_str: str) -> str:
    """Remove API keys and sensitive data from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(r'(api[_-]?key["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(apify_api_[a-zA-Z0-9_\-\.]+)', r'[REDACTED_APIFY_KEY]', error_str)
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


def read_creators(service, sheet_id: str) -> List[str]:
    """Read all creator LinkedIn URLs from the Creators tab."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='Creators!A:A'
    ).execute()
    values = result.get('values', [])
    # Skip header, return URLs
    urls = [row[0] for row in values[1:] if row and row[0].startswith('http')]
    return urls


def read_existing_post_urls(service, sheet_id: str) -> Set[str]:
    """Read existing post URLs from Source Posts tab for deduplication."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range='Source Posts!B:B'
        ).execute()
        values = result.get('values', [])
        return {row[0] for row in values[1:] if row}
    except HttpError:
        return set()


def scrape_creator_posts(apify_client: ApifyClient, creator_urls: List[str],
                         posted_limit: str, max_posts: int) -> List[Dict]:
    """Scrape recent posts from all creator profiles using Apify bulk scraper."""
    logger.info(f"Scraping posts from {len(creator_urls)} creators...")
    logger.info(f"  Posted limit: {posted_limit}, Max posts per creator: {max_posts}")

    run_input = {
        "targetUrls": creator_urls,
        "maxPosts": max_posts,
        "postedLimit": posted_limit,
        "maxComments": 0,
        "maxReactions": 0,
        "scrapeComments": False,
        "scrapeReactions": False,
    }

    try:
        run = apify_client.actor(APIFY_ACTOR_PROFILE_SCRAPER).call(run_input=run_input)
        items = list(apify_client.dataset(run['defaultDatasetId']).iterate_items())
        logger.info(f"Retrieved {len(items)} posts from Apify")
        return items
    except Exception as e:
        logger.error(f"Apify scrape failed: {sanitize_error(str(e))}")
        return []


def process_posts(raw_posts: List[Dict], existing_urls: Set[str]) -> List[Dict]:
    """Process raw Apify output into structured post data, deduplicate."""
    processed = []
    skipped_dupes = 0

    for post in raw_posts:
        post_url = post.get('linkedinUrl', '') or post.get('postUrl', '') or ''

        # Clean URL
        if '?' in post_url:
            post_url = post_url.split('?')[0]

        if not post_url:
            continue

        # Skip duplicates
        if post_url in existing_urls:
            skipped_dupes += 1
            continue

        # Skip posts with no content
        content = post.get('content', '') or ''
        if not content.strip():
            continue

        # Extract post ID from URL or use the provided ID
        post_id = post.get('id', '') or ''
        if not post_id and post_url:
            # Extract from URL pattern: activity-XXXX
            match = re.search(r'activity-(\d+)', post_url)
            if match:
                post_id = match.group(1)

        # Extract image URLs
        post_images = post.get('postImages', []) or []
        image_urls = []
        for img in post_images[:3]:
            if isinstance(img, dict):
                image_urls.append(img.get('url', ''))
            elif isinstance(img, str):
                image_urls.append(img)

        # Pad to 3 entries
        while len(image_urls) < 3:
            image_urls.append('')

        # Extract creator URL
        author = post.get('author', {}) or {}
        creator_url = author.get('linkedinUrl', '') or ''
        if '?' in creator_url:
            creator_url = creator_url.split('?')[0]

        # Extract posted date
        posted_at_data = post.get('postedAt', {}) or {}
        posted_at = ''
        if isinstance(posted_at_data, dict):
            posted_at = posted_at_data.get('date', '') or posted_at_data.get('timestamp', '')
        elif isinstance(posted_at_data, str):
            posted_at = posted_at_data

        processed.append({
            'post_id': post_id,
            'post_url': post_url,
            'content': content[:50000],  # Sheets cell limit
            'creator_url': creator_url,
            'posted_at': str(posted_at),
            'image_url_1': image_urls[0],
            'image_url_2': image_urls[1],
            'image_url_3': image_urls[2],
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'processed': 'no'
        })

        existing_urls.add(post_url)

    if skipped_dupes:
        logger.info(f"Skipped {skipped_dupes} duplicate posts")

    return processed


def append_source_posts(service, sheet_id: str, posts: List[Dict]):
    """Append processed posts to the Source Posts tab."""
    if not posts:
        return

    rows = []
    for p in posts:
        rows.append([
            p['post_id'],
            p['post_url'],
            p['content'],
            p['creator_url'],
            p['posted_at'],
            p['image_url_1'],
            p['image_url_2'],
            p['image_url_3'],
            p['scraped_at'],
            p['processed']
        ])

    # Batch append (avoid rate limits)
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range='Source Posts!A:J',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': batch}
        ).execute()

    logger.info(f"Appended {len(rows)} posts to Source Posts tab")


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Parasite — Scrape Source Posts')
    parser.add_argument('--posted-limit', type=str, default='week',
                        choices=['day', 'week', 'month'],
                        help='Time filter for posts (default: week)')
    parser.add_argument('--max-posts', type=int, default=10,
                        help='Max posts per creator (default: 10)')
    args = parser.parse_args()

    # Validate
    sheet_id = os.getenv('LINKEDIN_PARASITE_SHEET_ID')
    if not sheet_id:
        logger.error("LINKEDIN_PARASITE_SHEET_ID not found in .env")
        logger.error("Run Module 1 first: python3 execution/linkedin_parasite_init.py")
        sys.exit(1)

    apify_key = os.getenv('APIFY_API_KEY')
    if not apify_key:
        logger.error("APIFY_API_KEY not found in .env")
        sys.exit(1)

    logger.info("LinkedIn Parasite — Module 2: Scrape Source Posts")
    logger.info("=" * 50)

    # Initialize
    apify_client = ApifyClient(apify_key)
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)

    # Read creators
    creator_urls = read_creators(service, sheet_id)
    if not creator_urls:
        logger.warning("No creators found in database. Run Module 1 first.")
        return

    logger.info(f"Found {len(creator_urls)} creators to scrape")

    # Read existing posts for dedup
    existing_urls = read_existing_post_urls(service, sheet_id)
    logger.info(f"Existing posts in database: {len(existing_urls)}")

    # Scrape via Apify
    raw_posts = scrape_creator_posts(apify_client, creator_urls, args.posted_limit, args.max_posts)
    if not raw_posts:
        logger.warning("No posts returned from Apify.")
        return

    # Process and deduplicate
    new_posts = process_posts(raw_posts, existing_urls)
    logger.info(f"New posts to add: {len(new_posts)}")

    if not new_posts:
        logger.info("No new posts to add (all duplicates).")
        return

    # Append to sheet
    append_source_posts(service, sheet_id, new_posts)

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info(f"Scraped {len(new_posts)} new posts from {len(creator_urls)} creators")
    with_images = sum(1 for p in new_posts if p['image_url_1'])
    logger.info(f"  Posts with images: {with_images}")
    logger.info(f"  Posts without images: {len(new_posts) - with_images}")


if __name__ == '__main__':
    main()
