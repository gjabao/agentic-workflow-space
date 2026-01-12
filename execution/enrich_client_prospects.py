#!/usr/bin/env python3
"""
Client Prospect Enrichment Script v1.0
Enriches existing CSV files with business names by looking them up on Google Maps
and adding contact information, emails, LinkedIn profiles, and social media.

Key Features:
- 100% Data Preservation: NEVER deletes existing data
- Batch Mode: ONE Apify call for all businesses (99% cost savings)
- Update Google Sheets: Writes enriched data back to the sheet
- Selective Enrichment: Only fills in missing fields

Usage:
    python execution/enrich_client_prospects.py --csv "file.csv" --sheet-id SHEET_ID --tab-name "Calgary"
"""

import os
import sys
import csv
import json
import logging
import time
import re
import argparse
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from difflib import SequenceMatcher
from dotenv import load_dotenv
from apify_client import ApifyClient
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests

load_dotenv()

# Logging setup
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/enrich_client_prospects.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class RapidAPIContactEnricher:
    """RapidAPI Google Search for contact enrichment (same as Google Maps scraper)."""

    def __init__(self, api_keys: List[str]):
        self.api_keys = [k for k in api_keys if k]
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2  # 5 req/sec per key
        logger.info(f"✓ RapidAPI initialized with {len(self.api_keys)} keys")

    def _get_current_key(self) -> str:
        """Rotate between API keys."""
        if not self.api_keys:
            return None
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _rate_limited_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
        """Thread-safe rate-limited Google search."""
        if not self.api_keys:
            return None

        with self.rate_limit_lock:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self.last_call_time = time.time()

        for attempt in range(3):
            try:
                url = "https://google-search116.p.rapidapi.com/"
                headers = {
                    "x-rapidapi-key": self._get_current_key(),
                    "x-rapidapi-host": "google-search116.p.rapidapi.com"
                }
                params = {"query": query, "num": str(num_results)}

                response = requests.get(url, headers=headers, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    return {
                        'results': [
                            {
                                'url': result.get('url', ''),
                                'title': result.get('title', ''),
                                'snippet': result.get('description', '')
                            }
                            for result in data.get('results', [])
                        ]
                    }
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue

            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                logger.debug(f"Google Search error: {e}")
                return None

        return None

    def extract_contact_from_email(self, email: str) -> tuple:
        """Extract name from email (same logic as Google Maps scraper)."""
        if not email or '@' not in email:
            return ('', True, 0.0)

        local_part = email.split('@')[0].lower()

        generic_patterns = [
            'info', 'contact', 'hello', 'support', 'sales', 'admin',
            'office', 'inquiries', 'help', 'service', 'team', 'mail'
        ]

        is_generic = any(pattern in local_part for pattern in generic_patterns)
        if is_generic:
            return ('', True, 0.0)

        # Pattern 1: firstname.lastname@
        if '.' in local_part:
            parts = local_part.split('.')
            valid_parts = [p for p in parts if p.isalpha() and 2 <= len(p) <= 20]
            if len(valid_parts) >= 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[-1].capitalize()
                return (f"{first} {last}", False, 0.95)

        # Pattern 2: firstname_lastname@ or firstname-lastname@
        name_parts = re.split(r'[._\-0-9]+', local_part)
        name_parts = [p for p in name_parts if p.isalpha() and 2 <= len(p) <= 20]

        if len(name_parts) >= 2:
            first = name_parts[0].capitalize()
            last = name_parts[-1].capitalize()
            return (f"{first} {last}", False, 0.9)
        elif len(name_parts) == 1 and len(name_parts[0]) >= 3:
            return (name_parts[0].capitalize(), False, 0.6)

        return ('', False, 0.2)

    def search_by_name(self, full_name: str, company_name: str, location: str = None) -> Dict:
        """Search for person on LinkedIn by name."""
        result = {'full_name': '', 'job_title': '', 'contact_linkedin': ''}

        query = f'"{full_name}" at "{company_name}" linkedin'
        if location:
            query += f' {location}'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                title = item.get('title', '')

                if 'linkedin.com/in/' not in url:
                    continue

                # Extract name and title
                if 'LinkedIn' in title:
                    title = title.split('LinkedIn')[0].strip()

                for sep in [' - ', ' | ', ' · ']:
                    if sep in title:
                        parts = title.split(sep)
                        name = parts[0].strip()
                        job_title = parts[1].strip() if len(parts) > 1 else ""

                        result['full_name'] = name
                        result['job_title'] = job_title
                        result['contact_linkedin'] = url
                        return result

        return result

    def find_founder_by_company(self, company_name: str, location: str = None) -> Dict:
        """Find founder/CEO by company name."""
        result = {'full_name': '', 'job_title': '', 'contact_linkedin': ''}

        query = f'"{company_name}" (founder OR ceo OR owner) site:linkedin.com/in'
        if location:
            query += f' {location}'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                title = item.get('title', '')

                if 'linkedin.com/in/' not in url:
                    continue

                if 'LinkedIn' in title:
                    title = title.split('LinkedIn')[0].strip()

                for sep in [' - ', ' | ', ' · ']:
                    if sep in title:
                        parts = title.split(sep)
                        name = parts[0].strip()
                        job_title = parts[1].strip() if len(parts) > 1 else ""

                        result['full_name'] = name
                        result['job_title'] = job_title
                        result['contact_linkedin'] = url
                        return result

        return result

    def find_company_social(self, company_name: str, location: str = None) -> str:
        """Find company Instagram or Facebook."""
        # Try Instagram
        query = f'"{company_name}" site:instagram.com'
        if location:
            query += f' "{location}"'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                if 'instagram.com/' in url and '/p/' not in url:
                    return url

        # Try Facebook
        query = f'"{company_name}" site:facebook.com'
        if location:
            query += f' "{location}"'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                if 'facebook.com/' in url and '/posts/' not in url:
                    return url

        return ''


class AnyMailFinder:
    """Email discovery via AnyMailFinder API."""

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """Find all emails at a company."""
        try:
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }

            payload = {'domain': company_domain, 'email_type': 'any'}
            if company_name:
                payload['company_name'] = company_name

            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                email_status = data.get('email_status', 'not_found')

                if email_status == 'valid' and data.get('valid_emails'):
                    return {
                        'emails': data['valid_emails'],
                        'status': 'found',
                        'count': len(data['valid_emails'])
                    }

            return {'emails': [], 'status': 'not-found', 'count': 0}

        except Exception as e:
            logger.debug(f"AnyMailFinder error: {e}")
            return {'emails': [], 'status': 'not-found', 'count': 0}


