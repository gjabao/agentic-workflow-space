#!/usr/bin/env python3
"""
LinkedIn Job Scraper with Decision Maker Outreach (Bebity Pattern)
Streams jobs in real-time, processes in parallel, finds decision makers & emails.

Architecture:
- Streaming: Process jobs as they arrive (no batch wait)
- Parallel: 10 concurrent workers for company processing
- Resilient: Continues on errors, logs issues
- Self-annealing: Learns from failures, improves over time
"""

import os
import sys
import json
import logging
import time
import re
import argparse
import requests
import pandas as pd
from typing import Dict, List, Optional, Generator, Tuple
from difflib import SequenceMatcher
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv
from apify_client import ApifyClient
from openai import AzureOpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utils_notifications import notify_success, notify_error

load_dotenv()

# Setup Logging
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/linkedin_jobs_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Suppress noisy library logs
logging.getLogger('google_auth_oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class AnyMailFinder:
    """
    Company Email Finder - Returns ALL emails at a company (up to 20)
    Hardened with rate limiting, retry logic, and proper error handling.
    """

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.5  # 2 req/sec
        logger.info("✓ AnyMailFinder Company API initialized (v2.1 hardened)")

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """
        Find ALL emails at a company in ONE call.
        Returns up to 20 emails per company.
        Includes rate limiting, 3-attempt retry, and proper error handling.
        """
        not_found = {'emails': [], 'status': 'not-found', 'count': 0}

        # Rate limiting (reserve slot pattern)
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_call_time
            wait_time = max(0, self.min_delay - elapsed)
            self.last_call_time = time.time() + wait_time
        if wait_time > 0:
            time.sleep(wait_time)

        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }

        payload = {
            'domain': company_domain,
            'email_type': 'any'
        }

        if company_name:
            payload['company_name'] = company_name

        for attempt in range(3):
            try:
                response = requests.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=20
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
                    return {'emails': [], 'status': email_status or 'not-found', 'count': 0}

                elif response.status_code == 401:
                    logger.error(f"  ❌ AnyMailFinder 401 - Invalid API key")
                    return not_found

                elif response.status_code == 429:
                    wait = 2 ** attempt
                    logger.debug(f"  ⚠️ AnyMailFinder 429 rate limit, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue

                else:
                    logger.debug(f"  ⚠️ AnyMailFinder {response.status_code} for {company_domain}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    return not_found

            except Exception as e:
                logger.debug(f"  ⚠️ AnyMailFinder error for {company_domain} (attempt {attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return not_found

        return not_found


class RapidAPIGoogleSearch:
    """
    RapidAPI Google Search - For LinkedIn profile enrichment
    Migrated from Crunchbase scraper v4.0
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.1  # 10 req/sec per key
        logger.info(f"✓ RapidAPI Google Search initialized ({len(api_keys)} keys)")

    def _get_current_key(self) -> str:
        """Rotate between API keys for higher throughput (thread-safe)"""
        with self.rate_limit_lock:
            key = self.api_keys[self.current_key_index]
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            return key

    def _rate_limited_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
        """Thread-safe rate-limited Google search (reserve slot pattern)"""
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_call_time
            wait_time = max(0, self.min_delay - elapsed)
            self.last_call_time = time.time() + wait_time  # Reserve slot
        if wait_time > 0:
            time.sleep(wait_time)

        for attempt in range(3):
            try:
                url = "https://google-search116.p.rapidapi.com/"
                headers = {
                    "x-rapidapi-key": self._get_current_key(),
                    "x-rapidapi-host": "google-search116.p.rapidapi.com"
                }
                params = {
                    "query": query,
                    "num": str(num_results)
                }

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
                    logger.debug(f"  ⚠️ Rate limit hit, waiting {2 ** attempt}s")
                    time.sleep(2 ** attempt)
                    continue

            except Exception as e:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.debug(f"  ⚠️ Google Search error (attempt {attempt+1}), waiting {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                    continue
                logger.debug(f"  ⚠️ Google Search error after 3 attempts: {e}")
                return None

        return None

    def _is_company_match(self, company1: str, company2: str, threshold: float = 0.6) -> bool:
        """Fuzzy match company names"""
        if not company1 or not company2:
            return False

        norm1 = self._normalize_company(company1)
        norm2 = self._normalize_company(company2)

        if norm1 in norm2 or norm2 in norm1:
            return True

        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio() >= threshold

    def _normalize_company(self, text: str) -> str:
        """Normalize company name for comparison"""
        if not text:
            return ""
        text = text.lower()
        text = text.replace('&', 'and')
        suffixes = ['inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co']
        for suffix in suffixes:
            text = re.sub(rf'\b{suffix}\.?\b', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'[^\w\s]', '', text)
        return text

    def _is_name_match(self, name1: str, name2: str, threshold: float = 0.7) -> bool:
        """Fuzzy match person names"""
        if not name1 or not name2:
            return False

        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        if n1 in n2 or n2 in n1:
            return True

        matcher = SequenceMatcher(None, n1, n2)
        return matcher.ratio() >= threshold

    def _extract_name_from_title(self, title: str) -> str:
        """Extract person name from search result title"""
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

        cleaned = re.sub(r'[^\w\s]$', '', title.strip())
        return cleaned if len(cleaned) >= 3 else ""

    def _extract_title_from_search(self, title: str, snippet: str) -> str:
        """Extract job title from search result"""
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

    def _validate_person_name(self, name: str, company_name: str) -> bool:
        """Validate real person names (not company names or garbage)"""
        if not name or len(name) < 2 or len(name) > 40:
            return False

        name_lower = name.lower().strip()

        garbage_indicators = [
            'top 10', 'best', 'claim business', 'contact us', 'about us',
        ]

        for indicator in garbage_indicators:
            if indicator in name_lower:
                return False

        if re.search(r'\d', name) and not name_lower.startswith('dr'):
            return False

        invalid_patterns = [
            r'^(our team|division|home|about|contact|info|team|staff)$',
            r'^[A-Z\s]{3,}$',
            r'^\d',
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, name_lower):
                return False

        if self._is_company_match(name, company_name, threshold=0.7):
            return False

        business_keywords = ['inc', 'llc', 'ltd', 'corp', 'company']
        if any(keyword in name_lower for keyword in business_keywords):
            return False

        if not re.search(r'[a-zA-Z]{2,}', name):
            return False

        words = name.split()
        if len(words) > 4:
            return False

        return True

    def search_by_name(self, full_name: str, company_name: str, location: str = None, confidence: float = 1.0) -> Dict:
        """
        Search for person by name + company (extracted from email)
        Smart attempt strategy based on name confidence:
        - High confidence (>=0.7): 3 attempts (full names like "John Smith")
        - Low confidence (<0.7): 1 attempt (initials like "K Earle", single names)
        Returns dict with 'attempt' field indicating which attempt succeeded.
        """
        result = {
            'full_name': full_name,
            'job_title': '',
            'contact_linkedin': '',
            'attempt': 0
        }

        # Smart attempt count based on name confidence
        # Low-confidence names (initials, single names) rarely match after attempt 1
        max_attempts = 3 if confidence >= 0.7 else 1

        # 3-attempt strategy for >90% LinkedIn match rate
        search_attempts = [
            # Attempt 1: Most specific - quoted name + "at" + quoted company (highest accuracy)
            (f'"{full_name}" at "{company_name}" linkedin', 5),

            # Attempt 2: Medium specificity - name + quoted company (broader)
            (f'{full_name} "{company_name}" linkedin', 5),

            # Attempt 3: Broad - name + company without quotes (catches edge cases)
            (f'{full_name} {company_name} linkedin', 7)
        ][:max_attempts]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            logger.debug(f"  → Attempt {attempt_num}/{max_attempts}: Searching for {full_name} at {company_name}")

            data = self._rate_limited_search(query, num_results=num_results)

            if data and data.get('results'):
                found = self._extract_person_from_results(
                    data['results'],
                    full_name,
                    company_name,
                    require_linkedin=True
                )
                if found['full_name']:
                    found['attempt'] = attempt_num
                    return found

        logger.info(f"  ✗ No LinkedIn profile found for {full_name} after {max_attempts} attempt(s)")
        return result

    def _extract_person_from_results(self, results: List[Dict], search_name: str, company_name: str,
                                      require_linkedin: bool = False) -> Dict:
        """Extract person info from search results"""
        result = {
            'full_name': '',
            'job_title': '',
            'contact_linkedin': ''
        }

        for item in results:
            url = item.get('url', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')

            if require_linkedin and 'linkedin.com/in/' not in url:
                continue

            extracted_name = self._extract_name_from_title(title)
            if not extracted_name:
                continue

            if not self._is_name_match(search_name, extracted_name, threshold=0.6):
                logger.debug(f"  ⚠️ Name mismatch: '{extracted_name}' vs '{search_name}'")
                continue

            if not self._validate_person_name(extracted_name, company_name):
                logger.debug(f"  ⚠️ Invalid person name: '{extracted_name}'")
                continue

            job_title = self._extract_title_from_search(title, snippet)

            result['full_name'] = extracted_name
            result['job_title'] = job_title if job_title else ""
            result['contact_linkedin'] = url if 'linkedin.com' in url else ""

            logger.info(f"  ✓ Found: {extracted_name} - {job_title}")
            return result

        return result


class LinkedInJobScraper:
    """
    LinkedIn Job Scraper with Bebity-style architecture.

    Features:
    - Streaming: Process jobs as they arrive (real-time)
    - Parallel: 10 workers for concurrent processing
    - Resilient: Handles errors gracefully, continues execution
    - Smart Rate Limiting: Prevents API throttling
    """

    # Actor IDs
    LINKEDIN_SCRAPER_ACTOR_ID = "bebity/linkedin-jobs-scraper"

    # API URLs
    ANYMAILFINDER_URL = "https://api.anymailfinder.com/v5.1/find-email/person"
    RAPIDAPI_GOOGLE_SEARCH_URL = "https://google-search116.p.rapidapi.com/"

    # Google Sheets Scopes
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        """Initialize API clients and validate credentials."""

        # 1. Apify Client - Secure credential handling (Load → Use → Delete)
        apify_token = os.getenv("APIFY_API_KEY")
        if not apify_token:
            raise ValueError("❌ APIFY_API_KEY not found in .env file")
        self.apify_client = ApifyClient(apify_token)
        del apify_token  # Clear from memory
        logger.info("✓ Apify client initialized")

        # 2. AnyMailFinder (Company API - v2.0)
        anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        if not anymail_key:
            raise ValueError("❌ ANYMAILFINDER_API_KEY required for v2.0")
        self.anymail_finder = AnyMailFinder(anymail_key)
        del anymail_key

        # 3. RapidAPI Google Search (v2.0 with multiple keys support)
        rapidapi_key = os.getenv("RAPIDAPI_KEY")
        rapidapi_key2 = os.getenv("RAPIDAPI_KEY_2")  # Optional second key
        if not rapidapi_key:
            raise ValueError("❌ RAPIDAPI_KEY required for v2.0")

        api_keys = [rapidapi_key]
        if rapidapi_key2:
            api_keys.append(rapidapi_key2)

        self.rapidapi_search = RapidAPIGoogleSearch(api_keys)
        del rapidapi_key
        if rapidapi_key2:
            del rapidapi_key2

        # 4. Azure OpenAI - Secure credential handling
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if azure_key and azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=azure_endpoint
            )
            del azure_key, azure_endpoint  # Clear from memory
            logger.info("✓ Azure OpenAI initialized")
        else:
            self.openai_client = None
            logger.warning("⚠️ Azure OpenAI keys missing. Message generation will be disabled.")

        logger.info("🚀 LinkedInJobScraper v2.0 ready (email-first workflow)\n")

    # ===========================================
    # PHASE 1: START JOB SCRAPER (ASYNC)
    # ===========================================

    def start_linkedin_scraper(
        self,
        query: str,
        location: str = "",
        country: str = "United States",
        max_jobs: int = 50,
        days_posted: int = 14
    ) -> str:
        """
        Start LinkedIn job scraper (Apify actor) asynchronously.

        Returns:
            run_id (str): Apify run ID for streaming dataset
        """
        logger.info(f"🔍 Starting LinkedIn scraper...")
        logger.info(f"   Query: {query}")
        logger.info(f"   Location: {location or 'Any'}")
        logger.info(f"   Country: {country}")
        logger.info(f"   Max Jobs: {max_jobs}")
        logger.info(f"   Days Posted: {days_posted}\n")

        # Map country names to 2-letter codes for bebity actor
        country_code_map = {
            "United States": "US", "United Kingdom": "GB", "Canada": "CA",
            "Australia": "AU", "Germany": "DE", "France": "FR", "India": "IN",
            "Singapore": "SG", "Netherlands": "NL", "Spain": "ES", "Italy": "IT",
            "Brazil": "BR", "Mexico": "MX", "Japan": "JP", "South Korea": "KR"
        }
        country_code = country_code_map.get(country, "US")

        # bebity/linkedin-jobs-scraper input format
        # Uses exact format from your example
        run_input = {
            "title": query,
            "location": location if location else country,
            "rows": max_jobs,
            "publishedAt": "",  # Empty for all dates, or use specific date filter
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": country_code
            }
        }

        try:
            # Start actor asynchronously (don't wait for completion)
            run = self.apify_client.actor(self.LINKEDIN_SCRAPER_ACTOR_ID).start(run_input=run_input)
            run_id = run["id"]
            logger.info(f"✓ Scraper started (Run ID: {run_id})\n")
            return run_id
        except Exception as e:
            logger.error(f"❌ Failed to start scraper: {e}")
            logger.error("   Check: Apify API key, actor ID, input format")
            return ""

    # ===========================================
    # PHASE 2: STREAM JOBS (REAL-TIME)
    # ===========================================

    def stream_jobs(self, run_id: str) -> Generator[Dict, None, None]:
        """
        Stream jobs from Apify dataset as they become available.

        Yields jobs one-by-one (generator pattern) for immediate processing.
        Continues until actor completes AND no new items found.

        Args:
            run_id: Apify run ID

        Yields:
            Dict: Job data (company, title, url, etc.)
        """
        if not run_id:
            return

        offset = 0
        limit = 100
        seen_companies = set()  # Deduplicate on-the-fly

        logger.info("🔄 Streaming jobs in real-time...\n")

        while True:
            try:
                # Check actor status
                run = self.apify_client.run(run_id).get()
                status = run.get("status")
                dataset_id = run.get("defaultDatasetId")

                # Fetch new items from dataset
                list_items = self.apify_client.dataset(dataset_id).list_items(
                    offset=offset,
                    limit=limit
                )
                items = list_items.items

                # Process new items
                if items:
                    for item in items:
                        # bebity/linkedin-jobs-scraper field names
                        company = item.get('company', '') or item.get('companyName', '')
                        title = item.get('jobTitle', '') or item.get('title', '')

                        if not company or not title:
                            continue

                        # Normalize names
                        normalized_company = self.normalize_company_name(company)
                        normalized_title = self.normalize_job_title(title)

                        # Deduplicate (same company, different jobs)
                        company_key = normalized_company.lower().strip()
                        if company_key in seen_companies:
                            continue
                        seen_companies.add(company_key)

                        # Yield immediately (don't accumulate)
                        yield {
                            'company_name': normalized_company,
                            'job_title': normalized_title,
                            'job_url': item.get('jobUrl', '') or item.get('link', ''),
                            'job_description': item.get('description', '') or item.get('descriptionText', ''),
                            'posted_date': item.get('postedDate', '') or item.get('postedAt', ''),
                            'location': item.get('jobLocation', '') or item.get('location', ''),
                            'employment_type': item.get('employmentType', ''),
                            'seniority_level': item.get('seniorityLevel', '')
                        }

                    offset += len(items)

                # Exit condition: Actor done AND no new items
                if status in ["SUCCEEDED", "FAILED", "ABORTED"] and len(items) == 0:
                    logger.info(f"✓ Scraper finished (Status: {status})\n")
                    break

                # Poll interval (check for new items every 1 second)
                time.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error streaming jobs: {e}")
                break

    # ===========================================
    # PHASE 3: PROCESS COMPANY (PARALLEL)
    # ===========================================

    def process_single_company(self, job: Dict) -> List[Dict]:
        """
        Email-first workflow (v2.0) - Find ALL decision makers at company

        Pipeline:
        1. Find company website (Google search)
        2. Find ALL emails at company (AnyMailFinder Company API - up to 20)
        3. Extract names from emails (firstname.lastname@)
        4. Search LinkedIn for each name (3-attempt strategy)
        5. Validate decision-maker titles (CEO, CFO, VP, Director, etc.)
        6. Generate personalized messages for all DMs

        Args:
            job: Job data dict from stream

        Returns:
            List[Dict]: List of decision makers (2-3+ per company)
        """
        company_name = job['company_name']
        logger.info(f"\n{'='*70}\n🏢 Company: {company_name}")

        # Step 1: Find Website
        website_data = self.find_company_website(company_name)
        website = website_data.get('url', '')
        if not website:
            logger.info(f"  ⊘ No website found - skipping {company_name}")
            return []

        domain = self.extract_domain(website)
        logger.info(f"  ✓ Website: {domain}")

        # Step 2: Find ALL emails (Company API - v2.0)
        logger.info(f"  📧 Finding emails at {domain}...")
        email_result = self.anymail_finder.find_company_emails(domain, company_name)

        if email_result['status'] != 'found':
            logger.info(f"  ⊘ No emails found")
            return []

        emails = email_result.get('emails', [])[:20]  # Max 20 emails
        logger.info(f"  ✓ Found {len(emails)} emails")

        # Step 3: Process emails in parallel (5 workers)
        decision_makers = []
        seen_names = set()
        seen_names_lock = Lock()

        def process_single_email(email: str):
            # 3a. Extract name from email
            logger.info(f"  🔍 Processing: {email}")
            name, is_generic, confidence = self.extract_contact_from_email(email)

            if is_generic:
                logger.info(f"  ✗ Generic email - skipping")
                return None

            if confidence < 0.5:
                logger.info(f"  ✗ Low confidence ({confidence:.0%}) - skipping")
                return None

            logger.info(f"  → Extracted name: {name} (conf: {confidence:.0%})")

            # 3b. Dedup check (thread-safe)
            with seen_names_lock:
                if name in seen_names:
                    logger.info(f"  ✗ Duplicate name - skipping: {name}")
                    return None
                seen_names.add(name)

            # 3c. Search LinkedIn (smart-attempt strategy based on name confidence)
            logger.info(f"  → Searching LinkedIn for {name}...")
            contact = self.rapidapi_search.search_by_name(name, company_name, confidence=confidence)

            if not contact or not contact.get('job_title'):
                logger.info(f"  ✗ LinkedIn not found")
                return None

            # 3d. Validate decision-maker
            if not self.is_decision_maker(contact['job_title']):
                logger.info(f"  ✗ Not a decision-maker: {contact['job_title']}")
                return None

            logger.info(f"  ★ Found DM: {name} ({contact['job_title']})")

            # 3e. Build result
            name_parts = name.split()
            return {
                'company_name': company_name,
                'company_type': 'Technology & Software',  # Default (LinkedIn doesn't provide)
                'company_website': website,
                'company_domain': domain,
                'company_description': website_data.get('description', ''),
                'job_title': job.get('job_title', ''),
                'job_url': job.get('job_url', ''),
                'location': job.get('location', ''),
                'posted_date': job.get('posted_date', ''),
                'dm_name': name,
                'dm_first': name_parts[0] if name_parts else name,
                'dm_last': name_parts[-1] if len(name_parts) > 1 else '',
                'dm_title': contact['job_title'],
                'dm_linkedin': contact.get('contact_linkedin', ''),
                'dm_email': email,
                'email_status': 'found',
                'dm_source': f'RapidAPI Google Search by Name (Attempt {contact.get("attempt", "?")})',
                'dm_description': ''
            }

        # Parallel processing (8 workers) with early-exit after 3 DMs
        max_dms = 3
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(process_single_email, email) for email in emails]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        decision_makers.append(result)
                        # Early-exit: stop processing once we have enough DMs
                        if len(decision_makers) >= max_dms:
                            for f in futures:
                                f.cancel()
                            logger.info(f"  ⚡ Early-exit: {max_dms} DMs found, skipping remaining emails")
                            break
                except Exception as e:
                    logger.error(f"  ❌ Error processing email: {e}")

        # Step 4: Generate messages for all DMs (parallel)
        if self.openai_client and decision_makers:
            def _generate_msg(dm):
                try:
                    dm['message'] = self.generate_message(
                        dm['dm_name'], company_name, dm['job_title'],
                        dm.get('dm_description', ''), dm.get('company_description', '')
                    )
                except Exception as e:
                    logger.error(f"  ❌ Error generating message for {dm['dm_name']}: {e}")
                    dm['message'] = ""

            with ThreadPoolExecutor(max_workers=3) as msg_executor:
                list(msg_executor.map(_generate_msg, decision_makers))
        else:
            for dm in decision_makers:
                dm['message'] = ""

        logger.info(f"  ✓ Found {len(decision_makers)} decision-makers for {company_name}")
        logger.info(f"   ✓ [{len(decision_makers)}] {company_name} ({len(decision_makers)} DMs)")

        return decision_makers

    # ===========================================
    # HELPER FUNCTIONS
    # ===========================================

    def normalize_company_name(self, name: str) -> str:
        """Remove legal suffixes for cleaner searches."""
        if not name:
            return ""

        suffixes = [
            ', Inc.', ', Inc', ' Inc.',
            ', LLC', ' LLC',
            ', Ltd.', ', Ltd', ' Ltd.',
            ', Corp.', ', Corp', ' Corp.',
            ', Co.', ', Co', ' Co.',
            ', L.P.', ', LP', ' LP',
            ', LLP', ' LLP',
            ', PLC', ' PLC'
        ]

        normalized = name
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break

        return normalized.strip()

    def normalize_job_title(self, title: str) -> str:
        """Simplify job title by removing unnecessary details."""
        if not title:
            return ""

        # Remove everything after common delimiters
        # Examples:
        # "Senior Research Software Engineer - Security & Cryptography" → "Senior Research Software Engineer"
        # "Senior iOS Engineer, Music" → "Senior iOS Engineer"
        # "Product Manager (Remote)" → "Product Manager"

        for delimiter in [' - ', ' – ', ' — ', ',', ' (']:
            if delimiter in title:
                title = title.split(delimiter)[0].strip()
                break

        return title.strip()

    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """
        Extract name from email and classify as generic/personal
        Migrated from Crunchbase scraper v4.0

        Returns: (name, is_generic, confidence)
        """
        if not email or '@' not in email:
            return ('', True, 0.0)

        local_part = email.split('@')[0].lower()

        # Generic email patterns
        generic_patterns = [
            'info', 'contact', 'hello', 'support', 'sales', 'admin',
            'office', 'inquiries', 'help', 'service', 'team', 'mail',
            'general', 'reception', 'booking', 'hr', 'jobs', 'careers'
        ]

        is_generic = any(pattern in local_part for pattern in generic_patterns)

        if is_generic:
            return ('', True, 0.0)

        # Pattern 1: firstname.lastname@ (HIGHEST confidence)
        if '.' in local_part and not local_part.startswith('.') and not local_part.endswith('.'):
            parts = local_part.split('.')
            # Allow single-letter first initials (q.xu@, b.smith@) but last name must be 2+ chars
            valid_parts = []
            for i, p in enumerate(parts):
                if p.isalpha() and ((i == 0 and 1 <= len(p) <= 20) or (i > 0 and 2 <= len(p) <= 20)):
                    valid_parts.append(p)

            if len(valid_parts) == 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[1].capitalize()
                return (f"{first} {last}", False, 0.95)
            elif len(valid_parts) > 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[-1].capitalize()
                return (f"{first} {last}", False, 0.9)

        # Pattern 2: firstname_lastname@ or firstname-lastname@
        name_parts = re.split(r'[._\-0-9]+', local_part)
        name_parts = [
            p for p in name_parts
            if p.isalpha() and 2 <= len(p) <= 20
        ]

        if len(name_parts) >= 2:
            first = name_parts[0].capitalize()
            last = name_parts[-1].capitalize()

            if len(first) >= 3 and len(last) >= 3:
                return (f"{first} {last}", False, 0.9)
            else:
                return (f"{first} {last}", False, 0.7)

        # Pattern 3: Single name (kathy@, sarah@)
        elif len(name_parts) == 1:
            single_part = name_parts[0]

            # Try camelCase (johnSmith@)
            if len(single_part) >= 6:
                camel_match = re.match(r'^([a-z]+)([A-Z][a-z]+)$', email.split('@')[0])
                if camel_match:
                    first = camel_match.group(1).capitalize()
                    last = camel_match.group(2).capitalize()
                    return (f"{first} {last}", False, 0.85)

            # Single name with decent length
            if len(single_part) >= 3:
                return (single_part.capitalize(), False, 0.6)

        return ('', False, 0.2)

    def is_decision_maker(self, job_title: str) -> bool:
        """
        Validate if job title is a decision-maker position.
        Uses regex word-boundary matching to prevent partial matches.
        """
        if not job_title or len(job_title) < 3:
            return False

        job_title_lower = job_title.lower()

        # Regex word-boundary matching for decision-maker keywords
        dm_pattern = r'\b(?:' + '|'.join([
            r'founder', r'co-founder', r'ceo', r'chief executive', r'chief',
            r'owner', r'president', r'cfo', r'cto', r'coo', r'cmo',
            r'c-suite', r'c-level',
            r'vice president', r'vp', r'svp', r'evp',
            r'director', r'executive director', r'managing director',
            r'head of', r'managing partner', r'partner', r'principal',
            r'executive',
        ]) + r')\b'

        has_dm_keyword = bool(re.search(dm_pattern, job_title_lower))

        # Exclude non-decision-maker roles
        exclude_pattern = r'\b(?:' + '|'.join([
            r'assistant', r'associate', r'junior', r'intern', r'coordinator',
            r'analyst', r'specialist', r'representative', r'agent', r'clerk',
            r'trainee', r'apprentice', r'student',
        ]) + r')\b'

        has_exclude_keyword = bool(re.search(exclude_pattern, job_title_lower))

        return has_dm_keyword and not has_exclude_keyword

    def find_company_website(self, company_name: str) -> Dict:
        """
        Find company website using Google Search (v2.0 - uses RapidAPIGoogleSearch class)

        Args:
            company_name: Company name

        Returns:
            Dict: {url, description}
        """
        if not self.rapidapi_search:
            return {'url': '', 'description': ''}

        # 3-attempt strategy for website finding
        search_attempts = [
            f'"{company_name}" official website',      # Attempt 1: Most specific
            f'"{company_name}" company website',       # Attempt 2: Broader
            f'{company_name} site'                     # Attempt 3: Very broad
        ]

        for attempt_num, query in enumerate(search_attempts, 1):
            search_result = self.rapidapi_search._rate_limited_search(query, num_results=5)

            if not search_result or not search_result.get('results'):
                continue

            # Filter out social media sites and find first valid result
            skip_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'indeed.com', 'glassdoor.com', 'wikipedia.org']

            for result in search_result['results']:
                url = result.get('url', '')
                snippet = result.get('snippet', '')

                # Skip social media and unwanted domains
                if any(skip in url.lower() for skip in skip_domains):
                    continue

                # Return first valid result
                return {
                    'url': url,
                    'description': snippet
                }

        return {'url': '', 'description': ''}

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def validate_email_format(self, email: str) -> bool:
        """
        Validate email format using regex and block disposable domains.

        Returns:
            bool: True if valid and not disposable, False otherwise
        """
        # RFC 5322 format check
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False

        # Block disposable/temporary email domains
        disposable_domains = [
            'tempmail.com', 'guerrillamail.com', 'mailinator.com',
            '10minutemail.com', 'throwaway.email', 'trashmail.com',
            'maildrop.cc', 'temp-mail.org', 'getnada.com', 'mohmal.com'
        ]

        try:
            domain = email.split('@')[1].lower()
            return domain not in disposable_domains
        except (IndexError, AttributeError):
            return False

    def generate_message(
        self,
        dm_name: str,
        company: str,
        job_title: str,
        dm_desc: str,
        company_desc: str
    ) -> str:
        """
        Generate SSM-style connector email using Azure OpenAI.

        Args:
            dm_name: Decision maker name
            company: Company name
            job_title: Job title they're hiring for
            dm_desc: DM LinkedIn snippet
            company_desc: Company website snippet

        Returns:
            str: Personalized connector email
        """
        if not self.openai_client:
            return ""

        # Truncate descriptions (prevent token overflow)
        dm_desc = dm_desc[:500] if dm_desc else ""
        company_desc = company_desc[:500] if company_desc else ""

        prompt = f"""
Write a connector-style cold email to {dm_name} at {company}.

Context:
- They're hiring for: {job_title}
- Decision Maker LinkedIn snippet: "{dm_desc}"
- Company website snippet: "{company_desc}"

CRITICAL FRAMEWORK - PRESSURE-BASED APPROACH (NOT ROLE-BASED):
❌ DON'T say: "Saw you're hiring for {job_title}..." (stalkerish, fragile)
✅ DO say: Use pressure/pattern recognition instead of explicit job mentions

The hiring signal justifies WHY you're reaching out, but you NEVER mention it directly.
Switch from "roles" → "pressure" to make it about THEIR world, not what you noticed.

CRITICAL RULES:
1. Spartan/Laconic tone - Short, simple, direct. No fluff
2. NO PUNCTUATION at end of sentences/CTAs
3. 5-7 sentences max, under 100 words total
4. Connector Angle - helpful introducer, not seller
5. Lead with THEM and their pressure, not you or the role
6. No jargon: leverage, optimize, streamline, synergy, solutions, innovative, cutting-edge
7. Remove company legal suffixes (Inc., LLC, etc.)
8. NEVER mention: "saw you're hiring", "noticed your job posting", "careers page"
9. NO LINE BREAKS - Write as continuous flowing text, separate thoughts with periods only
10. NO CTA - End with "Sent from my iPhone" only (no "wondering if", "worth a chat", "happy to intro")

MANDATORY PAIN-MATCHING RULES:
Rule 1: Pain Point MUST Match Job Title
- The pain/function MUST be directly related to the job title being hired for
- Example: Hiring "SDR" → talk about "outbound" or "pipeline" ✅
- Example: Hiring "SDR" → talk about "engineering velocity" ❌ (wrong function!)
- Example: Hiring "Blockchain Engineer" → talk about "smart contract deployment" ✅
- Example: Hiring "Blockchain Engineer" → talk about "sales pipeline" ❌ (wrong function!)

Rule 2: Specificity Test - MUST Pass All Three Checks
Before writing, verify:
a) Can I quantify the pain? (Include specific metrics, numbers, or measurable outcomes)
b) Is this pain specific to their industry/job function? (Not generic to all companies)
c) Would 10 different companies have 10 different interpretations of this pain?
   → If YES = TOO VAGUE, rewrite with more specificity
   → If NO = GOOD, pain is specific enough

