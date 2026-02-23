#!/usr/bin/env python3
"""
Skool Community Owner Email Finder v1.0
Finds emails and contact info for Skool community owners.

Workflow:
1. Search Skool groups by keywords (Apify: futurizerush/skool-group-scraper)
2. Get detailed group info (Apify: gordian/skool-group-scraper)
3. Email cascade: supportEmail → ownerWebsite → Google Search → AnyMailFinder
4. LinkedIn enrichment (3-attempt strategy)
5. Export to Google Sheets (18 columns)

Follows directives/scrape_skool_community_owners.md
"""

import os
import sys
import json
import logging
import time
import re
import csv
import argparse
import requests
from typing import Dict, List, Optional, Any, Tuple
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

try:
    from utils_notifications import notify_success, notify_error
except ImportError:
    def notify_success(): pass
    def notify_error(): pass

load_dotenv()

os.makedirs('.tmp', exist_ok=True)
os.makedirs('.tmp/skool_cache', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/skool_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# REUSABLE CLASSES (from scrape_google_maps.py)
# =============================================================================

class RapidAPIGoogleSearch:
    """RapidAPI Google Search - For website discovery and LinkedIn enrichment."""

    def __init__(self, api_keys: List[str]):
        self.api_keys = [k for k in api_keys if k]
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2  # 5 req/sec per key
        logger.info(f"✓ RapidAPI Google Search initialized ({len(self.api_keys)} keys)")

    def _get_current_key(self) -> str:
        """Rotate between API keys for higher throughput."""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def search(self, query: str, num_results: int = 10) -> Optional[Dict]:
        """Thread-safe rate-limited Google search."""
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
                    logger.debug(f"⚠️ Rate limit hit, waiting {2 ** attempt}s")
                    time.sleep(2 ** attempt)
                    continue

            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                logger.debug(f"Google Search error: {e}")
                return None

        return None

    def _normalize_company(self, text: str) -> str:
        """Normalize company name for comparison."""
        if not text:
            return ""
        text = text.lower().replace('&', 'and')
        for suffix in ['inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co']:
            text = re.sub(rf'\b{suffix}\.?\b', '', text)
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', text)).strip()

    def _is_name_match(self, name1: str, name2: str, threshold: float = 0.6) -> bool:
        """Fuzzy match person names."""
        if not name1 or not name2:
            return False
        n1, n2 = name1.lower().strip(), name2.lower().strip()
        if n1 in n2 or n2 in n1:
            return True
        return SequenceMatcher(None, n1, n2).ratio() >= threshold


class AnyMailFinder:
    """Company Email Finder - Returns ALL emails at a company (up to 20)."""

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key
        logger.info("✓ AnyMailFinder initialized")

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """Find ALL emails at a company in ONE call."""
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
                if data.get('email_status') == 'valid' and data.get('valid_emails'):
                    return {
                        'emails': data['valid_emails'],
                        'status': 'found',
                        'count': len(data['valid_emails'])
                    }
            return {'emails': [], 'status': 'not-found', 'count': 0}

        except Exception as e:
            logger.debug(f"AnyMailFinder error for {company_domain}: {e}")
            return {'emails': [], 'status': 'error', 'count': 0}


# =============================================================================
# SKOOL-SPECIFIC CLASSES
# =============================================================================

class SkoolGroupSearcher:
    """Search Skool groups by keyword using Apify actor."""

    ACTOR_ID = "futurizerush/skool-group-scraper"

    def __init__(self, apify_client: ApifyClient):
        self.client = apify_client
        logger.info(f"✓ SkoolGroupSearcher initialized (actor: {self.ACTOR_ID})")

    def search_groups(self, keyword: str, max_results: int = 100) -> List[Dict]:
        """Search Skool for groups matching keyword."""
        logger.info(f"🔍 Searching Skool for: '{keyword}' (max: {max_results})")

        run_input = {
            "query": keyword,
            "maxItems": max_results,
            "language": "english",
            "includeOwnerInfo": False
        }

        try:
            run = self.client.actor(self.ACTOR_ID).call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"  ✓ Found {len(items)} groups for '{keyword}'")
            return items

        except Exception as e:
            logger.error(f"  ✗ Search failed for '{keyword}': {e}")
            return []


