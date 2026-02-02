#!/usr/bin/env python3
"""
LinkedIn Pain Signal Scraper v1.1 - Email-First Approach

Monitors LinkedIn posts for pain signals (expansion, hiring, funding) and enriches
with decision-maker data using proven email-first workflow.

v1.1 Optimizations:
- Skip non-companies (self-employed, freelance, etc.)
- Add post_snippet column (first 200 chars)
- Cache website lookups (reduces API calls)
- Parallel profile scraping in batches

WORKFLOW:
1. Scrape LinkedIn posts for pain signal keywords
2. Filter out recruitment agencies and job boards
3. Scrape author profiles to get company info
4. Find company website (3-attempt Google search)
5. Find ALL emails at company (AnyMailFinder Company API - up to 20)
6. Extract names from emails (firstname.lastname@ patterns)
7. Search LinkedIn for each name (3-attempt strategy)
8. Validate decision-maker titles
9. Export to Google Sheets + CSV backup

Based on:
- execution/scrape_crunchbase.py (email-first workflow)
- execution/scrape_linkedin_jobs.py (streaming/parallel architecture)
- execution/track_employee_departures.py (profile scraper usage)

Directive: directives/scrape_linkedin_pain_signals.md
"""

import os
import sys
import json
import time
import re
import argparse
import logging
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
    print(f"Missing dependency: {e}")
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

# Pain signal keyword categories
PAIN_SIGNAL_KEYWORDS = {
    'expansion': ['expanding into', 'new market', 'new office', 'opened our office', 'growing our team'],
    'hiring': ['hiring', 'looking for', 'open role', 'join our team', 'recruiting'],
    'funding': ['raised', 'funding', 'series a', 'series b', 'seed round', 'investment'],
    'launch': ['launching', 'excited to announce', 'introducing', 'new product'],
    'growth': ['scaling', 'growing', 'milestone', 'record quarter'],
    'pain': ['struggling with', 'challenge', 'looking for solution', 'need help with']
}

# Skip recruitment agencies and job boards
SKIP_AUTHOR_PATTERNS = [
    'recruiter', 'recruiting', 'talent acquisition', 'staffing',
    'job board', 'jobs board', 'career', 'hiring agency',
    'hr manager', 'headhunter', 'recruitment', 'jobs'
]

# Skip non-company patterns (self-employed, freelance, etc.)
SKIP_COMPANY_PATTERNS = [
    'self-employed', 'self employed', 'freelance', 'freelancer',
    'independent', 'independent contractor', 'consultant',
    'unemployed', 'looking for', 'seeking', 'open to work',
    'student', 'retired', 'n/a', 'none', '-'
]