BAD (too vague): "scaling challenges" - every company has these
GOOD (specific): "SDK adoption dropping below 30% after first integration" - measurable, specific to developer tools

BAD (too vague): "hiring issues" - too generic
GOOD (specific): "Web3 engineering pipeline running dry after 90 days without senior Solidity hires" - specific to crypto/blockchain

CHOOSE ONE OF THESE 5 PATTERNS - ROTATE THROUGH ALL VERSIONS (don't default to one):

VERSION 1: Pain Signal + Specificity
Format: Noticed [company] recently [growth_signal from context]. Teams at this stage usually hit capacity issues in [function from job_title], especially around [specific_pain_point]
NO LINE BREAKS - write as continuous paragraph
Example: "Noticed Ramp is scaling fast—25,000+ customers is no small feat. Teams growing at this pace often hit capacity issues in outbound, especially keeping top-of-funnel consistent"

VERSION 2: Peer Benchmark (Connector Angle)
Format: Working with a few [industry] companies around your size. They're all running into the same [function] bottleneck as they scale past [growth_stage from context]
NO LINE BREAKS - write as continuous paragraph
Example: "Working with a few fintech companies around your size. They're all running into the same deal flow constraints as they scale into new markets"

VERSION 3: Forward-Looking + Consultative
Format: [Company] is growing fast ([specific_signal from context]). At this trajectory, most [industry] teams start feeling the squeeze in [function] within 3-6 months
NO LINE BREAKS - write as continuous paragraph
Example: "Stripe is growing fast—15 new countries launched. At this trajectory, most payments teams start feeling the squeeze in go-to-market within 3-6 months"

VERSION 4: Pattern Recognition (Best for Multiple Intros)
Format: I've introduced 3 [industry] companies to specialists this month. All had the same issue: [function] became a bottleneck after [trigger_event from context]
NO LINE BREAKS - write as continuous paragraph
Example: "I've introduced 3 AI companies to specialists this month. All had the same issue: engineering velocity became a bottleneck after Series B"

VERSION 5: Direct + Low Pressure
Format: Quick question—is [function] keeping up with growth at [company], or starting to show cracks
NO LINE BREAKS - write as continuous paragraph
Example: "Quick question—is outbound keeping up with growth at Webflow, or starting to show cracks"

IMPORTANT: Mix up the versions. Don't always pick VERSION 2. Rotate through all 5 patterns based on context fit.

PRESSURE/FUNCTION INFERENCE FROM JOB TITLES (MUST MATCH JOB ROLE):
Generic Roles:
- SDR/BDR → "outbound", "pipeline", "top-of-funnel", "demo conversion"
- AE/Sales → "closing velocity", "deal flow", "revenue", "quota attainment"
- Product Manager → "roadmap clarity", "prioritization", "feature scope", "release velocity"
- Designer → "brand consistency", "design systems", "UX iteration speed"
- Operations → "process automation", "systems", "ops efficiency", "workflow bottlenecks"
- Marketing → "demand generation", "pipeline quality", "brand awareness", "MQL-to-SQL conversion"
- Customer Success → "retention", "expansion", "customer health", "NPS scores", "churn prevention"
- Recruiter → "talent pipeline", "hiring velocity", "team scaling", "time-to-fill"
- Data/Analytics → "insights speed", "data infrastructure", "reporting lag", "dashboard accuracy"

Web3/Blockchain-Specific Roles (USE THESE FOR CRYPTO JOBS):
- Blockchain Engineer/Developer → "smart contract deployment speed", "gas optimization", "audit cycles", "testnet-to-mainnet lag"
- Solidity Developer → "contract security audits", "deployment velocity", "vulnerability detection", "bytecode optimization"
- Smart Contract Engineer → "audit turnaround time", "exploit prevention", "contract upgradeability", "testing coverage"
- Web3 Frontend/Full-stack → "wallet integration", "Web3.js performance", "dApp user onboarding", "transaction confirmation UX"
- DeFi Engineer → "liquidity pool efficiency", "yield optimization", "TVL growth", "protocol security"
- NFT Developer → "minting pipeline", "metadata management", "marketplace integration", "royalty tracking"
- Crypto/Blockchain Architect → "chain interoperability", "bridge security", "cross-chain transaction speed", "validator performance"
- Protocol Engineer → "consensus mechanism", "block finality time", "network throughput", "validator set coordination"

GROWTH SIGNALS (infer from context):
- Funding, team size, product launch, market expansion, revenue milestones
- Examples: "just raised Series B", "scaling to 100 people", "entering new markets"

TRIGGER EVENTS (infer from context):
- "scaling past 50 people", "expanding to new markets", "post-funding", "product complexity increased"

Output ONLY the email body. No subject line. No explanations. Pick the version that feels most natural given the context.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.azure_deployment,
                messages=[
                    {"role": "system", "content": "You are an expert at SSM/connector-style cold emails. Spartan tone. No corporate speak."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ Message generation failed for {company}: {e}")
            return ""

    # ===========================================
    # GOOGLE SHEETS EXPORT
    # ===========================================

    def get_credentials(self):
        """Get Google OAuth credentials with proper token handling."""
        creds = None
        if os.path.exists('token.json'):
            try:
                creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            except Exception as e:
                logger.warning(f"⚠️ Token file corrupted: {e}")
                os.remove('token.json')
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("❌ credentials.json not found")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return creds

    def export_to_google_sheets(self, rows: List[Dict], title: str) -> str:
        """
        Export data to Google Sheets.

        Args:
            rows: List of job dicts
            title: Sheet title

        Returns:
            str: Google Sheets URL
        """
        logger.info("📊 Exporting to Google Sheets...")

        creds = self.get_credentials()
        if not creds:
            logger.error("❌ Failed to get Google credentials")
            return ""

        try:
            service = build('sheets', 'v4', credentials=creds)
            drive_service = build('drive', 'v3', credentials=creds)

            # Create spreadsheet
            spreadsheet = {'properties': {'title': title}}
            spreadsheet = service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl,sheets.properties.sheetId'
            ).execute()

            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
            sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']

            # Prepare data
            headers = [
                "Company Name", "Company Website", "Company Domain", "Company Description",
                "Job Title", "Job URL", "Location", "Posted Date",
                "DM Name", "DM Title", "DM First", "DM Last", "DM LinkedIn", "DM Description",
                "DM Email", "Email Status", "Email Confidence",
                "Message", "Scraped Date"
            ]

            values = [headers]
            for row in rows:
                values.append([
                    row.get('company_name', ''),
                    row.get('company_website', ''),
                    row.get('company_domain', ''),
                    row.get('company_description', ''),
                    row.get('job_title', ''),
                    row.get('job_url', ''),
                    row.get('location', ''),
                    row.get('posted_date', ''),
                    row.get('dm_name', ''),
                    row.get('dm_title', ''),
                    row.get('dm_first', ''),
                    row.get('dm_last', ''),
                    row.get('dm_linkedin', ''),
                    row.get('dm_description', ''),
                    row.get('dm_email', ''),
                    row.get('email_status', ''),
                    row.get('email_confidence', 0),
                    row.get('message', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ])

            # Write data
            body = {'values': values}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            # Format header (bold, blue background, freeze)
            requests_format = [{
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)"
                }
            }, {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1}
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            }]

            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests_format}
            ).execute()

            # Make public (view-only)
            permission = {'type': 'anyone', 'role': 'reader'}
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=permission
            ).execute()

            logger.info(f"✓ Exported {len(rows)} rows to Google Sheets")
            return spreadsheet_url

        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return ""

    # ===========================================
    # MAIN EXECUTION
    # ===========================================

    def execute(
        self,
        query: str,
        location: str = "",
        country: str = "United States",
        max_jobs: int = 50,
        days_posted: int = 14
    ):
        """
        Main execution flow: Scrape → Stream → Process → Export.

        Args:
            query: Job search query (e.g., "AI Engineer")
            location: Geographic location (e.g., "San Francisco")
            country: Country name or code (e.g., "United States")
            max_jobs: Maximum jobs to scrape
            days_posted: Filter jobs posted within X days
        """
        print("\n" + "=" * 70)
        print("🚀 LINKEDIN JOB SCRAPER & OUTREACH SYSTEM (STREAMING MODE)")
        print(f"Query: {query} | Location: {location or 'Any'} | Country: {country}")
        print("=" * 70 + "\n")

        # Phase 1: Start Scraper
        run_id = self.start_linkedin_scraper(query, location, country, max_jobs, days_posted)
        if not run_id:
            logger.error("❌ Failed to start scraper. Exiting.")
            return

        processed_jobs = []
        seen_emails = set()  # Cross-company email dedup
        company_count = 0  # Track unique companies processed

        # Phase 2 & 3: TRUE STREAMING - Process as jobs arrive
        print(f"🔄 Streaming & Processing jobs in real-time...\n")

        # Use 10 outer workers (I/O bound - mostly waiting on API calls)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}  # Track in-flight futures only
            stream_complete = False
            stream = self.stream_jobs(run_id)
            done_futures = []  # Initialize to avoid reference error

            while not stream_complete or futures:
                # Submit new jobs while stream is active and capacity available
                while len(futures) < 10 and not stream_complete:
                    try:
                        job = next(stream)
                        future = executor.submit(self.process_single_company, job)
                        futures[future] = job
                        print(f"   → Queued: {job['company_name']}")
                    except StopIteration:
                        stream_complete = True
                        break

                # Process completed results IMMEDIATELY (don't wait for all)
                if futures:
                    done_futures = [f for f in futures if f.done()]
                    for future in done_futures:
                        job_info = futures[future]
                        try:
                            results = future.result()  # Now returns List[Dict]
                            company_count += 1

                            # Dedup emails across companies
                            for dm in results:
                                email = dm.get('dm_email', '')
                                if email and email not in seen_emails:
                                    seen_emails.add(email)
                                    processed_jobs.append(dm)

                            # Real-time feedback
                            if results:
                                email_status = f"{len(results)} DMs"
                                print(f"   ✓ [{company_count}] {job_info['company_name']} ({email_status})")
                            else:
                                print(f"   ✗ [{company_count}] {job_info['company_name']} (0 DMs)")
                        except Exception as e:
                            logger.error(f"❌ Error processing {job_info['company_name']}: {e}")
                        finally:
                            del futures[future]

                # Small delay to prevent tight loop
                if not done_futures and futures:
                    time.sleep(0.1)

        # Phase 4: Filter & Export
        jobs_with_emails = [
            job for job in processed_jobs
            if job.get('dm_email') and job.get('email_status') == 'found'
        ]

        print("\n" + "-" * 70)
        print(f"📊 SUMMARY:")
        print(f"   Companies Processed: {company_count}")
        print(f"   Decision Makers Found: {len(processed_jobs)}")
        print(f"   Emails Exported: {len(jobs_with_emails)}")
        print(f"   Avg DMs/Company: {len(processed_jobs)/company_count:.1f}" if company_count else "   Avg DMs/Company: 0")
        print("-" * 70 + "\n")

        # Save CSV backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = f".tmp/linkedin_jobs_{timestamp}.csv"

        if jobs_with_emails:
            pd.DataFrame(jobs_with_emails).to_csv(csv_path, index=False)
            print(f"📁 CSV Backup: {csv_path}")

            # Export to Google Sheets
            sheet_title = f"LinkedIn Jobs - {query} - {datetime.now().strftime('%Y-%m-%d')}"
            url = self.export_to_google_sheets(jobs_with_emails, sheet_title)
            if url:
                print(f"🔗 Google Sheet: {url}")
        else:
            print("⚠️ No emails found. Skipping export.")
            print("   Check: API keys, query relevance, days_posted filter")

        print("\n✅ DONE!\n")
        notify_success()


