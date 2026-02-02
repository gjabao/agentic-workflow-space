#!/usr/bin/env python3
"""
Glassdoor Job Scraper & Decision Maker Outreach System
Scrapes jobs from Glassdoor, finds decision makers (Founder/CEO/CFO), gets emails, and generates outreach messages.
"""

import os
import sys
import json
import logging
import time
import re
import requests
import pandas as pd
from typing import Dict, List, Optional, Any, Generator, Tuple
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
        logging.FileHandler('.tmp/glassdoor_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Suppress noisy library logs
logging.getLogger('google_auth_oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class AnyMailFinderCompanyAPI:
    """
    Company Email Finder - Returns ALL emails at a company (up to 20)
    v2.0 Email-First Workflow - Based on Crunchbase v4.0
    """

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key
        logger.info("✓ AnyMailFinder Company API initialized (v2.0)")

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """Find ALL emails at company (up to 20) in one API call"""
        try:
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

            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                email_status = data.get('email_status', 'not_found')
                if email_status == 'valid' and data.get('valid_emails'):
                    return {'emails': data['valid_emails'], 'status': 'found', 'count': len(data['valid_emails'])}
                return {'emails': [], 'status': 'not-found', 'count': 0}
            return {'emails': [], 'status': 'not-found', 'count': 0}
        except Exception as e:
            logger.debug(f"Error for {company_domain}: {e}")
            return {'emails': [], 'status': 'not-found', 'count': 0}


class GlassdoorJobScraper:
    # Actor IDs
    JOB_SCRAPER_ACTOR_ID = "agentx/glassdoor-hiring-scraper"

    # API Config (v2.0 Email-First)
    RAPIDAPI_GOOGLE_SEARCH_URL = "https://google-search116.p.rapidapi.com/"
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    # Performance Configuration
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))  # Reduced from 20→10 for better rate limiting
    APIFY_POLL_INTERVAL_START = 1
    APIFY_POLL_INTERVAL_MAX = 5
    APIFY_MAX_WAIT = 600

    def __init__(self):
        # 1. Apify
        self.apify_token = os.getenv("APIFY_API_KEY")
        if not self.apify_token:
            raise ValueError("APIFY_API_KEY not found")
        self.apify_client = ApifyClient(self.apify_token)

        # 2. RapidAPI for Google Search
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY")
        if not self.rapidapi_key:
            logger.warning("⚠️ RAPIDAPI_KEY not found. Decision maker search will be slower.")

        # 3. AnyMailFinder Company API (v2.0 Email-First)
        anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        self.email_finder = AnyMailFinderCompanyAPI(anymail_key) if anymail_key else None
        if not anymail_key:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found. Email finding will be skipped.")

        # 4. Azure OpenAI
        self.azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if self.azure_key and self.azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=self.azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=self.azure_endpoint
            )
            logger.info("✓ Azure OpenAI initialized")
        else:
            self.openai_client = None
            logger.warning("⚠️ Azure OpenAI keys missing. Message generation will be skipped.")

        # Rate limiting for RapidAPI (prevent 429 errors)
        self.rapidapi_lock = Lock()
        self.last_rapidapi_call = 0
        self.rapidapi_delay = 0.25  # 250ms between calls = ~4 req/sec

        # Caching for performance
        self._website_cache = {}  # Cache company websites
        self._dm_cache = {}       # Cache decision makers

        logger.info("✓ GlassdoorJobScraper initialized")

    def normalize_company_name(self, company_name: str) -> str:
        """Normalize company name by removing legal suffixes and cleaning up."""
        if not company_name:
            return ""

        # Remove common legal suffixes
        suffixes = [
            ', Inc.', ', Inc',
            ', LLC', ' LLC',
            ', Ltd.', ', Ltd',
            ', Corp.', ', Corp',
            ', Co.', ', Co',
            ', L.P.', ', LP',
            ', LLP', ' LLP',
            ', PLC', ' PLC'
        ]

        normalized = company_name
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break

        return normalized.strip()

    def normalize_job_title(self, job_title: str) -> str:
        """Simplify job title by removing unnecessary details and locations."""
        if not job_title:
            return ""

        # Remove everything after common delimiters
        for delimiter in [' - ', ' – ', ' — ', ',', ' (', ' /', ' |']:
            if delimiter in job_title:
                job_title = job_title.split(delimiter)[0].strip()
                break

        return job_title.strip()

    def detect_company_type(self, company_name: str, industry: str = "", description: str = "", website_desc: str = "") -> str:
        """
        Detect company type/industry based on multiple signals.

        Priority: website description → job description → industry → company name
        """
        # Prioritize website description (most accurate)
        text = f"{website_desc} {description} {industry} {company_name}".lower()

        # Media & Information (NEW - for companies like Thomson Reuters)
        if any(word in text for word in ['news', 'media', 'publishing', 'journalist', 'information services', 'reuters', 'bloomberg']):
            return 'Media & Information'

        # Financial Services (IMPROVED - added payment processing)
        if any(word in text for word in ['bank', 'financial', 'finance', 'capital', 'investment', 'asset management', 'insurance', 'credit', 'payment', 'fintech', 'moneris']):
            return 'Financial Services'

        # Healthcare & Medical
        if any(word in text for word in ['hospital', 'health', 'medical', 'clinic', 'healthcare', 'pharmaceutical', 'pharma', 'biotech', 'cancer research', 'patient']):
            return 'Healthcare & Medical'

        # Construction & Real Estate (IMPROVED - added infrastructure)
        if any(word in text for word in ['construction', 'builder', 'contractor', 'real estate', 'property', 'development', 'infrastructure']):
            return 'Construction & Real Estate'

        # Technology & Software
        if any(word in text for word in ['software', 'technology', 'tech ', 'saas', 'cloud', 'digital', 'it ', 'data', 'ai ', 'cyber', 'innovation']):
            return 'Technology & Software'

        # Manufacturing & Industrial
        if any(word in text for word in ['manufacturing', 'industrial', 'fabrication', 'production', 'factory', 'machining']):
            return 'Manufacturing & Industrial'

        # Retail & Consumer
        if any(word in text for word in ['retail', 'store', 'shopping', 'consumer', 'ecommerce', 'e-commerce', 'commerce']):
            return 'Retail & Consumer'

        # Professional Services
        if any(word in text for word in ['consulting', 'accounting', 'legal', 'law', 'recruitment', 'staffing', 'hr ', 'advisory']):
            return 'Professional Services'

        # Non-Profit & Government
        if any(word in text for word in ['nonprofit', 'non-profit', 'charity', 'foundation', 'government', 'municipal', 'city of', 'town of', 'institute']):
            return 'Non-Profit & Government'

        # Education
        if any(word in text for word in ['school', 'university', 'college', 'education', 'academy', 'learning']):
            return 'Education'

        # Energy & Utilities
        if any(word in text for word in ['energy', 'power', 'utility', 'oil', 'gas', 'renewable', 'solar', 'hydro']):
            return 'Energy & Utilities'

        return 'Other'

    def start_scraping_job(self, query: str, location: str, country: str = "Canada", max_jobs: int = 10, days_posted: int = 60) -> str:
        """Start the Apify scraper job and return the run ID."""
        logger.info(f"🔍 Starting Glassdoor scrape for {max_jobs} jobs: '{query}' in '{location}', {country}...")

        # Glassdoor actor expects "posted_since" in format "60 days"
        posted_since = f"{days_posted} days"

        run_input = {
            "country": country,
            "location": location if location else "",
            "search_terms": [query],
            "max_results": max_jobs,
            "posted_since": posted_since
        }

        try:
            # Start the actor asynchronously
            run = self.apify_client.actor(self.JOB_SCRAPER_ACTOR_ID).start(run_input=run_input)
            run_id = run["id"]
            logger.info(f"✓ Glassdoor scraper started. Run ID: {run_id}")
            return run_id
        except Exception as e:
            logger.error(f"❌ Failed to start scraper: {e}")
            return ""

    def stream_jobs(self, run_id: str) -> Generator[Dict, None, None]:
        """Yield jobs from the Apify dataset as they become available with exponential backoff."""
        if not run_id:
            return

        offset = 0
        limit = 100
        poll_delay = self.APIFY_POLL_INTERVAL_START
        poll_start = time.time()

        while True:
            # Timeout check
            if time.time() - poll_start > self.APIFY_MAX_WAIT:
                logger.error(f"❌ Apify run {run_id} timed out after {self.APIFY_MAX_WAIT}s")
                break

            run = self.apify_client.run(run_id).get()
            status = run.get("status")
            dataset_id = run.get("defaultDatasetId")

            # Fetch new items
            list_items = self.apify_client.dataset(dataset_id).list_items(offset=offset, limit=limit)
            items = list_items.items

            if items:
                for item in items:
                    company = item.get('company_name', '')
                    title = item.get('title', '')

                    if not company or not title:
                        continue

                    # Normalize
                    normalized_company = self.normalize_company_name(company)
                    normalized_title = self.normalize_job_title(title)

                    # Build salary range string if available
                    salary_range = ""
                    if item.get('salary_minimum') and item.get('salary_maximum'):
                        currency = item.get('salary_currency', 'CAD')
                        period = item.get('salary_period', 'yearly')
                        salary_range = f"{currency} {item['salary_minimum']:,}-{item['salary_maximum']:,} {period}"

                    yield {
                        'company_name': normalized_company if normalized_company else company,
                        'job_title': normalized_title if normalized_title else title,
                        'job_url': item.get('platform_url', ''),
                        'job_description': item.get('description', ''),
                        'posted_date': item.get('posted_date', ''),
                        'location': item.get('location', ''),
                        'salary_range': salary_range,
                        'company_size': item.get('employee_count', ''),
                        'company_industry': item.get('company_industry', ''),
                        'company_rating': item.get('company_rating', '')
                    }

                offset += len(items)
                poll_delay = self.APIFY_POLL_INTERVAL_START  # Reset delay when we get data

            if status in ["SUCCEEDED", "FAILED", "ABORTED"] and len(items) == 0:
                break

            # Exponential backoff polling
            time.sleep(poll_delay)
            poll_delay = min(poll_delay * 1.5, self.APIFY_POLL_INTERVAL_MAX)

    def find_decision_maker_by_name(self, person_name: str, company_name: str) -> Dict:
        """
        Find LinkedIn profile by PERSON NAME + COMPANY (v2.1 Email-First Fix).

        This searches for the SPECIFIC PERSON extracted from email, not generic decision-makers.
        Example: "Fatima Kamalia" at "Mackenzie Health" → finds Fatima's profile
        """
        # Check cache first (use person+company as key)
        cache_key = f"{person_name}|{company_name}"
        if cache_key in self._dm_cache:
            return self._dm_cache[cache_key]

        if not self.rapidapi_key or not person_name:
            return {}

        # 3-ATTEMPT STRATEGY: Search by NAME + COMPANY
        search_attempts = [
            # Attempt 1: Exact name + company on LinkedIn
            f'site:linkedin.com/in/ "{person_name}" "{company_name}"',

            # Attempt 2: Name + company without site restriction (broader)
            f'"{person_name}" "{company_name}" linkedin profile',

            # Attempt 3: Just name + company (very broad)
            f'{person_name} {company_name} linkedin'
        ]

        for search_attempt_num, query in enumerate(search_attempts, 1):
            logger.debug(f"    → LinkedIn search attempt {search_attempt_num}/3: {person_name}")

            result = self._linkedin_search(query, search_attempt_num)
            if result.get('full_name'):
                # Cache the result
                self._dm_cache[cache_key] = result
                logger.debug(f"    ✓ LinkedIn found: {result['full_name']} - {result.get('title', '')}")
                return result

        # All 3 attempts failed
        logger.debug(f"    ✗ LinkedIn not found for {person_name}")
        return {}

    def find_decision_maker(self, company_name: str) -> Dict:
        """
        [LEGACY] Find decision makers by COMPANY NAME only (for backwards compatibility).

        NOTE: This method is used by old workflows. New email-first workflow uses
        find_decision_maker_by_name() instead for better accuracy.
        """
        # Check cache first
        if company_name in self._dm_cache:
            return self._dm_cache[company_name]

        if not self.rapidapi_key:
            return {}

        # 3-ATTEMPT STRATEGY for finding decision makers
        search_attempts = [
            # Attempt 1: Finance-specific titles with company name (most targeted)
            f'site:linkedin.com/in/ ("cfo" OR "chief financial officer" OR "vp finance" OR "vice president finance" OR "director of finance" OR "controller") "{company_name}"',

            # Attempt 2: Broader executive titles (fallback if no finance leaders found)
            f'site:linkedin.com/in/ ("founder" OR "co-founder" OR "ceo" OR "chief executive officer" OR "owner" OR "managing partner" OR "president") "{company_name}"',

            # Attempt 3: Very broad search without site restriction (last resort)
            f'("{company_name}" AND (cfo OR "chief financial officer" OR ceo OR founder OR president) linkedin profile)'
        ]

        # Try 3 different search attempts before giving up
        for search_attempt_num, query in enumerate(search_attempts, 1):
            logger.info(f"  → Attempt {search_attempt_num}/3: Searching for decision maker at {company_name}")

            result = self._linkedin_search(query, search_attempt_num)
            if result.get('full_name'):
                # Cache the result
                self._dm_cache[company_name] = result
                logger.info(f"  ✓ Found: {result['full_name']} - {result.get('title', '')}")
                return result

        # All 3 attempts failed
        logger.info(f"  ✗ No decision maker found after 3 attempts")
        return {}

    def _linkedin_search(self, query: str, attempt_num: int) -> Dict:
        """
        Execute LinkedIn search via RapidAPI Google Search.
        Returns parsed LinkedIn profile data or empty dict.
        """
        max_retries = 2
        for retry in range(max_retries):
            try:
                # Rate limiting logic - sleep OUTSIDE the lock
                wait_time = 0
                with self.rapidapi_lock:
                    elapsed = time.time() - self.last_rapidapi_call
                    if elapsed < self.rapidapi_delay:
                        wait_time = self.rapidapi_delay - elapsed
                    else:
                        self.last_rapidapi_call = time.time()

                if wait_time > 0:
                    time.sleep(wait_time)
                    # Update timestamp after sleep
                    with self.rapidapi_lock:
                        self.last_rapidapi_call = time.time()

                headers = {
                    'x-rapidapi-host': 'google-search116.p.rapidapi.com',
                    'x-rapidapi-key': self.rapidapi_key
                }
                params = {'query': query}

                response = requests.get(
                    self.RAPIDAPI_GOOGLE_SEARCH_URL,
                    headers=headers,
                    params=params,
                    timeout=10
                )

                if response.status_code == 429:
                    if retry < max_retries - 1:
                        time.sleep((retry + 1) * 2)
                        continue
                    return {}

                if response.status_code != 200:
                    return {}

                data = response.json()
                organic_results = data.get('results', [])
                if not organic_results:
                    return {}

                top_result = organic_results[0]
                title = top_result.get('title', '')
                link = top_result.get('url', '')
                description = top_result.get('description', '')

                # Parse name/title logic
                name_part = title.split('-')[0].strip() if '-' in title else title.strip()
                dm_title = ""
                if '-' in title and len(title.split('-')) > 1:
                    title_part = title.split('-')[1].strip()
                    if '|' in title_part:
                        title_part = title_part.split('|')[0].strip()
                    dm_title = title_part

                name_parts = name_part.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = name_part
                    last_name = ""

                # SUCCESS - Found a profile
                return {
                    'full_name': name_part,
                    'first_name': first_name,
                    'last_name': last_name,
                    'title': dm_title,
                    'linkedin_url': link,
                    'description': description,
                    'source': f'RapidAPI Google Search (Attempt {attempt_num})'
                }

            except Exception as e:
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return {}

        return {}

    def find_company_website(self, company_name: str, keywords: str = "") -> Dict:
        """
        IMPROVED v2.1: Find company website with 90%+ success rate using MULTI-RETRY strategy

        Strategy 1: RapidAPI Google Search with keywords (3 query variations)
        Strategy 2: RapidAPI Google Search without keywords (3 query variations)
        Strategy 3: Domain guessing with expanded TLDs (.com, .ca, .org, .io, .co, .net, .biz)
        Strategy 4: Wildcard Google Search (last resort)

        Args:
            company_name: Company name to search for
            keywords: Contextual keywords (location + industry) to improve search accuracy
        """
        # Check cache first
        cache_key = f"{company_name}|{keywords}" if keywords else company_name
        if cache_key in self._website_cache:
            return self._website_cache[cache_key]

        logger.info(f"  🔍 Finding website for: {company_name}")

        # ========== STRATEGY 1: Google Search WITH Keywords (3 attempts) ==========
        if self.rapidapi_key and keywords:
            queries_with_keywords = [
                f'"{company_name}" {keywords} official website',
                f'{company_name} {keywords} website',
                f'{company_name} {keywords} home'
            ]

            for attempt, query in enumerate(queries_with_keywords, 1):
                logger.info(f"  → Strategy 1.{attempt}: Google + keywords")
                result = self._try_google_search(query)
                if result.get('url'):
                    logger.info(f"  ✅ SUCCESS (Strategy 1.{attempt}): {result['url']}")
                    self._website_cache[cache_key] = result
                    return result
                time.sleep(0.3)  # Small delay between attempts

        # ========== STRATEGY 2: Google Search WITHOUT Keywords (3 attempts) ==========
        if self.rapidapi_key:
            queries_without_keywords = [
                f'"{company_name}" official website',
                f'{company_name} company website',
                f'{company_name} homepage'
            ]

            for attempt, query in enumerate(queries_without_keywords, 1):
                logger.info(f"  → Strategy 2.{attempt}: Google search")
                result = self._try_google_search(query)
                if result.get('url'):
                    logger.info(f"  ✅ SUCCESS (Strategy 2.{attempt}): {result['url']}")
                    self._website_cache[cache_key] = result
                    return result
                time.sleep(0.3)

        # ========== STRATEGY 3: Domain Guessing with Expanded TLDs ==========
        logger.info(f"  → Strategy 3: Domain guessing")
        guessed_domain = self._guess_domain(company_name, keywords)
        if guessed_domain:
            result = {'url': f"https://{guessed_domain}", 'description': 'Domain guessed from company name'}
            logger.info(f"  ✅ SUCCESS (Strategy 3): {guessed_domain}")
            self._website_cache[cache_key] = result
            return result

        # ========== STRATEGY 4: Wildcard Google Search (last resort) ==========
        if self.rapidapi_key:
            wildcard_queries = [
                f'{company_name} Canada',
                f'{company_name} company',
                company_name  # Just the name
            ]

            for attempt, query in enumerate(wildcard_queries, 1):
                logger.info(f"  → Strategy 4.{attempt}: Wildcard search")
                result = self._try_google_search(query)
                if result.get('url'):
                    logger.info(f"  ✅ SUCCESS (Strategy 4.{attempt}): {result['url']}")
                    self._website_cache[cache_key] = result
                    return result
                time.sleep(0.3)

        # ========== ALL STRATEGIES FAILED ==========
        logger.warning(f"  ⚠️  FAILED: No website found for {company_name} after all strategies")
        empty_result = {'url': '', 'description': ''}
        self._website_cache[cache_key] = empty_result
        return empty_result

    def _try_google_search(self, query: str) -> Dict:
        """Try Google Search API with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                wait_time = 0
                with self.rapidapi_lock:
                    elapsed = time.time() - self.last_rapidapi_call
                    if elapsed < self.rapidapi_delay:
                        wait_time = self.rapidapi_delay - elapsed
                    else:
                        self.last_rapidapi_call = time.time()

                if wait_time > 0:
                    time.sleep(wait_time)
                    with self.rapidapi_lock:
                        self.last_rapidapi_call = time.time()

                headers = {
                    'x-rapidapi-host': 'google-search116.p.rapidapi.com',
                    'x-rapidapi-key': self.rapidapi_key
                }
                params = {'query': query}

                response = requests.get(
                    self.RAPIDAPI_GOOGLE_SEARCH_URL,
                    headers=headers,
                    params=params,
                    timeout=10
                )

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                    return {'url': '', 'description': ''}

                if response.status_code != 200:
                    return {'url': '', 'description': ''}

                data = response.json()
                organic_results = data.get('results', [])

                if not organic_results:
                    return {'url': '', 'description': ''}

                # Filter out social media and job boards
                for result in organic_results:
                    url = result.get('url', '')
                    if any(skip in url.lower() for skip in ['linkedin.com', 'facebook.com', 'twitter.com', 'glassdoor.com', 'indeed.com']):
                        continue
                    return {
                        'url': url,
                        'description': result.get('description', '')
                    }

                return {'url': '', 'description': ''}

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return {'url': '', 'description': ''}
        return {'url': '', 'description': ''}

    def _guess_domain(self, company_name: str, keywords: str = "") -> str:
        """
        Guess company domain from name using smart heuristics.

        Returns: domain string (e.g., "acme.com") or empty string
        """
        if not company_name or company_name.lower() == 'confidential':
            return ""

        # Clean company name
        clean_name = company_name.lower()

        # Remove common legal suffixes
        legal_suffixes = [
            ' inc.', ' inc', ' llc', ' ltd.', ' ltd', ' corp.', ' corp',
            ' co.', ' co', ' l.p.', ' lp', ' llp', ' plc', ' limited',
            ' corporation', ' company', ' incorporated'
        ]
        for suffix in legal_suffixes:
            clean_name = clean_name.replace(suffix, '')

        # Remove special characters and extra spaces
        clean_name = re.sub(r'[^\w\s]', '', clean_name)
        clean_name = clean_name.strip().replace(' ', '')

        if len(clean_name) < 3:
            return ""

        # Determine TLD based on keywords/context (EXPANDED for better coverage)
        tld_options = []

        # Canadian keywords → prioritize .ca
        if 'canada' in keywords.lower() or 'toronto' in keywords.lower() or 'vancouver' in keywords.lower():
            tld_options = ['.ca', '.com', '.io', '.co', '.net']
        # Healthcare/Education → prioritize .org
        elif any(kw in keywords.lower() for kw in ['hospital', 'health', 'university', 'college', 'school']):
            tld_options = ['.org', '.com', '.ca', '.net']
        # Tech companies → try .io
        elif any(kw in keywords.lower() for kw in ['technology', 'software', 'tech', 'saas', 'ai', 'data']):
            tld_options = ['.com', '.io', '.ai', '.co', '.ca', '.net']
        # Default → comprehensive list
        else:
            tld_options = ['.com', '.ca', '.io', '.co', '.net', '.org']

        # Try each TLD and validate with HTTP HEAD request
        for tld in tld_options:
            domain = f"{clean_name}{tld}"
            if self._validate_domain(domain):
                logger.debug(f"    ✓ Domain found: {domain}")
                return domain

        return ""

    def _validate_domain(self, domain: str) -> bool:
        """
        Validate if domain exists by checking HTTP response.
        Returns True if domain responds (200, 301, 302, etc.)
        """
        try:
            url = f"https://{domain}"
            response = requests.head(url, timeout=3, allow_redirects=True)
            # Accept any response that's not a connection error
            if response.status_code < 500:
                logger.debug(f"    ✓ Domain validated: {domain} (HTTP {response.status_code})")
                return True
        except:
            pass

        # Try HTTP if HTTPS fails
        try:
            url = f"http://{domain}"
            response = requests.head(url, timeout=3, allow_redirects=True)
            if response.status_code < 500:
                logger.debug(f"    ✓ Domain validated: {domain} (HTTP {response.status_code})")
                return True
        except:
            pass

        return False

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""


    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """Extract name from email (firstname.lastname@ → "Firstname Lastname")"""
        if not email or '@' not in email:
            return ('', True, 0.0)

        local_part = email.split('@')[0].lower()

        # Skip generic emails
        generic_patterns = ['info', 'contact', 'hello', 'support', 'sales', 'admin',
                          'office', 'help', 'team', 'hr', 'jobs', 'careers', 'inquiries',
                          'general', 'reception', 'booking', 'mail', 'service']
        if any(pattern in local_part for pattern in generic_patterns):
            return ('', True, 0.0)

        # Pattern 1: firstname.lastname@
        if '.' in local_part and not local_part.startswith('.') and not local_part.endswith('.'):
            parts = local_part.split('.')
            valid_parts = [p for p in parts if p.isalpha() and 2 <= len(p) <= 20]
            if len(valid_parts) == 2:
                return (f"{valid_parts[0].capitalize()} {valid_parts[1].capitalize()}", False, 0.95)
            elif len(valid_parts) > 2:
                return (f"{valid_parts[0].capitalize()} {valid_parts[-1].capitalize()}", False, 0.9)

        # Pattern 2: firstname_lastname@ or firstname-lastname@
        name_parts = re.split(r'[._\-0-9]+', local_part)
        name_parts = [p for p in name_parts if p.isalpha() and 2 <= len(p) <= 20]
        if len(name_parts) >= 2:
            first, last = name_parts[0].capitalize(), name_parts[-1].capitalize()
            conf = 0.9 if len(first) >= 3 and len(last) >= 3 else 0.7
            return (f"{first} {last}", False, conf)
        elif len(name_parts) == 1 and len(name_parts[0]) >= 3:
            return (name_parts[0].capitalize(), False, 0.6)

        return ('', False, 0.2)

    def _names_match(self, name1: str, name2: str, threshold: float = 0.6) -> bool:
        """
        Validate if two names match (FLEXIBLE fuzzy matching inspired by Crunchbase).

        v2.2 SIMPLIFIED LOGIC (fixes single-name email bug):
        - Uses simple containment check first (handles "Neil" vs "Neil T.", "Lily Feng" vs "Lily Feng, MBA")
        - Falls back to SequenceMatcher for fuzzy similarity
        - No complex first/last parsing → avoids rejecting valid single-name matches

        Examples:
        - "Fatima Kamalia" vs "Fatima Kamalia" → True (exact)
        - "Lily Feng" vs "Lily Feng, MBA, CPA, CGA" → True (containment)
        - "Neil" vs "Neil Thangavelu" → True (containment)
        - "J Chu" vs "Justin Chu" → True (containment after cleaning)
        - "Fatima Kamalia" vs "Greg Chow" → False (different)
        """
        if not name1 or not name2:
            return False

        # Clean names: remove credentials/suffixes and normalize
        def clean_name(name):
            # Remove credentials like MBA, CPA, PhD, etc.
            cleaned = re.sub(r',?\s+(MBA|CPA|CGA|CFO|CEO|PhD|MD|JD|Esq|Jr|Sr|II|III|IV)\b.*$', '', name, flags=re.IGNORECASE)
            # Remove extra whitespace and punctuation
            cleaned = re.sub(r'[.,\-_]+', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.lower().strip()

        n1 = clean_name(name1)
        n2 = clean_name(name2)

        # Strategy 1: Exact match after cleaning
        if n1 == n2:
            return True

        # Strategy 2: Containment check (handles most variations)
        # "neil" in "neil thangavelu" → True
        # "lily feng" in "lily feng mba cpa" → True
        if n1 in n2 or n2 in n1:
            return True

        # Strategy 3: Fuzzy similarity with SequenceMatcher (Crunchbase-style)
        # Handles typos, slight variations
        from difflib import SequenceMatcher
        matcher = SequenceMatcher(None, n1, n2)
        similarity = matcher.ratio()

        return similarity >= threshold

    def is_decision_maker(self, job_title: str) -> bool:
        """Validate if job title is decision-maker"""
        if not job_title or len(job_title) < 3:
            return False
        jt_lower = job_title.lower()

        # Must have decision-maker keyword
        dm_keywords = ['founder', 'co-founder', 'ceo', 'chief', 'owner', 'president',
                       'managing partner', 'managing director', 'vice president', 'vp ',
                       'cfo', 'cto', 'coo', 'cmo', 'executive', 'c-suite', 'c-level',
                       'principal', 'partner', 'executive director']
        has_dm = any(kw in jt_lower for kw in dm_keywords)

        # Must NOT have exclude keyword
        exclude_keywords = ['assistant', 'associate', 'junior', 'intern', 'coordinator',
                           'analyst', 'specialist', 'representative', 'agent', 'clerk',
                           'trainee', 'apprentice', 'student']
        has_exclude = any(kw in jt_lower for kw in exclude_keywords)

        return has_dm and not has_exclude

    def extract_company_keywords(self, job_data: Dict) -> str:
        """
        Extract contextual keywords from job posting to improve company search accuracy.
        Returns: Space-separated keywords (location + industry terms)
        """
        keywords = []

        # Extract location (city/state)
        location = job_data.get('location', '')
        if location:
            # Clean location string
            loc_parts = location.replace(',', ' ').split()
            # Take first 2-3 parts (e.g., "Toronto Ontario" or "San Francisco CA")
            keywords.extend(loc_parts[:3])

        # Extract industry/job category keywords from job title
        job_title = job_data.get('job_title', '').lower()

        # Industry-specific keywords mapping
        industry_keywords = {
            'finance': ['cfo', 'controller', 'finance', 'accounting', 'treasury', 'financial'],
            'technology': ['engineer', 'developer', 'software', 'blockchain', 'ai', 'machine learning', 'data', 'cloud'],
            'healthcare': ['medical', 'health', 'clinical', 'hospital', 'doctor', 'nurse', 'pharmaceutical'],
            'retail': ['retail', 'store', 'merchandising', 'ecommerce', 'consumer'],
            'construction': ['construction', 'building', 'contractor', 'real estate', 'property'],
            'manufacturing': ['manufacturing', 'production', 'industrial', 'supply chain', 'operations'],
            'legal': ['legal', 'attorney', 'counsel', 'law', 'compliance'],
            'marketing': ['marketing', 'brand', 'digital', 'content', 'growth', 'seo'],
            'sales': ['sales', 'business development', 'account', 'revenue'],
        }

        # Find matching industry keywords
        for industry, terms in industry_keywords.items():
            if any(term in job_title for term in terms):
                keywords.append(industry)
                break

        # Limit to 4-5 keywords max for focused search
        return ' '.join(keywords[:5])

    def generate_message(self, decision_maker: str, company: str, role: str, dm_desc: str, company_desc: str) -> str:
        """Generate SSM-style personalized connector email using Azure OpenAI."""
        if not self.openai_client:
            return ""

        prompt = f"""
