#!/usr/bin/env python3
"""
CSV Direct Enrichment Script v1.0
Enriches CSV files in-place with business data from Google Maps, emails, and contacts.
NEVER removes rows - only fills missing data.

Usage:
    python execution/enrich_csv_directly.py --csv "input.csv" --output "output.csv" --location "City, Country"
"""

import os
import sys
import logging
import time
import re
import argparse
import pandas as pd
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from difflib import SequenceMatcher
from dotenv import load_dotenv
from apify_client import ApifyClient
import requests

load_dotenv()

# Logging setup
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/enrich_csv_directly.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class RapidAPIContactEnricher:
    """RapidAPI Google Search for contact enrichment."""

    def __init__(self, api_keys: List[str]):
        self.api_keys = [k for k in api_keys if k]
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2
        logger.info(f"✓ RapidAPI initialized with {len(self.api_keys)} keys")

    def _get_current_key(self) -> str:
        if not self.api_keys:
            return None
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _rate_limited_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
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

        if '.' in local_part:
            parts = local_part.split('.')
            valid_parts = [p for p in parts if p.isalpha() and 2 <= len(p) <= 20]
            if len(valid_parts) >= 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[-1].capitalize()
                return (f"{first} {last}", False, 0.95)

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
        query = f'"{company_name}" site:instagram.com'
        if location:
            query += f' "{location}"'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                if 'instagram.com/' in url and '/p/' not in url:
                    return url

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


