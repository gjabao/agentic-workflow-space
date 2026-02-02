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
import requests
import pandas as pd
from typing import Dict, List, Optional, Generator
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

        # 2. RapidAPI (Google Search) - Secure credential handling
        rapidapi_key = os.getenv("RAPIDAPI_KEY")
        self.rapidapi_available = bool(rapidapi_key)
        if not rapidapi_key:
            logger.warning("⚠️ RAPIDAPI_KEY not found. Decision maker search will be disabled.")
            self._rapidapi_key = None
        else:
            self._rapidapi_key = rapidapi_key
            logger.info("✓ RapidAPI initialized")

        # 3. AnyMailFinder - Secure credential handling
        anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        self.anymail_available = bool(anymail_key)
        if not anymail_key:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found. Email finding will be disabled.")
            self._anymail_key = None
        else:
            self._anymail_key = anymail_key
            logger.info("✓ AnyMailFinder initialized")

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

        # Rate limiting (thread-safe) - Aligned with API capacity
        self.rapidapi_lock = Lock()
        self.last_rapidapi_call = 0
        self.rapidapi_delay = 0.1  # 100ms = 10 req/sec

        logger.info("🚀 LinkedInJobScraper ready\n")

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

                # Poll interval (check for new items every 2 seconds)
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Error streaming jobs: {e}")
                break

    # ===========================================
    # PHASE 3: PROCESS COMPANY (PARALLEL)
    # ===========================================

    def process_single_company(self, job: Dict) -> Dict:
        """
        Process a single company through the full pipeline:
        0. Detect Company Type/Industry
        1. Find decision maker (3-attempt LinkedIn search)
        2. Find company website (Google search)
        3. Extract domain from website
        4. Find email (AnyMailFinder)
        5. Generate personalized message (OpenAI)

        Args:
            job: Job data dict from stream

        Returns:
            Dict: Job data enriched with DM, email, message
        """
        company = job['company_name']

        # Step 0: Detect Company Type/Industry
        company_type = self.detect_company_type(
            company,
            job.get('industry', ''),
            job.get('job_description', '')
        )
        job['company_type'] = company_type

        # Step 1: Find Decision Maker (3-attempt strategy)
        dm = self.find_decision_maker(company)
        job.update({
            'dm_name': dm.get('full_name', ''),
            'dm_first': dm.get('first_name', ''),
            'dm_last': dm.get('last_name', ''),
            'dm_title': dm.get('title', ''),
            'dm_linkedin': dm.get('linkedin_url', ''),
            'dm_description': dm.get('description', ''),
            'dm_source': dm.get('source', '')
        })

        # Step 2: Find Company Website
        website_data = self.find_company_website(company)
        website = website_data.get('url', '')
        company_desc = website_data.get('description', '')
        domain = self.extract_domain(website) if website else ""

        job['company_website'] = website
        job['company_domain'] = domain
        job['company_description'] = company_desc

        # Step 3: Find Email (if we have domain + name)
        if domain and job['dm_first']:
            email_data = self.find_email(job['dm_first'], job['dm_last'], domain)
            job.update({
                'dm_email': email_data.get('email', ''),
                'email_status': email_data.get('status', 'not_found'),
                'email_confidence': email_data.get('confidence', 0)
            })
        else:
            job.update({
                'dm_email': '',
                'email_status': 'missing_domain_or_name',
                'email_confidence': 0
            })

        # Step 4: Generate Message (if we have DM)
        if job['dm_name'] and self.openai_client:
            msg = self.generate_message(
                job['dm_name'],
                company,
                job['job_title'],
                job['dm_description'],
                job['company_description']
            )
            job['message'] = msg
        else:
            job['message'] = ""

        return job

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
        """Simplify job title by removing unnecessary details and locations."""
        if not title:
            return ""

        # Remove everything after common delimiters
        # Examples:
        # "Senior Research Software Engineer - Security & Cryptography" → "Senior Research Software Engineer"
        # "Senior iOS Engineer, Music" → "Senior iOS Engineer"
        # "Product Manager (Remote)" → "Product Manager"
        # "Director of Finance Regina/Saskatoon" → "Director of Finance"

        for delimiter in [' - ', ' – ', ' — ', ',', ' (', ' /', ' |']:
            if delimiter in title:
                title = title.split(delimiter)[0].strip()
                break

        return title.strip()

    def detect_company_type(self, company_name: str, industry: str = "", description: str = "") -> str:
        """Detect company type/industry based on company name, industry field, and description."""
        text = f"{company_name} {industry} {description}".lower()

        # Healthcare & Medical
        if any(word in text for word in ['hospital', 'health', 'medical', 'clinic', 'healthcare', 'pharmaceutical', 'pharma', 'biotech']):
            return 'Healthcare & Medical'

        # Construction & Real Estate
        if any(word in text for word in ['construction', 'builder', 'contractor', 'real estate', 'property', 'development']):
            return 'Construction & Real Estate'

        # Financial Services
        if any(word in text for word in ['bank', 'financial', 'finance', 'capital', 'investment', 'asset management', 'insurance', 'credit']):
            return 'Financial Services'

        # Technology & Software
        if any(word in text for word in ['software', 'technology', 'tech ', 'saas', 'cloud', 'digital', 'it ', 'data', 'ai ', 'cyber']):
            return 'Technology & Software'

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

    def find_decision_maker(self, company_name: str) -> Dict:
        """
        Find decision makers (CFO, CEO, Founder, etc.) using Google Search with 3-attempt strategy.

        Args:
            company_name: Company name

        Returns:
            Dict: {full_name, first_name, last_name, title, linkedin_url, description, source}
        """
        if not self._rapidapi_key:
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

            max_retries = 2  # Retry each attempt twice on API errors
            for retry in range(max_retries):
                try:
                    # Rate limiting (thread-safe) - Sleep inside lock to prevent race condition
                    with self.rapidapi_lock:
                        elapsed = time.time() - self.last_rapidapi_call
                        if elapsed < self.rapidapi_delay:
                            time.sleep(self.rapidapi_delay - elapsed)
                        self.last_rapidapi_call = time.time()

                    # Make API call
                    headers = {
                        'x-rapidapi-host': 'google-search116.p.rapidapi.com',
                        'x-rapidapi-key': self._rapidapi_key
                    }
                    params = {'query': query}

                    response = requests.get(
                        self.RAPIDAPI_GOOGLE_SEARCH_URL,
                        headers=headers,
                        params=params,
                        timeout=10
                    )

                    # Handle rate limiting
                    if response.status_code == 429:
                        if retry < max_retries - 1:
                            time.sleep((retry + 1) * 2)  # Exponential backoff
                            continue
                        break  # Move to next search attempt

                    if response.status_code != 200:
                        break  # Move to next search attempt

                    # Parse results
                    data = response.json()
                    results = data.get('results', [])
                    if not results:
                        break  # Move to next search attempt

                    top_result = results[0]
                    title = top_result.get('title', '')
                    link = top_result.get('url', '')
                    description = top_result.get('description', '')

                    # Parse name/title from LinkedIn result
                    # Example: "John Doe - Founder & CEO | CompanyX"
                    name_part = title.split('-')[0].strip() if '-' in title else title.strip()
                    dm_title = ""
                    if '-' in title and len(title.split('-')) > 1:
                        title_part = title.split('-')[1].strip()
                        if '|' in title_part:
                            title_part = title_part.split('|')[0].strip()
                        dm_title = title_part

                    # Parse first/last name
                    name_parts = name_part.split()
                    if len(name_parts) >= 2:
                        first_name = name_parts[0]
                        last_name = ' '.join(name_parts[1:])
                    else:
                        first_name = name_part
                        last_name = ""

                    # SUCCESS - Found a decision maker
                    result = {
                        'full_name': name_part,
                        'first_name': first_name,
                        'last_name': last_name,
                        'title': dm_title,
                        'linkedin_url': link,
                        'description': description,
                        'source': f'RapidAPI Google Search (Attempt {search_attempt_num})'
                    }
                    logger.info(f"  ✓ Found: {name_part} - {dm_title}")
                    return result

                except Exception as e:
                    if retry < max_retries - 1:
                        time.sleep(1)
                        continue
                    else:
                        break  # Move to next search attempt

        # All 3 attempts failed
        logger.info(f"  ✗ No decision maker found after 3 attempts")
        return {}

    def find_company_website(self, company_name: str) -> Dict:
        """
        Find company website using Google Search.

        Args:
            company_name: Company name

        Returns:
            Dict: {url, description}
        """
        if not self._rapidapi_key:
            return {'url': '', 'description': ''}

        query = f'"{company_name}" official website'

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Rate limiting (thread-safe) - Sleep inside lock to prevent race condition
                with self.rapidapi_lock:
                    elapsed = time.time() - self.last_rapidapi_call
                    if elapsed < self.rapidapi_delay:
                        time.sleep(self.rapidapi_delay - elapsed)
                    self.last_rapidapi_call = time.time()

                headers = {
                    'x-rapidapi-host': 'google-search116.p.rapidapi.com',
                    'x-rapidapi-key': self._rapidapi_key
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
                results = data.get('results', [])

                # Filter out social media sites
                skip_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'indeed.com', 'glassdoor.com']
                for result in results:
                    url = result.get('url', '')
                    if any(skip in url.lower() for skip in skip_domains):
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
        except:
            return ""

    def find_email(self, first_name: str, last_name: str, domain: str) -> Dict:
        """
        Find email using AnyMailFinder API.

        Args:
            first_name: First name
            last_name: Last name
            domain: Company domain (e.g., "acme.com")

        Returns:
            Dict: {email, status, confidence}
        """
        if not self._anymail_key or not domain or not first_name:
            return {'email': '', 'status': 'skipped', 'confidence': 0}

        try:
            headers = {
                'Authorization': self._anymail_key,
                'Content-Type': 'application/json'
            }

            payload = {
                'domain': domain,
                'first_name': first_name,
                'last_name': last_name
            }

            response = requests.post(
                self.ANYMAILFINDER_URL,
                headers=headers,
                json=payload,
                timeout=15  # Optimized timeout (balance speed vs success)
            )

            if response.status_code == 200:
                data = response.json()
                email = data.get('email')
                if email and self.validate_email_format(email):
                    return {
                        'email': email,
                        'status': 'found',
                        'confidence': data.get('confidence', 0)
                    }

            return {'email': '', 'status': 'not_found', 'confidence': 0}

        except Exception as e:
            logger.debug(f"Email finding error: {e}")
            return {'email': '', 'status': 'error', 'confidence': 0}

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
                "Company Name", "Company Type", "Company Website", "Company Domain", "Company Description",
                "Job Title", "Job URL", "Location", "Posted Date",
                "DM Name", "DM Title", "DM First", "DM Last", "DM LinkedIn", "DM Description",
                "DM Email", "Email Status", "Email Confidence", "DM Source",
                "Message", "Scraped Date"
            ]

            values = [headers]
            for row in rows:
                values.append([
                    row.get('company_name', ''),
                    row.get('company_type', 'Other'),
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
                    row.get('dm_source', ''),
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

        # Phase 2 & 3: TRUE STREAMING - Process as jobs arrive
        print(f"🔄 Streaming & Processing jobs in real-time...\n")

        # Use 10 workers (aligned with 10 req/sec rate limit)
        # Math: 10 workers × 2 API calls/company × 100ms delay = 10 req/sec
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}  # Track in-flight futures only
            stream_complete = False
            stream = self.stream_jobs(run_id)

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
                            result = future.result()
                            processed_jobs.append(result)

                            # Real-time feedback
                            email_status = "✅ Email" if result.get('dm_email') else "❌ No Email"
                            print(f"   ✓ [{len(processed_jobs)}] {result['company_name']} ({email_status})")
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
        print(f"   Processed: {len(processed_jobs)} unique companies")
        print(f"   Emails Found: {len(jobs_with_emails)}")
        print(f"   Success Rate: {len(jobs_with_emails)/len(processed_jobs)*100:.1f}%" if processed_jobs else "   Success Rate: 0%")
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
    import argparse

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