Write a connector-style cold email to {decision_maker} at {company}.

Context:
- They're hiring for: {role}
- Decision Maker LinkedIn snippet: "{dm_desc}"
- Company website snippet: "{company_desc}"

CRITICAL FRAMEWORK - PRESSURE-BASED APPROACH (NOT ROLE-BASED):
❌ DON'T say: "Saw you're hiring for {role}..." (stalkerish, fragile)
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
10. NO SIGNATURE - End message abruptly after last observation (no "wondering if", "worth a chat", "sent from my iPhone")

MANDATORY PAIN-MATCHING RULES:
Rule 1: Pain Point MUST Match Job Title
- The pain/function MUST be directly related to the job title being hired for
- Example: Hiring "SDR" → talk about "outbound" or "pipeline" ✅
- Example: Hiring "SDR" → talk about "engineering velocity" ❌ (wrong function!)

Rule 2: Specificity Test - MUST Pass All Three Checks
Before writing, verify:
a) Can I quantify the pain? (Include specific metrics, numbers, or measurable outcomes)
b) Is this pain specific to their industry/job function? (Not generic to all companies)
c) Would 10 different companies have 10 different interpretations of this pain?
   → If YES = TOO VAGUE, rewrite with more specificity
   → If NO = GOOD, pain is specific enough

