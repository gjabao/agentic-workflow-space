#!/usr/bin/env python3
"""
Indeed Job Scraper & Decision Maker Outreach System
Scrapes jobs from Indeed, finds decision makers (Founder/CEO), gets emails, and generates outreach messages.
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
        logging.FileHandler('.tmp/indeed_scraper.log'),
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


class RapidAPIGoogleSearch:
    """
    RapidAPI Google Search - Thread-safe wrapper with rate limiting
    Copied from LinkedIn scraper v2.0 (lines 137-413)
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2  # 5 req/sec per key
        logger.info(f"✓ RapidAPI Google Search initialized ({len(api_keys)} keys)")

    def _get_current_key(self) -> str:
        """Rotate between API keys for higher throughput"""
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
                    logger.debug(f"  ⚠️ Google Search error (attempt {attempt+1}), waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                logger.debug(f"  ⚠️ Google Search error after 3 attempts: {e}")
                return None

        return None

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

    def search_website(self, company_name: str, keywords: str = "") -> Dict:
        """
        Search for company website with 3-attempt fallback strategy
        """
        search_attempts = [
            f'"{company_name}" {keywords} official website' if keywords else f'"{company_name}" official website',
            f'"{company_name}" company website',
            f'{company_name} site'
        ]

        for attempt_num, query in enumerate(search_attempts, 1):
            logger.info(f"  🔍 Website search attempt {attempt_num}/3: {query[:60]}...")

            data = self._rate_limited_search(query, num_results=10)

            if data and data.get('results'):
                # Two-pass: prefer homepage over subpages
                homepage_result = None
                subpage_result = None

                for result in data['results']:
                    url = result.get('url', '')
                    title = result.get('title', '').lower()

                    # Skip unwanted domains
                    skip_patterns = [
                        'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
                        'indeed.com', 'glassdoor.com', 'ziprecruiter.com',
                        'wikipedia.org', 'zoominfo.com', 'crunchbase.com',
                        '.gov', '.edu', '.pdf'
                    ]
                    if any(skip in url.lower() for skip in skip_patterns):
                        continue

                    # Company name match
                    company_lower = company_name.lower()
                    is_match = False

                    if attempt_num <= 2:
                        # Strict match
                        is_match = company_lower in title or company_lower in url.lower()
                    else:
                        # Relaxed match
                        company_words = company_lower.split()[:2]
                        is_match = any(word in title or word in url.lower() for word in company_words if len(word) > 3)

                    if not is_match:
                        continue

                    # Detect subpage
                    subpage_patterns = ['/careers', '/jobs', '/about', '/team', '/contact']
                    is_subpage = any(pattern in url.lower() for pattern in subpage_patterns)

                    website_result = {
                        'url': url,
                        'description': result.get('snippet', '')
                    }

                    if is_subpage:
                        if not subpage_result:
                            subpage_result = website_result
                            logger.info(f"    → Found subpage (backup): {url[:60]}")
                    else:
                        homepage_result = website_result
                        logger.info(f"    ✓ Found homepage: {url[:60]}")
                        return homepage_result

                # Return homepage if found, otherwise use subpage as fallback
                if homepage_result:
                    return homepage_result
                elif subpage_result and attempt_num == len(search_attempts):
                    logger.info(f"    ⚠️ Using subpage as fallback")
                    return subpage_result

        logger.info(f"  ✗ Website not found after 3 attempts")
        return {'url': '', 'description': ''}

    def search_linkedin_by_name(self, person_name: str, company_name: str) -> Dict:
        """
        Search LinkedIn for a specific person at a company
        2-query relaxed strategy for single initials
        """
        # 2-query strategy: strict first, then relaxed
        name_parts = person_name.split()
        if len(name_parts) == 2 and len(name_parts[0]) == 1:
            # Single initial + last name (I Leikin, M Welling)
            queries = [
                (f'site:linkedin.com/in/ "{person_name}" "{company_name}"', 5),  # Strict
                (f'site:linkedin.com/in/ {name_parts[1]} {company_name}', 7)     # Relaxed (last name only)
            ]
        else:
            # Full name
            queries = [(f'site:linkedin.com/in/ "{person_name}" "{company_name}"', 5)]

        logger.info(f"  → Searching LinkedIn for: {person_name} at {company_name}")

        for query_num, (query, num_results) in enumerate(queries, 1):
            if query_num > 1:
                logger.info(f"  → Attempt {query_num}: Relaxed search (last name only)")

            data = self._rate_limited_search(query, num_results=num_results)

            if data and data.get('results'):
                for result in data['results']:
                    url = result.get('url', '')
                    title = result.get('title', '')
                    snippet = result.get('snippet', '')

                    if 'linkedin.com/in/' not in url:
                        continue

                    # Parse name/title from LinkedIn result
                    name_part = title.split('-')[0].strip() if '-' in title else title.strip()
                    dm_title = ""
                    if '-' in title and len(title.split('-')) > 1:
                        title_part = title.split('-')[1].strip()
                        if '|' in title_part:
                            title_part = title_part.split('|')[0].strip()
                        dm_title = title_part

                    name_parts_result = name_part.split()
                    if len(name_parts_result) >= 2:
                        first_name = name_parts_result[0]
                        last_name = ' '.join(name_parts_result[1:])
                    else:
                        first_name = name_part
                        last_name = ""

                    result_data = {
                        'full_name': name_part,
                        'first_name': first_name,
                        'last_name': last_name,
                        'title': dm_title,
                        'linkedin_url': url,
                        'description': snippet,
                        'source': f'LinkedIn Name Search (Query {query_num})'
                    }

                    logger.info(f"  ✓ Found: {name_part} - {dm_title}")
                    return result_data

        # All queries failed
        return {}


class IndeedJobScraper:
    # Actor IDs
    JOB_SCRAPER_ACTOR_ID = "misceres/indeed-scraper"  # Indeed Jobs Scraper

    # API Config
    ANYMAILFINDER_URL = "https://api.anymailfinder.com/v5.1/find-email/person"
    RAPIDAPI_GOOGLE_SEARCH_URL = "https://google-search116.p.rapidapi.com/"
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    # Performance Configuration
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "20"))  # Increased from 10 to 20
    APIFY_POLL_INTERVAL_START = 1  # Start at 1 second
    APIFY_POLL_INTERVAL_MAX = 5    # Cap at 5 seconds
    APIFY_MAX_WAIT = 600  # 10 minutes timeout

    def __init__(self):
        # 1. Apify
        self.apify_token = os.getenv("APIFY_API_KEY")
        if not self.apify_token:
            raise ValueError("APIFY_API_KEY not found")
        self.apify_client = ApifyClient(self.apify_token)

        # 2. RapidAPI for Google Search (v2.2 wrapper class)
        rapidapi_key = os.getenv("RAPIDAPI_KEY")
        rapidapi_key2 = os.getenv("RAPIDAPI_KEY_2")  # Optional second key for higher throughput
        api_keys = [k for k in [rapidapi_key, rapidapi_key2] if k]

        if api_keys:
            self.rapidapi_search = RapidAPIGoogleSearch(api_keys)
        else:
            self.rapidapi_search = None
            logger.warning("⚠️ RAPIDAPI_KEY not found. Decision maker search will be skipped.")

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

        # Caching for performance
        self._website_cache = {}  # Cache company websites
        self._dm_cache = {}       # Cache decision makers

        logger.info("✓ IndeedJobScraper initialized")

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
        # Examples:
        # "Senior Research Software Engineer - Security & Cryptography" → "Senior Research Software Engineer"
        # "Senior iOS Engineer, Music" → "Senior iOS Engineer"
        # "Product Manager (Remote)" → "Product Manager"
        # "Director of Finance Regina/Saskatoon" → "Director of Finance"

        for delimiter in [' - ', ' – ', ' — ', ',', ' (', ' /', ' |']:
            if delimiter in job_title:
                job_title = job_title.split(delimiter)[0].strip()
                break

        return job_title.strip()

    def detect_company_type(self, company_name: str, industry: str = "", description: str = "") -> str:
        """Detect company type/industry based on company name, industry field, and description."""
        # Only use company name + industry for detection (skip job description to avoid false positives)
        text = f"{company_name} {industry}".lower()

        # Technology & Software (CHECK FIRST - most common for dev jobs)
        if any(word in text for word in ['software', 'technology', 'tech ', 'saas', 'cloud', 'digital', 'it ', 'data', 'ai ', 'cyber', 'web3', 'blockchain', 'crypto']):
            return 'Technology & Software'

        # Financial Services
        if any(word in text for word in ['bank', 'financial', 'finance', 'capital', 'investment', 'asset management', 'insurance', 'credit', 'fintech', 'payment']):
            return 'Financial Services'

        # Healthcare & Medical (More specific keywords to avoid false positives)
        if any(word in text for word in ['hospital', 'healthcare provider', 'medical center', 'clinic', 'pharmaceutical', 'pharma', 'biotech', 'diagnostic']):
            return 'Healthcare & Medical'

        # Construction & Real Estate
        if any(word in text for word in ['construction', 'builder', 'contractor', 'real estate', 'property management', 'homebuilding', 'architecture']):
            return 'Construction & Real Estate'

        # Manufacturing & Industrial
        if any(word in text for word in ['manufacturing', 'industrial', 'fabrication', 'production', 'factory']):
            return 'Manufacturing & Industrial'

        # Retail & Consumer
        if any(word in text for word in ['retail', 'store', 'shopping', 'consumer', 'ecommerce', 'e-commerce']):
            return 'Retail & Consumer'

        # Professional Services
        if any(word in text for word in ['consulting', 'consulting', 'accounting', 'legal', 'law', 'recruitment', 'staffing', 'hr ']):
            return 'Professional Services'

        # Non-Profit & Government
        if any(word in text for word in ['nonprofit', 'non-profit', 'charity', 'foundation', 'government', 'municipal', 'city of', 'town of']):
            return 'Non-Profit & Government'

        # Education
        if any(word in text for word in ['school', 'university', 'college', 'education', 'academy', 'learning']):
            return 'Education'

        # Energy & Utilities
        if any(word in text for word in ['energy', 'power', 'utility', 'oil', 'gas', 'renewable', 'solar', 'hydro']):
            return 'Energy & Utilities'

        return 'Other'

    def start_scraping_job(self, query: str, location: str, country: str = "United States", max_jobs: int = 10, days_posted: int = 7) -> str:
        """Start the Apify scraper job and return the run ID."""
        logger.info(f"🔍 Starting scrape for {max_jobs} jobs: '{query}' in '{location}', {country}...")

        # Map country names to country codes for Indeed
        country_code_map = {
            "United States": "US", "United Kingdom": "GB", "Canada": "CA", "Australia": "AU",
            "Germany": "DE", "France": "FR", "India": "IN", "Singapore": "SG", "Netherlands": "NL",
            "Spain": "ES", "Italy": "IT", "Brazil": "BR", "Mexico": "MX", "Japan": "JP", "China": "CN"
        }
        country_code = country_code_map.get(country, "US")

        run_input = {
            "position": query,
            "country": country_code,
            "location": location if location else "",
            "maxItems": max_jobs,
            "parseCompanyDetails": True,
            "saveOnlyUniqueItems": True,
            "followApplyRedirects": False,
            "maxAge": days_posted  # Filter by days
        }
        
        try:
            # Start the actor asynchronously
            run = self.apify_client.actor(self.JOB_SCRAPER_ACTOR_ID).start(run_input=run_input)
            run_id = run["id"]
            logger.info(f"✓ Scraper started. Run ID: {run_id}")
            return run_id
        except Exception as e:
            logger.error(f"❌ Failed to start scraper: {e}")
            return ""

    def is_web3_job(self, title: str) -> bool:
        """Filter for Web3-specific job titles only."""
        # DISABLED: Return True for all jobs (no filtering)
        # This allows scraping of any job type (finance, tech, etc.)
        return True

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
                    company = item.get('company', '')
                    title = item.get('positionName', '')

                    if not company or not title:
                        continue

                    # Normalize
                    normalized_company = self.normalize_company_name(company)
                    normalized_title = self.normalize_job_title(title)

                    # Filter for Web3-specific jobs only
                    if not self.is_web3_job(normalized_title if normalized_title else title):
                        continue

                    posted_date_raw = item.get('postedAt', '')
                    job_age_days, pain_level = self.parse_job_age(posted_date_raw)

                    yield {
                        'company_name': normalized_company if normalized_company else company,
                        'job_title': normalized_title if normalized_title else title,
                        'job_url': item.get('url', ''),
                        'job_description': item.get('description', ''),
                        'posted_date': posted_date_raw,
                        'location': item.get('location', ''),
                        'job_age_days': job_age_days,
                        'pain_level': pain_level
                    }

                offset += len(items)
                poll_delay = self.APIFY_POLL_INTERVAL_START  # Reset delay when we get data

            if status in ["SUCCEEDED", "FAILED", "ABORTED"] and len(items) == 0:
                break

            # Exponential backoff polling
            time.sleep(poll_delay)
            poll_delay = min(poll_delay * 1.5, self.APIFY_POLL_INTERVAL_MAX)

    def find_company_website(self, company_name: str, keywords: str = "") -> Dict:
        """
        Find company website using RapidAPI wrapper with 3-attempt fallback strategy (v2.2).

        Args:
            company_name: Company name to search for
            keywords: Contextual keywords (location + industry) to improve search accuracy
        """
        # Check cache first (include keywords in cache key for unique searches)
        cache_key = f"{company_name}|{keywords}" if keywords else company_name
        if cache_key in self._website_cache:
            return self._website_cache[cache_key]

        if not self.rapidapi_search:
            return {'url': '', 'description': ''}

        # Use wrapper class method (handles rate limiting, retries, 3-attempt strategy)
        result = self.rapidapi_search.search_website(company_name, keywords)

        # Cache result
        self._website_cache[cache_key] = result
        return result
    
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
            # Allow single-letter first initials (q.xu@, b.smith@) but last name must be 2+ chars
            valid_parts = []
            for i, p in enumerate(parts):
                if p.isalpha() and ((i == 0 and 1 <= len(p) <= 20) or (i > 0 and 2 <= len(p) <= 20)):
                    valid_parts.append(p)

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
            single_part = name_parts[0]

            # Try camelCase detection (jagirim → J Agirim, mleander → M Leander)
            if len(single_part) >= 4:
                # Check if starts with lowercase followed by uppercase (jAgirim, mLeander)
                for i in range(1, len(single_part)):
                    if single_part[i].isupper():
                        # Found camelCase boundary
                        first_initial = single_part[0].upper()
                        rest = single_part[i:].capitalize()
                        return (f"{first_initial} {rest}", False, 0.85)

                # Check if pattern is [single-letter][rest] (jagirim → J Agirim)
                if len(single_part) >= 4:
                    first_initial = single_part[0].upper()
                    rest = single_part[1:].capitalize()
                    return (f"{first_initial} {rest}", False, 0.75)

            # Fallback: single name
            return (single_part.capitalize(), False, 0.6)

        return ('', False, 0.2)

    def is_decision_maker(self, job_title: str) -> bool:
        """Validate if job title is decision-maker (RELAXED FOR FINANCE ROLES)"""
        if not job_title or len(job_title) < 3:
            return False
        jt_lower = job_title.lower()

        # RELAXED: Accept decision-makers + senior finance roles + managers
        dm_keywords = [
            # C-Suite & Founders
            'founder', 'co-founder', 'ceo', 'chief', 'owner', 'president',
            'cfo', 'cto', 'coo', 'cmo', 'c-suite', 'c-level',
            # Vice Presidents & Directors
            'vice president', 'vp ', 'director', 'executive director', 'managing director',
            # Heads & Partners
            'head of', 'managing partner', 'partner', 'principal',
            # Executive roles
            'executive',
            # ADDED: Finance-specific senior roles
            'controller', 'senior manager', 'accounting manager', 'finance manager',
            'senior accountant', 'senior analyst', 'manager', 'supervisor', 'lead'
        ]
        has_dm = any(kw in jt_lower for kw in dm_keywords)

        # RELAXED: Only exclude entry-level roles
        exclude_keywords = ['assistant', 'junior', 'intern', 'coordinator',
                           'trainee', 'apprentice', 'student', 'clerk']
        has_exclude = any(kw in jt_lower for kw in exclude_keywords)

        return has_dm and not has_exclude

    def is_decision_maker_by_size(self, job_title: str, company_size: str = "medium") -> bool:
        """Size-aware decision maker validation."""
        if not job_title or len(job_title) < 3:
            return False
        jt_lower = job_title.lower()
        exclude_keywords = ['assistant', 'junior', 'intern', 'coordinator',
                           'trainee', 'apprentice', 'student', 'clerk']
        if any(kw in jt_lower for kw in exclude_keywords):
            return False

        if company_size == "small":
            dm_keywords = ['founder', 'co-founder', 'ceo', 'chief executive',
                          'owner', 'president', 'managing director']
        elif company_size == "medium":
            dm_keywords = ['founder', 'co-founder', 'ceo', 'chief executive',
                          'owner', 'president', 'managing director',
                          'hr manager', 'human resources manager',
                          'people lead', 'head of people', 'head of hr',
                          'head of human resources', 'people manager',
                          'talent manager', 'hr lead']
        else:  # large (150-300)
            dm_keywords = ['founder', 'co-founder', 'ceo', 'chief executive',
                          'owner', 'president', 'managing director',
                          'hr director', 'director of hr', 'director of human resources',
                          'head of hr', 'head of people', 'head of human resources',
                          'vp of people', 'vp people', 'vp hr', 'vp human resources',
                          'chief people officer', 'cpo']
        return any(kw in jt_lower for kw in dm_keywords)

    def parse_job_age(self, posted_date_str: str) -> Tuple[int, str]:
        """Parse job posting date and calculate age. Returns (age_days, pain_level)."""
        if not posted_date_str:
            return (-1, "unknown")
        posted_str = posted_date_str.strip().lower()
        age_days = -1
        relative_match = re.match(r'(\d+)\s*(day|week|month|hour|minute)s?\s*ago', posted_str)
        if relative_match:
            num = int(relative_match.group(1))
            unit = relative_match.group(2)
            if unit == 'day': age_days = num
            elif unit == 'week': age_days = num * 7
            elif unit == 'month': age_days = num * 30
            elif unit in ('hour', 'minute'): age_days = 0
        else:
            for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    posted_date = datetime.strptime(posted_date_str.strip(), fmt)
                    age_days = (datetime.now() - posted_date).days
                    break
                except ValueError:
                    continue
        if age_days < 0: return (age_days, "unknown")
        elif age_days >= 30: return (age_days, "high")
        elif age_days >= 14: return (age_days, "medium")
        else: return (age_days, "low")

    def estimate_company_size(self, company_name: str) -> Tuple[str, int]:
        """Estimate company size from LinkedIn company page via Google Search."""
        if not self.rapidapi_search:
            return ("unknown", -1)
        max_size = getattr(self, '_max_company_size', 300)
        query = f'"{company_name}" site:linkedin.com/company/ employees'
        data = self.rapidapi_search._rate_limited_search(query, num_results=3)
        if not data or not data.get('results'):
            return ("unknown", -1)
        def _classify(count):
            if count > max_size: return ("skip", count)
            elif count > 150: return ("large", count)
            elif count >= 50: return ("medium", count)
            else: return ("small", count)
        for result in data['results']:
            combined = f"{result.get('title', '')} {result.get('snippet', '')}"
            range_match = re.search(r'(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)\s*employees?', combined, re.IGNORECASE)
            if range_match:
                low = int(range_match.group(1).replace(',', ''))
                high = int(range_match.group(2).replace(',', ''))
                return _classify((low + high) // 2)
            single_match = re.search(r'(\d[\d,]*)\+?\s*employees?', combined, re.IGNORECASE)
            if single_match:
                return _classify(int(single_match.group(1).replace(',', '')))
        return ("unknown", -1)

    def has_internal_recruiter(self, company_name: str) -> Tuple[bool, str]:
        """Check if company has internal recruiter/TA via Google Search."""
        if not self.rapidapi_search:
            return (False, "")
        recruiter_titles = ["recruiter", "talent acquisition", "people operations", "head of talent", "people & culture", "recruiting manager", "talent partner"]
        titles_query = ' OR '.join(f'"{t}"' for t in recruiter_titles[:4])
        query = f'site:linkedin.com/in/ ({titles_query}) "{company_name}"'
        data = self.rapidapi_search._rate_limited_search(query, num_results=3)
        if not data or not data.get('results'):
            return (False, "")
        for result in data['results']:
            url = result.get('url', '')
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            combined = f"{title} {snippet}".lower()
            if 'linkedin.com/in/' not in url:
                continue
            if any(kw in combined for kw in recruiter_titles):
                if company_name.lower() in combined:
                    evidence = title.split(' - ')[0].strip() if ' - ' in title else title[:50]
                    return (True, evidence)
        return (False, "")

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
Format: Noticed [company] recently [growth_signal from context]. Teams at this stage usually hit capacity issues in [function from role], especially around [specific_pain_point]
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
            logger.error(f"❌ Message generation failed: {e}")
            return ""

    def process_single_company(self, job: Dict) -> List[Dict]:
        """
        v2.0 EMAIL-FIRST WORKFLOW (Crunchbase Pattern):
        1. Find website (3-attempt validation)
        2. Find ALL emails at company (up to 20)
        3. Extract names from emails (parallel processing)
        4. Search LinkedIn for each name (3-attempt)
        5. Validate if decision-maker
        6. Return 2-3+ DMs per company (as many as found)
        """
        company = job['company_name']

        # Signal ③: Company Size Check (skip >max_size employees)
        if not getattr(self, '_skip_size_check', False):
            size_bucket, employee_count = self.estimate_company_size(company)
            if size_bucket == "skip":
                logger.info(f"  ⊘ SKIP: Too large ({employee_count} est. employees)")
                return []
        else:
            size_bucket, employee_count = "unknown", -1

        # Signal ①: Recruiter Check (skip if internal recruiter found)
        if not getattr(self, '_skip_recruiter_check', False):
            has_recruiter, evidence = self.has_internal_recruiter(company)
            if has_recruiter:
                logger.info(f"  ⊘ SKIP: Internal recruiter found ({evidence})")
                return []
        else:
            has_recruiter = False

        # Step 0: Detect company type
        company_type = self.detect_company_type(
            company,
            job.get('industry', ''),
            job.get('job_description', '')
        )

        # Step 1: Extract contextual keywords from job posting
        keywords = self.extract_company_keywords(job)

        # Step 2: Find company website (with location + industry context)
        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Company: {company} [{size_bucket}, ~{employee_count}emp]")
        if keywords:
            logger.info(f"  → Keywords: {keywords}")

        website_data = self.find_company_website(company, keywords)
        website = website_data.get('url', '')
        company_desc = website_data.get('description', '')
        domain = self.extract_domain(website) if website else ""

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
            """Extract name → Search LinkedIn (3 attempts) → Validate DM"""
            logger.info(f"  🔍 Processing: {email}")

            # Extract name from email
            extracted_name, is_generic, confidence = self.extract_contact_from_email(email)

            if is_generic:
                logger.info(f"  → Generic email - skipping")
                return None

            # RELAXED: Accept confidence ≥ 20% (was 50%)
            if not extracted_name or confidence < 0.2:
                logger.info(f"  → Could not extract name (conf: {confidence:.0%}) - skipping")
                return None

            logger.info(f"  → Extracted name: {extracted_name} (conf: {confidence:.0%})")

            # Search LinkedIn by name + company (v2.2: use wrapper class)
            if not self.rapidapi_search:
                logger.info(f"  ✗ RapidAPI not configured - skipping")
                return None

            logger.info(f"  → Searching LinkedIn...")
            dm = self.rapidapi_search.search_linkedin_by_name(extracted_name, company)

            if not dm.get('full_name'):
                logger.info(f"  ✗ LinkedIn not found")
                return None

            full_name = dm.get('full_name', extracted_name)
            job_title = dm.get('title', '')

            # Thread-safe duplicate check (AFTER LinkedIn search)
            with seen_names_lock:
                if full_name in seen_names:
                    logger.info(f"  ✗ Duplicate name - skipping: {full_name}")
                    return None
                seen_names.add(full_name)

            # Validate decision-maker (size-aware)
            if size_bucket != "unknown":
                if not self.is_decision_maker_by_size(job_title, size_bucket):
                    logger.info(f"  ✗ Not a decision-maker for {size_bucket} company: {job_title}")
                    return None
            else:
                if not self.is_decision_maker(job_title):
                    logger.info(f"  ✗ Not a decision-maker: {job_title}")
                    return None

            # Build decision-maker record
            logger.info(f"  ★ Found DM: {full_name} ({job_title})")

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
                'employee_count_est': employee_count,
                'company_size': size_bucket,
                'job_title': job.get('job_title', ''),
                'job_url': job.get('job_url', ''),
                'location': job.get('location', ''),
                'posted_date': job.get('posted_date', ''),
                'job_age_days': job.get('job_age_days', -1),
                'pain_level': job.get('pain_level', 'unknown'),
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
                "Company Name", "Company Type", "Company Website",
                "Est. Employees", "Company Size",
                "Job Title", "Job URL", "Location",
                "Job Age (Days)", "Pain Level",
                "DM Name", "DM Title", "DM First", "DM Last", "DM LinkedIn",
                "DM Email", "Email Status", "DM Source", "Message", "Scraped Date"
            ]

            values = [headers]
            for row in rows:
                values.append([
                    row.get('company_name', ''),
                    row.get('company_type', 'Other'),
                    row.get('company_website', ''),
                    row.get('employee_count_est', ''),
                    row.get('company_size', ''),
                    row.get('job_title', ''),
                    row.get('job_url', ''),
                    row.get('location', ''),
                    row.get('job_age_days', ''),
                    row.get('pain_level', ''),
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

    def execute(self, query: str, location: str = "", country: str = "United States", max_jobs: int = 10, days_posted: int = 14,
                min_age: int = 0, max_size: int = 300, skip_recruiter_check: bool = False, skip_size_check: bool = False):
        start_time = time.time()

        # Store config flags
        self._skip_recruiter_check = skip_recruiter_check
        self._skip_size_check = skip_size_check
        self._max_company_size = max_size

        print("\n" + "="*70)
        print("🚀 INDEED JOB SCRAPER & OUTREACH SYSTEM (3-SIGNAL MODE)")
        print(f"Query: {query} | Location: {location} | Country: {country}")
        print(f"Signals: Size<{max_size} | Recruiter Skip: {'ON' if not skip_recruiter_check else 'OFF'} | Min Age: {min_age}d")
        print("="*70 + "\n")

        # 1. Start Scraper
        run_id = self.start_scraping_job(query, location, country, max_jobs, days_posted)
        if not run_id:
            return

        processed_jobs = []
        seen_companies = set()
        skipped_too_young = 0
        high_pain_count = 0

        # 2. Stream & Process
        print(f"🔄 Streaming & Processing jobs in parallel (workers={self.MAX_WORKERS})...")

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = []

            # Producer: Stream jobs from Apify
            for job in self.stream_jobs(run_id):
                company = job['company_name'].lower().strip()

                # Deduplicate on the fly
                if company in seen_companies:
                    continue
                seen_companies.add(company)

                # Signal ②: Job age filter
                if min_age > 0:
                    job_age = job.get('job_age_days', -1)
                    if 0 <= job_age < min_age:
                        skipped_too_young += 1
                        print(f"   ⊘ Skipped: {job['company_name']} (job only {job_age}d old)")
                        continue

                if job.get('pain_level') == 'high':
                    high_pain_count += 1

                # Consumer: Submit to thread pool
                future = executor.submit(self.process_single_company, job)
                futures.append(future)
                pain_tag = f" 🔥{job.get('job_age_days', '?')}d" if job.get('pain_level') == 'high' else ""
                print(f"   → Found: {job['company_name']}{pain_tag} (Processing...)")

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
        if min_age > 0:
            print(f"   Skipped (Job <{min_age}d old): {skipped_too_young}")
        print(f"   High Pain (30+ days): {high_pain_count}")
        print(f"   Emails Found: {len(jobs_with_emails)} ({success_rate:.1f}% success rate)")
        print(f"   Total Time: {total_time:.1f}s")
        print(f"   Avg Time/Company: {avg_time_per_company:.1f}s")
        print(f"   Cache Hits - Websites: {len(self._website_cache)} | Decision Makers: {len(self._dm_cache)}")
        print("-"*70 + "\n")

        logger.info(f"METRICS: companies={len(processed_jobs)} emails={len(jobs_with_emails)} success_rate={success_rate:.1f}% total_time={total_time:.1f}s avg_time={avg_time_per_company:.1f}s")

        # Save CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = f".tmp/indeed_jobs_{timestamp}.csv"
        
        if jobs_with_emails:
            pd.DataFrame(jobs_with_emails).to_csv(csv_path, index=False)
            print(f"📁 CSV Backup: {csv_path}")
            
            # Export to Sheets
            sheet_title = f"Jobs - {query} - {datetime.now().strftime('%Y-%m-%d')}"
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
    parser = argparse.ArgumentParser(description='Indeed Job Scraper & Outreach System')
    
    parser.add_argument('--query', type=str, default="AI Automation Expert", help='Job search query')
    parser.add_argument('--location', type=str, default="", help='Job location')
    parser.add_argument('--country', type=str, default="United States", help='Country to scrape')
    parser.add_argument('--limit', type=int, default=10, help='Max jobs to scrape')
    parser.add_argument('--days', type=int, default=14, help='Days posted')
    parser.add_argument('--min-age', type=int, default=0, help='Min job age in days (30 = only stale/pain jobs)')
    parser.add_argument('--max-size', type=int, default=300, help='Max company size - skip larger (default: 300)')
    parser.add_argument('--no-recruiter-check', action='store_true', help='Skip recruiter detection')
    parser.add_argument('--no-size-check', action='store_true', help='Skip company size detection')

    args = parser.parse_args()

    try:
        scraper = IndeedJobScraper()
        scraper.execute(
            query=args.query,
            location=args.location,
            country=args.country,
            max_jobs=args.limit,
            days_posted=args.days,
            min_age=args.min_age,
            max_size=args.max_size,
            skip_recruiter_check=args.no_recruiter_check,
            skip_size_check=args.no_size_check
        )
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)

if __name__ == "__main__":
    main()