class CSVDirectEnricher:
    """Main enrichment engine for CSV files."""

    ACTOR_ID = "nwua9Gu5YrADL7ZDj"

    def __init__(self):
        self.apify_token = os.getenv("APIFY_API_KEY")
        self.anymailfinder_token = os.getenv("ANYMAILFINDER_API_KEY")

        if not self.apify_token:
            raise ValueError("❌ APIFY_API_KEY not found in .env")

        rapidapi_keys_str = os.getenv("RAPIDAPI_KEYS", "")
        rapidapi_keys = [k.strip() for k in rapidapi_keys_str.split(",") if k.strip()]

        if not rapidapi_keys:
            single_key = os.getenv("RAPIDAPI_KEY")
            if single_key:
                rapidapi_keys = [single_key]

        self.apify_client = ApifyClient(self.apify_token)
        self.email_enricher = AnyMailFinder(self.anymailfinder_token) if self.anymailfinder_token else None
        self.contact_enricher = RapidAPIContactEnricher(rapidapi_keys) if rapidapi_keys else None

        logger.info("✓ CSVDirectEnricher initialized")

    def extract_domain(self, url: str) -> Optional[str]:
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
        for result in results:
            result_name = result.get('title', '') or result.get('name', '')
            if self.fuzzy_match_company(business_name, result_name, threshold=0.6):
                return result
        return None

    def enrich_row(self, row: pd.Series, gmap_data: Optional[Dict]) -> pd.Series:
        """Enrich a single row (PRESERVE existing data)."""
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
                        personal_emails = []
                        generic_emails = []

                        for email in email_result['emails']:
                            _, is_generic, _ = self.contact_enricher.extract_contact_from_email(email) if self.contact_enricher else ('', True, 0)
                            if is_generic:
                                generic_emails.append(email)
                            else:
                                personal_emails.append(email)

                        # Store ALL emails (will create duplicate rows later)
                        all_emails = personal_emails + generic_emails
                        row['Email'] = all_emails[0] if all_emails else ''
                        row['_all_emails'] = all_emails  # Temporary field for duplicate row creation

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

    def enrich_csv(self, input_csv: str, output_csv: str, location: str = "", test_limit: int = 0):
        """Enrich CSV file and save to output."""
        print(f"\n{'='*70}")
        print("🚀 CSV DIRECT ENRICHMENT v1.0")
        print(f"Input: {input_csv}")
        print(f"Output: {output_csv}")
        print(f"{'='*70}\n")

        # Read CSV
        df = pd.read_csv(input_csv, keep_default_na=False)
        logger.info(f"✓ Loaded CSV: {len(df)} rows, {len(df.columns)} columns")

        # Ensure required columns exist
        required_columns = [
            'Business Name', 'Primary Contact', 'Phone', 'Email', 'City',
            'Job Title', 'Contact LinkedIn', 'Website', 'Full Address',
            'Type', 'Quadrant', 'Company Social', 'Personal Instagram'
        ]

        for col in required_columns:
            if col not in df.columns:
                df[col] = ''

        # Test mode
        if test_limit > 0:
            df = df.head(test_limit)
            logger.info(f"⚠️ TEST MODE: Processing first {test_limit} rows only")

        # Batch lookup all businesses
        business_names = df['Business Name'].tolist()
        gmap_results = self.batch_lookup_google_maps(business_names, location)

        # Enrich each row
        logger.info(f"📊 Enriching {len(df)} rows...")

        # Helper function
        def is_empty(value):
            return pd.isna(value) or value == '' or not value

        enriched_rows = []

        for idx, row in df.iterrows():
            business_name = row['Business Name']
            gmap_data = self.match_business_result(business_name, gmap_results)
            enriched_row = self.enrich_row(row, gmap_data)

            # Check if multiple emails found
            all_emails = enriched_row.get('_all_emails', [])

            if isinstance(all_emails, list) and len(all_emails) > 1:
                # Create duplicate rows for each additional email
                for email in all_emails:
                    duplicate_row = enriched_row.copy()
                    duplicate_row['Email'] = email

                    # Re-enrich contact info for this specific email
                    if self.contact_enricher and not is_empty(email):
                        name, is_generic, confidence = self.contact_enricher.extract_contact_from_email(str(email))

                        if not is_generic and name and confidence >= 0.5:
                            contact_info = self.contact_enricher.search_by_name(name, business_name, row.get('City', ''))
                            if contact_info:
                                duplicate_row['Primary Contact'] = contact_info.get('name', '')
                                duplicate_row['Job Title'] = contact_info.get('title', '')
                                duplicate_row['Contact LinkedIn'] = contact_info.get('linkedin_url', '')

                    # Remove temporary field
                    if '_all_emails' in duplicate_row:
                        del duplicate_row['_all_emails']

                    enriched_rows.append(duplicate_row)

                logger.info(f"  ✓ {business_name}: Created {len(all_emails)} rows for {len(all_emails)} emails")
            else:
                # Single email or no email - keep as is
                if '_all_emails' in enriched_row:
                    del enriched_row['_all_emails']
                enriched_rows.append(enriched_row)

            if (idx + 1) % 10 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(df)}")

        logger.info("✓ Enrichment complete!")

        # Create new DataFrame from enriched rows
        df_final = pd.DataFrame(enriched_rows)

        # Ensure column order matches original
        final_columns = [col for col in df.columns if col in df_final.columns]
        df_final = df_final[final_columns]

        # Save to output CSV
        df_final.to_csv(output_csv, index=False)
        logger.info(f"✓ Saved to: {output_csv}")

        print(f"\n{'='*70}")
        print("✅ SUCCESS!")
        print(f"📊 Input: {len(df)} businesses")
        print(f"📊 Output: {len(df_final)} rows (includes duplicate rows for multiple emails)")
        print(f"💾 Output: {output_csv}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='CSV Direct Enrichment v1.0')
    parser.add_argument('--csv', type=str, required=True, help='Input CSV file path')
    parser.add_argument('--output', type=str, required=True, help='Output CSV file path')
    parser.add_argument('--location', type=str, default='', help='Default location for lookups')
    parser.add_argument('--test-limit', type=int, default=0, help='Test with first N rows only')

    args = parser.parse_args()

    try:
        enricher = CSVDirectEnricher()
        enricher.enrich_csv(args.csv, args.output, args.location, args.test_limit)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