class AnyMailFinder:
    """
    Company Email Finder - Returns ALL emails at a company (up to 20)
    Copied from scrape_crunchbase.py
    """

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key
        logger.info("  AnyMailFinder (Company Email API) initialized")

    def find_company_emails(self, company_domain: str, company_name: str = None) -> Dict:
        """
        Find ALL emails at a company in ONE call.
        Returns up to 20 emails per company!

        Returns:
            Dict with 'emails' list and 'status'
        """
        try:
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }

            payload = {
                'domain': company_domain,
                'email_type': 'any'  # Get all types: generic + personal
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
                elif email_status == 'not_found':
                    return {
                        'emails': [],
                        'status': 'not-found',
                        'count': 0
                    }
                else:
                    return {
                        'emails': [],
                        'status': email_status,
                        'count': 0
                    }
            else:
                logger.debug(f"API error for {company_domain}: {response.status_code}")
                return {
                    'emails': [],
                    'status': 'not-found',
                    'count': 0
                }

        except Exception as e:
            logger.debug(f"Error for {company_domain}: {e}")
            return {
                'emails': [],
                'status': 'not-found',
                'count': 0
            }


class RapidAPIGoogleSearch:
    """
    RapidAPI Google Search - For LinkedIn profile enrichment and website finding
    Copied from scrape_crunchbase.py
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2  # 5 req/sec per key
        logger.info(f"  RapidAPI Google Search initialized ({len(api_keys)} keys)")

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
                    logger.debug(f"Rate limit hit, waiting {2 ** attempt}s")
                    time.sleep(2 ** attempt)
                    continue

            except Exception as e:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.debug(f"Google Search error (attempt {attempt+1}), waiting {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                    continue
                logger.debug(f"Google Search error after 3 attempts: {e}")
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

    def search_by_name(self, full_name: str, company_name: str, location: str = None) -> Dict:
        """
        Search for person by name + company (extracted from email)
        Max 3 attempts with different query strategies
        """
        result = {
            'full_name': full_name,
            'job_title': '',
            'contact_linkedin': ''
        }

        # 3-attempt strategy for >90% LinkedIn match rate
        search_attempts = [
            # Attempt 1: Most specific - quoted name + "at" + quoted company (highest accuracy)
            (f'"{full_name}" at "{company_name}" linkedin', 5),

            # Attempt 2: Medium specificity - name + quoted company (broader)
            (f'{full_name} "{company_name}" linkedin', 5),

            # Attempt 3: Broad - name + company without quotes (catches edge cases)
            (f'{full_name} {company_name} linkedin', 7)
        ]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            logger.debug(f"  -> LinkedIn query {attempt_num}/3: {query}")

            data = self._rate_limited_search(query, num_results=num_results)

            if data and data.get('results'):
                found = self._extract_person_from_results(
                    data['results'],
                    full_name,
                    company_name,
                    require_linkedin=True
                )
                if found['full_name']:
                    return found

        logger.info(f"    LinkedIn not found for: {full_name}")
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
                logger.debug(f"    Name mismatch: '{extracted_name}' vs '{search_name}'")
                continue

            if not self._validate_person_name(extracted_name, company_name):
                logger.debug(f"    Invalid person name: '{extracted_name}'")
                continue

            job_title = self._extract_title_from_search(title, snippet)

            result['full_name'] = extracted_name
            result['job_title'] = job_title if job_title else ""
            result['contact_linkedin'] = url if 'linkedin.com' in url else ""

            logger.info(f"    Found on LinkedIn: {extracted_name} - {job_title}")
            return result

        return result

    def find_company_website(self, company_name: str, description: str = "") -> Optional[str]:
        """
        Find company website using 3-attempt Google search strategy
        """
        # Extract keywords from description for better search
        keywords = []
        if description:
            desc_words = description.split()[:50]
            desc_snippet = ' '.join(desc_words)

            business_terms = ['blockchain', 'crypto', 'fintech', 'software', 'platform',
                            'technology', 'ai', 'defi', 'nft', 'web3', 'infrastructure',
                            'payments', 'trading', 'security', 'wallet', 'saas', 'enterprise']

            for term in business_terms:
                if term.lower() in desc_snippet.lower():
                    keywords.append(term)
                    if len(keywords) >= 3:
                        break

        # 3-attempt strategy
        search_attempts = [
            (f'"{company_name}" {" ".join(keywords[:2])} official website' if keywords else f'"{company_name}" official website', 5),
            (f'"{company_name}" company website', 5),
            (f'{company_name} site', 7)
        ]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            logger.debug(f"  Website search {attempt_num}/3: {query}")

            search_result = self._rate_limited_search(query, num_results=num_results)

            if not search_result or not search_result.get('results'):
                continue

            homepage_result = None
            subpage_result = None

            for result in search_result['results']:
                url = result.get('url', '')
                title = result.get('title', '').lower()

                # Skip social media and unwanted sites
                skip_patterns = ['linkedin.com', 'twitter.com', 'facebook.com',
                               'crunchbase.com', 'wikipedia.org', 'youtube.com',
                               'instagram.com', 'tiktok.com', 'glassdoor.com', 'indeed.com',
                               '.pdf', '/documents/', '/notices/', '/files/', '/downloads/']
                if any(x in url.lower() for x in skip_patterns):
                    continue

                # Company name match
                company_lower = company_name.lower()
                is_match = False
                if attempt_num <= 2:
                    is_match = company_lower in title or company_lower in url.lower()
                else:
                    company_words = company_lower.split()[:2]
                    is_match = any(word in title or word in url.lower() for word in company_words if len(word) > 3)

                if not is_match:
                    continue

                # Detect subpage
                subpage_patterns = ['/careers', '/jobs', '/about', '/team', '/contact', '/company',
                                  '/news', '/press', '/blog', '/media', '/resources', '/solutions']
                is_subpage = any(pattern in url.lower() for pattern in subpage_patterns)

                domain = self._extract_domain_from_website(url)

                if is_subpage:
                    if not subpage_result:
                        subpage_result = domain
                else:
                    homepage_result = domain
                    break

            if homepage_result:
                return homepage_result
            elif subpage_result:
                return subpage_result

        return None

    def _extract_domain_from_website(self, website: str) -> Optional[str]:
        """Extract clean domain from website URL"""
        if not website:
            return None

        domain = website.replace('https://', '').replace('http://', '')
        domain = domain.split('/')[0]
        domain = domain.replace('www.', '')

        return domain


class LinkedInPainSignalScraper:
    """
    LinkedIn Pain Signal Scraper v1.1 - Email-First Approach

    Features:
    - Scrape LinkedIn posts for pain signals
    - Filter recruitment agencies and job boards
    - Skip non-companies (self-employed, freelance, etc.)
    - Email-first decision-maker enrichment
    - Parallel processing (10 workers for companies, 5 for emails)
    - Parallel profile scraping in batches
    - Website lookup caching (reduces API calls)
    - Pain signal classification and relevance scoring
    - Post snippet column (200 chars)
    - Google Sheets export with formatted headers
    """

    # Apify Actor IDs
    POSTS_SCRAPER_ACTOR = "apimaestro/linkedin-posts-search-scraper-no-cookies"
    PROFILE_SCRAPER_ACTOR = "harvestapi/linkedin-profile-scraper"

    def __init__(self):
        """Initialize API clients and validate credentials"""
        logger.info("Initializing LinkedInPainSignalScraper v1.0...")

        # Load API keys
        self.apify_api_key = self._load_secret("APIFY_API_KEY", required=True)
        self.anymailfinder_api_key = self._load_secret("ANYMAILFINDER_API_KEY", required=True)

        # RapidAPI keys (support multiple for rotation)
        rapidapi_keys = [
            os.getenv("RAPIDAPI_KEY"),
            os.getenv("RAPIDAPI_KEY_2")
        ]
        rapidapi_keys = [k for k in rapidapi_keys if k]

        if not rapidapi_keys:
            raise ValueError("RAPIDAPI_KEY not found in .env file")

        # Initialize clients
        self.apify_client = ApifyClient(self.apify_api_key)
        self.email_enricher = AnyMailFinder(self.anymailfinder_api_key)
        self.search_client = RapidAPIGoogleSearch(rapidapi_keys)

        # Cache for website lookups (reduces API calls)
        self._website_cache = {}
        self._website_cache_lock = Lock()

        logger.info("LinkedInPainSignalScraper v1.1 initialized\n")

    def _load_secret(self, key_name: str, required: bool = False) -> Optional[str]:
        """Load secret from environment"""
        value = os.getenv(key_name)
        if required and not value:
            raise ValueError(f"{key_name} not found in .env file")
        if value:
            logger.info(f"  {key_name} loaded")
        return value

    # =========================================
    # PHASE 1: Scrape LinkedIn Posts
    # =========================================

    def scrape_linkedin_posts(self, keywords: str, date_filter: str = "past-month", limit: int = 50) -> List[Dict]:
        """
        Scrape LinkedIn posts using Apify actor.

        Args:
            keywords: Boolean OR query for pain signals
            date_filter: "past-day", "past-week", "past-month"
            limit: Maximum posts to scrape

        Returns:
            List of post dictionaries with author info
        """
        logger.info(f"Scraping LinkedIn posts...")
        logger.info(f"  Keywords: {keywords[:50]}...")
        logger.info(f"  Date filter: {date_filter}")
        logger.info(f"  Limit: {limit}")

        run_input = {
            "date_filter": date_filter,
            "keyword": keywords,
            "limit": limit,
            "page_number": 1,
            "sort_type": "date_posted"
        }

        try:
            run = self.apify_client.actor(self.POSTS_SCRAPER_ACTOR).call(run_input=run_input)

            posts = []
            for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                posts.append(item)

            logger.info(f"  Scraped {len(posts)} posts\n")
            return posts

        except Exception as e:
            logger.error(f"Failed to scrape posts: {e}")
            return []

    # =========================================
    # PHASE 2: Filter Recruitment/Job Boards
    # =========================================

    def should_skip_author(self, author_name: str, headline: str) -> bool:
        """
        Check if author should be skipped (recruitment agency, job board, etc.)
        """
        combined = f"{author_name} {headline}".lower()
        return any(pattern in combined for pattern in SKIP_AUTHOR_PATTERNS)

    def should_skip_company(self, company_name: str) -> bool:
        """
        Check if company should be skipped (self-employed, freelance, etc.)
        """
        if not company_name:
            return True
        company_lower = company_name.lower().strip()
        # Skip if company name is too short or matches skip patterns
        if len(company_lower) < 2:
            return True
        return any(pattern in company_lower for pattern in SKIP_COMPANY_PATTERNS)

    # =========================================
    # PHASE 3: Scrape Author Profiles
    # =========================================

    def scrape_author_profiles(self, profile_urls: List[str], batch_size: int = 10) -> List[Dict]:
        """
        Scrape full LinkedIn profiles for post authors in parallel batches.

        Args:
            profile_urls: List of LinkedIn profile URLs
            batch_size: Number of profiles per batch (default: 10)

        Returns:
            List of full profile dictionaries
        """
        if not profile_urls:
            return []

        total_profiles = len(profile_urls)
        logger.info(f"Scraping {total_profiles} author profiles in batches of {batch_size}...")

        all_profiles = []

        # Split into batches
        batches = [profile_urls[i:i + batch_size] for i in range(0, len(profile_urls), batch_size)]
        logger.info(f"  Split into {len(batches)} batches")

        def scrape_batch(batch_urls: List[str], batch_num: int) -> List[Dict]:
            """Scrape a single batch of profiles"""
            run_input = {
                "profileScraperMode": "Profile details no email ($4 per 1k)",
                "queries": batch_urls
            }

            try:
                run = self.apify_client.actor(self.PROFILE_SCRAPER_ACTOR).call(run_input=run_input)

                profiles = []
                for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                    profiles.append(item)

                logger.info(f"    Batch {batch_num}: scraped {len(profiles)} profiles")
                return profiles

            except Exception as e:
                logger.error(f"    Batch {batch_num} failed: {e}")
                return []

        # Process batches in parallel (max 3 concurrent batches to avoid rate limits)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(scrape_batch, batch, i + 1): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_profiles = future.result()
                    all_profiles.extend(batch_profiles)
                except Exception as e:
                    logger.error(f"  Batch {batch_idx + 1} error: {e}")

        logger.info(f"  Total scraped: {len(all_profiles)} profiles\n")
        return all_profiles

    # =========================================
    # PHASE 4: Extract Company Info
    # =========================================

    def extract_company_from_profile(self, profile: Dict) -> Optional[Dict]:
        """
        Extract current company info from profile.

        Returns:
            Dict with company_name, company_linkedin_url, author_position
            or None if not employed
        """
        # Log profile structure for debugging
        logger.debug(f"  Profile keys: {list(profile.keys())}")

        # Check if this is a company page (not a person profile)
        if profile.get('type') == 'company' or 'companyName' in profile:
            company_name = profile.get('companyName', '') or profile.get('name', '')
            if company_name:
                return {
                    'company_name': company_name,
                    'company_linkedin_url': profile.get('linkedinUrl', ''),
                    'author_position': 'Company Page'
                }

        # Try different field names for experiences
        experiences = profile.get('experience', []) or profile.get('experiences', []) or profile.get('positions', [])

        if not experiences:
            return None

        # Find current job (endDate is None or "Present")
        for exp in experiences:
            end_date = exp.get('endDate', {})
            if not end_date or (isinstance(end_date, dict) and end_date.get('text') == 'Present'):
                return {
                    'company_name': exp.get('companyName', ''),
                    'company_linkedin_url': exp.get('companyLinkedinUrl', ''),
                    'author_position': exp.get('position', '')
                }

        # Fall back to first experience
        if experiences:
            exp = experiences[0]
            company_name = exp.get('companyName', '') or exp.get('company', '') or exp.get('name', '')
            return {
                'company_name': company_name,
                'company_linkedin_url': exp.get('companyLinkedinUrl', '') or exp.get('companyUrl', ''),
                'author_position': exp.get('position', '') or exp.get('title', '')
            }

        # Try to extract from headline if no experience found
        headline = profile.get('headline', '') or profile.get('title', '')
        if headline and ' at ' in headline:
            parts = headline.split(' at ')
            if len(parts) >= 2:
                return {
                    'company_name': parts[-1].strip(),
                    'company_linkedin_url': '',
                    'author_position': parts[0].strip()
                }

        return None

    # =========================================
    # PHASE 5: Pain Signal Classification
    # =========================================

    def classify_pain_signal(self, post_text: str) -> str:
        """
        Classify post by pain signal type.

        Returns:
            Primary pain signal category or 'general'
        """
        if not post_text:
            return 'general'

        text_lower = post_text.lower()

        for category, keywords in PAIN_SIGNAL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return 'general'

    def calculate_relevance_score(self, post: Dict, author_headline: str = "") -> int:
        """
        Calculate relevance score (0-100) to prioritize posts.

        Higher scores for:
        - Post author is decision-maker (not recruiter)
        - High engagement
        - Multiple pain signals
        """
        score = 0

        # Author is decision-maker (+30)
        if author_headline and self.is_decision_maker(author_headline):
            score += 30

        # Author is NOT recruiter (+20)
        if not self.should_skip_author("", author_headline):
            score += 20

        # High engagement (+20 for >100 reactions, +10 for 50-100)
        stats = post.get('stats', {})
        reactions = stats.get('total_reactions', 0) if isinstance(stats, dict) else 0
        if reactions > 100:
            score += 20
        elif reactions > 50:
            score += 10

        # Multiple pain signals (+10 each, max 30)
        post_text = post.get('text', '').lower()
        signals_found = 0
        for keywords in PAIN_SIGNAL_KEYWORDS.values():
            if any(kw in post_text for kw in keywords):
                signals_found += 1
        score += min(signals_found * 10, 30)

        return min(score, 100)

    # =========================================
    # PHASE 6: Email-First Enrichment
    # =========================================

    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """
        Extract name from email and classify as generic/personal
        Copied from scrape_crunchbase.py

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
        Validate if job title is a decision-maker position
        """
        if not job_title or len(job_title) < 3:
            return False

        job_title_lower = job_title.lower()

        decision_maker_keywords = [
            'founder', 'co-founder', 'ceo', 'chief executive', 'chief',
            'owner', 'president', 'cfo', 'cto', 'coo', 'cmo',
            'c-suite', 'c-level',
            'vice president', 'vp ', 'director', 'executive director', 'managing director',
            'head of', 'managing partner', 'partner', 'principal',
            'executive'
        ]

        has_dm_keyword = any(kw in job_title_lower for kw in decision_maker_keywords)

        exclude_keywords = [
            'assistant', 'associate', 'junior', 'intern', 'coordinator',
            'analyst', 'specialist', 'representative', 'agent', 'clerk',
            'trainee', 'apprentice', 'student'
        ]

        has_exclude_keyword = any(kw in job_title_lower for kw in exclude_keywords)

        return has_dm_keyword and not has_exclude_keyword

    def _get_cached_website(self, company_name: str) -> Optional[str]:
        """
        Get company website from cache or search.
        Thread-safe caching to reduce API calls.
        """
        cache_key = company_name.lower().strip()

        # Check cache first (thread-safe)
        with self._website_cache_lock:
            if cache_key in self._website_cache:
                cached = self._website_cache[cache_key]
                if cached:
                    logger.info(f"  Website (cached): {cached}")
                return cached

        # Not in cache, search for it
        domain = self.search_client.find_company_website(company_name, "")

        # Store in cache (thread-safe)
        with self._website_cache_lock:
            self._website_cache[cache_key] = domain

        return domain

    def enrich_single_company(self, company_data: Dict, post_data: Dict, profile_data: Dict = None) -> List[Dict]:
        """
        Email-first enrichment for a company.
        Returns list of decision-makers with emails.
        """
        company_name = company_data.get('company_name', '')

        if not company_name:
            return []

        # Skip non-companies (self-employed, freelance, etc.)
        if self.should_skip_company(company_name):
            logger.info(f"  Skipping non-company: {company_name}")
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"Company: {company_name}")

        # Step 1: Find website (with caching)
        domain = self._get_cached_website(company_name)

        if not domain:
            logger.info(f"  No website found - skipping")
            return []

        logger.info(f"  Website: {domain}")

        # Step 2: Find ALL emails (up to 20)
        logger.info(f"  Finding emails at {domain}...")
        email_result = self.email_enricher.find_company_emails(domain, company_name)

        emails = email_result.get('emails', [])
        logger.info(f"  Found {len(emails)} emails")

        if not emails:
            logger.info(f"  No emails found - skipping")
            return []

        # Step 3-5: Process emails in parallel (5 workers)
        decision_makers = []
        seen_names_lock = Lock()
        seen_names = set()

        def process_single_email(email: str) -> Optional[Dict]:
            """Process a single email: extract name -> search LinkedIn -> validate DM"""
            logger.info(f"  Processing: {email}")

            # Extract name from email
            extracted_name, is_generic, confidence = self.extract_contact_from_email(email)

            if is_generic:
                logger.info(f"    Generic email - skipping")
                return None

            if not extracted_name or confidence < 0.5:
                logger.info(f"    Could not extract name (conf: {confidence:.0%}) - skipping")
                return None

            logger.info(f"    Extracted name: {extracted_name} (conf: {confidence:.0%})")

            # Search LinkedIn by name + company
            logger.info(f"    Searching LinkedIn...")
            contact_info = self.search_client.search_by_name(extracted_name, company_name)

            full_name = contact_info.get('full_name', extracted_name)
            job_title = contact_info.get('job_title', '')
            linkedin_url = contact_info.get('contact_linkedin', '')

            # Skip duplicates (thread-safe)
            with seen_names_lock:
                if full_name.lower() in seen_names:
                    logger.info(f"    Duplicate name - skipping: {full_name}")
                    return None
                seen_names.add(full_name.lower())

            # Validate decision-maker
            if not self.is_decision_maker(job_title):
                logger.info(f"    Not a decision-maker: {job_title}")
                return None

            logger.info(f"  Found DM: {full_name} ({job_title})")

            # Build result
            name_parts = full_name.split()
            post_text = post_data.get('text', '')
            # Create snippet (first 200 chars, clean up whitespace)
            post_snippet = ' '.join(post_text.split())[:200]
            if len(post_text) > 200:
                post_snippet += '...'

            return {
                # Post data
                'post_snippet': post_snippet,
                'post_url': post_data.get('post_url', ''),
                'pain_signal_type': self.classify_pain_signal(post_text),
                'relevance_score': post_data.get('relevance_score', 0),
                'posted_date': post_data.get('posted_at', {}).get('date', '') if isinstance(post_data.get('posted_at'), dict) else '',

                # Author data (post author)
                'post_author_name': post_data.get('author', {}).get('name', '') if isinstance(post_data.get('author'), dict) else '',
                'post_author_linkedin': post_data.get('author', {}).get('profile_url', '') if isinstance(post_data.get('author'), dict) else '',

                # Company data
                'company_name': company_name,
                'company_website': domain,

                # Decision-maker data
                'dm_first_name': name_parts[0] if name_parts else '',
                'dm_last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
                'dm_job_title': job_title,
                'dm_email': email,
                'dm_linkedin_url': linkedin_url
            }

        # Parallel processing (5 workers)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_single_email, email): email
                      for email in emails[:20]}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        decision_makers.append(result)
                except Exception as e:
                    email = futures[future]
                    logger.error(f"    Error processing {email}: {str(e)}")

        logger.info(f"Found {len(decision_makers)} decision-makers for {company_name}")
        return decision_makers

    # =========================================
    # PHASE 7: Export
    # =========================================

    def export_to_csv(self, leads: List[Dict], filename: Optional[str] = None) -> str:
        """Export leads to CSV"""
        import csv

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_pain_signals_{timestamp}.csv"

        logger.info(f"Exporting to CSV: {filename}...")

        if not leads:
            logger.warning("No leads to export")
            return filename

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=leads[0].keys())
            writer.writeheader()
            writer.writerows(leads)

        logger.info(f"CSV exported: {filename}")
        return filename

    def export_to_google_sheets(self, leads: List[Dict], title: str) -> str:
        """Export leads to Google Sheets"""
        logger.info("Exporting to Google Sheets...")

        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"OAuth token refresh failed: {e}")
                    logger.info("Will use CSV export instead")
                    return ""
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("credentials.json not found")
                    return ""

                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        try:
            service = build('sheets', 'v4', credentials=creds)
            drive_service = build('drive', 'v3', credentials=creds)

            spreadsheet = {
                'properties': {'title': title}
            }
            spreadsheet = service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()

            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')

            logger.info(f"Created: {spreadsheet_url}")

            if not leads:
                return spreadsheet_url

            # Headers
            headers = list(leads[0].keys())
            values = [headers]

            for lead in leads:
                values.append([str(lead.get(h, '')) for h in headers])

            body = {'values': values}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            # Format header
            requests_format = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
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

            # Make publicly viewable
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            logger.info(f"Exported {len(leads)} rows to Google Sheets")

            return spreadsheet_url

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ""

    # =========================================
    # MAIN ORCHESTRATION
    # =========================================

    def run(self, keywords: str, date_filter: str = "past-month", limit: int = 50, min_relevance: int = 30) -> str:
        """
        Main workflow:
        1. Scrape LinkedIn posts
        2. Filter recruitment/job boards
        3. Scrape author profiles
        4. Extract company info
        5. Email-first enrichment
        6. Export to Google Sheets + CSV
        """
        start_time = time.time()

        # Print header
        logger.info("=" * 70)
        logger.info("LINKEDIN PAIN SIGNAL SCRAPER v1.1 - EMAIL-FIRST APPROACH")
        logger.info("=" * 70)
        logger.info(f"Keywords: {keywords[:60]}...")
        logger.info(f"Date filter: {date_filter}")
        logger.info(f"Limit: {limit} posts")
        logger.info(f"Min relevance: {min_relevance}")
        logger.info("=" * 70 + "\n")

        # Phase 1: Scrape posts
        posts = self.scrape_linkedin_posts(keywords, date_filter, limit)

        if not posts:
            logger.error("No posts scraped")
            return ""

        # Phase 2: Filter recruitment/job boards
        filtered_posts = []
        for post in posts:
            author = post.get('author', {})
            author_name = author.get('name', '') if isinstance(author, dict) else ''
            author_headline = author.get('headline', '') if isinstance(author, dict) else ''

            if self.should_skip_author(author_name, author_headline):
                logger.info(f"  Skipping recruiter/job board: {author_name}")
                continue

            # Calculate relevance score
            relevance = self.calculate_relevance_score(post, author_headline)
            post['relevance_score'] = relevance

            if relevance >= min_relevance:
                filtered_posts.append(post)
            else:
                logger.debug(f"  Skipping low relevance ({relevance}): {author_name}")

        logger.info(f"\nFiltered to {len(filtered_posts)} posts (excluded {len(posts) - len(filtered_posts)} recruiters/low relevance)\n")

        if not filtered_posts:
            logger.warning("No posts after filtering")
            return ""

        # Phase 3: Extract profile URLs and scrape
        profile_urls = []
        url_to_post = {}

        for post in filtered_posts:
            author = post.get('author', {})
            profile_url = author.get('profile_url', '') if isinstance(author, dict) else ''

            if profile_url and 'linkedin.com' in profile_url:
                # Clean up URL
                if '/posts' in profile_url:
                    profile_url = profile_url.replace('/posts', '')
                if not profile_url.endswith('/'):
                    profile_url = profile_url + '/'

                if profile_url not in url_to_post:
                    profile_urls.append(profile_url)
                    url_to_post[profile_url] = post

        logger.info(f"Found {len(profile_urls)} unique author profile URLs\n")

        if not profile_urls:
            logger.warning("No valid profile URLs found")
            return ""

        profiles = self.scrape_author_profiles(profile_urls)

        # Phase 4: Extract companies and deduplicate
        companies_to_process = []
        seen_companies = set()

        logger.info(f"Processing {len(profiles)} scraped profiles...")

        for profile in profiles:
            # Match profile to post - try multiple URL formats
            linkedin_url = profile.get('linkedinUrl', '') or profile.get('url', '') or profile.get('profileUrl', '')

            # Normalize URL for matching
            def normalize_url(url):
                if not url:
                    return ''
                url = url.replace('https://www.linkedin.com', '').replace('https://linkedin.com', '')
                url = url.replace('http://www.linkedin.com', '').replace('http://linkedin.com', '')
                url = url.rstrip('/')
                # Remove query params
                if '?' in url:
                    url = url.split('?')[0]
                return url.lower()

            normalized_profile_url = normalize_url(linkedin_url)

            post = None
            for original_url, p in url_to_post.items():
                normalized_original = normalize_url(original_url)
                if normalized_profile_url and normalized_original:
                    # Check if URLs match (handle variations)
                    if normalized_profile_url in normalized_original or normalized_original in normalized_profile_url:
                        post = p
                        break

            if not post:
                # Try to match by name
                profile_name = (profile.get('firstName', '') + ' ' + profile.get('lastName', '')).strip().lower()
                profile_name_alt = profile.get('name', '').lower() if profile.get('name') else ''

                for url, p in url_to_post.items():
                    author = p.get('author', {})
                    if isinstance(author, dict):
                        author_name = author.get('name', '').lower()
                        if author_name and (author_name in profile_name or author_name in profile_name_alt or
                                          profile_name in author_name or profile_name_alt in author_name):
                            post = p
                            break

            if not post:
                logger.debug(f"  Could not match profile to post: {linkedin_url}")
                continue

            company_info = self.extract_company_from_profile(profile)

            if not company_info or not company_info.get('company_name'):
                logger.info(f"  No company found for profile: {profile.get('firstName', '')} {profile.get('lastName', '')}")
                continue

            logger.info(f"  Found company: {company_info['company_name']}")

            company_key = company_info['company_name'].lower().strip()

            if company_key in seen_companies:
                logger.debug(f"  Skipping duplicate company: {company_info['company_name']}")
                continue

            seen_companies.add(company_key)
            companies_to_process.append({
                'company_data': company_info,
                'post_data': post,
                'profile_data': profile
            })

        logger.info(f"\nUnique companies to enrich: {len(companies_to_process)}\n")

        # Phase 5: Email-first enrichment (parallel, 10 workers)
        all_decision_makers = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self.enrich_single_company,
                    item['company_data'],
                    item['post_data'],
                    item['profile_data']
                ): item
                for item in companies_to_process
            }

            completed = 0
            total = len(companies_to_process)

            for future in as_completed(futures):
                item = futures[future]

                try:
                    decision_makers = future.result()
                    all_decision_makers.extend(decision_makers)
                except Exception as e:
                    logger.error(f"Error processing {item['company_data'].get('company_name', 'unknown')}: {str(e)}")

                completed += 1

                if completed % max(1, total // 10) == 0:
                    progress = (completed / total) * 100
                    logger.info(f"\nProgress: {completed}/{total} ({progress:.0f}%)")

        logger.info(f"\n\nEnrichment complete: {len(all_decision_makers)} decision-makers from {len(companies_to_process)} companies")

        # Phase 6: Export
        if not all_decision_makers:
            logger.warning("No decision-makers found with emails")
            return ""

        # Always save CSV first (prevents data loss)
        logger.info("\nSaving CSV backup...")
        csv_file = self.export_to_csv(all_decision_makers)
        logger.info(f"CSV saved: {os.path.abspath(csv_file)}")

        # Try to export to Google Sheets
        sheet_title = f"LinkedIn Pain Signals - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        sheet_url = ""
        try:
            sheet_url = self.export_to_google_sheets(all_decision_makers, sheet_title)
        except Exception as e:
            logger.warning(f"Google Sheets export failed: {e}")
            logger.info(f"Data is safe in CSV: {csv_file}")

        # Print summary
        duration = time.time() - start_time

        logger.info("\n" + "=" * 70)
        logger.info("LINKEDIN PAIN SIGNAL SCRAPER SUMMARY (v1.1)")
        logger.info("=" * 70)
        logger.info(f"Posts scraped:               {len(posts)}")
        logger.info(f"Posts after filtering:       {len(filtered_posts)}")
        logger.info(f"Unique companies:            {len(companies_to_process)}")
        logger.info(f"Decision-makers with emails: {len(all_decision_makers)}")
        logger.info(f"Duration:                    {duration:.1f}s")
        logger.info("=" * 70)

        if sheet_url:
            logger.info(f"\nComplete! Google Sheet: {sheet_url}")

        return sheet_url or csv_file


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="LinkedIn Pain Signal Scraper v1.1 - Monitor posts for expansion signals"
    )

    parser.add_argument(
        "--keywords",
        type=str,
        default='"expanding into" OR "new market" OR "new office" OR "opened our office"',
        help='Pain signal keywords (OR syntax supported)'
    )

    parser.add_argument(
        "--date-filter",
        type=str,
        default="past-month",
        choices=["past-day", "past-week", "past-month"],
        help="Date filter for posts"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum posts to scrape (default: 50)"
    )

    parser.add_argument(
        "--min-relevance",
        type=int,
        default=30,
        help="Minimum relevance score to include (0-100, default: 30)"
    )

    args = parser.parse_args()

    try:
        scraper = LinkedInPainSignalScraper()
        scraper.run(
            keywords=args.keywords,
            date_filter=args.date_filter,
            limit=args.limit,
            min_relevance=args.min_relevance
        )
    except KeyboardInterrupt:
        logger.info("\n\nScraper interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()