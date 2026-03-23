#!/usr/bin/env python3
"""
LinkedIn Parasite — Module 1: Find Viral Creators
Searches LinkedIn for viral posts in a niche and extracts creator profiles.

Usage:
    python3 execution/linkedin_parasite_init.py --keyword "B2B sales" --min-likes 100
    python3 execution/linkedin_parasite_init.py --keyword "outbound sales" --min-likes 50 --max-results 300

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import re
import argparse
import logging
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

try:
    from apify_client import ApifyClient
    import requests
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install apify-client requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
APIFY_ACTOR_KEYWORD_SEARCH = 'buIWk2uOUzTmcLsuB'
SHEET_NAME = 'LinkedIn Parasite System'
TAB_CREATORS = 'Creators'
CREATORS_HEADERS = ['linkedin_url', 'name', 'headline', 'sample_post_likes', 'added_date']


def sanitize_error(error_str: str) -> str:
    """Remove API keys and sensitive data from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(r'(api[_-]?key["\s:=]+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', error_str, flags=re.IGNORECASE)
    error_str = re.sub(r'(apify_api_[a-zA-Z0-9_\-\.]+)', r'[REDACTED_APIFY_KEY]', error_str)
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
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
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


def get_or_create_spreadsheet(service, drive_service):
    """Get existing spreadsheet by ID from env, or create a new one."""
    sheet_id = os.getenv('LINKEDIN_PARASITE_SHEET_ID')

    if sheet_id:
        try:
            service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            return sheet_id
        except HttpError:
            logger.warning("Sheet ID in .env is invalid. Creating new spreadsheet...")

    # Create new spreadsheet
    spreadsheet = service.spreadsheets().create(
        body={'properties': {'title': SHEET_NAME}},
        fields='spreadsheetId,spreadsheetUrl'
    ).execute()

    sheet_id = spreadsheet.get('spreadsheetId')
    sheet_url = spreadsheet.get('spreadsheetUrl')
    logger.info(f"Created spreadsheet: {sheet_url}")

    # Create tabs: rename Sheet1 to Creators, add Source Posts and Destination Posts
    batch_requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 0, "title": TAB_CREATORS},
                "fields": "title"
            }
        },
        {
            "addSheet": {
                "properties": {"title": "Source Posts"}
            }
        },
        {
            "addSheet": {
                "properties": {"title": "Destination Posts"}
            }
        }
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': batch_requests}
    ).execute()

    # Write headers for each tab
    headers = {
        'Creators!A1': [CREATORS_HEADERS],
        'Source Posts!A1': [['post_id', 'post_url', 'content', 'creator_url', 'posted_at',
                            'image_url_1', 'image_url_2', 'image_url_3', 'scraped_at', 'processed']],
        'Destination Posts!A1': [['dest_id', 'source_post_id', 'source_post_url',
                                  'generated_content', 'status', 'generated_at', 'published_at']]
    }

    for range_name, values in headers.items():
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

    # Format all header rows (bold + freeze)
    sheet_ids = _get_sheet_ids(service, sheet_id)
    format_requests = []
    for sid in sheet_ids:
        format_requests.extend([
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
                        }
                    },
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

    if format_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': format_requests}
        ).execute()

    # Make publicly viewable
    drive_service.permissions().create(
        fileId=sheet_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    # Save sheet ID to .env for future use
    _update_env('LINKEDIN_PARASITE_SHEET_ID', sheet_id)
    logger.info(f"Sheet ID saved to .env: {sheet_id}")

    return sheet_id


def _get_sheet_ids(service, spreadsheet_id: str) -> List[int]:
    """Get all sheet IDs in the spreadsheet."""
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [s['properties']['sheetId'] for s in metadata.get('sheets', [])]


def _update_env(key: str, value: str):
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


def get_existing_creator_urls(service, sheet_id: str) -> set:
    """Read existing creator URLs from the Creators tab."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f'{TAB_CREATORS}!A:A'
        ).execute()
        values = result.get('values', [])
        # Skip header row
        return {row[0] for row in values[1:] if row}
    except HttpError:
        return set()


def search_linkedin_posts(apify_client: ApifyClient, keyword: str, max_results: int) -> List[Dict]:
    """Search LinkedIn posts using Apify keyword search actor."""
    logger.info(f"Searching LinkedIn for '{keyword}' (max {max_results} results)...")

    run_input = {
        "searchQueries": [keyword],
        "maxPosts": max_results,
        "maxComments": 0,
        "maxReactions": 0,
        "scrapeComments": False,
        "scrapeReactions": False,
    }

    try:
        run = apify_client.actor(APIFY_ACTOR_KEYWORD_SEARCH).call(run_input=run_input)
        items = list(apify_client.dataset(run['defaultDatasetId']).iterate_items())
        logger.info(f"Retrieved {len(items)} posts from Apify")
        return items
    except Exception as e:
        logger.error(f"Apify search failed: {sanitize_error(str(e))}")
        return []


def extract_creators(posts: List[Dict], min_likes: int) -> List[Dict]:
    """Filter posts by engagement and extract unique creator profiles."""
    seen_urls = set()
    creators = []

    # Sort by likes descending
    posts.sort(key=lambda p: p.get('engagement', {}).get('likes', 0), reverse=True)

    for post in posts:
        likes = post.get('engagement', {}).get('likes', 0)
        if likes < min_likes:
            continue

        author = post.get('author', {})
        profile_url = author.get('linkedinUrl', '')

        # Clean profile URL (remove query params)
        if '?' in profile_url:
            profile_url = profile_url.split('?')[0]

        if not profile_url or profile_url in seen_urls:
            continue

        seen_urls.add(profile_url)
        creators.append({
            'linkedin_url': profile_url,
            'name': author.get('name', ''),
            'headline': author.get('info', ''),
            'sample_post_likes': likes,
            'added_date': datetime.now().strftime('%Y-%m-%d')
        })

    return creators


def append_creators(service, sheet_id: str, creators: List[Dict]):
    """Append new creators to the Creators tab."""
    if not creators:
        return

    rows = []
    for c in creators:
        rows.append([
            c['linkedin_url'],
            c['name'],
            c['headline'],
            str(c['sample_post_likes']),
            c['added_date']
        ])

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f'{TAB_CREATORS}!A:E',
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': rows}
    ).execute()


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Parasite — Find Viral Creators')
    parser.add_argument('--keyword', type=str, default='B2B sales',
                        help='Search keyword (default: "B2B sales")')
    parser.add_argument('--min-likes', type=int, default=100,
                        help='Minimum likes to qualify as viral (default: 100)')
    parser.add_argument('--max-results', type=int, default=200,
                        help='Max posts to search (default: 200)')
    args = parser.parse_args()

    # Validate API key
    apify_key = os.getenv('APIFY_API_KEY')
    if not apify_key:
        logger.error("APIFY_API_KEY not found in .env")
        sys.exit(1)

    logger.info("LinkedIn Parasite — Module 1: Find Viral Creators")
    logger.info("=" * 50)
    logger.info(f"  Keyword: {args.keyword}")
    logger.info(f"  Min likes: {args.min_likes}")
    logger.info(f"  Max results: {args.max_results}")
    logger.info("")

    # Initialize clients
    apify_client = ApifyClient(apify_key)
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # Get or create spreadsheet
    sheet_id = get_or_create_spreadsheet(service, drive_service)

    # Get existing creators (for dedup)
    existing_urls = get_existing_creator_urls(service, sheet_id)
    logger.info(f"Existing creators in database: {len(existing_urls)}")

    # Search LinkedIn
    posts = search_linkedin_posts(apify_client, args.keyword, args.max_results)
    if not posts:
        logger.warning("No posts found. Try a different keyword.")
        return

    # Extract creators
    all_creators = extract_creators(posts, args.min_likes)
    logger.info(f"Found {len(all_creators)} creators with {args.min_likes}+ likes")

    # Deduplicate
    new_creators = [c for c in all_creators if c['linkedin_url'] not in existing_urls]
    logger.info(f"New creators (not in database): {len(new_creators)}")

    if not new_creators:
        logger.info("No new creators to add.")
        return

    # Append to sheet
    append_creators(service, sheet_id, new_creators)

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info(f"Added {len(new_creators)} new creators:")
    for c in new_creators[:10]:
        logger.info(f"  {c['name']} — {c['sample_post_likes']} likes — {c['headline'][:60]}")
    if len(new_creators) > 10:
        logger.info(f"  ... and {len(new_creators) - 10} more")
    logger.info(f"Total creators in database: {len(existing_urls) + len(new_creators)}")


if __name__ == '__main__':
    main()
