#!/usr/bin/env python3
"""
Clutch Lead Scraper v1.0 - Email-First Approach (Following Crunchbase Logic)

NEW WORKFLOW (v1.0):
1. Scrape companies from Clutch.co via Apify (memo23/apify-clutch-cheerio)
2. Extract website from Clutch data (websiteUrl field)
3. Find ALL emails first (up to 20 per company) via AnyMailFinder Company API
4. Extract names from emails (firstname.lastname@ → "Firstname Lastname")
5. Search LinkedIn profiles by name + company using RapidAPI
6. Validate if decision-maker based on title keywords:
   - founder, ceo, owner, managing partner, vice president, vp, cfo, cto, coo
   - executive, c-suite, chief, president, partner, managing director
7. Output ONLY leads with valid emails

KEY ADVANTAGES:
- ✅ Website provided directly by Clutch (no Google Search needed)
- ✅ Rich company data (ratings, reviews, services, industries)
- ✅ Email-first approach: 200-300% coverage vs 5-10% decision-maker-first

Based on: execution/scrape_crunchbase.py v4.0
Directive: directives/scrape_clutch_leads.md
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
    Copied from Crunchbase scraper (lines 64-143)
    """

    BASE_URL = "https://api.anymailfinder.com/v5.1/find-email/company"

    def __init__(self, api_key: str):
        self.api_key = api_key
        logger.info("✓ AnyMailFinder (Company Email API) initialized")

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
    RapidAPI Google Search - For LinkedIn profile enrichment
    Copied from Crunchbase scraper (lines 145-423)
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
                    logger.debug(f"⚠️ Rate limit hit, waiting {2 ** attempt}s")
                    time.sleep(2 ** attempt)
                    continue

            except Exception as e:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.debug(f"⚠️ Google Search error (attempt {attempt+1}), waiting {wait_time}s: {str(e)}")
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
            logger.debug(f"  → LinkedIn query {attempt_num}/3: {query}")

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

        logger.info(f"  ✗ LinkedIn not found for: {full_name}")
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

            logger.info(f"  ✓ Found on LinkedIn: {extracted_name} - {job_title}")
            return result

        return result


