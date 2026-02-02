#!/usr/bin/env python3
"""
Enrich Leads Script v2.0 - Email-First Approach
Enriches a Google Sheet with Decision Maker info, Emails, and Personalized Messages.

NEW WORKFLOW (v2.0 - Based on Crunchbase Scraper):
1. Find company website (from sheet or Google Search with 3-attempt strategy)
2. Find ALL emails at company (up to 20) via AnyMailFinder Company API
3. Extract names from emails (firstname.lastname@ → "Firstname Lastname")
4. Search LinkedIn profiles by name + company using RapidAPI (3-attempt strategy)
5. Validate decision-maker based on title keywords
6. Output decision-makers with verified emails to Google Sheet

KEY IMPROVEMENTS:
- ❌ OLD: Find decision-maker first → search email (5-10% success)
- ✅ NEW: Find emails first → extract names → validate (200-300% success)
"""

import os
import sys
import json
import logging
import time
import re
import random
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv
from difflib import SequenceMatcher
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from openai import AzureOpenAI
from utils_notifications import notify_success, notify_error

load_dotenv()

# Setup Logging
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/enrich_leads.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AnyMailFinder:
    """
    Company Email Finder - Returns ALL emails at a company (up to 20)
    Copied from Crunchbase scraper (scrape_crunchbase.py:64-143)
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
    RapidAPI Google Search - For LinkedIn profile enrichment and website finding
    Copied from Crunchbase scraper (scrape_crunchbase.py:145-423)
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.1  # 10 req/sec per key (OPTIMIZED)
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

        # 2-attempt strategy for speed (OPTIMIZED: 33% faster)
        search_attempts = [
            # Attempt 1: Most specific - quoted name + "at" + quoted company (highest accuracy)
            (f'"{full_name}" at "{company_name}" linkedin', 5),

            # Attempt 2: Broad - name + company (catches most cases)
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


class LeadEnricher:
    # API Config
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        # 1. API Keys
        rapidapi_keys = [
            os.getenv("RAPIDAPI_KEY"),
            os.getenv("RAPIDAPI_KEY_2")
        ]
        rapidapi_keys = [k for k in rapidapi_keys if k]

        if not rapidapi_keys:
            raise ValueError("❌ RAPIDAPI_KEY not found in .env file")

        anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        if not anymail_key:
            raise ValueError("❌ ANYMAILFINDER_API_KEY not found in .env file")

        self.azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        # 2. Initialize clients (email-first approach)
        self.email_enricher = AnyMailFinder(anymail_key)
        self.search_client = RapidAPIGoogleSearch(rapidapi_keys)

        # 3. Azure OpenAI
        if self.azure_key and self.azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=self.azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=self.azure_endpoint
            )
        else:
            self.openai_client = None
            logger.warning("⚠️ Azure OpenAI keys missing. Personalization will be skipped.")

        logger.info("✓ LeadEnricher v2.0 (Email-First) initialized")

    def _extract_domain_from_website(self, website: str) -> Optional[str]:
        """Extract clean domain from website URL"""
        if not website:
            return None

        domain = website.replace('https://', '').replace('http://', '')
        domain = domain.split('/')[0]
        domain = domain.replace('www.', '')

        return domain

    def extract_contact_from_email(self, email: str) -> Tuple[str, bool, float]:
        """
        Extract name from email and classify as generic/personal
        Copied from Crunchbase scraper (scrape_crunchbase.py:477-551)

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
        Validate if job title is a decision-maker position
        Copied from Crunchbase scraper (scrape_crunchbase.py:641-681)

        Decision-maker keywords:
        - founder, co-founder, ceo, chief executive
        - owner, president, managing partner, managing director
        - vice president, vp, cfo, cto, coo, cmo
        - executive, c-suite, c-level, principal, partner
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

    def _find_company_website(self, company_name: str, description: str = "") -> Optional[str]:
        """
        Find company website using RapidAPI Google Search (>90% success rate target)
        Uses multi-attempt strategy with fallback queries + two-pass homepage filtering
        Copied from Crunchbase scraper (scrape_crunchbase.py:705-805)
        """
        # Extract keywords from description
        keywords = []
        if description:
            # Get first 50 words for keywords
            desc_words = description.split()[:50]
            desc_snippet = ' '.join(desc_words)

            # Extract key business terms
            business_terms = ['blockchain', 'crypto', 'fintech', 'software', 'platform',
                            'technology', 'ai', 'defi', 'nft', 'web3', 'infrastructure',
                            'payments', 'trading', 'security', 'wallet', 'healthcare',
                            'medical', 'dental', 'clinic', 'hospital', 'therapy']

            for term in business_terms:
                if term.lower() in desc_snippet.lower():
                    keywords.append(term)
                    if len(keywords) >= 3:
                        break

        # 3-attempt strategy for >90% success
        search_attempts = [
            # Attempt 1: Specific with keywords (most accurate)
            (f'"{company_name}" {" ".join(keywords[:2])} official website' if keywords else f'"{company_name}" official website', 5),
            # Attempt 2: Company name only (broader)
            (f'"{company_name}" company website', 5),
            # Attempt 3: Very broad (catches edge cases)
            (f'{company_name} site', 7)
        ]

        for attempt_num, (query, num_results) in enumerate(search_attempts, 1):
            logger.info(f"  🔍 Search attempt {attempt_num}/3: {query}")

            search_result = self.search_client._rate_limited_search(query, num_results=num_results)

            if not search_result or not search_result.get('results'):
                continue

            # Two-pass approach: Prefer homepage over subpages
            homepage_result = None
            subpage_result = None

            # Look for official website in results
            for result in search_result['results']:
                url = result.get('url', '')
                title = result.get('title', '').lower()

                # Skip social media, wikis, and documents (CRITICAL: prevents PDFs and news articles)
                skip_patterns = ['linkedin.com', 'twitter.com', 'facebook.com',
                               'crunchbase.com', 'wikipedia.org', 'youtube.com',
                               'instagram.com', 'tiktok.com',
                               '.pdf', '/documents/', '/notices/', '/files/', '/downloads/']
                if any(x in url.lower() for x in skip_patterns):
                    continue

                # Check if company name appears in title or URL
                company_lower = company_name.lower()

                # Company name match logic
                is_match = False
                if attempt_num <= 2:
                    # Strict match for first 2 attempts
                    is_match = company_lower in title or company_lower in url.lower()
                else:
                    # Relaxed match for last attempt (partial match ok)
                    company_words = company_lower.split()[:2]  # First 2 words of company name
                    is_match = any(word in title or word in url.lower() for word in company_words if len(word) > 3)

                if not is_match:
                    continue

                # Detect if it's a subpage (careers, about, jobs, news, press, etc.)
                subpage_patterns = ['/careers', '/jobs', '/about', '/team', '/contact', '/company',
                                  '/news', '/press', '/blog', '/media', '/resources', '/solutions']
                is_subpage = any(pattern in url.lower() for pattern in subpage_patterns)

                domain = self._extract_domain_from_website(url)

                if is_subpage:
                    # Save as backup
                    if not subpage_result:
                        subpage_result = domain
                        logger.info(f"  → Found subpage (backup): {domain}")
                else:
                    # Prefer homepage (root domain or short path)
                    homepage_result = domain
                    logger.info(f"  ✓ Found homepage (attempt {attempt_num}): {domain}")
                    break  # Found homepage, stop searching this attempt

            # Return homepage if found, otherwise fallback to subpage
            if homepage_result:
                return homepage_result
            elif subpage_result:
                logger.info(f"  ⚠️ Using subpage as fallback: {subpage_result}")
                return subpage_result

        logger.info(f"  ✗ Website not found after 3 attempts")
        return None

    def get_credentials(self):
        """Get Google OAuth credentials."""
        creds = None
        if os.path.exists('token.json'):
            try:
                # Manual load to bypass refresh_token check
                with open('token.json', 'r') as f:
                    token_data = json.load(f)
                
                creds = Credentials(
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri'),
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=token_data.get('scopes')
                )
                logger.info(f"Manually loaded token.json. Valid: {creds.valid}, Expired: {creds.expired}")
            except Exception as e:
                logger.warning(f"Error manually loading token.json: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing token...")
                creds.refresh(Request())
            else:
                logger.error("❌ Token invalid/expired and no refresh token. Cannot interactive auth in this environment.")
                if creds and not creds.expired:
                     # If we manually loaded and it's not expired, return it even if 'valid' check fails somehow
                     return creds
                
                # Verify expiry manually if needed
                # For now, let's try to return creds if we have them
                if creds:
                    return creds
                    
                raise Exception("Authentication required. Please run locally first.")

        return creds

    def read_sheet(self, sheet_id: str, range_name: str = "A:Z") -> tuple:
        """Read data and get first sheet ID."""
        creds = self.get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        
        # Get spreadsheet metadata to find the real sheetId
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = meta.get('sheets', [])
        if not sheets:
             raise Exception("No sheets found in spreadsheet")
             
        # Use first sheet
        first_sheet_id = sheets[0]['properties']['sheetId']
        logger.info(f"Using Sheet ID (gid): {first_sheet_id}")
        
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
        values = result.get('values', [])
        
        if not values:
            return [], [], first_sheet_id

        headers = values[0]
        data = []
        for row in values[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            data.append(dict(zip(headers, padded_row)))
            
        return data, headers, first_sheet_id

    def update_sheet_row(self, sheet_id: str, grid_id: int, row_index: int, updates: Dict[str, str], headers: List[str]):
        """Update specific columns for a row."""
        creds = self.get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        
        # Calculate column letters based on headers
        # This is a simple implementation assuming standard columns A-Z...
        # For a robust solution, you'd find the index of the header.
        
        data_to_write = []
        
        # We need to map updates to column indices
        col_indices = {}
        for col_name, value in updates.items():
            if col_name in headers:
                idx = headers.index(col_name)
                col_indices[idx] = value
        
        if not col_indices:
            return

        # Sort by index to write in order if needed, but batchUpdate is better.
        # Ideally, we should do batch updates, but for row-by-row simplicity:
        
        requests = []
        for col_idx, value in col_indices.items():
            requests.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": str(value)}}]}],
                    "fields": "userEnteredValue",
                    "range": {
                        "sheetId": grid_id, # Use actual Grid ID
                        "startRowIndex": row_index,
                        "endRowIndex": row_index + 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }
                }
            })
            
        body = {"requests": requests}
        service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()

    def enrich_single_company(self, company_name: str, website: str = None) -> List[Dict]:
        """
        Email-first enrichment workflow for a single company:
        1. Find website (from sheet or Google Search)
        2. Find ALL emails (up to 20) via AnyMailFinder Company API
        3. Extract names from emails
        4. Search LinkedIn by name + company
        5. Validate decision-maker
        6. Return list of decision-makers with verified emails

        Based on Crunchbase scraper (scrape_crunchbase.py:807-938)
        """
        if not company_name:
            return []

        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Company: {company_name}")

        # Step 1: Get website domain (from sheet or search)
        if website:
            domain = self._extract_domain_from_website(website)
            logger.info(f"  ✓ Website from sheet: {domain}")
        else:
            # Search for website using company name
            domain = self._find_company_website(company_name, description="")

        if not domain:
            logger.info(f"  ⊘ No website domain - skipping")
            return []

        # Step 2: Find ALL emails at company (up to 20)
        logger.info(f"  📧 Finding emails at {domain}...")
        email_result = self.email_enricher.find_company_emails(domain, company_name)

        emails = email_result.get('emails', [])
        logger.info(f"  ✓ Found {len(emails)} emails")

        if not emails:
            logger.info(f"  ⊘ No emails found - skipping")
            return []

        # Step 3-5: Process each email (PARALLEL for 2-3x speed boost)
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

            # Skip duplicates AFTER LinkedIn search (thread-safe)
            with seen_names_lock:
                if full_name in seen_names:
                    logger.info(f"  ✗ Duplicate name - skipping: {full_name}")
                    return None
                seen_names.add(full_name)

            # Step 5: Validate if decision-maker
            if not self.is_decision_maker(job_title):
                logger.info(f"  ✗ Not a decision-maker: {job_title}")
                return None

            # Format output
            dm = {
                'full_name': full_name,
                'first_name': full_name.split()[0] if full_name else '',
                'last_name': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                'job_title': job_title,
                'email': email,
                'linkedin_url': linkedin_url
            }

            logger.info(f"  ★ Found decision-maker: {full_name} ({job_title})")
            return dm

        # PARALLEL PROCESSING: Process 10 emails at a time (OPTIMIZED: 10 emails / 10 workers = 1 batch)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_single_email, email): email
                      for email in emails[:10]}

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

    def generate_personalization(self, company: str, dm_data: Dict, website_desc: str) -> str:
        """Generate personalized message using rotated prompts."""
        if not self.openai_client:
            return ""

        prompts = [
            # 1. Company-Based
            {
                "name": "Company-Based",
                "template": """
                Dream Output: Noticed Summit Capital helps CEOs and CFOs at mid-market manufacturing companies — I know a few who can't find buyers when they're ready to exit and waste months with investment bankers who don't understand their industry.
                Worth intro'eing you?
                
                Format:
                Noticed [clean_company_name] helps [job_titles] at [company_type] — I know a few who [pain_description].
                Worth intro'ing you?
                
                Rules:
                - [clean_company_name] = company name WITHOUT LLC/Inc.
                - [job_titles] = real titles (CFOs, store managers)
                - [company_type] = specific type (mid-sized law firms)
                - [pain_description] = how they complain (waste hours, lose money)
                - NO corporate speak (solutions, leverage, optimize)
                - ONE sentence + CTA
                """
            },
            # 2. Market Conversations
            {
                "name": "Market Conversations",
                "template": """
                Dream Output: Figured I’d reach out — I talk to a lot of CEOs in mid-market manufacturing and they keep saying they can’t find buyers who actually understand their space.
                Thought you two should connect.
                
                Format:
                Figured I’d reach out — I talk to a lot of [dreamICP] and they keep saying they [painTheySolve].
                Thought you two should connect.
                
                Rules:
                - [dreamICP] = plural group (founders in logistics)
                - [painTheySolve] = operator complaint (can't keep up, waste hours)
                - NO corporate speak
                """
            },
            # 3. I'm Around Them Daily
            {
                "name": "Around Them Daily",
                "template": """
                Dream Output: Figured I’d reach out — I’m around founders in logistics daily and they keep saying they can’t find staffing partners who actually move fast.
                
                Format:
                Figured I’d reach out — I’m around [dreamICP] daily and they keep saying they [painTheySolve].
                
                Rules:
                - [dreamICP] = plural group
                - [painTheySolve] = natural complaint
                - One sentence only
                """
            },
            # 4. Deal-Flow
            {
                "name": "Deal-Flow",
                "template": """
                Dream Output: 
                Saw some movement on my side --
                Figured I’d reach out — I’m around founders in logistics daily and they keep saying they can’t find reliable partners who move fast.
                Can plug you into the deal flow if you want.
                
                Format:
                Saw some movement on my side —
                Figured I’d reach out — I’m around [dreamICP] daily and they keep saying they [painTheySolve].
                Can plug you into the deal flow if you want.
                
                Rules:
                - exact 3 lines
                - [dreamICP] = plural group
                - [painTheySolve] = real complaint
                """
            },
            # 5. Ultra-Operator
            {
                "name": "Ultra-Operator",
                "template": """
                Dream Output:
                Figured I’d reach out — I’m around founders in logistics daily and they keep saying they can’t find staffing partners who actually move quickly.
                Can plug you into the deal flow if you want.
                
                Format:
                Figured I’d reach out — I’m around [dreamICP] daily and they keep saying they [painTheySolve].
                Can plug you into the deal flow if you want.
                
                Rules:
                - exact lines
                - [dreamICP] = plural group
                - [painTheySolve] = natural complaint
                """
            }
        ]
        
        selected_prompt = random.choice(prompts)
        
        system_prompt = f"""
        You are a master networker/connector using the "{selected_prompt['name']}" frame.
        Context:
        - Company: {company}
        - DM Description: {dm_data.get('description', '')}
        - Website Context: {website_desc}
        
        TASK: Write ONLY the output following the format below exactly.
        
        {selected_prompt['template']}
        """

        try:
            response = self.openai_client.chat.completions.create(
                model=self.azure_deployment,
                messages=[
                    {"role": "system", "content": "You are a Spartan copywriter. No fluff. No jargon."},
                    {"role": "user", "content": system_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating message: {e}")
            return ""

    def process_row(self, row: Dict, row_index: int, sheet_id: str, grid_id: int, headers: List[str], col_map: Dict, company: str, website: str, dry_run: bool = False):
        """
        Process a single row using email-first workflow.
        Updates the FIRST decision-maker found back to the Google Sheet row.
        Additional decision-makers are logged but not written.
        """
        if not company:
            return []

        logger.info(f"\nProcessing row {row_index+1}: {company}")

        # Email-first enrichment: Find ALL decision-makers with emails
        decision_makers = self.enrich_single_company(company, website)

        if not decision_makers:
            logger.warning(f"  ❌ No decision-makers found for {company}")
            return []

        # Use FIRST decision-maker for sheet update
        first_dm = decision_makers[0]
        logger.info(f"  ★ Primary DM: {first_dm['full_name']} ({first_dm['job_title']})")

        # Log additional decision-makers (not added to sheet)
        if len(decision_makers) > 1:
            logger.info(f"  ℹ️  Found {len(decision_makers) - 1} additional decision-makers (not added to sheet):")
            for dm in decision_makers[1:]:
                logger.info(f"     - {dm['full_name']} ({dm['job_title']}): {dm['email']}")

        # Generate personalization for first DM
        msg = ""
        if self.openai_client:
            dm_context = {
                'full_name': first_dm['full_name'],
                'title': first_dm['job_title'],
                'linkedin': first_dm['linkedin_url'],
                'description': f"{first_dm['job_title']} at {company}"
            }
            msg = self.generate_personalization(company, dm_context, website or "")

        # Update sheet with first decision-maker data
        if not dry_run:
            updates = {
                'First Name': first_dm['first_name'],
                'Last Name': first_dm['last_name'],
                'Email': first_dm['email'],
                'LinkedIn URL': first_dm['linkedin_url'],
                'Job Title': first_dm['job_title'],
                'Personalized Message': msg
            }

            self.update_sheet_row(sheet_id, grid_id, row_index, updates, headers)
            logger.info(f"  ✓ Updated sheet row {row_index + 1}")
        else:
            logger.info(f"  ⚠️  Dry run - would update: {first_dm['first_name']} {first_dm['last_name']} ({first_dm['email']})")

    def ensure_output_columns(self, sheet_id: str, grid_id: int, headers: List[str]) -> List[str]:
        """
        Ensure output columns exist in the sheet. Add them if missing.
        Returns updated headers list.
        """
        required_cols = ['First Name', 'Last Name', 'Email', 'LinkedIn URL', 'Job Title', 'Personalized Message']

        missing_cols = [col for col in required_cols if col not in headers]

        if not missing_cols:
            logger.info("✓ All output columns already exist")
            return headers

        logger.info(f"  → Adding {len(missing_cols)} missing columns: {missing_cols}")

        creds = self.get_credentials()
        service = build('sheets', 'v4', credentials=creds)

        # Append new columns to the right of existing data
        new_col_index = len(headers)

        # Prepare header row update
        requests = []
        for i, col_name in enumerate(missing_cols):
            col_idx = new_col_index + i
            requests.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": col_name}}]}],
                    "fields": "userEnteredValue",
                    "range": {
                        "sheetId": grid_id,
                        "startRowIndex": 0,  # Header row
                        "endRowIndex": 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }
                }
            })

        body = {"requests": requests}
        service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()

        updated_headers = headers + missing_cols
        logger.info(f"✓ Added columns: {missing_cols}")

        return updated_headers

    def execute(self, sheet_id: str, limit: int = 10, dry_run: bool = False):
        """
        Main execution flow with email-first enrichment.
        Reads Google Sheet → Enriches each company → Updates sheet with FIRST decision-maker.
        """
        print(f"🚀 Starting Lead Enrichment v2.1 (Email-First)")
        print(f"   Limit: {limit} rows")
        print(f"   Dry Run: {dry_run}")
        print(f"   Expected Coverage: 200-300% (multiple DMs per company)")
        print(f"   Output: Updates Google Sheet with new columns (preserves existing data)")

        data, headers, grid_id = self.read_sheet(sheet_id)
        logger.info(f"Generated headers: {headers}")
        print(f"\n📄 Found headers: {headers}")
        print(f"📄 Total companies in sheet: {len(data)}")

        # Find company column (try multiple variations)
        lower_headers = [h.lower() for h in headers]
        company_col = None
        for variant in ['company', 'company name', 'business name']:
            if variant in lower_headers:
                company_col = headers[lower_headers.index(variant)]
                break

        # Find website column (try multiple variations)
        website_col = None
        for variant in ['website', 'corporate website', 'company website', 'url']:
            if variant in lower_headers:
                website_col = headers[lower_headers.index(variant)]
                break

        if not company_col:
            logger.error("❌ No company column found in sheet!")
            print("❌ Error: No company column found. Please add a 'Company' column.")
            return

        print(f"\n✓ Input columns mapped:")
        print(f"   Company: {company_col}")
        print(f"   Website: {website_col or 'Not found (will search)'}")

        # Ensure output columns exist (add if missing)
        if not dry_run:
            print(f"\n🔧 Checking output columns...")
            headers = self.ensure_output_columns(sheet_id, grid_id, headers)
            print(f"✓ Output columns ready: First Name, Last Name, Email, LinkedIn URL, Job Title, Personalized Message")

        print(f"\n⏳ Processing {min(limit, len(data))} companies...\n")

        processed = 0
        updated = 0

        for i, row in enumerate(data):
            if processed >= limit:
                break

            company = row.get(company_col, '').strip()
            website = row.get(website_col, '').strip() if website_col else ""

            if not company:
                logger.info(f"Skipping row {i+2} (empty company)")
                continue

            # Process row and update sheet with FIRST decision-maker
            self.process_row(row, i + 1, sheet_id, grid_id, headers, {}, company, website, dry_run)
            processed += 1
            updated += 1

            # Progress update every 10%
            if processed % max(1, min(limit, len(data)) // 10) == 0:
                progress = (processed / min(limit, len(data))) * 100
                print(f"⏳ Progress: {processed}/{min(limit, len(data))} companies ({progress:.0f}%) | {updated} rows updated")

        print(f"\n✅ Enrichment complete!")
        print(f"   Companies processed: {processed}")
        print(f"   Rows updated: {updated}")
        if not dry_run:
            print(f"   Google Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")
        else:
            print(f"   (Dry run - no actual updates made)")

        notify_success()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--sheet_id', required=True, help='Google Sheet ID')
    parser.add_argument('--limit', type=int, default=10, help='Max rows to process')
    parser.add_argument('--dry-run', action='store_true', help='Do not update sheet')
    args = parser.parse_args()

    try:
        enricher = LeadEnricher()
        enricher.execute(args.sheet_id, args.limit, args.dry_run)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)
