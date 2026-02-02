#!/usr/bin/env python3
"""
Email Extraction from Websites - Google Sheet Enrichment
Scrapes company websites to extract contact emails and fills missing email columns.

Usage:
    python3 extract_emails_from_websites.py --sheet-id "ABC123" --website-column "Website" --email-column "Email"
"""

import os
import re
import time
import argparse
import logging
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "delay_between_requests": 2.5,  # seconds (be polite)
    "timeout_per_site": 15,         # seconds
    "max_workers": 5,               # parallel threads
    "max_retries": 2,
    "check_contact_page": True,
    "check_about_page": True,
    "prefer_company_domain": True,
    "skip_existing_emails": True,
    "batch_update_size": 25,        # update sheet every N rows
}

CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/team"]

DISPOSABLE_DOMAINS = [
    "tempmail.com", "guerrillamail.com", "mailinator.com", "10minutemail.com",
    "throwaway.email", "temp-mail.org", "getnada.com", "trashmail.com"
]

GENERIC_PREFIXES = ["noreply", "no-reply", "donotreply", "do-not-reply", "bounce"]

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'.tmp/email_extraction_{int(time.time())}.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# GOOGLE SHEETS AUTHENTICATION
# ============================================================================

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('sheets', 'v4', credentials=creds)

# ============================================================================
# EMAIL VALIDATION
# ============================================================================

def validate_email(email: str) -> bool:
    """Validate email format and block disposables."""
    if not email:
        return False

    # RFC 5322 format check
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return False

    email_lower = email.lower().strip()

    # Block generic prefixes
    prefix = email_lower.split('@')[0]
    if prefix in GENERIC_PREFIXES:
        return False

    # Block disposable domains
    domain = email_lower.split('@')[1]
    if domain in DISPOSABLE_DOMAINS:
        return False

    return True

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url if url.startswith('http') else f'http://{url}')
        domain = parsed.netloc or parsed.path
        return domain.replace('www.', '').lower()
    except:
        return ""

# ============================================================================
# EMAIL EXTRACTION ENGINE
# ============================================================================

class EmailExtractor:
    """Thread-safe email extractor with rate limiting."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
        })
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = CONFIG["delay_between_requests"]

    def _rate_limit(self):
        """Thread-safe rate limiting."""
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self.last_call_time = time.time()

    def _fetch_page(self, url: str, timeout: int = None) -> Optional[str]:
        """Fetch webpage HTML with retries."""
        timeout = timeout or CONFIG["timeout_per_site"]

        # Ensure URL has scheme
        if not url.startswith('http'):
            url = f'https://{url}'

        for attempt in range(CONFIG["max_retries"]):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=timeout, allow_redirects=True)

                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                if response.status_code == 200:
                    return response.text

                logger.warning(f"Status {response.status_code} for {url}")
                return None

            except requests.Timeout:
                logger.warning(f"Timeout on {url} (attempt {attempt + 1})")
                if attempt < CONFIG["max_retries"] - 1:
                    time.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                return None

        return None

    def _extract_emails_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract all emails from HTML content."""
        emails = set()

        # Regex pattern for emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        # Extract from text
        found_emails = re.findall(email_pattern, html)
        emails.update(found_emails)

        # Extract from mailto: links
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a', href=True):
            if link['href'].startswith('mailto:'):
                email = link['href'].replace('mailto:', '').split('?')[0]
                emails.add(email)

        # Validate all emails
        valid_emails = [e for e in emails if validate_email(e)]

        return valid_emails

    def _rank_emails(self, emails: List[str], website_domain: str) -> List[Tuple[str, int]]:
        """Rank emails by priority (higher score = better)."""
        scored_emails = []

        for email in emails:
            score = 0
            email_lower = email.lower()
            prefix = email_lower.split('@')[0]
            domain = email_lower.split('@')[1]

            # Prefer company domain
            if CONFIG["prefer_company_domain"] and domain in website_domain:
                score += 100

            # Prefer professional prefixes
            if prefix in ['contact', 'info', 'hello']:
                score += 50
            elif prefix in ['team', 'support', 'sales']:
                score += 30
            elif prefix in ['admin', 'office']:
                score += 20

            # Penalize generic domains
            if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                score -= 20

            scored_emails.append((email, score))

        # Sort by score (descending)
        scored_emails.sort(key=lambda x: x[1], reverse=True)
        return scored_emails

    def extract_email(self, website: str) -> Optional[str]:
        """Extract best email from website."""
        if not website:
            return None

        domain = extract_domain(website)
        all_emails = []

        # 1. Check homepage
        logger.info(f"Checking {website}")
        html = self._fetch_page(website)
        if html:
            all_emails.extend(self._extract_emails_from_html(html, website))

        # 2. Check contact/about pages
        base_url = website if website.startswith('http') else f'https://{website}'

        if CONFIG["check_contact_page"]:
            for path in CONTACT_PATHS:
                contact_url = urljoin(base_url, path)
                html = self._fetch_page(contact_url)
                if html:
                    # Emails from contact pages get higher priority
                    contact_emails = self._extract_emails_from_html(html, contact_url)
                    all_emails = contact_emails + all_emails  # Prepend for priority
                    if contact_emails:
                        break  # Found emails on contact page

        if not all_emails:
            logger.warning(f"No emails found for {website}")
            return None

        # Remove duplicates
        unique_emails = list(set(all_emails))

        # Rank and return best email
        ranked = self._rank_emails(unique_emails, domain)

        if ranked:
            best_email = ranked[0][0]
            logger.info(f"✓ Found email for {website}: {best_email}")
            return best_email

        return None

# ============================================================================
# GOOGLE SHEETS OPERATIONS
# ============================================================================