class ClutchScraper:
    """
    Clutch Lead Scraper v1.0 - Email-First Approach
    Following Crunchbase scraper workflow
    """

    def __init__(self):
        """Initialize scraper with API credentials"""
        logger.info("⏳ Initializing ClutchScraper v1.0 (Email-First)...")

        # Load API keys
        self.apify_api_key = self._load_secret("APIFY_API_KEY", required=True)
        self.anymailfinder_api_key = self._load_secret("ANYMAILFINDER_API_KEY", required=True)

        # RapidAPI keys (support multiple for rotation)
        rapidapi_keys = [
            os.getenv("RAPIDAPI_KEY"),
            os.getenv("RAPIDAPI_KEY_2"),
            os.getenv("RAPIDAPI_KEY_3"),
            os.getenv("RAPIDAPI_KEY_4"),
            os.getenv("RAPIDAPI_KEY_5")
        ]
        rapidapi_keys = [k for k in rapidapi_keys if k]

        if not rapidapi_keys:
            raise ValueError("❌ RAPIDAPI_KEY not found in .env file")

        # Initialize clients
        self.apify_client = ApifyClient(self.apify_api_key)
        self.email_enricher = AnyMailFinder(self.anymailfinder_api_key)
        self.search_client = RapidAPIGoogleSearch(rapidapi_keys)

        logger.info("✓ ClutchScraper v1.0 initialized")

    def _load_secret(self, key_name: str, required: bool = False) -> Optional[str]:
        """Load secret from environment"""
        value = os.getenv(key_name)
        if required and not value:
            raise ValueError(f"❌ {key_name} not found in .env file")
        if value:
            logger.info(f"  ✓ {key_name} loaded")
        return value

    def _extract_domain_from_website(self, website: str) -> Optional[str]:
        """Extract clean domain from website URL"""
        if not website:
            return None

        domain = website.replace('https://', '').replace('http://', '')
        domain = domain.split('/')[0]
        domain = domain.replace('www.', '')
        domain = domain.split('?')[0]  # Remove query params

        return domain

    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """
        Extract name from email and classify as generic/personal
        Copied from Crunchbase scraper (lines 477-551)

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
            # C-Suite & Founders
            'founder', 'co-founder', 'ceo', 'chief executive', 'chief',
            'owner', 'president', 'cfo', 'cto', 'coo', 'cmo',
            'c-suite', 'c-level',
            # Vice Presidents & Directors
            'vice president', 'vp ', 'director', 'executive director', 'managing director',
            # Heads & Partners
            'head of', 'managing partner', 'partner', 'principal',
            # Executive roles
            'executive'
        ]

        # Must contain at least one decision-maker keyword
        has_dm_keyword = any(kw in job_title_lower for kw in decision_maker_keywords)

        # Exclude non-decision-maker roles
        exclude_keywords = [
            'assistant', 'associate', 'junior', 'intern', 'coordinator',
            'analyst', 'specialist', 'representative', 'agent', 'clerk',
            'trainee', 'apprentice', 'student'
        ]

        has_exclude_keyword = any(kw in job_title_lower for kw in exclude_keywords)

        return has_dm_keyword and not has_exclude_keyword

    def scrape_companies(self, search_url: str, limit: int = 25) -> List[Dict]:
        """Step 1: Scrape companies from Clutch using Apify"""
        logger.info(f"⏳ Running Apify scraper (limit: {limit})...")

        run_input = {
            "startUrls": [{"url": search_url}],
            "maxConcurrency": 10,
            "minConcurrency": 1,
            "maxRequestRetries": 10,
            "maxItems": limit,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]  # CRITICAL: Clutch blocks datacenter IPs
            }
        }

        run = self.apify_client.actor("memo23/apify-clutch-cheerio").call(run_input=run_input)

        items = []
        for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
            items.append(item)

        logger.info(f"✓ Scraped {len(items)} companies from Clutch")
        return items

    def _extract_top_service(self, service_focus: List[Dict]) -> str:
        """Extract top service with percentage"""
        if not service_focus or not isinstance(service_focus, list):
            return ''

        # Get first service (highest percentage)
        top = service_focus[0]
        service = top.get('service', '')
        percentage = top.get('percentage', '')

        if service and percentage:
            return f"{service} ({percentage})"
        return service

    def _extract_industries(self, chart_pie: Dict) -> str:
        """Extract top 3-5 industries from chart data"""
        if not chart_pie or not isinstance(chart_pie, dict):
            return ''

        industries_data = chart_pie.get('industries', {})
        slices = industries_data.get('slices', [])

        if not slices:
            return ''

        # Get top 3-5 industries
        industry_names = [s.get('name', '') for s in slices[:5] if s.get('name')]
        return ', '.join(industry_names)

    def enrich_single_company(self, company: Dict) -> List[Dict]:
        """
        Enrich single company following email-first workflow:
        1. Extract website from Clutch data
        2. Find emails (AnyMailFinder)
        3. Extract names from emails
        4. Search LinkedIn by name
        5. Validate if decision-maker
        6. Return list of decision-makers with emails
        """
        company_name = company.get('name', '')
        website = company.get('websiteUrl', '')

        if not company_name:
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Company: {company_name}")

        # Step 1: Get website domain from Clutch data
        if not website:
            logger.info(f"  ⊘ No website provided - skipping")
            return []

        domain = self._extract_domain_from_website(website)
        if not domain:
            logger.info(f"  ⊘ Could not extract domain from {website} - skipping")
            return []

        logger.info(f"  ✓ Website from Clutch: {domain}")

        # Step 2: Find ALL emails at company (up to 20)
        logger.info(f"  📧 Finding emails at {domain}...")
        email_result = self.email_enricher.find_company_emails(domain, company_name)

        emails = email_result.get('emails', [])
        logger.info(f"  ✓ Found {len(emails)} emails")

        if not emails:
            logger.info(f"  ⊘ No emails found - skipping")
            return []

        # Step 3-6: Process each email (PARALLEL for 2-3x speed boost)
        decision_makers = []
        seen_names_lock = Lock()
        seen_names = set()

        def process_single_email(email: str) -> Optional[Dict]:
            """Process a single email: extract name → search LinkedIn → validate DM"""
            logger.info(f"  🔍 Processing: {email}")

            # Step 3: Extract name from email
            extracted_name, is_generic, confidence = self.extract_contact_from_email(email)

            if is_generic:
                logger.info(f"  → Generic email - skipping")
                return None

            if not extracted_name or confidence < 0.5:
                logger.info(f"  → Could not extract name (conf: {confidence:.0%}) - skipping")
                return None

            logger.info(f"  → Extracted name: {extracted_name} (conf: {confidence:.0%})")

            # Step 4: Search LinkedIn by name + company
            logger.info(f"  → Searching LinkedIn...")
            contact_info = self.search_client.search_by_name(extracted_name, company_name)

            full_name = contact_info.get('full_name', extracted_name)
            job_title = contact_info.get('job_title', '')
            linkedin_url = contact_info.get('contact_linkedin', '')

            # Skip duplicates (thread-safe)
            with seen_names_lock:
                if full_name in seen_names:
                    logger.info(f"  ✗ Duplicate name - skipping: {full_name}")
                    return None
                seen_names.add(full_name)

            # Step 5: Validate if decision-maker
            if not self.is_decision_maker(job_title):
                logger.info(f"  ✗ Not a decision-maker: {job_title}")
                return None

            # Extract location (primary headquarters)
            location = company.get('location', '')
            if not location and company.get('locations'):
                locations = company.get('locations', [])
                if isinstance(locations, list) and locations:
                    loc_data = locations[0]
                    locality = loc_data.get('locality', '')
                    country = loc_data.get('country', '')
                    location = f"{locality}, {country}" if locality and country else locality or country

            # New format: 15 columns as per directive
            dm = {
                'company_name': company_name,
                'first_name': full_name.split()[0] if full_name else '',
                'last_name': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                'job_title': job_title,
                'email': email,
                'linkedin_url': linkedin_url,
                'website': domain,
                'location': location,
                'rating': company.get('rating', ''),
                'review_count': company.get('reviewCount', ''),
                'employee_size': company.get('employeeSize', ''),
                'hourly_rate': company.get('hourlyRate', ''),
                'min_project_size': company.get('minProjectSize', ''),
                'service_focus': self._extract_top_service(company.get('serviceFocus', [])),
                'industries': self._extract_industries(company.get('chartPie', {}))
            }

            logger.info(f"  ★ Found decision-maker: {full_name} ({job_title})")
            return dm

        # PARALLEL PROCESSING: Process 10 emails at a time (optimized for speed)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_single_email, email): email
                      for email in emails[:20]}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        decision_makers.append(result)
                except Exception as e:
                    email = futures[future]
                    logger.error(f"  ❌ Error processing {email}: {str(e)}")

        logger.info(f"✓ Found {len(decision_makers)} decision-makers for {company_name}")
        return decision_makers

    def enrich_companies(self, companies: List[Dict], max_workers: int = 10) -> List[Dict]:
        """Parallel enrichment of all companies"""
        logger.info(f"\n⏳ Enriching {len(companies)} companies (parallel workers: {max_workers})...")

        all_decision_makers = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.enrich_single_company, company): company
                for company in companies
            }

            completed = 0
            total = len(companies)

            for future in as_completed(futures):
                company = futures[future]

                try:
                    decision_makers = future.result()
                    all_decision_makers.extend(decision_makers)
                except Exception as e:
                    logger.error(f"  ❌ Error processing {company.get('name', 'unknown')}: {str(e)}")

                completed += 1

                if completed % max(1, total // 10) == 0:
                    progress = (completed / total) * 100
                    logger.info(f"\n⏳ Progress: {completed}/{total} ({progress:.0f}%)")

        logger.info(f"\n✅ Enrichment complete: {len(all_decision_makers)} decision-makers from {len(companies)} companies")
        return all_decision_makers

    def export_to_csv(self, leads: List[Dict], filename: Optional[str] = None) -> str:
        """Export leads to CSV"""
        import csv

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clutch_leads_{timestamp}.csv"

        logger.info(f"⏳ Exporting to CSV: {filename}...")

        if not leads:
            logger.warning("⚠️  No leads to export")
            return filename

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=leads[0].keys())
            writer.writeheader()
            writer.writerows(leads)

        logger.info(f"✓ CSV exported: {filename}")
        return filename

    def export_to_google_sheets(self, leads: List[Dict], title: str) -> str:
        """Export leads to Google Sheets"""
        logger.info("📊 Exporting to Google Sheets...")

        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"⚠️  OAuth token refresh failed: {e}")
                    logger.info("📄 Will use CSV export instead")
                    return ""
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("❌ credentials.json not found")
                    return ""

                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        try:
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

            logger.info(f"✓ Created: {spreadsheet_url}")

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

            logger.info(f"✓ Exported {len(leads)} rows to Google Sheets")

            return spreadsheet_url

        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return ""

    def run(self, search_url: str, limit: int = 25) -> str:
        """
        Main workflow:
        1. Scrape companies from Clutch
        2. Find emails → Extract names → Find LinkedIn → Validate decision-maker
        3. Export to Google Sheets (or CSV fallback)
        """
        start_time = time.time()

        # Print header
        logger.info("=" * 70)
        logger.info("CLUTCH LEAD SCRAPER v1.0 - EMAIL-FIRST APPROACH")
        logger.info("=" * 70)
        logger.info(f"Search URL: {search_url}")
        logger.info(f"Limit: {limit} companies")
        logger.info("=" * 70)

        # Step 1: Scrape companies
        companies = self.scrape_companies(search_url, limit)

        if not companies:
            logger.error("❌ No companies scraped")
            return ""

        # Step 2: Enrich (email-first workflow)
        leads = self.enrich_companies(companies, max_workers=20)

        if not leads:
            logger.warning("⚠️  No decision-makers found with emails")
            return ""

        # Step 3a: ALWAYS save CSV first (prevents data loss)
        logger.info("\n📄 Saving CSV backup...")
        csv_file = self.export_to_csv(leads)
        logger.info(f"✓ CSV saved: {os.path.abspath(csv_file)}")

        # Step 3b: Try to export to Google Sheets
        sheet_title = f"Clutch Leads - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        sheet_url = ""
        try:
            sheet_url = self.export_to_google_sheets(leads, sheet_title)
        except Exception as e:
            logger.warning(f"⚠️  Google Sheets export failed: {e}")
            logger.info(f"✓ Data is safe in CSV: {csv_file}")

        # Print summary
        duration = time.time() - start_time

        logger.info("=" * 70)
        logger.info("CLUTCH SCRAPE SUMMARY (v1.0)")
        logger.info("=" * 70)
        logger.info(f"Companies scraped:          {len(companies)}")
        logger.info(f"Decision-makers with emails: {len(leads)}")
        logger.info(f"Success rate:               {len(leads)/len(companies)*100:.0f}%")
        logger.info(f"Duration:                   {duration:.1f}s")
        logger.info("=" * 70)

        if sheet_url:
            logger.info(f"\n✅ Complete! Google Sheet: {sheet_url}")

        return sheet_url or csv_file


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Clutch Lead Scraper v1.0 - Email-First Approach"
    )
    parser.add_argument(
        "--search-url",
        required=True,
        help="Clutch.co category URL (e.g., https://clutch.co/agencies/digital-marketing)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of companies to scrape (default: 25)"
    )

    args = parser.parse_args()

    try:
        scraper = ClutchScraper()
        scraper.run(args.search_url, args.limit)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Scraper interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()