CHOOSE ONE OF THESE 5 PATTERNS - ROTATE THROUGH ALL VERSIONS (don't default to one):

VERSION 1: Pain Signal + Specificity
Format: Noticed [company] recently [growth_signal from context]. Teams at this stage usually hit capacity issues in [function from role], especially around [specific_pain_point]
NO LINE BREAKS - write as continuous paragraph

VERSION 2: Peer Benchmark (Connector Angle)
Format: Working with a few [industry] companies around your size. They're all running into the same [function] bottleneck as they scale past [growth_stage from context]
NO LINE BREAKS - write as continuous paragraph

VERSION 3: Forward-Looking + Consultative
Format: [Company] is growing fast ([specific_signal from context]). At this trajectory, most [industry] teams start feeling the squeeze in [function] within 3-6 months
NO LINE BREAKS - write as continuous paragraph

VERSION 4: Pattern Recognition (Best for Multiple Intros)
Format: I've introduced 3 [industry] companies to specialists this month. All had the same issue: [function] became a bottleneck after [trigger_event from context]
NO LINE BREAKS - write as continuous paragraph

VERSION 5: Direct + Low Pressure
Format: Quick question—is [function] keeping up with growth at [company], or starting to show cracks
NO LINE BREAKS - write as continuous paragraph

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
- Controller/CFO → "financial reporting speed", "cash flow visibility", "audit readiness", "forecasting accuracy"
- Accountant → "close cycle time", "reconciliation efficiency", "compliance tracking", "month-end bottlenecks"

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
            logger.error(f"❌ Message generation failed: {e}")
            return ""

    def process_single_company(self, job: Dict) -> List[Dict]:
        """
        v2.3 EMAIL-FIRST WORKFLOW (Crunchbase Pattern + Filtering):
        0. Filter out recruitment firms and confidential postings
        1. Find website (3-attempt validation with expanded TLDs)
        2. Find ALL emails at company (up to 20)
        3. Extract names from emails (parallel processing)
        4. Search LinkedIn for each name (3-attempt)
        5. Validate if decision-maker
        6. Return 2-3+ DMs per company (as many as found)
        """
        company = job['company_name']

        # Step 0: Filter out recruitment firms and confidential postings
        recruitment_keywords = ['recruiting', 'recruitment', 'staffing', 'headhunter', 'talent acquisition', 'search firm']
        if company.lower() == 'confidential' or any(kw in company.lower() for kw in recruitment_keywords):
            logger.info(f"\n{'='*70}")
            logger.info(f"🏢 Company: {company}")
            logger.info(f"  ⊘ Skipping recruitment firm/confidential posting")
            return []

        # Step 1: Extract contextual keywords from job posting
        keywords = self.extract_company_keywords(job)

        # Step 2: Find company website (with location + industry context)
        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Company: {company}")
        if keywords:
            logger.info(f"  → Keywords: {keywords}")

        website_data = self.find_company_website(company, keywords)
        website = website_data.get('url', '')
        company_desc = website_data.get('description', '')
        domain = self.extract_domain(website) if website else ""

        # Step 3: Detect company type (v2.1 - uses website desc for better accuracy)
        company_type = self.detect_company_type(
            company,
            job.get('industry', ''),
            job.get('job_description', ''),
            company_desc  # NEW: website description for better detection
        )

        if not domain:
            logger.info(f"  ⊘ No website domain - skipping")
            return []

        logger.info(f"  ✓ Website: {domain}")

        # Step 2: Find ALL emails at company (Company API - up to 20)
        if not self.email_finder:
            logger.info(f"  ⊘ Email finder not configured - skipping")
            return []

        logger.info(f"  📧 Finding emails at {domain}...")
        email_result = self.email_finder.find_company_emails(domain, company)
        emails = email_result.get('emails', [])
        logger.info(f"  ✓ Found {len(emails)} emails")

        if not emails:
            logger.info(f"  ⊘ No emails found - skipping")
            return []

        # Step 3-5: Process each email in PARALLEL (5 workers)
        decision_makers = []
        seen_names_lock = Lock()
        seen_names = set()

        def process_single_email(email: str) -> Optional[Dict]:
            """
            v2.3 EMAIL-FIRST WORKFLOW WITH FALLBACK (Crunchbase-inspired):
            1. Extract name from email
            2. Search LinkedIn BY NAME (primary strategy)
            3. If fails → Search BY COMPANY (fallback strategy)
            4. Validate name match (CRITICAL - prevents wrong matches)
            5. Validate decision-maker title
            """
            logger.info(f"  🔍 Processing: {email}")

            # Step 1: Extract name from email
            extracted_name, is_generic, confidence = self.extract_contact_from_email(email)

            if is_generic:
                logger.info(f"    → Generic email - skipping")
                return None

            if not extracted_name or confidence < 0.5:
                logger.info(f"    → Could not extract name (conf: {confidence:.0%}) - skipping")
                return None

            logger.info(f"    → Extracted: {extracted_name} (conf: {confidence:.0%})")

            # Step 2: PRIMARY - Search LinkedIn by PERSON NAME + COMPANY
            logger.info(f"    → Searching LinkedIn by NAME: {extracted_name}...")
            dm = self.find_decision_maker_by_name(extracted_name, company)

            # Step 3: FALLBACK - If name search fails, try company-wide search
            if not dm.get('full_name'):
                logger.info(f"    → Name search failed, trying company-wide search...")
                dm = self.find_decision_maker(company)

                if not dm.get('full_name'):
                    logger.info(f"    ✗ LinkedIn not found (both strategies failed)")
                    return None
                else:
                    logger.info(f"    → Found via company search: {dm.get('full_name')}")

            full_name = dm.get('full_name')
            job_title = dm.get('title', '')

            # Step 4: Validate name match (CRITICAL - prevents fatima→Greg Chow bugs)
            if not self._names_match(extracted_name, full_name):
                logger.info(f"    ✗ Name mismatch: {extracted_name} ≠ {full_name}")
                return None

            logger.info(f"    ✓ Name match: {extracted_name} = {full_name}")

            # Step 5: Thread-safe duplicate check
            with seen_names_lock:
                if full_name in seen_names:
                    logger.info(f"    ✗ Duplicate name - skipping: {full_name}")
                    return None
                seen_names.add(full_name)

            # Step 6: Validate decision-maker title
            if not self.is_decision_maker(job_title):
                logger.info(f"    ✗ Not a decision-maker: {job_title}")
                return None

            # SUCCESS - Build decision-maker record
            logger.info(f"    ★ Found DM: {full_name} ({job_title})")

            # Generate message
            msg = ""
            if self.openai_client:
                msg = self.generate_message(
                    full_name,
                    company,
                    job['job_title'],
                    dm.get('description', ''),
                    company_desc
                )

            return {
                'company_name': company,
                'company_type': company_type,
                'company_website': website,
                'company_domain': domain,
                'company_description': company_desc,
                'job_title': job.get('job_title', ''),
                'job_url': job.get('job_url', ''),
                'location': job.get('location', ''),
                'posted_date': job.get('posted_date', ''),
                'dm_name': full_name,
                'dm_first': full_name.split()[0] if full_name else '',
                'dm_last': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                'dm_title': job_title,
                'dm_linkedin': dm.get('linkedin_url', ''),
                'dm_email': email,
                'email_status': 'found',
                'dm_source': dm.get('source', ''),
                'dm_description': dm.get('description', ''),
                'message': msg
            }

        # PARALLEL processing: 5 workers (20 emails / 5 = 4 batches)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(process_single_email, email): email
                for email in emails[:20]  # Process up to 20 emails
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        decision_makers.append(result)
                except Exception as e:
                    email = futures[future]
                    logger.error(f"  ❌ Error processing {email}: {str(e)}")

        logger.info(f"  ✓ Found {len(decision_makers)} decision-makers for {company}")
        return decision_makers


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
        """Export to Google Sheets."""
        logger.info("📊 Exporting to Google Sheets...")

        creds = self.get_credentials()
        if not creds:
            return ""

        try:
            service = build('sheets', 'v4', credentials=creds)
            drive_service = build('drive', 'v3', credentials=creds)

            spreadsheet = {'properties': {'title': title}}
            spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId,spreadsheetUrl,sheets.properties.sheetId').execute()
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
            sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']

            headers = [
                "Company Name", "Company Type", "Company Website", "Job Title", "Job URL", "Location",
                "DM Name", "DM Title", "DM First", "DM Last", "DM LinkedIn",
                "DM Email", "Email Status", "DM Source", "Message", "Scraped Date"
            ]

            values = [headers]
            for row in rows:
                values.append([
                    row.get('company_name', ''),
                    row.get('company_type', 'Other'),
                    row.get('company_website', ''),
                    row.get('job_title', ''),
                    row.get('job_url', ''),
                    row.get('location', ''),
                    row.get('dm_name', ''),
                    row.get('dm_title', ''),
                    row.get('dm_first', ''),
                    row.get('dm_last', ''),
                    row.get('dm_linkedin', ''),
                    row.get('dm_email', ''),
                    row.get('email_status', ''),
                    row.get('dm_source', ''),
                    row.get('message', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ])

            body = {'values': values}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="A1", valueInputOption="RAW", body=body
            ).execute()

            # Format header
            requests_format = [{
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}}},
                    "fields": "userEnteredFormat(textFormat,backgroundColor)"
                }
            }, {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount"
                }
            }]
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': requests_format}).execute()

            permission = {'type': 'anyone', 'role': 'reader'}
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=permission
            ).execute()

            return spreadsheet_url

        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return ""

    def execute(self, query: str, location: str = "", country: str = "Canada", max_jobs: int = 10, days_posted: int = 60):
        start_time = time.time()

        print("\n" + "="*70)
        print("🚀 GLASSDOOR JOB SCRAPER & OUTREACH SYSTEM (STREAMING MODE)")
        print(f"Query: {query} | Location: {location} | Country: {country}")
        print("="*70 + "\n")

        # 1. Start Scraper
        run_id = self.start_scraping_job(query, location, country, max_jobs, days_posted)
        if not run_id:
            return

        processed_jobs = []
        seen_companies = set()

        # 2. Stream & Process
        print(f"🔄 Streaming & Processing jobs in parallel (workers={self.MAX_WORKERS})...")

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = []

            # Producer: Stream jobs from Apify
            for job in self.stream_jobs(run_id):
                company = job['company_name'].lower().strip()

                # Skip invalid company names
                if not company or len(company) < 2 or company == 'company' or company == 'confidential':
                    continue

                # Deduplicate on the fly
                if company in seen_companies:
                    continue
                seen_companies.add(company)

                # Consumer: Submit to thread pool
                future = executor.submit(self.process_single_company, job)
                futures.append(future)
                print(f"   → Found: {job['company_name']} (Processing...)")

            # Wait for all to finish
            print("\n⏳ Waiting for processing to complete...")
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    results = future.result()  # Now returns List[Dict]
                    if results:  # Multiple DMs per company
                        processed_jobs.extend(results)  # Extend, not append
                        # Visual progress indicator - show count of DMs found
                        dm_count = len(results)
                        print(f"   ✓ [{completed}/{len(futures)}] {results[0]['company_name']} ({dm_count} DMs)")
                    else:
                        print(f"   ✓ [{completed}/{len(futures)}] Company (0 DMs)")
                except Exception as e:
                    logger.error(f"❌ Error processing job: {e}")

        # 3. Filter & Export
        jobs_with_emails = [job for job in processed_jobs if job.get('dm_email') and job.get('email_status') == 'found']

        total_time = time.time() - start_time
        avg_time_per_company = total_time / len(processed_jobs) if processed_jobs else 0
        success_rate = len(jobs_with_emails) / len(processed_jobs) * 100 if processed_jobs else 0

        print("\n" + "-"*70)
        print(f"📊 PERFORMANCE METRICS:")
        print(f"   Companies Processed: {len(processed_jobs)}")
        print(f"   Emails Found: {len(jobs_with_emails)} ({success_rate:.1f}% success rate)")
        print(f"   Total Time: {total_time:.1f}s")
        print(f"   Avg Time/Company: {avg_time_per_company:.1f}s")
        print(f"   Cache Hits - Websites: {len(self._website_cache)} | Decision Makers: {len(self._dm_cache)}")
        print("-"*70 + "\n")

        logger.info(f"METRICS: companies={len(processed_jobs)} emails={len(jobs_with_emails)} success_rate={success_rate:.1f}% total_time={total_time:.1f}s avg_time={avg_time_per_company:.1f}s")

        # Save CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = f".tmp/glassdoor_jobs_{timestamp}.csv"

        if jobs_with_emails:
            pd.DataFrame(jobs_with_emails).to_csv(csv_path, index=False)
            print(f"📁 CSV Backup: {csv_path}")

            # Export to Sheets
            sheet_title = f"Glassdoor Jobs - {query} - {datetime.now().strftime('%Y-%m-%d')}"
            url = self.export_to_google_sheets(jobs_with_emails, sheet_title)
            if url:
                print(f"🔗 Google Sheet: {url}")
        else:
            print("⚠️ No emails found, skipping export.")

        print("\n✅ DONE!")
        notify_success()

def main():
    """Main function with CLI arguments."""
    import argparse
    parser = argparse.ArgumentParser(description='Glassdoor Job Scraper & Outreach System')

    parser.add_argument('--query', type=str, default="Controller", help='Job search query')
    parser.add_argument('--location', type=str, default="Toronto", help='Job location')
    parser.add_argument('--country', type=str, default="Canada", help='Country to scrape')
    parser.add_argument('--limit', type=int, default=10, help='Max jobs to scrape')
    parser.add_argument('--days', type=int, default=60, help='Days posted')

    args = parser.parse_args()

    try:
        scraper = GlassdoorJobScraper()
        scraper.execute(
            query=args.query,
            location=args.location,
            country=args.country,
            max_jobs=args.limit,
            days_posted=args.days
        )
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)

if __name__ == "__main__":
    main()