def main():
    """CLI entry point with argparse."""

    parser = argparse.ArgumentParser(
        description='LinkedIn Job Scraper with Decision Maker Outreach (Bebity Pattern)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_linkedin_jobs.py --query "AI Engineer" --location "San Francisco" --limit 50
  python scrape_linkedin_jobs.py --query "Marketing Manager" --location "Remote" --limit 100 --days 7
  python scrape_linkedin_jobs.py --query "Full Stack Developer" --country "United Kingdom" --limit 25
        """
    )

    parser.add_argument('--query', type=str, required=True, help='Job search query (e.g., "AI Engineer")')
    parser.add_argument('--location', type=str, default="", help='Job location (e.g., "San Francisco", "Remote")')
    parser.add_argument('--country', type=str, default="United States", help='Country (e.g., "United States", "United Kingdom")')
    parser.add_argument('--limit', type=int, default=50, help='Max jobs to scrape (default: 50)')
    parser.add_argument('--days', type=int, default=14, help='Days posted (default: 14)')

    args = parser.parse_args()

    try:
        scraper = LinkedInJobScraper()
        scraper.execute(
            query=args.query,
            location=args.location,
            country=args.country,
            max_jobs=args.limit,
            days_posted=args.days
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user. Exiting gracefully...\n")
        notify_error()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)


if __name__ == "__main__":
    main()