def read_sheet(service, sheet_id: str, range_name: str) -> List[List]:
    """Read data from Google Sheet."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_name
    ).execute()
    return result.get('values', [])

def update_sheet_batch(service, sheet_id: str, updates: List[dict]):
    """Batch update Google Sheet."""
    body = {'data': updates, 'valueInputOption': 'RAW'}
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body=body
    ).execute()

def find_column_index(headers: List[str], column_name: str) -> int:
    """Find column index by name (case-insensitive)."""
    column_name_lower = column_name.lower()
    for i, header in enumerate(headers):
        if header.lower() == column_name_lower:
            return i
    return -1

# ============================================================================
# MAIN ENRICHMENT LOGIC
# ============================================================================

def enrich_sheet_with_emails(
    sheet_id: str,
    website_column: str,
    email_column: str,
    start_row: int = 2,
    end_row: Optional[int] = None
):
    """Main function to enrich Google Sheet with emails."""

    logger.info("🚀 Starting email extraction workflow...")

    # Authenticate
    service = authenticate_google_sheets()
    logger.info("✓ Google Sheets authenticated")

    # Read sheet data
    range_name = f'A1:ZZ{end_row or 10000}'
    data = read_sheet(service, sheet_id, range_name)

    if not data:
        logger.error("❌ Sheet is empty")
        return

    headers = data[0]
    logger.info(f"✓ Found {len(headers)} columns")

    # Find column indices
    website_idx = find_column_index(headers, website_column)
    email_idx = find_column_index(headers, email_column)

    if website_idx == -1:
        logger.error(f"❌ Website column '{website_column}' not found")
        return

    # Create email column if missing
    if email_idx == -1:
        logger.warning(f"Email column '{email_column}' not found, creating it...")
        email_idx = len(headers)
        headers.append(email_column)
        update_sheet_batch(service, sheet_id, [{
            'range': f'{chr(65 + email_idx)}1',
            'values': [[email_column]]
        }])
        logger.info(f"✓ Created column '{email_column}' at position {email_idx + 1}")

    # Filter rows needing emails
    rows_to_process = []
    for i, row in enumerate(data[start_row - 1:], start=start_row):
        # Ensure row has enough columns
        while len(row) <= max(website_idx, email_idx):
            row.append('')

        website = row[website_idx].strip() if website_idx < len(row) else ''
        email = row[email_idx].strip() if email_idx < len(row) else ''

        # Skip if no website or email already exists
        if not website:
            continue
        if CONFIG["skip_existing_emails"] and email:
            continue

        rows_to_process.append((i, website, row))

    total_rows = len(rows_to_process)
    logger.info(f"📊 Found {total_rows} rows needing email extraction")

    if total_rows == 0:
        logger.info("✓ All rows already have emails!")
        return

    # Extract emails (parallel processing)
    extractor = EmailExtractor()
    updates = []
    completed = 0
    found = 0

    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
        futures = {
            executor.submit(extractor.extract_email, website): (row_num, website, row)
            for row_num, website, row in rows_to_process
        }

        for future in as_completed(futures):
            row_num, website, row = futures[future]
            completed += 1

            try:
                email = future.result()

                if email:
                    found += 1
                    # Prepare update
                    cell = f'{chr(65 + email_idx)}{row_num}'
                    updates.append({
                        'range': cell,
                        'values': [[email]]
                    })
                    logger.info(f"✓ [{completed}/{total_rows}] {website} → {email}")
                else:
                    logger.warning(f"⚠ [{completed}/{total_rows}] No email found for {website}")

                # Batch update every N rows
                if len(updates) >= CONFIG["batch_update_size"]:
                    update_sheet_batch(service, sheet_id, updates)
                    logger.info(f"📝 Updated {len(updates)} rows in sheet")
                    updates = []

            except Exception as e:
                logger.error(f"❌ Error processing {website}: {str(e)}")

            # Progress update
            if completed % 10 == 0:
                progress = (completed / total_rows) * 100
                logger.info(f"⏳ Progress: {completed}/{total_rows} ({progress:.0f}%) | Found: {found}")

    # Final batch update
    if updates:
        update_sheet_batch(service, sheet_id, updates)
        logger.info(f"📝 Updated {len(updates)} rows in sheet")

    # Summary
    success_rate = (found / total_rows) * 100 if total_rows > 0 else 0
    logger.info(f"""
    ✅ EMAIL EXTRACTION COMPLETE
    ═══════════════════════════════════════
    Total Rows Processed: {total_rows}
    Emails Found: {found}/{total_rows} ({success_rate:.1f}%)
    Failed Extractions: {total_rows - found}
    ═══════════════════════════════════════
    """)

# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract emails from websites and enrich Google Sheet'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--sheet-id', help='Google Sheet ID')
    group.add_argument('--sheet-url', help='Google Sheet URL')

    parser.add_argument('--website-column', required=True, help='Column name containing websites')
    parser.add_argument('--email-column', required=True, help='Column name for emails')
    parser.add_argument('--start-row', type=int, default=2, help='Start row (default: 2)')
    parser.add_argument('--end-row', type=int, help='End row (optional)')

    args = parser.parse_args()

    # Extract sheet ID from URL if needed
    sheet_id = args.sheet_id
    if args.sheet_url:
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', args.sheet_url)
        if match:
            sheet_id = match.group(1)
        else:
            logger.error("❌ Invalid Google Sheet URL")
            return

    # Run enrichment
    enrich_sheet_with_emails(
        sheet_id=sheet_id,
        website_column=args.website_column,
        email_column=args.email_column,
        start_row=args.start_row,
        end_row=args.end_row
    )

if __name__ == '__main__':
    main()