class SkoolGroupDetailScraper:
    """Get detailed group info including owner data using Apify actor."""

    ACTOR_ID = "gordian/skool-group-scraper"

    def __init__(self, apify_client: ApifyClient):
        self.client = apify_client
        logger.info(f"✓ SkoolGroupDetailScraper initialized (actor: {self.ACTOR_ID})")

    def get_group_details(self, group_urls: List[str]) -> List[Dict]:
        """Scrape detailed info for each group."""
        if not group_urls:
            return []

        logger.info(f"📋 Scraping details for {len(group_urls)} groups...")

        start_urls = [{"url": url} for url in group_urls]
        # IMPORTANT: Set urls to empty array to prevent scraping discovery page
        run_input = {
            "startUrls": start_urls,
            "urls": []  # Override default discovery URL
        }

        try:
            run = self.client.actor(self.ACTOR_ID).call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"  ✓ Got details for {len(items)} groups")
            return items

        except Exception as e:
            logger.error(f"  ✗ Detail scrape failed: {e}")
            return []


class SkoolOwnerEmailFinder:
    """Finds owner email using cascade logic."""

    SOCIAL_DOMAINS = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
                      'youtube.com', 'tiktok.com', 'x.com', 'skool.com']

    def __init__(self, email_finder: AnyMailFinder, google_search: RapidAPIGoogleSearch):
        self.email_finder = email_finder
        self.google_search = google_search

    def find_email(self, group_data: Dict) -> Dict:
        """
        Email discovery cascade:
        1. supportEmail exists → use directly
        2. ownerWebsite exists → AnyMailFinder(domain)
        3. No website → Google Search (3-attempt) → AnyMailFinder
        """
        result = {
            'email': '',
            'source': '',
            'website': group_data.get('ownerWebsite', '') or ''
        }

        owner_name = self._get_owner_name(group_data)
        group_name = group_data.get('displayName', '')

        # CASE 1: supportEmail exists
        support_email = group_data.get('supportEmail', '')
        if support_email and self._is_valid_email(support_email):
            result['email'] = support_email
            result['source'] = 'skool_support_email'
            logger.info(f"  ✓ Using support email: {support_email}")
            return result

        # CASE 2: ownerWebsite exists
        owner_website = group_data.get('ownerWebsite', '')
        if owner_website:
            domain = self._extract_domain(owner_website)
            if domain and not self._is_social_domain(domain):
                result['website'] = owner_website
                email_result = self.email_finder.find_company_emails(domain)
                if email_result['emails']:
                    best_email = self._select_best_email(email_result['emails'], owner_name)
                    result['email'] = best_email
                    result['source'] = 'anymailfinder_website'
                    logger.info(f"  ✓ Found via website: {best_email}")
                    return result

        # CASE 3: No website → Google Search (3-attempt strategy)
        if self.google_search:
            logger.info(f"  → No website, searching via Google...")
            found_website = self._search_website_3_attempt(owner_name, group_name)

            if found_website:
                result['website'] = found_website
                domain = self._extract_domain(found_website)
                if domain:
                    email_result = self.email_finder.find_company_emails(domain)
                    if email_result['emails']:
                        best_email = self._select_best_email(email_result['emails'], owner_name)
                        result['email'] = best_email
                        result['source'] = 'google_search_anymailfinder'
                        logger.info(f"  ✓ Found via Google Search: {best_email}")
                        return result

        logger.info(f"  ✗ No email found for {owner_name}")
        return result

    def _get_owner_name(self, group_data: Dict) -> str:
        """Extract owner name from group data."""
        first = group_data.get('ownerFirstName', '')
        last = group_data.get('ownerLastName', '')
        if first and last:
            return f"{first} {last}"
        return group_data.get('ownerName', '') or ''

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format (RFC 5322)."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))

    def _extract_domain(self, url: str) -> Optional[str]:
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

    def _is_social_domain(self, domain: str) -> bool:
        """Check if domain is a social media site."""
        domain_lower = domain.lower()
        return any(social in domain_lower for social in self.SOCIAL_DOMAINS)

    def _select_best_email(self, emails: List[str], owner_name: str) -> str:
        """Select the best email from a list, prioritizing personal emails."""
        if not emails:
            return ''

        # Personal email patterns (firstname, firstname.lastname, etc.)
        personal_patterns = []
        generic_patterns = []

        owner_name_lower = owner_name.lower().replace(' ', '')
        owner_parts = owner_name.lower().split()

        for email in emails:
            local_part = email.split('@')[0].lower()

            # Check if email contains owner name parts
            if owner_parts and any(part in local_part for part in owner_parts):
                personal_patterns.insert(0, email)  # Highest priority
            elif '.' in local_part or '_' in local_part:
                personal_patterns.append(email)
            elif local_part in ['info', 'contact', 'hello', 'support', 'admin', 'team']:
                generic_patterns.append(email)
            else:
                personal_patterns.append(email)

        # Return best match
        if personal_patterns:
            return personal_patterns[0]
        if generic_patterns:
            return generic_patterns[0]
        return emails[0]

    def _search_website_3_attempt(self, owner_name: str, group_name: str) -> str:
        """3-attempt strategy to find owner's website."""
        if not owner_name:
            return ''

        attempts = [
            f'"{owner_name}" website -linkedin -facebook -twitter -instagram -youtube',
            f'"{owner_name}" "{group_name}" website',
            f'"{group_name}" founder owner website'
        ]

        num_results = [5, 5, 7]

        for i, query in enumerate(attempts):
            logger.debug(f"  → Website search attempt {i+1}: {query}")
            result = self.google_search.search(query, num_results=num_results[i])

            if result and result.get('results'):
                for item in result['results']:
                    url = item.get('url', '')
                    if self._is_valid_website(url):
                        logger.info(f"  ✓ Found website (attempt {i+1}): {url}")
                        return url

        return ''

    def _is_valid_website(self, url: str) -> bool:
        """Check if URL is a valid personal/business website."""
        if not url:
            return False

        url_lower = url.lower()

        # Exclude social media and Skool
        for domain in self.SOCIAL_DOMAINS:
            if domain in url_lower:
                return False

        # Must have proper domain extension
        valid_extensions = ['.com', '.io', '.co', '.net', '.org', '.me', '.xyz', '.dev']
        return any(ext in url_lower for ext in valid_extensions)