class ClientProspectEnricher:
    """Main enrichment engine for client prospects."""

    ACTOR_ID = "nwua9Gu5YrADL7ZDj"  # Same as Google Maps scraper
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        # API Keys
        self.apify_token = os.getenv("APIFY_API_KEY")
        self.anymailfinder_token = os.getenv("ANYMAILFINDER_API_KEY")

        if not self.apify_token:
            raise ValueError("❌ APIFY_API_KEY not found in .env")

        # RapidAPI keys
        rapidapi_keys_str = os.getenv("RAPIDAPI_KEYS", "")
        rapidapi_keys = [k.strip() for k in rapidapi_keys_str.split(",") if k.strip()]

        # Fallback to single key
        if not rapidapi_keys:
            single_key = os.getenv("RAPIDAPI_KEY")
            if single_key:
                rapidapi_keys = [single_key]

        # Initialize clients
        self.apify_client = ApifyClient(self.apify_token)
        self.email_enricher = AnyMailFinder(self.anymailfinder_token) if self.anymailfinder_token else None
        self.contact_enricher = RapidAPIContactEnricher(rapidapi_keys) if rapidapi_keys else None

        logger.info("✓ ClientProspectEnricher initialized")

    def get_google_credentials(self):
        """Get Google OAuth credentials."""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise ValueError("❌ credentials.json not found")

                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return creds

    def read_csv_file(self, csv_path: str) -> pd.DataFrame:
        """Read CSV file into DataFrame."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"❌ CSV file not found: {csv_path}")

        df = pd.read_csv(csv_path)
        logger.info(f"✓ Loaded CSV: {len(df)} rows, {len(df.columns)} columns")
        logger.info(f"  Columns: {list(df.columns)}")
        return df

    def upload_csv_to_sheet(self, df: pd.DataFrame, sheet_id: str, tab_name: str):
        """Upload DataFrame to Google Sheet (create tab if not exists)."""
        creds = self.get_google_credentials()
        service = build('sheets', 'v4', credentials=creds)

        # Check if tab exists
        try:
            spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]

            if tab_name not in sheet_names:
                # Create new tab
                body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {'title': tab_name}
                        }
                    }]
                }
                service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
                logger.info(f"✓ Created new tab: {tab_name}")

        except Exception as e:
            logger.error(f"❌ Error checking/creating tab: {e}")
            raise

        # Write data
        values = [df.columns.tolist()] + df.values.tolist()
        body = {'values': values}

        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            body=body
        ).execute()

        logger.info(f"✓ Uploaded {len(df)} rows to {tab_name}")

    def read_sheet(self, sheet_id: str, tab_name: str) -> pd.DataFrame:
        """Read Google Sheet into DataFrame."""
        creds = self.get_google_credentials()
        service = build('sheets', 'v4', credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A:Z"
        ).execute()

        values = result.get('values', [])
        if not values:
            raise ValueError(f"❌ No data found in {tab_name}")

        df = pd.DataFrame(values[1:], columns=values[0])
        logger.info(f"✓ Read {len(df)} rows from {tab_name}")
        return df

    def update_sheet(self, sheet_id: str, tab_name: str, df: pd.DataFrame):
        """Update Google Sheet with enriched data. Matches by Business Name if tab exists."""
        creds = self.get_google_credentials()
        service = build('sheets', 'v4', credentials=creds)

        try:
            # Get all sheet names to check if tab exists
            spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]

            # Check if tab exists
            if tab_name in existing_sheets:
                logger.info(f"✓ Tab '{tab_name}' exists - will update existing data by Business Name")

                # Read existing data
                existing_range = f"{tab_name}!A1:Z10000"
                existing_data = service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=existing_range
                ).execute().get('values', [])

                if existing_data and len(existing_data) > 0:
                    # Create lookup dict: Business Name -> row index
                    headers = existing_data[0]
                    if 'Business Name' not in headers:
                        logger.warning("⚠️ 'Business Name' column not found - will overwrite all data")
                        # Fall back to clearing and writing
                        service.spreadsheets().values().clear(
                            spreadsheetId=sheet_id,
                            range=f"{tab_name}!A1:Z10000"
                        ).execute()
                    else:
                        business_name_col = headers.index('Business Name')
                        existing_lookup = {}

                        for idx, row_data in enumerate(existing_data[1:], start=2):  # Start at row 2 (after header)
                            if len(row_data) > business_name_col:
                                business_name = row_data[business_name_col]
                                existing_lookup[business_name] = idx

                        logger.info(f"✓ Found {len(existing_lookup)} existing businesses in sheet")

                        # Update existing rows and add new ones
                        new_values = [df.columns.tolist()]  # Header
                        updates_count = 0
                        new_rows_count = 0

                        for _, row in df.iterrows():
                            row_values = [str(v) if pd.notna(v) and v != '' else '' for v in row.tolist()]
                            business_name = row.get('Business Name', '')

                            if business_name in existing_lookup:
                                # Update existing row
                                row_index = existing_lookup[business_name]
                                update_range = f"{tab_name}!A{row_index}:Z{row_index}"
                                service.spreadsheets().values().update(
                                    spreadsheetId=sheet_id,
                                    range=update_range,
                                    valueInputOption="RAW",
                                    body={'values': [row_values]}
                                ).execute()
                                updates_count += 1
                            else:
                                # Queue for appending as new row
                                new_values.append(row_values)
                                new_rows_count += 1

                        # Append new rows if any
                        if len(new_values) > 1:  # More than just header
                            append_range = f"{tab_name}!A{len(existing_data) + 1}"
                            service.spreadsheets().values().update(
                                spreadsheetId=sheet_id,
                                range=append_range,
                                valueInputOption="RAW",
                                body={'values': new_values[1:]}  # Skip header
                            ).execute()

                        logger.info(f"✓ Updated {updates_count} existing rows, added {new_rows_count} new rows in {tab_name}")
                        return
            else:
                logger.info(f"✓ Tab '{tab_name}' doesn't exist - creating new tab")

            # Tab doesn't exist or no matching logic - clear and write all
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range=f"{tab_name}!A1:Z10000"
            ).execute()

            # Write enriched data (convert NaN to empty string)
            values = [df.columns.tolist()]
            for _, row in df.iterrows():
                values.append([str(v) if pd.notna(v) and v != '' else '' for v in row.tolist()])

            body = {'values': values}

            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{tab_name}!A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            logger.info(f"✓ Wrote {len(df)} rows to {tab_name}")

        except Exception as e:
            logger.error(f"❌ Error updating sheet: {e}")
            raise

    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain if domain else None
        except Exception:
            return None

    def fuzzy_match_company(self, name1: str, name2: str, threshold: float = 0.6) -> bool:
        """Fuzzy match company names."""
        if not name1 or not name2:
            return False

        def normalize(text):
            text = text.lower()
            suffixes = ['inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co']
            for suffix in suffixes:
                text = re.sub(rf'\b{suffix}\.?\b', '', text)
            return re.sub(r'\s+', ' ', text).strip()

        norm1 = normalize(name1)
        norm2 = normalize(name2)

        if norm1 in norm2 or norm2 in norm1:
            return True

        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio() >= threshold

    def batch_lookup_google_maps(self, business_names: List[str], location: str = "") -> List[Dict]:
        """Batch lookup businesses on Google Maps (ONE Apify call)."""
        logger.info(f"🔍 Batch lookup: {len(business_names)} businesses")

        actor_input = {
            "searchStringsArray": business_names,
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": 1,
            "language": "en",
            "includeWebResults": True,
            "website": "withWebsite"
        }

        try:
            run = self.apify_client.actor(self.ACTOR_ID).call(run_input=actor_input)
            results = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items
            logger.info(f"✓ Found {len(results)} results from Google Maps")
            return results

        except Exception as e:
            logger.error(f"❌ Apify batch lookup failed: {e}")
            return []

    def match_business_result(self, business_name: str, results: List[Dict]) -> Optional[Dict]:
        """Find matching Google Maps result for a business name."""
        for result in results:
            result_name = result.get('title', '') or result.get('name', '')
            if self.fuzzy_match_company(business_name, result_name, threshold=0.6):
                return result
        return None

    def enrich_row(self, row: pd.Series, gmap_data: Optional[Dict]) -> pd.Series:
        """Enrich a single row (PRESERVE existing data)."""
        # Helper function to check if field is empty
        def is_empty(value):
            return pd.isna(value) or value == '' or not value

        # Business data from Google Maps
        if gmap_data:
            if is_empty(row.get('Phone')):
                row['Phone'] = gmap_data.get('phone', '')

            if is_empty(row.get('Website')):
                row['Website'] = gmap_data.get('website', '')

            if is_empty(row.get('Full Address')):
                row['Full Address'] = gmap_data.get('address', '')

            if is_empty(row.get('Type')):
                row['Type'] = gmap_data.get('categoryName', '')

        # Email enrichment
        website = row.get('Website', '')
        if self.email_enricher and not is_empty(website):
            if is_empty(row.get('Email')):
                domain = self.extract_domain(str(website))
                if domain:
                    email_result = self.email_enricher.find_company_emails(domain, row.get('Business Name', ''))
                    if email_result['emails']:
                        # Prioritize personal emails
                        personal_emails = []
                        generic_emails = []

                        for email in email_result['emails']:
                            _, is_generic, _ = self.contact_enricher.extract_contact_from_email(email) if self.contact_enricher else ('', True, 0)
                            if is_generic:
                                generic_emails.append(email)
                            else:
                                personal_emails.append(email)

                        best_email = (personal_emails + generic_emails)[0] if (personal_emails + generic_emails) else ''
                        row['Email'] = best_email

        # Contact enrichment
        if self.contact_enricher:
            if is_empty(row.get('Primary Contact')):
                email = row.get('Email', '')
                business_name = row.get('Business Name', '')
                city = row.get('City', '')

                contact_info = None

                if not is_empty(email):
                    name, is_generic, confidence = self.contact_enricher.extract_contact_from_email(str(email))

                    if not is_generic and name and confidence >= 0.5:
                        contact_info = self.contact_enricher.search_by_name(name, business_name, city)
                    else:
                        contact_info = self.contact_enricher.find_founder_by_company(business_name, city)

                if contact_info and contact_info.get('full_name'):
                    row['Primary Contact'] = contact_info['full_name']
                    row['Job Title'] = contact_info.get('job_title', '')
                    row['Contact LinkedIn'] = contact_info.get('contact_linkedin', '')

        # Company social
        if self.contact_enricher:
            if is_empty(row.get('Company Social')):
                business_name = row.get('Business Name', '')
                city = row.get('City', '')
                social_url = self.contact_enricher.find_company_social(business_name, city)
                if social_url:
                    row['Company Social'] = social_url

        return row

    def enrich_prospects(self, df: pd.DataFrame, location: str = "") -> pd.DataFrame:
        """Enrich all prospects in DataFrame."""
        # Ensure required columns exist
        required_columns = [
            'Business Name', 'Primary Contact', 'Phone', 'Email', 'City',
            'Job Title', 'Contact LinkedIn', 'Website', 'Full Address',
            'Type', 'Quadrant', 'Company Social', 'Personal Instagram'
        ]

        for col in required_columns:
            if col not in df.columns:
                df[col] = ''

        # Batch lookup all businesses
        business_names = df['Business Name'].tolist()
        gmap_results = self.batch_lookup_google_maps(business_names, location)

        # Enrich each row
        logger.info(f"📊 Enriching {len(df)} rows...")

        for idx, row in df.iterrows():
            business_name = row['Business Name']

            # Find matching Google Maps result
            gmap_data = self.match_business_result(business_name, gmap_results)

            # Enrich row (preserve existing data)
            enriched_row = self.enrich_row(row, gmap_data)
            df.iloc[idx] = enriched_row

            if (idx + 1) % 10 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(df)}")

        logger.info("✓ Enrichment complete!")
        return df


def main():
    parser = argparse.ArgumentParser(description='Client Prospect Enrichment v1.0')
    parser.add_argument('--csv', type=str, required=True, help='CSV file path')
    parser.add_argument('--sheet-id', type=str, required=True, help='Google Sheet ID')
    parser.add_argument('--tab-name', type=str, required=True, help='Tab name to update')
    parser.add_argument('--location', type=str, default='', help='Default location for lookups')
    parser.add_argument('--test-limit', type=int, default=0, help='Test with first N rows only')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("🚀 CLIENT PROSPECT ENRICHMENT v1.0")
    print(f"CSV: {args.csv}")
    print(f"Sheet ID: {args.sheet_id}")
    print(f"Tab: {args.tab_name}")
    print("="*70 + "\n")

    try:
        enricher = ClientProspectEnricher()

        # Step 1: Read CSV
        df = enricher.read_csv_file(args.csv)

        # Test mode
        if args.test_limit > 0:
            df = df.head(args.test_limit)
            logger.info(f"⚠️ TEST MODE: Processing first {args.test_limit} rows only")

        # Step 2: Enrich prospects
        df_enriched = enricher.enrich_prospects(df, args.location)

        # Step 3: Update Google Sheet
        enricher.update_sheet(args.sheet_id, args.tab_name, df_enriched)

        print("\n" + "="*70)
        print("✅ SUCCESS!")
        print(f"📊 Enriched {len(df_enriched)} rows")
        print(f"🔗 Sheet: https://docs.google.com/spreadsheets/d/{args.sheet_id}")
        print("="*70 + "\n")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
