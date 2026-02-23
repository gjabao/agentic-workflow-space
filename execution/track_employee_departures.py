#!/usr/bin/env python3
"""
Employee Departure Tracker v1.1 - Find Decision Makers at Previous Companies

WORKFLOW:
1. Read Google Sheet with LinkedIn profile URLs (people who changed jobs)
2. Scrape LinkedIn profiles via Apify (harvestapi/linkedin-profile-scraper)
3. Extract PREVIOUS company (job they JUST LEFT, within 6 months)
4. Find decision makers at previous company (email-first approach)
5. Output to Google Sheet

Based on: execution/scrape_crunchbase.py (v4.0 email-first workflow)
Directive: directives/track_employee_departures.md
"""

import os
import sys
import csv
import json
import time
import re
import argparse
import logging
import threading
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from difflib import SequenceMatcher

# Third-party imports
try:
    from apify_client import ApifyClient
    import requests
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install: pip install apify-client requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']


class AnyMailFinder:
    """
    Company Email Finder - Returns ALL emails at a company (up to 20)
    Thread-safe with rate limiting and retry logic.
    """

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self._auth_header = api_key  # Stored minimally for request auth
        self._rate_limit_lock = Lock()
        self._last_call_time = 0
        self._min_delay = 0.2  # 5 req/sec max
        logger.info("✓ AnyMailFinder (Company Email API) initialized")

    def __repr__(self):
        return "<AnyMailFinder initialized>"

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """
        Find ALL emails at a company in ONE call.
        Returns up to 20 emails per company.
        Thread-safe with rate limiting and retry on 429.
        """
        # Rate limiting
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_call_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)
            self._last_call_time = time.time()

        for attempt in range(3):
            try:
                headers = {
                    'Authorization': self._auth_header,
                    'Content-Type': 'application/json'
                }

                payload = {
                    'domain': company_domain,
                    'email_type': 'any'
                }

                if company_name:
                    payload['company_name'] = company_name

                response = requests.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=15
                )

                if response.status_code == 200:
                    data = response.json()
                    email_status = data.get('email_status', 'not_found')

                    if email_status == 'valid' and data.get('valid_emails'):
                        return {
                            'emails': data['valid_emails'],
                            'status': 'found',
                            'count': len(data['valid_emails'])
                        }
                    else:
                        return {'emails': [], 'status': 'not-found', 'count': 0}
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.debug(f"AnyMailFinder 429 for {company_domain}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return {'emails': [], 'status': 'not-found', 'count': 0}

            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                logger.debug(f"Error for {company_domain}: {e}")
                return {'emails': [], 'status': 'not-found', 'count': 0}

        return {'emails': [], 'status': 'not-found', 'count': 0}


class RapidAPIGoogleSearch:
    """
    RapidAPI Google Search - For LinkedIn profile enrichment
    Thread-safe key rotation and rate limiting.
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.1  # 10 req/sec per key (faster with 2 keys)
        logger.info(f"✓ RapidAPI Google Search initialized ({len(api_keys)} keys)")

    def __repr__(self):
        return f"<RapidAPIGoogleSearch keys={len(self.api_keys)}>"

    def _get_current_key(self) -> str:
        """Thread-safe key rotation"""
        with self.rate_limit_lock:
            key = self.api_keys[self.current_key_index]
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _rate_limited_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
        """Thread-safe rate-limited Google search"""
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
                return None

        return None

    def _is_name_match(self, name1: str, name2: str, threshold: float = 0.7) -> bool:
        if not name1 or not name2:
            return False
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        if n1 in n2 or n2 in n1:
            return True
        matcher = SequenceMatcher(None, n1, n2)
        return matcher.ratio() >= threshold

    def _extract_name_from_title(self, title: str) -> str:
        if not title:
            return ""
        if 'LinkedIn' in title:
            title = title.split('LinkedIn')[0].strip()
        for separator in [' - ', ' | ', ' · ', ', ', ' at ', ' @ ']:
            if separator in title:
                name = title.split(separator)[0].strip()
                name = re.sub(r'[^\w\s]$', '', name)
                if len(name) >= 3:
                    return name
        return re.sub(r'[^\w\s]$', '', title.strip()) if len(title.strip()) >= 3 else ""

    def _extract_title_from_search(self, title: str, snippet: str) -> str:
        combined = title + ' ' + snippet
        patterns = [
            r' - ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+|\s*-\s*)',
            r' \| ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',
            r' · ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',
            r', ([^,]+?)(?:\s+at\s+|\s+@\s+)',
            r'\b((?:Chief|Senior|Vice President|VP|Director|Manager|Owner|Founder|Co-Founder|CEO|COO|CFO|CTO|President|Partner|Executive)\s*(?:of|at|for|&)?\s*[A-Za-z\s]{0,30})\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                title_text = match.group(1).strip()
                if 3 <= len(title_text) <= 100:
                    title_text = re.sub(r'\s+', ' ', title_text)
                    title_text = re.sub(r'[^\w\s&-]$', '', title_text)
                    if not re.search(r'(http|www\.|\.com|linkedin)', title_text, re.IGNORECASE):
                        return title_text.strip()
        return ""

    def search_by_name(self, full_name: str, company_name: str) -> Dict:
        """Search for person by name + company"""
        result = {'full_name': full_name, 'job_title': '', 'contact_linkedin': ''}

        search_attempts = [
            (f'"{full_name}" at "{company_name}" linkedin', 5),
            (f'{full_name} "{company_name}" linkedin', 5),
            (f'{full_name} {company_name} linkedin', 7)
        ]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            data = self._rate_limited_search(query, num_results=num_results)

            if data and data.get('results'):
                for item in data['results']:
                    url = item.get('url', '')
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')

                    if 'linkedin.com/in/' not in url:
                        continue

                    extracted_name = self._extract_name_from_title(title)
                    if not extracted_name or not self._is_name_match(full_name, extracted_name, threshold=0.6):
                        continue

                    job_title = self._extract_title_from_search(title, snippet)

                    result['full_name'] = extracted_name
                    result['job_title'] = job_title if job_title else ""
                    result['contact_linkedin'] = url
                    logger.info(f"    ✓ Found on LinkedIn: {extracted_name} - {job_title}")
                    return result

        logger.info(f"    ✗ LinkedIn not found for: {full_name}")
        return result


class EmployeeDepartureTracker:
    """
    Track employee departures and find decision makers at their previous companies
    """

    def __init__(self):
        logger.info("⏳ Initializing EmployeeDepartureTracker v1.1...")

        # Load API keys (Load → Use → Delete pattern)
        apify_key = self._load_secret("APIFY_API_KEY", required=True)
        amf_key = self._load_secret("ANYMAILFINDER_API_KEY", required=True)

        rapidapi_keys = [
            os.getenv("RAPIDAPI_KEY"),
            os.getenv("RAPIDAPI_KEY_2")
        ]
        rapidapi_keys = [k for k in rapidapi_keys if k]
        if not rapidapi_keys:
            raise ValueError("❌ RAPIDAPI_KEY not found in .env file")

        # Initialize clients (keys passed directly, not stored on self)
        self.apify_client = ApifyClient(apify_key)
        self.email_enricher = AnyMailFinder(amf_key)
        self.search_client = RapidAPIGoogleSearch(rapidapi_keys)

        # Delete local key references
        del apify_key
        del amf_key
        del rapidapi_keys

        # Global semaphore to cap total concurrent API calls across nested executors
        self._api_semaphore = threading.Semaphore(15)

        logger.info("✓ EmployeeDepartureTracker v1.1 initialized")

    def __repr__(self):
        return "<EmployeeDepartureTracker v1.1>"

    def _load_secret(self, key_name: str, required: bool = False) -> Optional[str]:
        value = os.getenv(key_name)
        if required and not value:
            raise ValueError(f"❌ {key_name} not found in .env file")
        if value:
            logger.info(f"  ✓ {key_name} loaded")
        return value

    def _get_google_creds(self):
        """Get Google API credentials"""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise ValueError("❌ credentials.json not found")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return creds

    def read_linkedin_urls_from_sheet(self, sheet_url: str) -> List[str]:
        """Read LinkedIn profile URLs from Google Sheet"""
        logger.info(f"📊 Reading LinkedIn URLs from Google Sheet...")

        # Extract spreadsheet ID from URL
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
        if not match:
            raise ValueError(f"❌ Invalid Google Sheets URL: {sheet_url}")

        spreadsheet_id = match.group(1)

        creds = self._get_google_creds()
        service = build('sheets', 'v4', credentials=creds)

        # Read all data from first sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="A:Z"
        ).execute()

        values = result.get('values', [])

        if not values:
            logger.warning("⚠️ No data found in sheet")
            return []

        # Find linkedin_url column (specifically "linkedin url" or "linkedin_url")
        headers = [h.lower().strip() for h in values[0]]

        linkedin_col = None

        # Priority 1: Exact match "linkedin" (personal profiles column)
        for i, h in enumerate(headers):
            if h == 'linkedin':
                linkedin_col = i
                break

        # Priority 2: Exact match "linkedin url" or "linkedin_url"
        if linkedin_col is None:
            for i, h in enumerate(headers):
                if h == 'linkedin url' or h == 'linkedin_url' or h == 'linkedinurl':
                    linkedin_col = i
                    break

        # Priority 3: Contains "linkedin" but NOT "company" (avoid company linkedin)
        if linkedin_col is None:
            for i, h in enumerate(headers):
                if 'linkedin' in h and 'company' not in h:
                    linkedin_col = i
                    break

        # Priority 4: Just "url" column
        if linkedin_col is None:
            for i, h in enumerate(headers):
                if h == 'url':
                    linkedin_col = i
                    break

        if linkedin_col is None:
            # Fallback: scan all columns for LinkedIn URLs
            logger.info("⚠️ No 'linkedin url' column found, scanning all columns...")
            data_rows = values[1:]
            urls = []
            for row in data_rows:
                for cell in row:
                    if isinstance(cell, str) and 'linkedin.com/in/' in cell:
                        urls.append(cell.strip())
                        break
            logger.info(f"✓ Found {len(urls)} LinkedIn profile URLs")
            return urls

        logger.info(f"✓ Found 'linkedin url' column at index {linkedin_col}: '{headers[linkedin_col]}'")
        data_rows = values[1:]

        urls = []
        for row in data_rows:
            if len(row) > linkedin_col:
                url = row[linkedin_col].strip()
                if 'linkedin.com/in/' in url:
                    urls.append(url)

        logger.info(f"✓ Found {len(urls)} LinkedIn profile URLs")
        return urls

    def scrape_linkedin_profiles(self, urls: List[str]) -> List[Dict]:
        """Scrape LinkedIn profiles using Apify harvestapi actor"""
        logger.info(f"⏳ Scraping {len(urls)} LinkedIn profiles via Apify...")

        run_input = {
            "profileScraperMode": "Profile details no email ($4 per 1k)",
            "queries": urls
        }

        run = self.apify_client.actor("harvestapi/linkedin-profile-scraper").call(run_input=run_input)

        profiles = []
        for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
            profiles.append(item)

        logger.info(f"✓ Scraped {len(profiles)} profiles")
        return profiles

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for comparison"""
        if not name:
            return ''
        # Lowercase, remove common suffixes, strip whitespace
        normalized = name.lower().strip()
        suffixes = [' inc', ' inc.', ' llc', ' ltd', ' ltd.', ' corp', ' corp.',
                   ' co', ' co.', ' company', ' limited', ' gmbh', ' ag', ' sa']
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        return normalized.strip()

    def _normalize_job_title(self, title: str) -> str:
        """
        Normalize and clean job title
        Examples:
        - "Director of Sales, North America (Full-time)" → "Director of Sales"
        - "Managing Director, Sales & Retention, North America (Full-time)" → "Managing Director"
        - "CEO & Co-Founder" → "CEO & Co-Founder"
        """
        if not title:
            return ''

        # Remove (Full-time), (Part-time), (Contract), etc.
        title = re.sub(r'\s*\([^)]*\)\s*', ' ', title)

        # Remove location/region suffixes after comma
        # But keep important parts like "CEO & Co-Founder"
        location_patterns = [
            r',\s*(North America|EMEA|APAC|Europe|Asia|Americas|Global|Worldwide|Canada|USA|US|UK).*$',
            r',\s*(Remote|Hybrid|On-site|Onsite).*$',
        ]
        for pattern in location_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # Remove trailing commas and extra whitespace
        title = re.sub(r',\s*$', '', title)
        title = ' '.join(title.split())

        return title.strip()

    def extract_previous_company(self, profile: Dict) -> Optional[Dict]:
        """
        Extract the company they JUST LEFT (within 6 months)

        Logic:
        - Filter jobs with endDate.year (not "Present")
        - Filter jobs ended within 6 months
        - SKIP internal promotions (same company, different role)
        - Return most recent ACTUAL departure (different company)
        """
        experiences = profile.get('experience', [])

        if not experiences:
            return None

        # First, find all CURRENT companies (jobs with "Present")
        current_companies = set()
        for exp in experiences:
            end_date = exp.get('endDate', {})
            if not end_date or end_date.get('text') == 'Present':
                company_name = self._normalize_company_name(exp.get('companyName', ''))
                if company_name:
                    current_companies.add(company_name)

        # Find jobs that have ended (not "Present")
        recent_departures = []

        for exp in experiences:
            end_date = exp.get('endDate', {})

            # Skip current jobs
            if not end_date:
                continue
            if end_date.get('text') == 'Present':
                continue

            end_year = end_date.get('year')
            company_name = exp.get('companyName', '')
            normalized_company = self._normalize_company_name(company_name)

            # SKIP if this is an internal promotion (still at same company)
            # Example: Peter Liu went from "Associate Director" to "Director" at Legacy+
            # Both roles are at Legacy+, so this is NOT a departure
            if normalized_company in current_companies:
                continue  # Skip - this is just a role change, not a company departure

            if end_year:
                recent_departures.append({
                    'company_name': company_name,
                    'company_linkedin_url': exp.get('companyLinkedinUrl', ''),
                    'position': self._normalize_job_title(exp.get('position', '')),
                    'location': exp.get('location', ''),
                    'end_year': end_year,
                    'duration': exp.get('duration', '')
                })

        if not recent_departures:
            return None

        # Filter: Only jobs ended in last 6 months
        # Current date: Feb 2026
        # If month <= 6 (Jan-Jun), cutoff = previous year (2025)
        # If month > 6 (Jul-Dec), cutoff = current year (2026)
        current_year = datetime.now().year  # 2026
        current_month = datetime.now().month  # 2 (February)

        if current_month <= 6:
            # We're in first half of 2026, so accept jobs that ended in 2025 or 2026
            cutoff_year = current_year - 1  # 2025
        else:
            # We're in second half, only accept current year
            cutoff_year = current_year  # 2026

        recent_departures = [
            dep for dep in recent_departures
            if dep['end_year'] >= cutoff_year  # end_year >= 2025
        ]

        if not recent_departures:
            return None

        # Sort by end_year descending and return most recent
        recent_departures.sort(key=lambda x: x['end_year'], reverse=True)
        most_recent = recent_departures[0]

        # Split name into first and last
        first_name = profile.get('firstName', '').strip()
        last_name = profile.get('lastName', '').strip()

        return {
            'first_name': first_name,
            'last_name': last_name,
            'person_who_left': f"{first_name} {last_name}".strip(),
            'person_linkedin': profile.get('linkedinUrl', ''),
            'person_headline': profile.get('headline', ''),
            'role_they_left': most_recent['position'],
            'previous_company': most_recent['company_name'],
            'company_linkedin_url': most_recent['company_linkedin_url'],
            'left_date': most_recent['end_year'],
            'location': most_recent['location']
        }

    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email format (RFC 5322 simplified)"""
        if not email or '@' not in email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _find_company_website(self, company_name: str) -> Optional[str]:
        """Find company website via Google Search (3 attempts) with strict filtering"""

        # Bad domains to ALWAYS skip (data aggregators, job sites, etc.)
        BAD_DOMAINS = {
            # Social media
            'linkedin.com', 'twitter.com', 'facebook.com', 'instagram.com',
            'youtube.com', 'tiktok.com', 'x.com',
            # Data aggregators
            'rocketreach.co', 'zoominfo.com', 'apollo.io', 'lusha.com',
            'clearbit.com', 'hunter.io', 'snov.io', 'seamless.ai',
            'leadiq.com', 'salesintel.io', 'datanyze.com',
            # Business directories
            'crunchbase.com', 'bloomberg.com', 'pitchbook.com', 'owler.com',
            'dnb.com', 'hoovers.com', 'manta.com', 'yellowpages.com',
            'yelp.com', 'bbb.org', 'glassdoor.com', 'indeed.com',
            # Reference sites
            'wikipedia.org', 'wikimedia.org', 'britannica.com',
            # News/media
            'forbes.com', 'techcrunch.com', 'reuters.com', 'bloomberg.com',
            'businessinsider.com', 'inc.com', 'entrepreneur.com',
            # Other
            'github.com', 'medium.com', 'substack.com', 'pdf'
        }

        search_attempts = [
            (f'"{company_name}" official website', 7),
            (f'{company_name} company homepage', 7),
            (f'{company_name} website', 10)
        ]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            logger.info(f"    🔍 Website search {attempt_num}/3: {query}")

            search_result = self.search_client._rate_limited_search(query, num_results=num_results)

            if not search_result or not search_result.get('results'):
                continue

            for result in search_result['results']:
                url = result.get('url', '')
                title = result.get('title', '').lower()

                # Extract domain
                domain = url.replace('https://', '').replace('http://', '').split('/')[0].replace('www.', '').lower()

                # Skip bad domains
                if any(bad in domain for bad in BAD_DOMAINS):
                    continue

                # Skip if domain is too generic (less than 4 chars before TLD)
                domain_name = domain.split('.')[0] if '.' in domain else domain
                if len(domain_name) < 3:
                    continue

                # Check if company name matches URL or title
                company_lower = company_name.lower().replace('.', '').replace(' ', '')
                domain_clean = domain.replace('.', '').replace('-', '')

                # Match strategies:
                # 1. Company name in domain (f12.net contains "f12")
                # 2. Company name in title
                # 3. Domain name similar to company name
                company_words = company_name.lower().split()

                match_found = False

                # Strategy 1: Domain contains company name or key word
                if company_lower in domain_clean:
                    match_found = True
                elif any(word in domain for word in company_words if len(word) > 3):
                    match_found = True
                # Strategy 2: Title contains company name
                elif company_lower in title.replace(' ', ''):
                    match_found = True
                elif any(word in title for word in company_words if len(word) > 3):
                    match_found = True

                if match_found:
                    logger.info(f"    ✓ Found website: {domain}")
                    return domain

        logger.info(f"    ✗ Website not found")
        return None

    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """Extract name from email pattern"""
        if not email or '@' not in email:
            return ('', True, 0.0)

        local_part = email.split('@')[0].lower()

        generic_patterns = [
            'info', 'contact', 'hello', 'support', 'sales', 'admin',
            'office', 'inquiries', 'help', 'service', 'team', 'mail',
            'general', 'reception', 'booking', 'hr', 'jobs', 'careers'
        ]

        is_generic = any(pattern in local_part for pattern in generic_patterns)
        if is_generic:
            return ('', True, 0.0)

        # Pattern: firstname.lastname@
        if '.' in local_part:
            parts = local_part.split('.')
            valid_parts = [p for p in parts if p.isalpha() and 1 <= len(p) <= 20]
            if len(valid_parts) >= 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[-1].capitalize()
                return (f"{first} {last}", False, 0.95)

        # Pattern: firstname_lastname@ or firstname-lastname@
        name_parts = re.split(r'[._\-0-9]+', local_part)
        name_parts = [p for p in name_parts if p.isalpha() and 2 <= len(p) <= 20]

        if len(name_parts) >= 2:
            first = name_parts[0].capitalize()
            last = name_parts[-1].capitalize()
            return (f"{first} {last}", False, 0.9)

        if len(name_parts) == 1 and len(name_parts[0]) >= 3:
            return (name_parts[0].capitalize(), False, 0.6)

        return ('', False, 0.2)

    def is_decision_maker(self, job_title: str) -> bool:
        """Check if job title is a decision-maker position"""
        if not job_title or len(job_title) < 3:
            return False

        job_title_lower = job_title.lower()

        dm_keywords = [
            'founder', 'co-founder', 'ceo', 'chief executive', 'chief',
            'owner', 'president', 'cfo', 'cto', 'coo', 'cmo',
            'c-suite', 'c-level',
            'vice president', 'vp ', 'director', 'executive director', 'managing director',
            'head of', 'managing partner', 'partner', 'principal',
            'executive'
        ]

        exclude_keywords = [
            'assistant', 'associate', 'junior', 'intern', 'coordinator',
            'analyst', 'specialist', 'representative', 'agent', 'clerk'
        ]

        has_dm = any(kw in job_title_lower for kw in dm_keywords)
        has_exclude = any(kw in job_title_lower for kw in exclude_keywords)

        return has_dm and not has_exclude

    def _build_departure_row(self, departure_info: Dict, domain: str = '',
                              full_name: str = '', job_title: str = '',
                              email: str = '', linkedin_url: str = '') -> Dict:
        """Build a single output row for a decision-maker (or empty DM placeholder)"""
        return {
            'departed_first_name': departure_info.get('first_name', ''),
            'departed_last_name': departure_info.get('last_name', ''),
            'departed_linkedin': departure_info['person_linkedin'],
            'role_they_left': departure_info['role_they_left'],
            'previous_company': departure_info['previous_company'],
            'left_date': departure_info['left_date'],
            'dm_first_name': full_name.split()[0] if full_name else '',
            'dm_last_name': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
            'dm_job_title': self._normalize_job_title(job_title),
            'dm_email': email,
            'dm_linkedin_url': linkedin_url,
            'company_website': domain
        }

    def enrich_previous_company(self, departure_info: Dict) -> List[Dict]:
        """
        Find decision makers at the previous company.
        Returns list of decision makers with emails.
        If no DMs found, returns a placeholder row per directive.
        """
        company_name = departure_info['previous_company']
        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Previous Company: {company_name}")
        logger.info(f"   Person who left: {departure_info['person_who_left']} ({departure_info['role_they_left']})")

        # Find website
        domain = self._find_company_website(company_name)
        if not domain:
            logger.info(f"   ⊘ No website found - including placeholder row")
            return [self._build_departure_row(departure_info)]

        # Find emails
        logger.info(f"   📧 Finding emails at {domain}...")
        email_result = self.email_enricher.find_company_emails(domain, company_name)
        emails = email_result.get('emails', [])
        logger.info(f"   ✓ Found {len(emails)} emails")

        if not emails:
            logger.info(f"   ⊘ No emails found - including placeholder row")
            return [self._build_departure_row(departure_info, domain=domain)]

        # Process emails to find decision makers
        decision_makers = []
        seen_names = set()
        seen_names_lock = Lock()

        def process_email(email_addr: str) -> Optional[Dict]:
            # Global semaphore to cap total concurrent API calls
            with self._api_semaphore:
                logger.info(f"   🔍 Processing: {email_addr}")

                # Validate email format
                if not self._validate_email(email_addr):
                    logger.info(f"      ✗ Invalid email format: {email_addr}")
                    return None

                extracted_name, is_generic, confidence = self.extract_contact_from_email(email_addr)

                if is_generic or not extracted_name or confidence < 0.5:
                    return None

                logger.info(f"      → Name: {extracted_name} (conf: {confidence:.0%})")

                # Search LinkedIn
                contact_info = self.search_client.search_by_name(extracted_name, company_name)

                full_name = contact_info.get('full_name', extracted_name)
                job_title = contact_info.get('job_title', '')
                linkedin_url = contact_info.get('contact_linkedin', '')

                # Deduplicate
                with seen_names_lock:
                    if full_name.lower() in seen_names:
                        return None
                    seen_names.add(full_name.lower())

                # Validate decision maker
                if not self.is_decision_maker(job_title):
                    logger.info(f"      ✗ Not a decision-maker: {job_title}")
                    return None

                dm = self._build_departure_row(
                    departure_info, domain=domain,
                    full_name=full_name, job_title=job_title,
                    email=email_addr, linkedin_url=linkedin_url
                )

                logger.info(f"      ★ Decision-maker: {full_name} ({job_title})")
                return dm

        # Parallel processing with early termination (stop after 5 DMs)
        # 5 workers per directive (not 10)
        MAX_DMS_PER_COMPANY = 5

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_email, email): email for email in emails[:20]}

            for future in as_completed(futures):
                # Early termination - stop if we have enough DMs
                if len(decision_makers) >= MAX_DMS_PER_COMPANY:
                    for f in futures:
                        f.cancel()
                    break

                try:
                    result = future.result()
                    if result:
                        decision_makers.append(result)
                except Exception as e:
                    logger.error(f"      ❌ Error: {e}")

        # If no decision-makers found, include placeholder row for manual research (per directive)
        if not decision_makers:
            logger.info(f"   ⊘ No decision-makers found - including placeholder row for manual research")
            return [self._build_departure_row(departure_info, domain=domain)]

        logger.info(f"   ✓ Found {len(decision_makers)} decision-makers at {company_name}")
        return decision_makers

    def export_to_google_sheets(self, leads: List[Dict], title: str) -> str:
        """Export leads to new Google Sheet"""
        logger.info("📊 Exporting to Google Sheets...")

        creds = self._get_google_creds()
        service = build('sheets', 'v4', credentials=creds)

        spreadsheet = {
            'properties': {'title': title}
        }
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        spreadsheet_id = spreadsheet.get('spreadsheetId')
        spreadsheet_url = spreadsheet.get('spreadsheetUrl')

        if not leads:
            return spreadsheet_url

        # Prepare data
        headers = list(leads[0].keys())
        values = [headers]
        for lead in leads:
            values.append([str(lead.get(h, '')) for h in headers])

        # Write data
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body={'values': values}
        ).execute()

        # Format header
        requests_format = [
            {
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
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
                    "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount"
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests_format}
        ).execute()

        logger.info(f"✓ Exported {len(leads)} rows to Google Sheets")
        return spreadsheet_url

    def export_to_csv(self, leads: List[Dict], filename: Optional[str] = None) -> str:
        """Export leads to CSV"""

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"employee_departures_{timestamp}.csv"

        if not leads:
            logger.warning("⚠️ No leads to export")
            return filename

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=leads[0].keys())
            writer.writeheader()
            writer.writerows(leads)

        logger.info(f"✓ CSV exported: {filename}")
        return filename

    def run(self, sheet_url: str, limit: int = 25) -> str:
        """
        Main workflow:
        1. Read LinkedIn URLs from Google Sheet
        2. Scrape profiles
        3. Extract previous companies
        4. Find decision makers
        5. Deduplicate & export results
        """
        start_time = time.time()

        logger.info("=" * 70)
        logger.info("EMPLOYEE DEPARTURE TRACKER v1.1")
        logger.info("=" * 70)
        logger.info(f"Input Sheet: {sheet_url[:80]}...")
        logger.info(f"Limit: {limit} profiles")
        logger.info("=" * 70)

        # Step 1: Read LinkedIn URLs
        urls = self.read_linkedin_urls_from_sheet(sheet_url)

        if not urls:
            logger.error("❌ No LinkedIn URLs found in sheet")
            return ""

        urls = urls[:limit]
        logger.info(f"✓ Processing {len(urls)} profiles")

        # Step 2: Scrape profiles
        profiles = self.scrape_linkedin_profiles(urls)

        if not profiles:
            logger.error("❌ No profiles scraped")
            return ""

        # Step 3: Extract previous companies
        departures = []
        for profile in profiles:
            departure_info = self.extract_previous_company(profile)
            if departure_info:
                departures.append(departure_info)
                logger.info(f"✓ {departure_info['person_who_left']} left {departure_info['previous_company']} ({departure_info['left_date']})")

        logger.info(f"\n✓ Found {len(departures)} recent departures from {len(profiles)} profiles")

        if not departures:
            logger.warning("⚠️ No recent departures found (all jobs older than 6 months?)")
            return ""

        # Step 4: Enrich with decision makers (PARALLEL - 10 companies at a time)
        all_leads = []
        completed = 0
        total = len(departures)
        leads_lock = Lock()

        def process_departure(departure):
            return self.enrich_previous_company(departure)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_departure, dep): dep for dep in departures}

            for future in as_completed(futures):
                try:
                    leads = future.result()
                    with leads_lock:
                        all_leads.extend(leads)
                        completed += 1
                        # Progress: every item when <10 total, else every 10%
                        if total < 10 or completed % max(1, total // 10) == 0 or completed == total:
                            logger.info(f"⏳ Company progress: {completed}/{total} ({100*completed//total}%)")
                except Exception as e:
                    logger.error(f"❌ Error processing departure: {e}")

        # Step 4b: Global deduplication by dm_email across all companies
        raw_count = len(all_leads)
        seen_emails = set()
        deduped_leads = []
        for lead in all_leads:
            email = lead.get('dm_email', '').lower()
            if email and email in seen_emails:
                continue  # Skip duplicate
            if email:
                seen_emails.add(email)
            deduped_leads.append(lead)

        all_leads = deduped_leads
        if raw_count != len(all_leads):
            logger.info(f"✓ Deduplication: {raw_count} → {len(all_leads)} (removed {raw_count - len(all_leads)} duplicates)")

        logger.info(f"\n✓ Total leads (incl. placeholders): {len(all_leads)}")

        if not all_leads:
            logger.warning("⚠️ No leads found")
            return ""

        # Step 5: Export
        csv_file = self.export_to_csv(all_leads)

        sheet_title = f"Employee Departures - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        sheet_url = ""
        try:
            sheet_url = self.export_to_google_sheets(all_leads, sheet_title)
        except Exception as e:
            logger.warning(f"⚠️ Google Sheets export failed: {e}")

        # Summary
        duration = time.time() - start_time
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Profiles scraped:      {len(profiles)}")
        logger.info(f"Recent departures:     {len(departures)}")
        logger.info(f"Leads exported:        {len(all_leads)}")
        logger.info(f"Duration:              {duration:.1f}s")
        logger.info("=" * 70)

        if sheet_url:
            logger.info(f"\n✅ Complete! Google Sheet: {sheet_url}")

        return sheet_url or csv_file


def main():
    parser = argparse.ArgumentParser(
        description="Employee Departure Tracker v1.1 - Find decision makers at companies where people recently left"
    )
    parser.add_argument(
        "--sheet-url",
        required=True,
        help="Google Sheet URL with LinkedIn profile URLs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of profiles to process (default: 25)"
    )

    args = parser.parse_args()

    try:
        tracker = EmployeeDepartureTracker()
        tracker.run(args.sheet_url, args.limit)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()