class LinkedInEnricher:
    """LinkedIn profile enrichment using 3-attempt strategy."""

    def __init__(self, google_search: RapidAPIGoogleSearch):
        self.google_search = google_search

    def enrich(self, name: str, group_name: str) -> Dict:
        """
        3-attempt LinkedIn search strategy.
        """
        result = {
            'linkedin_url': '',
            'job_title': ''
        }

        if not name or not self.google_search:
            return result

        attempts = [
            (f'"{name}" at "{group_name}" linkedin', 5),
            (f'{name} "{group_name}" linkedin', 5),
            (f'{name} skool community owner linkedin', 7)
        ]

        for query, num_results in attempts:
            logger.debug(f"  → LinkedIn attempt: {query}")
            data = self.google_search.search(query, num_results=num_results)

            if data and data.get('results'):
                for item in data['results']:
                    url = item.get('url', '')
                    if 'linkedin.com/in/' in url:
                        title = item.get('title', '')
                        extracted_name = self._extract_name_from_title(title)

                        if self.google_search._is_name_match(name, extracted_name):
                            result['linkedin_url'] = url
                            result['job_title'] = self._extract_job_title(title, item.get('snippet', ''))
                            logger.info(f"  ✓ LinkedIn found: {url}")
                            return result

        return result

    def _extract_name_from_title(self, title: str) -> str:
        """Extract person name from LinkedIn title."""
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

        return re.sub(r'[^\w\s]$', '', title.strip())

    def _extract_job_title(self, title: str, snippet: str) -> str:
        """Extract job title from LinkedIn search result."""
        combined = title + ' ' + snippet

        patterns = [
            r' - ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+|\s*-\s*)',
            r' \| ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',
            r' · ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, combined)
            if match:
                job_title = match.group(1).strip()
                if len(job_title) >= 3 and len(job_title) <= 100:
                    return job_title

        return ''


# =============================================================================
# NAME EXTRACTION FROM EMAIL
# =============================================================================

def extract_name_from_email(email: str) -> Tuple[str, float]:
    """
    Extract name from email patterns.
    Returns (name, confidence)
    """
    if not email or '@' not in email:
        return ('', 0.0)

    local_part = email.split('@')[0].lower()

    # firstname.lastname@ → "Firstname Lastname" (95%)
    if '.' in local_part:
        parts = local_part.split('.')
        if len(parts) == 2 and all(len(p) >= 2 for p in parts):
            name = ' '.join(p.capitalize() for p in parts)
            return (name, 0.95)

    # firstname_lastname@ → "Firstname Lastname" (90%)
    if '_' in local_part:
        parts = local_part.split('_')
        if len(parts) == 2 and all(len(p) >= 2 for p in parts):
            name = ' '.join(p.capitalize() for p in parts)
            return (name, 0.90)

    # camelCase → "Firstname Lastname" (85%)
    camel_match = re.findall(r'[A-Z][a-z]+|[a-z]+', local_part)
    if len(camel_match) == 2 and all(len(p) >= 2 for p in camel_match):
        name = ' '.join(p.capitalize() for p in camel_match)
        return (name, 0.85)

    # firstname@ → "Firstname" (80%)
    if local_part.isalpha() and len(local_part) >= 3:
        return (local_part.capitalize(), 0.80)

    return ('', 0.0)


# =============================================================================
# MAIN SCRAPER CLASS
# =============================================================================

class SkoolOwnerScraper:
    """Main orchestrator for Skool community owner scraping."""

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        self.apify_token = os.getenv("APIFY_API_KEY")
        self.anymailfinder_token = os.getenv("ANYMAILFINDER_API_KEY")

        if not self.apify_token:
            raise ValueError("❌ APIFY_API_KEY not found in .env")

        self.apify_client = ApifyClient(self.apify_token)

        # Initialize components
        self.group_searcher = SkoolGroupSearcher(self.apify_client)
        self.detail_scraper = SkoolGroupDetailScraper(self.apify_client)

        # Email finder
        if self.anymailfinder_token:
            self.email_finder = AnyMailFinder(self.anymailfinder_token)
        else:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found - email finding limited")
            self.email_finder = None

        # Google Search for website discovery and LinkedIn
        rapidapi_keys = [os.getenv("RAPIDAPI_KEY"), os.getenv("RAPIDAPI_KEY_2")]
        rapidapi_keys = [k for k in rapidapi_keys if k]

        if rapidapi_keys:
            self.google_search = RapidAPIGoogleSearch(rapidapi_keys)
            self.linkedin_enricher = LinkedInEnricher(self.google_search)
        else:
            logger.warning("⚠️ RAPIDAPI_KEY not found - website search disabled")
            self.google_search = None
            self.linkedin_enricher = None

        # Email cascade finder
        if self.email_finder:
            self.owner_email_finder = SkoolOwnerEmailFinder(
                self.email_finder,
                self.google_search
            )
        else:
            self.owner_email_finder = None

        logger.info("✓ SkoolOwnerScraper initialized")

    def execute(self, keywords: List[str], max_groups: int = 50, skip_test: bool = False) -> Dict:
        """Execute full workflow."""
        start_time = time.time()

        print("\n" + "=" * 70)
        print("🎓 SKOOL COMMUNITY OWNER EMAIL FINDER v1.0")
        print(f"Keywords: {', '.join(keywords)}")
        print(f"Max groups per keyword: {max_groups}")
        print("=" * 70 + "\n")

        all_groups = []
        seen_urls = set()

        # Step 1: Search groups for each keyword
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue

            groups = self.group_searcher.search_groups(keyword, max_groups)

            for group in groups:
                url = group.get('groupUrl', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    group['_keyword'] = keyword
                    all_groups.append(group)

        logger.info(f"\n📊 Total unique groups found: {len(all_groups)}")

        if not all_groups:
            logger.error("❌ No groups found. Exiting.")
            return {'success': False, 'error': 'No groups found'}

        # Step 2: Test batch (10 groups) unless skipped
        if not skip_test and len(all_groups) > 10:
            logger.info("\n🧪 Running test batch (10 groups)...")
            test_groups = all_groups[:10]
            test_results = self._process_groups(test_groups)

            email_found = sum(1 for r in test_results if r.get('owner_email'))
            email_rate = email_found / len(test_results) * 100

            logger.info(f"\n📈 Test Results:")
            logger.info(f"   → Email found: {email_found}/10 ({email_rate:.0f}%)")

            if email_rate < 40:
                logger.warning(f"⚠️ Email rate ({email_rate:.0f}%) below 40% threshold")
                logger.info("   → Proceeding anyway (social profiles will be included)")

        # Step 3: Get detailed info for all groups
        group_urls = [g.get('groupUrl') for g in all_groups if g.get('groupUrl')]
        detailed_groups = self.detail_scraper.get_group_details(group_urls)

        # Create lookup by URL
        detail_lookup = {}
        for detail in detailed_groups:
            # Match by name or construct URL
            name = detail.get('name', '')
            if name:
                url = f"https://www.skool.com/{name}"
                detail_lookup[url] = detail

        # Step 4: Process all groups
        logger.info(f"\n🔄 Processing {len(all_groups)} groups...")
        results = self._process_groups_with_details(all_groups, detail_lookup)

        # Step 5: Export to Google Sheets
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        keywords_slug = '_'.join(k.strip()[:10] for k in keywords[:3])
        sheet_title = f"Skool Owners - {keywords_slug} - {timestamp}"

        sheet_url = self.export_to_google_sheets(results, sheet_title)

        elapsed = time.time() - start_time

        # Summary
        email_found = sum(1 for r in results if r.get('owner_email'))
        social_only = sum(1 for r in results if r.get('status') == 'social_only')

        print("\n" + "=" * 70)
        print("✅ COMPLETE!")
        print(f"   → Total owners: {len(results)}")
        print(f"   → Emails found: {email_found} ({email_found/len(results)*100:.0f}%)")
        print(f"   → Social only: {social_only}")
        print(f"   → Time: {elapsed/60:.1f} minutes")
        if sheet_url:
            print(f"   → Sheet: {sheet_url}")
        print("=" * 70)

        notify_success()

        return {
            'success': True,
            'total_owners': len(results),
            'emails_found': email_found,
            'social_only': social_only,
            'sheet_url': sheet_url,
            'elapsed_seconds': elapsed
        }

    def _process_groups(self, groups: List[Dict]) -> List[Dict]:
        """Process groups without detailed info (for test batch)."""
        results = []
        for group in groups:
            result = self._create_result_row(group, {})
            results.append(result)
        return results

    def _process_groups_with_details(self, groups: List[Dict], detail_lookup: Dict) -> List[Dict]:
        """Process groups with detailed info."""
        results = []
        total = len(groups)

        for i, group in enumerate(groups):
            group_url = group.get('groupUrl', '')
            detail = detail_lookup.get(group_url, {})

            # Merge basic group info with detail
            merged = {**group, **detail}

            result = self._create_result_row(group, detail)
            results.append(result)

            # Progress
            if (i + 1) % max(1, total // 10) == 0:
                progress = (i + 1) / total * 100
                logger.info(f"⏳ Progress: {i+1}/{total} ({progress:.0f}%)")

        return results

    def _create_result_row(self, group: Dict, detail: Dict) -> Dict:
        """Create a result row for export."""
        merged = {**group, **detail}

        # Get owner name
        owner_first = merged.get('ownerFirstName', '')
        owner_last = merged.get('ownerLastName', '')
        if owner_first and owner_last:
            owner_name = f"{owner_first} {owner_last}"
        else:
            owner_name = merged.get('ownerName', '')

        # Email cascade
        email_result = {'email': '', 'source': '', 'website': ''}
        if self.owner_email_finder and detail:
            logger.info(f"\n📧 Finding email for: {owner_name or merged.get('displayName', 'Unknown')}")
            email_result = self.owner_email_finder.find_email(merged)

        # If email found, try to extract better name
        extracted_name = ''
        if email_result['email']:
            extracted_name, confidence = extract_name_from_email(email_result['email'])
            if confidence >= 0.85 and extracted_name:
                owner_name = extracted_name

        # LinkedIn enrichment
        linkedin_result = {'linkedin_url': '', 'job_title': ''}
        owner_linkedin = merged.get('ownerLinkedin', '')

        if not owner_linkedin and self.linkedin_enricher and owner_name:
            linkedin_result = self.linkedin_enricher.enrich(owner_name, merged.get('displayName', ''))
            owner_linkedin = linkedin_result.get('linkedin_url', '')

        # Determine status
        if email_result['email']:
            status = 'found'
        elif any([merged.get('ownerInstagram'), merged.get('ownerYoutube'),
                  merged.get('ownerTwitter'), merged.get('ownerFacebook'), owner_linkedin]):
            status = 'social_only'
        else:
            status = 'not_found'

        # Construct Skool profile URL
        owner_username = merged.get('ownerName', '')
        owner_skool_profile = f"https://www.skool.com/@{owner_username}" if owner_username else ''

        return {
            'group_name': merged.get('displayName', ''),
            'group_url': merged.get('groupUrl', '') or f"https://www.skool.com/{merged.get('name', '')}",
            'member_count': merged.get('memberCount', '') or merged.get('totalMembers', ''),
            'owner_name': owner_name,
            'owner_email': email_result['email'],
            'email_source': email_result['source'],
            'owner_website': email_result['website'] or merged.get('ownerWebsite', ''),
            'owner_linkedin': owner_linkedin,
            'owner_instagram': merged.get('ownerInstagram', ''),
            'owner_youtube': merged.get('ownerYoutube', ''),
            'owner_twitter': merged.get('ownerTwitter', ''),
            'owner_facebook': merged.get('ownerFacebook', ''),
            'job_title': linkedin_result.get('job_title', ''),
            'owner_skool_profile': owner_skool_profile,
            'group_description': (merged.get('description', '') or '')[:500],
            'monthly_price': merged.get('monthlyPrice', '') or merged.get('pricePerMonth', ''),
            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'status': status
        }

    def export_to_google_sheets(self, rows: List[Dict], title: str) -> str:
        """Export to Google Sheets with 18 columns."""
        logger.info("📊 Exporting to Google Sheets...")

        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("❌ credentials.json not found - exporting to CSV instead")
                    return self.export_to_csv(rows, title)

                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        try:
            service = build('sheets', 'v4', credentials=creds)

            spreadsheet = {'properties': {'title': title}}
            spreadsheet = service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()

            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')

            logger.info(f"✓ Created: {spreadsheet_url}")

            if not rows:
                return spreadsheet_url

            # 18 columns as per directive
            headers = [
                "Group Name", "Group URL", "Member Count", "Owner Name", "Owner Email",
                "Email Source", "Owner Website", "Owner LinkedIn", "Owner Instagram",
                "Owner YouTube", "Owner Twitter", "Owner Facebook", "Job Title",
                "Owner Skool Profile", "Group Description", "Monthly Price",
                "Scraped Date", "Status"
            ]

            values = [headers]

            for row in rows:
                values.append([
                    row.get('group_name', ''),
                    row.get('group_url', ''),
                    str(row.get('member_count', '')),
                    row.get('owner_name', ''),
                    row.get('owner_email', ''),
                    row.get('email_source', ''),
                    row.get('owner_website', ''),
                    row.get('owner_linkedin', ''),
                    row.get('owner_instagram', ''),
                    row.get('owner_youtube', ''),
                    row.get('owner_twitter', ''),
                    row.get('owner_facebook', ''),
                    row.get('job_title', ''),
                    row.get('owner_skool_profile', ''),
                    row.get('group_description', ''),
                    str(row.get('monthly_price', '')),
                    row.get('scraped_date', ''),
                    row.get('status', '')
                ])

            body = {'values': values}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            # Format header row
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
                        "properties": {
                            "sheetId": 0,
                            "gridProperties": {"frozenRowCount": 1}
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                }
            ]

            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests_format}
            ).execute()

            logger.info(f"✓ Exported {len(rows)} rows")

            return spreadsheet_url

        except Exception as e:
            logger.error(f"❌ Sheets export failed: {e}")
            return self.export_to_csv(rows, title)

    def export_to_csv(self, rows: List[Dict], title: str) -> str:
        """Export to CSV as fallback."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_path = f".tmp/skool_owners_{timestamp}.csv"

            headers = [
                "Group Name", "Group URL", "Member Count", "Owner Name", "Owner Email",
                "Email Source", "Owner Website", "Owner LinkedIn", "Owner Instagram",
                "Owner YouTube", "Owner Twitter", "Owner Facebook", "Job Title",
                "Owner Skool Profile", "Group Description", "Monthly Price",
                "Scraped Date", "Status"
            ]

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

                for row in rows:
                    writer.writerow({
                        "Group Name": row.get('group_name', ''),
                        "Group URL": row.get('group_url', ''),
                        "Member Count": row.get('member_count', ''),
                        "Owner Name": row.get('owner_name', ''),
                        "Owner Email": row.get('owner_email', ''),
                        "Email Source": row.get('email_source', ''),
                        "Owner Website": row.get('owner_website', ''),
                        "Owner LinkedIn": row.get('owner_linkedin', ''),
                        "Owner Instagram": row.get('owner_instagram', ''),
                        "Owner YouTube": row.get('owner_youtube', ''),
                        "Owner Twitter": row.get('owner_twitter', ''),
                        "Owner Facebook": row.get('owner_facebook', ''),
                        "Job Title": row.get('job_title', ''),
                        "Owner Skool Profile": row.get('owner_skool_profile', ''),
                        "Group Description": row.get('group_description', ''),
                        "Monthly Price": row.get('monthly_price', ''),
                        "Scraped Date": row.get('scraped_date', ''),
                        "Status": row.get('status', '')
                    })

            logger.info(f"✓ Exported {len(rows)} rows to CSV: {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"❌ CSV export failed: {e}")
            return ""


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Skool Community Owner Email Finder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single keyword
  python scrape_skool_owners.py --keywords "marketing"

  # Multiple keywords
  python scrape_skool_owners.py --keywords "marketing, coaching, crypto" --max_groups 50

  # Skip test batch
  python scrape_skool_owners.py --keywords "ai" --max_groups 100 --skip_test
        """
    )

    parser.add_argument(
        '--keywords',
        type=str,
        required=True,
        help='Comma-separated keywords (e.g., "marketing, coaching")'
    )

    parser.add_argument(
        '--max_groups',
        type=int,
        default=50,
        help='Max groups per keyword (default: 50)'
    )

    parser.add_argument(
        '--skip_test',
        action='store_true',
        help='Skip test batch validation'
    )

    args = parser.parse_args()

    # Parse keywords
    keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]

    if not keywords:
        logger.error("❌ No valid keywords provided")
        sys.exit(1)

    try:
        scraper = SkoolOwnerScraper()
        result = scraper.execute(
            keywords=keywords,
            max_groups=args.max_groups,
            skip_test=args.skip_test
        )

        if result.get('success'):
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)


if __name__ == "__main__":
    main()