#!/usr/bin/env python3
"""
Google Maps Lead Scraper v7.0 - RapidAPI Edition
Exports ALL contacts with LinkedIn titles (max 10 per company)
Uses RapidAPI Google Search for accurate contact enrichment
Follows directives/scrape_google_maps_leads.md workflow exactly
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
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from difflib import SequenceMatcher
from dotenv import load_dotenv
from apify_client import ApifyClient
from exa_py import Exa
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils_notifications import notify_success, notify_error

load_dotenv()

os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/google_maps_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class RapidAPIGoogleSearch:
    """RapidAPI Google Search - For LinkedIn profile enrichment."""

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.rate_limit_lock = Lock()
        self.last_call_time = 0
        self.min_delay = 0.2  # 5 req/sec per key
        logger.info(f"✓ RapidAPI Google Search initialized")
        logger.info(f"  → Keys: {len(api_keys)}")
        logger.info(f"  → Rate: 5 req/sec per key")

    def _get_current_key(self) -> str:
        """Rotate between API keys for higher throughput."""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _rate_limited_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
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
                    # Rate limited - wait longer
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

    def _normalize_company(self, text: str) -> str:
        """Normalize company name for comparison."""
        if not text:
            return ""
        text = text.lower()
        # Replace & with and
        text = text.replace('&', 'and')
        # Remove common suffixes
        suffixes = ['inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co', 'clinic', 'center']
        for suffix in suffixes:
            text = re.sub(rf'\b{suffix}\.?\b', '', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove special characters
        text = re.sub(r'[^\w\s]', '', text)
        return text

    def _is_company_match(self, company1: str, company2: str, threshold: float = 0.6) -> bool:
        """Fuzzy match company names."""
        if not company1 or not company2:
            return False
        
        norm1 = self._normalize_company(company1)
        norm2 = self._normalize_company(company2)
        
        if norm1 in norm2 or norm2 in norm1:
            return True
            
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio() >= threshold

    def _is_name_match(self, name1: str, name2: str, threshold: float = 0.7) -> bool:
        """Fuzzy match person names."""
        if not name1 or not name2:
            return False
            
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Direct substring match (e.g. "Sabrina" in "Sabrina Smith")
        if n1 in n2 or n2 in n1:
            return True
            
        matcher = SequenceMatcher(None, n1, n2)
        return matcher.ratio() >= threshold


class RapidAPIContactEnricher(RapidAPIGoogleSearch):
    """Extended RapidAPI search with contact enrichment methods."""

    def search_by_name(self, full_name: str, company_name: str, location: str = None) -> Dict:
        """
        Optimized person search (from extracted email name).
        Format: [name] at [company] canada linkedin
        Max 2 attempts.
        """
        result = {
            'full_name': full_name,
            'job_title': '',
            'contact_linkedin': ''
        }

        # Attempt 1: "full_name at company_name canada linkedin"
        q1 = f'"{full_name}" at "{company_name}" canada linkedin'
        
        logger.debug(f"  → Query 1: {q1}")
        data = self._rate_limited_search(q1, num_results=5)

        if data and data.get('results'):
            found = self._extract_person_from_results(data['results'], full_name, company_name, require_linkedin=True)
            if found['full_name']:
                return found

        # Attempt 2: "full_name company_name canada linkedin"
        q2 = f'{full_name} "{company_name}" canada linkedin'
        
        logger.debug(f"  → Query 2 (Retry): {q2}")
        data = self._rate_limited_search(q2, num_results=5)

        if data and data.get('results'):
            found = self._extract_person_from_results(data['results'], full_name, company_name, require_linkedin=True)
            if found['full_name']:
                return found

        logger.info(f"  ✗ Person '{full_name}' not found on LinkedIn after 2 attempts.")
        # Return result with Name (from email) but blank title/linkedin
        return result

    def _extract_person_from_results(self, results: List[Dict], search_name: str, company_name: str,
                                      require_linkedin: bool = False, allow_website: bool = False) -> Dict:
        """
        Extract person info from search results.

        Args:
            results: List of search results
            search_name: Name we're searching for
            company_name: Company name for validation
            require_linkedin: If True, only accept LinkedIn URLs
            allow_website: If True, accept company website/team pages

        Returns:
            Dict with full_name, job_title, contact_linkedin
        """
        result = {
            'full_name': '',
            'job_title': '',
            'contact_linkedin': ''
        }

        for item in results:
            url = item.get('url', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')

            # URL filtering
            if require_linkedin and 'linkedin.com/in/' not in url:
                continue

            # Extract name from title
            extracted_name = self._extract_name_from_title(title)
            if not extracted_name:
                continue

            # NAME VALIDATION: Must match search name
            if not self._is_name_match(search_name, extracted_name, threshold=0.6):
                logger.debug(f"  ⚠️ Name mismatch: '{extracted_name}' vs '{search_name}'")
                continue

            # Validate it's a real person name (not company/generic)
            if not self._validate_person_name(extracted_name, company_name):
                logger.debug(f"  ⚠️ Invalid person name: '{extracted_name}'")
                continue

            # Extract job title from title + snippet
            job_title = self._extract_title_from_search(title, snippet)

            result['full_name'] = extracted_name
            result['job_title'] = job_title if job_title else ""
            result['contact_linkedin'] = url if 'linkedin.com' in url else ""

            source_type = "LinkedIn" if 'linkedin.com' in url else "Website"
            logger.info(f"  ✓ Found on {source_type}: {extracted_name} - {job_title}")
            return result

        return result

    def _extract_name_from_title(self, title: str) -> str:
        """Extract person name from search result title."""
        if not title:
            return ""

        # Remove "LinkedIn" suffix if present
        if 'LinkedIn' in title:
            title = title.split('LinkedIn')[0].strip()

        # Common separators
        for separator in [' - ', ' | ', ' · ', ', ', ' at ', ' @ ']:
            if separator in title:
                name = title.split(separator)[0].strip()
                # Clean trailing punctuation
                name = re.sub(r'[^\w\s]$', '', name)
                if len(name) >= 3:
                    return name

        # No separator - return cleaned title
        cleaned = re.sub(r'[^\w\s]$', '', title.strip())
        return cleaned if len(cleaned) >= 3 else ""

    def _extract_title_from_search(self, title: str, snippet: str) -> str:
        """
        Extract job title from search result (title + snippet).
        Enhanced patterns for medical/aesthetic industry.
        """
        combined = title + ' ' + snippet

        # Pattern groups (ordered by reliability)
        patterns = [
            # LinkedIn standard: "Name - Title at Company"
            r' - ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+|\s*-\s*)',
            r' \| ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',
            r' · ([^-|·@,]+?)(?:\s+at\s+|\s+@\s+)',

            # Comma format: "Name, Title at Company"
            r', ([^,]+?)(?:\s+at\s+|\s+@\s+)',

            # Snippet extraction: "is the CEO of", "works as Director"
            r'(?:is|as|works as|serves as)\s+(?:a|an|the)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})',

            # Title keywords (medical/aesthetic specific)
            r'\b((?:Chief|Senior|Junior|Lead|Head|Vice President|VP|Director|Manager|Owner|Founder|Co-Founder|CEO|COO|CFO|President|Partner|Specialist|Consultant|Coordinator|Administrator|Executive|Medical Director|Practice Manager|Clinic Manager|Nurse Injector|Advanced Nurse|Aesthetician|Esthetician|Doctor|Dr\.|Physician|Dentist|Dermatologist)\s*(?:of|at|for|&)?\s*[A-Za-z\s]{0,30})\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                title_text = match.group(1).strip()

                # Validate title:
                # - Length: 3-100 chars
                # - Not just punctuation
                # - Not a URL fragment
                if 3 <= len(title_text) <= 100:
                    # Clean up
                    title_text = re.sub(r'\s+', ' ', title_text)  # Normalize spaces
                    title_text = re.sub(r'[^\w\s&-]$', '', title_text)  # Remove trailing punct

                    # Validate it's not garbage
                    if not re.search(r'(http|www\.|\.com|linkedin)', title_text, re.IGNORECASE):
                        return title_text.strip()

        return ""

    def _validate_person_name(self, name: str, company_name: str) -> bool:
        """
        STRICT validation: Only accept real person names.
        Reject: search queries, yelp titles, service names, button text, company names.
        """
        if not name or len(name) < 2:
            return False

        name_lower = name.lower().strip()

        # CRITICAL: Reject if too long (likely description/sentence)
        if len(name) > 40:
            return False

        # CRITICAL: Reject search queries, yelp spam, service descriptions
        garbage_indicators = [
            'top 10', 'best', 'affordable', 'near me', 'in edmonton', 'in st albert', 'in red deer',
            'bioidentical', 'hormone', 'replacement', 'therapy', 'bhrt',
            'skin tightening', 'treatments', 'facials', 'massage', 'laser',
            'claim business', 'request', 'contact us', 'about us', 'your role',
            'health centre', 'health professionals', 'medical clinic', 'medical group',
            'hair by design', 'inside out',  # Specific company names
        ]

        for indicator in garbage_indicators:
            if indicator in name_lower:
                return False

        # Reject if contains numbers (except "Dr." prefix)
        if re.search(r'\d', name) and not name_lower.startswith('dr'):
            return False

        # Invalid patterns
        invalid_patterns = [
            r'^(our team|division|home|about|contact|info|team|staff|directory|members|claim|request)$',
            r'^[A-Z\s]{3,}$',  # All caps
            r'^\d',  # Starts with number
            r'^(dr|mr|ms|mrs|miss)\.?\s*$',  # Only title
            r'\b(top|best|near|affordable|treatment|service|clinic|centre|center)\b',
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, name_lower):
                return False

        # Don't accept company name as person
        if self._is_company_match(name, company_name, threshold=0.7):
            return False

        # Reject business keywords
        business_keywords = ['inc', 'llc', 'ltd', 'corp', 'clinic', 'center', 'centre', 'medical', 'spa', 'aesthetics', 'beauty', 'wellness', 'health', 'professionals']
        if any(keyword in name_lower for keyword in business_keywords):
            return False

        # Must contain at least 2 consecutive letters
        if not re.search(r'[a-zA-Z]{2,}', name):
            return False

        # STRICT: Real names are typically 1-3 words
        words = name.split()
        if len(words) > 4:  # "Shannon", "Dr. Johnson", "Mary Anne Smith" OK, long sentences NO
            return False

        return True

    def find_founder_by_company(self, company_name: str, location: str = None) -> Dict:
        """
        Optimized founder search.
        Format: founder/ceo at [companyname] canada linkedin
        Max 2 attempts.
        """
        result = {
            'full_name': '',
            'job_title': '',
            'contact_linkedin': ''
        }

        # Attempt 1: Standard query
        # "founder/ceo at [company_name] canada linkedin"
        q1 = f'founder/ceo at "{company_name}" canada linkedin'
        
        logger.debug(f"  → Query 1: {q1}")
        data = self._rate_limited_search(q1, num_results=5)

        if data and data.get('results'):
            found = self._process_founder_results(data['results'], company_name, threshold=0.7)
            if found['full_name']:
                return found

        # Attempt 2: Fallback (broader)
        # "[company_name] owner OR founder OR ceo canada linkedin"
        q2 = f'"{company_name}" owner OR founder OR ceo canada linkedin'
        
        logger.debug(f"  → Query 2 (Retry): {q2}")
        data = self._rate_limited_search(q2, num_results=5)

        if data and data.get('results'):
            found = self._process_founder_results(data['results'], company_name, threshold=0.6)
            if found['full_name']:
                return found

        logger.info(f"  ✗ Founder not found after 2 attempts.")
        return result

        if data and data.get('results'):
            found = self._process_founder_results(data['results'], company_name, threshold=0.6)
            if found['full_name']:
                return found

        # STRICT: If LinkedIn not found, return empty (no garbage acceptance)
        # GPT-4 web search removed after testing (0/32 success rate)
        logger.info(f"  ✗ LinkedIn not found for founder/decision maker - skipping (no garbage acceptance)")
        return result

    def _process_founder_results(self, results: List[Dict], company_name: str,
                                  threshold: float = 0.6, allow_non_linkedin: bool = True) -> Dict:
        """
        Process search results to find founder/decision maker.
        Two-pass strategy:
        1. LinkedIn profiles (highest confidence)
        2. Credible web sources with strict validation (company sites, Wikipedia, news)
        """
        result = {
            'full_name': '',
            'job_title': '',
            'contact_linkedin': ''
        }

        # PASS 1: Prioritize LinkedIn profiles (highest confidence)
        for item in results:
            url = item.get('url', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')

            # Only process LinkedIn in this pass
            if 'linkedin.com/in/' not in url:
                continue

            # Company validation (title + snippet)
            full_text = (title + ' ' + snippet).lower()
            if not self._is_company_match(company_name, full_text, threshold=threshold):
                continue

            # Extract name
            extracted_name = self._extract_name_from_title(title)
            if not extracted_name or len(extracted_name) < 3:
                continue

            # Validate it's a person, not company
            if not self._validate_person_name(extracted_name, company_name):
                continue

            # Extract title
            job_title = self._extract_title_from_search(title, snippet)

            result['full_name'] = extracted_name
            result['job_title'] = job_title if job_title else ""
            result['contact_linkedin'] = url

            logger.info(f"  ✓ Found on LinkedIn: {extracted_name} - {job_title}")
            return result

        # PASS 2: Credible web sources (if LinkedIn not found and allowed)
        if allow_non_linkedin and not result['full_name']:
            logger.debug("  → LinkedIn not found, checking credible web sources...")
            
            for item in results:
                url = item.get('url', '')
                title = item.get('title', '')
                snippet = item.get('snippet', '')

                # Skip LinkedIn (already checked)
                if 'linkedin.com/in/' in url:
                    continue

                # Check if source is credible
                if not self._is_credible_source(url, company_name):
                    logger.debug(f"  ⚠️ Skipped non-credible source: {url}")
                    continue

                # Extract name
                extracted_name = self._extract_name_from_title(title)
                if not extracted_name or len(extracted_name) < 3:
                    continue

                # STRICT validation for web sources
                if not self._validate_founder_from_web(extracted_name, company_name, item):
                    logger.debug(f"  ⚠️ Failed strict validation: {extracted_name}")
                    continue

                # Extract title
                job_title = self._extract_title_from_search(title, snippet)

                result['full_name'] = extracted_name
                result['job_title'] = job_title if job_title else ""
                result['contact_linkedin'] = ''  # No LinkedIn for web sources

                source_type = "Wikipedia" if 'wikipedia.org' in url else "Company Website"
                logger.info(f"  ✓ Found on {source_type}: {extracted_name} - {job_title}")
                return result

        # If nothing found, return empty
        if not result['full_name']:
            logger.info(f"  ✗ No decision maker found (checked LinkedIn + credible web sources)")
        
        return result

    def find_company_social(self, company_name: str, location: str = None) -> str:
        """Find company Instagram or Facebook."""
        # Try Instagram first
        query = f'"{company_name}" site:instagram.com'
        if location:
            query += f' "{location}"'

        data = self._rate_limited_search(query, num_results=5)

        if data and data.get('results'):
            for item in data['results']:
                url = item.get('url', '')
                if 'instagram.com/' in url and '/p/' not in url:
                    return url

        # Try Facebook if no Instagram
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

    def _is_credible_source(self, url: str, company_name: str = None) -> bool:
        """
        Check if URL is from a credible source for founder information.
        Accepts: LinkedIn, Wikipedia, company's own website, reputable news.
        Rejects: Yelp, review sites, directories, social media posts.
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # ALWAYS accept LinkedIn profiles
        if 'linkedin.com/in/' in url_lower:
            return True
        
        # Accept Wikipedia
        if 'wikipedia.org' in url_lower:
            return True
        
        # Accept reputable news/business sites
        credible_news = [
            'forbes.com', 'bloomberg.com', 'reuters.com',
            'businessinsider.com', 'entrepreneur.com',
            'inc.com', 'fastcompany.com'
        ]
        if any(news in url_lower for news in credible_news):
            return True
        
        # BLOCK review sites and directories
        blocked_domains = [
            'yelp.com', 'yellowpages.com', 'google.com/maps',
            'facebook.com/posts', 'instagram.com/p/',
            'tripadvisor.com', 'healthgrades.com',
            'ratemds.com', 'vitals.com'
        ]
        if any(blocked in url_lower for blocked in blocked_domains):
            return False
        
        # Check if it's the company's own website
        if company_name:
            # Extract domain from URL
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
                # Remove www.
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                # Normalize company name for matching
                company_normalized = self._normalize_company(company_name)
                
                # Check if company name is in domain
                # e.g., "formface.com" matches "Form Face & Body"
                if company_normalized and len(company_normalized) > 3:
                    # Remove spaces and special chars from company name
                    company_clean = re.sub(r'[^a-z0-9]', '', company_normalized)
                    domain_clean = re.sub(r'[^a-z0-9]', '', domain)
                    
                    if company_clean in domain_clean or domain_clean in company_clean:
                        return True
            except:
                pass
        
        return False

    def _validate_founder_from_web(self, name: str, company: str, search_result: dict) -> bool:
        """
        STRICT validation for founder names from non-LinkedIn sources.
        Only accept if name appears in context with founder/CEO keywords.
        """
        if not name or not search_result:
            return False
        
        # 1. Basic person name validation (reuse existing)
        if not self._validate_person_name(name, company):
            return False
        
        # 2. Get title and snippet
        title = search_result.get('title', '').lower()
        snippet = search_result.get('snippet', '').lower()
        combined = title + ' ' + snippet
        
        # 3. Must have founder/CEO/decision maker keywords
        decision_maker_keywords = [
            'founder', 'co-founder', 'ceo', 'owner', 'president',
            'chief executive', 'managing director', 'executive director',
            'medical director', 'practice owner'
        ]
        
        has_dm_keyword = any(kw in combined for kw in decision_maker_keywords)
        if not has_dm_keyword:
            logger.debug(f"  ⚠️ No decision maker keyword found for '{name}'")
            return False
        
        # 4. Name must appear near decision maker keyword (within 100 chars)
        name_lower = name.lower()
        if name_lower not in combined:
            return False
        
        # Find position of name and closest keyword
        name_pos = combined.find(name_lower)
        min_distance = float('inf')
        
        for kw in decision_maker_keywords:
            if kw in combined:
                kw_pos = combined.find(kw)
                distance = abs(kw_pos - name_pos)
                min_distance = min(min_distance, distance)
        
        if min_distance > 100:
            logger.debug(f"  ⚠️ Name '{name}' too far from decision maker keyword (distance: {min_distance})")
            return False
        
        # 5. Company name should appear in result
        if not self._is_company_match(company, combined, threshold=0.5):
            logger.debug(f"  ⚠️ Company '{company}' not found in result")
            return False
        
        return True


class AnyMailFinder:
    """Company Email Finder - Returns ALL emails at a company (up to 20)."""

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


class GoogleMapsLeadScraper:
    """Google Maps Lead Scraper - Following MD file workflow."""

    ACTOR_ID = "nwua9Gu5YrADL7ZDj"
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        self.apify_token = os.getenv("APIFY_API_KEY")
        self.anymailfinder_token = os.getenv("ANYMAILFINDER_API_KEY")
        self.exa_token = os.getenv("EXA_API_KEY")

        if not self.apify_token:
            raise ValueError("APIFY_API_KEY not found")

        if not self.anymailfinder_token:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found")
            self.email_enricher = None
        else:
            self.email_enricher = AnyMailFinder(self.anymailfinder_token)

        # Use RapidAPI Google Search for LinkedIn enrichment
        rapidapi_keys = [
            os.getenv("RAPIDAPI_KEY"),
            os.getenv("RAPIDAPI_KEY_2")
        ]
        rapidapi_keys = [k for k in rapidapi_keys if k]  # Filter None values

        if not rapidapi_keys:
            logger.warning("⚠️ RAPIDAPI_KEY not found - contact enrichment disabled")
            self.search_client = None
        else:
            self.search_client = RapidAPIContactEnricher(rapidapi_keys)

        self.apify_client = ApifyClient(self.apify_token)
        self.output_dir = '.tmp/scraped_data'
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info("✓ GoogleMapsLeadScraper initialized (RapidAPI v7.0)")

    def load_existing_domains(self, csv_path: str) -> set:
        """
        Load domains from existing CSV to avoid duplicates.
        Returns set of domains to exclude.
        """
        if not os.path.exists(csv_path):
            logger.warning(f"⚠️  Exclude file not found: {csv_path}")
            return set()

        logger.info(f"📋 Loading existing leads from: {csv_path}")

        exclude_domains = set()

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                website = row.get('Website', '') or row.get('website', '')
                if website:
                    domain = self.extract_domain(website)
                    if domain:
                        exclude_domains.add(domain)

        logger.info(f"   ✓ Loaded {len(exclude_domains)} domains to exclude")
        return exclude_domains

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

    def normalize_phone(self, phone: str) -> str:
        if not phone:
            return ""
        return re.sub(r'[^\d+]', '', phone)

    def is_valid_job_title(self, job_title: str) -> tuple:
        """
        Filter out irrelevant job titles using blacklist AND classify role type.
        Returns: (is_valid: bool, role_type: str)

        Blacklist includes:
        - Students, Interns (not decision makers)
        - Low-level positions (Cashier, Driver, Security)
        - Irrelevant roles (Contractor, Freelancer)
        - Generic terms that aren't real titles

        Role Types:
        - Executive: C-level, VP, President, Owner, Founder
        - Manager: Director, Manager, Head, Team Lead
        - Professional: Specialist, Analyst, Engineer, Consultant
        - Other: Valid but doesn't match above categories
        - Blacklisted: Invalid title
        """
        if not job_title or len(job_title) < 3:
            return (False, 'Unknown')

        job_title_lower = job_title.lower()

        # Negative title blacklist (case-insensitive)
        blacklist_terms = [
            'student', 'intern', 'trainee', 'apprentice',
            'cashier', 'driver', 'security', 'guard',
            'janitor', 'cleaner', 'maintenance',
            'contractor', 'freelancer', 'volunteer',
            'seeking', 'looking for', 'open to',
            'former', 'ex-', 'previous', 'past',
            'unemployed', 'between jobs',
            'retail', 'sales associate', 'clerk',
            'receptionist', 'front desk',
            'waiter', 'waitress', 'server', 'bartender'
        ]

        for term in blacklist_terms:
            if term in job_title_lower:
                logger.debug(f"  ⚠️ Blacklisted title: '{job_title}' (contains '{term}')")
                return (False, 'Blacklisted')

        # ROLE TYPE CLASSIFICATION (for valid titles only)

        # Executive: C-level, VP, President, Owner, Founder
        executive_keywords = [
            'ceo', 'cto', 'cfo', 'coo', 'cmo', 'chief',
            'president', 'vice president', 'vp',
            'owner', 'founder', 'co-founder', 'partner',
            'managing director', 'executive director'
        ]
        for keyword in executive_keywords:
            if keyword in job_title_lower:
                return (True, 'Executive')

        # Manager: Director, Manager, Head, Lead
        manager_keywords = [
            'director', 'manager', 'head of', 'lead',
            'supervisor', 'coordinator', 'team lead'
        ]
        for keyword in manager_keywords:
            if keyword in job_title_lower:
                return (True, 'Manager')

        # Professional: Specialist, Analyst, Consultant, Engineer, etc.
        professional_keywords = [
            'specialist', 'analyst', 'consultant',
            'engineer', 'developer', 'designer',
            'architect', 'advisor', 'strategist',
            'officer', 'representative', 'coordinator'
        ]
        for keyword in professional_keywords:
            if keyword in job_title_lower:
                return (True, 'Professional')

        # Default: Valid but unclassified
        return (True, 'Other')

    def fuzzy_match_company(self, company1: str, company2: str, threshold: float = 0.6) -> tuple:
        """
        Fuzzy string matching for company names using Levenshtein-based similarity.
        Returns: (match_score, is_match)

        Algorithm: SequenceMatcher (based on Gestalt Pattern Matching)
        - Handles typos, abbreviations, extra words
        - Normalizes whitespace and case
        - threshold: 0.6 = 60% similarity required (configurable)

        Examples:
        - "Happy Skin Esthetics" vs "Happy Skin Esthetics Clinic" → 0.92 (MATCH)
        - "ABC Corp" vs "ABC Corporation" → 0.85 (MATCH)
        - "Google" vs "Facebook" → 0.0 (NO MATCH)
        """
        if not company1 or not company2:
            return (0.0, False)

        # Normalize both company names
        def normalize(text: str) -> str:
            # Convert to lowercase
            text = text.lower()
            # Remove common company suffixes
            suffixes = ['inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co', 'clinic', 'center']
            for suffix in suffixes:
                text = re.sub(rf'\b{suffix}\.?\b', '', text)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            # Remove special characters
            text = re.sub(r'[^\w\s]', '', text)
            return text

        normalized1 = normalize(company1)
        normalized2 = normalize(company2)

        # Calculate similarity ratio (0.0 to 1.0)
        matcher = SequenceMatcher(None, normalized1, normalized2)
        match_score = matcher.ratio()

        # Check if match exceeds threshold
        is_match = match_score >= threshold

        return (match_score, is_match)

    def extract_contact_from_email(self, email: str) -> tuple:
        """
        Extract name from email and classify as generic/personal.
        Returns: (name, is_generic, confidence)

        Enhanced v3.0 (Jan 2026):
        - Better firstname.lastname detection (kathy.smith@ → "Kathy Smith")
        - Improved single name extraction (kathy@ → "Kathy")
        - Filters invalid patterns (numbers, too short, business keywords)
        - Higher confidence for well-formed patterns
        """
        if not email or '@' not in email:
            return ('', True, 0.0)

        local_part = email.split('@')[0].lower()

        # Generic email patterns (expanded)
        generic_patterns = [
            'info', 'contact', 'hello', 'support', 'sales', 'admin',
            'office', 'inquiries', 'help', 'service', 'team', 'mail',
            'general', 'reception', 'booking', 'appointments', 'inquiry',
            'customerservice', 'cs', 'hr', 'jobs', 'careers', 'appointments'
        ]

        # Check if generic
        is_generic = any(pattern in local_part for pattern in generic_patterns)

        if is_generic:
            return ('', True, 0.0)

        # NEW: Pattern 1 - firstname.lastname@ (HIGHEST confidence)
        if '.' in local_part and not local_part.startswith('.') and not local_part.endswith('.'):
            parts = local_part.split('.')
            # Filter valid parts
            valid_parts = [p for p in parts if p.isalpha() and 2 <= len(p) <= 20]

            if len(valid_parts) == 2:
                first = valid_parts[0].capitalize()
                last = valid_parts[1].capitalize()
                return (f"{first} {last}", False, 0.95)  # Very high confidence
            elif len(valid_parts) > 2:
                # firstname.middle.lastname@ or firstname.m.lastname@
                first = valid_parts[0].capitalize()
                last = valid_parts[-1].capitalize()
                return (f"{first} {last}", False, 0.9)

        # Pattern 2 - firstname_lastname@ or firstname-lastname@
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

        # Pattern 3 - Single name (kathy@, sarah@)
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
                return (single_part.capitalize(), False, 0.6)  # Increased from 0.4

        # No valid name found
        return ('', False, 0.2)

    def matches_industry(self, category: str, search_queries: List[str]) -> bool:
        """
        FLEXIBLE: Match businesses by keywords OR related terms.
        Filter out ALL unrelated businesses (auto glass, pharmacies, colleges, retail, etc.)
        Returns True if business category matches search keywords OR related industry terms.
        """
        if not category:
            return False

        category_lower = category.lower()

        # Extract keywords from all search queries
        query_keywords = []
        for query in search_queries:
            keywords = re.findall(r'\b\w+\b', query.lower())
            query_keywords.extend([k for k in keywords if len(k) > 2])  # Filter short words

        # STRICT EXCLUDE - Unrelated business types
        exclude_terms = [
            'windshield', 'auto glass', 'auto repair', 'car wash',
            'pharmacy', 'drug mart', 'shoppers',
            'massage', 'hair salon', 'nail', 'barber',
            'dental', 'dentist', 'orthodont', 'teeth',
            'veterinary', 'vet clinic',
            'restaurant', 'cafe', 'hotel', 'gym', 'fitness',
            'college', 'university', 'school', 'education',
            'vasectomy', 'urology',
            'medical center', 'medical centre', 'walk-in', 'walk in', 'urgent care',
            'attorney', 'lawyer', 'law firm', 'legal',
        ]

        for term in exclude_terms:
            if term in category_lower:
                return False

        # RELATED TERMS MAPPING - Accept related industry terms
        # If searching for "aesthetic clinic", also accept "medical spa", "skin care clinic", etc.
        related_terms = {
            'aesthetic': ['medical spa', 'medspa', 'med spa', 'skin care', 'skincare', 'beauty', 'cosmetic'],
            'clinic': ['medical spa', 'medspa', 'med spa', 'skin care clinic', 'beauty clinic'],
            'spa': ['medical spa', 'medspa', 'med spa', 'aesthetic', 'beauty', 'wellness'],
            'medical': ['aesthetic', 'cosmetic', 'dermatology', 'skin care'],
        }

        # Check if category matches query keywords OR related terms
        matched = False
        
        # Direct keyword match
        for keyword in query_keywords:
            if len(keyword) >= 3 and keyword in category_lower:
                matched = True
                break
        
        # Related terms match
        if not matched:
            for keyword in query_keywords:
                if keyword in related_terms:
                    for related_term in related_terms[keyword]:
                        if related_term in category_lower:
                            matched = True
                            break
                if matched:
                    break

        return matched

    def scrape_google_maps(self, search_queries: List[str], location: str, max_results: int = 50) -> List[Dict]:
        """
        Step 1: Apify → Scrape Google Maps (searchStringsArray + locationQuery)
        """
        logger.info(f"🔍 Scraping: {search_queries} in '{location}'")

        actor_input = {
            "searchStringsArray": search_queries,
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": max_results,
            "language": "en",
            "includeWebResults": True,
            "website": "withWebsite",
            "searchMatching": "all",
            "placeMinimumStars": "",
            "skipClosedPlaces": False,
            "scrapePlaceDetailPage": False,
            "scrapeTableReservationProvider": False,
            "scrapeDirectories": False,
            "maxQuestions": 0,
            "scrapeContacts": False,
            "scrapeSocialMediaProfiles": {
                "facebooks": False,
                "instagrams": False,
                "youtubes": False,
                "tiktoks": False,
                "twitters": False
            },
            "maximumLeadsEnrichmentRecords": 0,
            "maxReviews": 0,
            "reviewsSort": "newest",
            "reviewsFilterString": "",
            "reviewsOrigin": "all",
            "scrapeReviewsPersonalData": True,
            "scrapeImageAuthors": False,
            "allPlacesNoSearchAction": ""
        }

        try:
            run = self.apify_client.actor(self.ACTOR_ID).call(run_input=actor_input)
            dataset_items = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items

            logger.info(f"✓ Scraped {len(dataset_items)} businesses")
            return dataset_items

        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            raise

    def clean_data(self, raw_data: List[Dict], search_queries: List[str], exclude_domains: set = None) -> List[Dict]:
        """Clean data and filter by industry."""
        logger.info("🧹 Cleaning & filtering...")

        if exclude_domains is None:
            exclude_domains = set()

        if exclude_domains:
            logger.info(f"   📋 Excluding {len(exclude_domains)} previously scraped domains")

        cleaned = []
        seen_domains = set()
        filtered_count = 0
        duplicate_count = 0

        for item in raw_data:
            website = item.get('website') or item.get('url') or ""
            domain = self.extract_domain(website) if website else None

            company_name = item.get('title') or item.get('name') or ""
            if not company_name:
                continue

            category = item.get('categoryName') or (item.get('categories', [None])[0] if item.get('categories') else "")

            # Filter non-matching
            if not self.matches_industry(category, search_queries):
                logger.debug(f"Filtered: {company_name} ({category})")
                filtered_count += 1
                continue

            # Deduplicate - check both exclude list and current scrape
            if domain:
                # Skip if already scraped in previous runs
                if domain in exclude_domains:
                    duplicate_count += 1
                    continue
                # Skip if duplicate within current scrape
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

            if website and not website.startswith(('http://', 'https://')):
                website = 'https://' + website

            address = item.get('address') or ""
            phone = self.normalize_phone(item.get('phone') or "")

            cleaned_item = {
                'company_name': company_name,
                'website': website,
                'domain': domain,
                'phone': phone,
                'address': address,
                'category': category,
                'total_score': item.get('totalScore') or item.get('rating'),
                'reviews_count': item.get('reviewsCount'),
                'source': 'Google Maps',
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'emails': []
            }

            cleaned.append(cleaned_item)

        if duplicate_count > 0:
            logger.info(f"✓ {len(cleaned)} valid (filtered {filtered_count}, skipped {duplicate_count} duplicates)")
        else:
            logger.info(f"✓ {len(cleaned)} valid (filtered {filtered_count})")
        return cleaned

    def enrich_single_lead(self, lead: Dict) -> Dict:
        """
        Step 2: AnyMailFinder → Get ALL emails (1 call per company)
        """
        domain = lead.get('domain')
        company_name = lead.get('company_name')

        if not domain or not self.email_enricher:
            lead['emails'] = []
            lead['email_status'] = "not-found" if domain else "no-website"
            return lead

        # ONE API call gets ALL company emails (up to 20)!
        result = self.email_enricher.find_company_emails(domain, company_name)

        lead['emails'] = result['emails']
        lead['email_status'] = result['status']
        lead['email_count'] = result['count']

        return lead

    def enrich_emails(self, leads: List[Dict]) -> List[Dict]:
        """Parallel email enrichment."""
        if not self.email_enricher:
            for lead in leads:
                lead['emails'] = []
                lead['email_status'] = "not-enriched"
            return leads

        logger.info(f"📧 Enriching {len(leads)} companies (parallel)...")

        # 20 workers for maximum speed
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_lead = {executor.submit(self.enrich_single_lead, lead): lead for lead in leads}

            enriched_leads = []
            for future in as_completed(future_to_lead):
                enriched_leads.append(future.result())

        total_emails = sum(len(l.get('emails', [])) for l in enriched_leads)
        found_count = sum(1 for l in enriched_leads if l.get('email_status') == 'found')

        logger.info(f"✓ Found {total_emails} emails for {found_count}/{len(leads)} companies")

        return enriched_leads

    def enrich_decision_makers_for_company(self, lead: Dict) -> List[Dict]:
        """
        Steps 3-6: Email prioritization + Contact enrichment + Company social
        v3.2: Export ALL contacts with LinkedIn titles (max 10 per company)
        """
        company_name = lead.get('company_name', '')
        website = lead.get('website', '')
        address = lead.get('address', '')
        phone = lead.get('phone', '')
        domain = lead.get('domain', '')
        emails = lead.get('emails', [])
        category = lead.get('category', '')

        logger.info(f"\n{'='*70}")
        logger.info(f"🏢 Company: {company_name}")
        logger.info(f"📧 Found {len(emails)} emails")

        # v3.3: Process ALL companies (even without emails via founder search)

        # Step 6: Find company social
        company_social = ''
        if self.search_client:
            logger.info(f"  🔍 Finding company social...")
            company_social = self.search_client.find_company_social(company_name)

        # Extract city and quadrant from address
        city = ''
        quadrant = ''
        clinic_type = category  # Use the category from Google Maps

        if address:
            parts = [p.strip() for p in address.split(',')]
            if len(parts) >= 2:
                city = parts[-2].strip()

            quadrant_match = re.search(r'\b([NS][EW])\b', address)
            if quadrant_match:
                quadrant = quadrant_match.group(1)

        # Base row data (shared across all contacts)
        base_row = {
            'business_name': company_name,
            'website': website,
            'full_address': address,
            'type': clinic_type,
            'company_social': company_social,
            'city': city,
            'quadrant': quadrant,
            'phone': phone,
        }

        contacts = []
        seen_names = set()

        # Step 3: Email Prioritization (Max 10 emails per company)
        sorted_emails = []
        generic_emails = []

        for email in emails:
            _, is_generic, _ = self.extract_contact_from_email(email)
            if is_generic:
                generic_emails.append(email)
            else:
                sorted_emails.append(email)

        # Add personal emails first, then generics (if space)
        sorted_emails.extend(generic_emails)
        emails_to_search = sorted_emails[:10]  # Max 10 emails

        if len(emails) > 10:
            logger.info(f"  ⚠️ Company has {len(emails)} emails, limiting to 10 most relevant")

        # Dictionary to cache founder info for this company so we don't re-search multiple times
        cached_founder_info = None

        # Step 4: Loop through prioritized emails → Google Search
        for email in emails_to_search:
            logger.info(f"  🔍 Processing: {email}")

            contact_info = None
            extracted_name = ''
            is_generic = False

            # 1. EXTRACT NAME FROM EMAIL FIRST
            extracted_name, is_generic, confidence = self.extract_contact_from_email(email)
            
            # CASE A: GENERIC EMAIL (info@, etc.)
            if is_generic:
                logger.info(f"  → Generic email ({email}) - Searching for Founder to fill details...")
                
                # Check cache first
                if cached_founder_info is None and self.search_client:
                     cached_founder_info = self.search_client.find_founder_by_company(company_name, city)
                
                if cached_founder_info:
                    contact_info = cached_founder_info
                    logger.info(f"  ✓ Using Founder info for generic email: {contact_info.get('full_name')}")
                else:
                    logger.info("  ✗ No founder found for generic email.")

            # CASE B: PERSONAL EMAIL
            elif self.search_client and extracted_name and confidence >= 0.5:
                # Search by extracted name
                logger.info(f"  → Extracted name: {extracted_name} (conf: {confidence:.0%}) - Searching LinkedIn...")
                contact_info = self.search_client.search_by_name(extracted_name, company_name, city)
                    
                # If search failed, at least we have the extracted name (better than nothing)
                # STRICT USER UPDATE: "if not found/match on LinkedIn, leave empty"
                # so we do NOT use extracted_name fallback anymore.
                pass

            # Populate results
            full_name = ''
            job_title = ''
            contact_linkedin = ''
            
            if contact_info:
               full_name = contact_info.get('full_name', '')
               job_title = contact_info.get('job_title', '')
               contact_linkedin = contact_info.get('contact_linkedin', '')
            
            logger.info(f"  ✓ Result: name={full_name}, title={job_title}, linkedin={bool(contact_linkedin)}")

            # CRITICAL: Only add to contacts if we have a decision maker name
            # User requirement: "chỉ output khi tìm được đúng name decistion marker"
            # CRITICAL UPDATE: Always add to contacts if we have an email
            # User feedback: "sao tôi thất mất các email info@" -> Want generic emails even if name not found
            if len(contacts) < 10:
                # Deduplicate
                if full_name and full_name in seen_names:
                    logger.info(f"  ✗ Skipped (duplicate): {full_name}")
                    continue

                if full_name:
                    seen_names.add(full_name)

                row = base_row.copy()
                row['email'] = email
                row['primary_contact'] = full_name 
                row['job_title'] = job_title
                row['contact_linkedin'] = contact_linkedin
                row['personal_instagram'] = ''
                contacts.append(row)

                if full_name:
                    logger.info(f"  ★ Added contact: {full_name} - {job_title}")
                else:
                    logger.info(f"  ★ Added email (no name): {email}")

        # If no contacts found via email search, and we haven't found a founder yet (e.g. no emails at all), try one last founder search
        # Only if we have NO emails, because if we had generic emails, we already did the search above.
        if len(contacts) == 0 and len(emails) == 0 and self.search_client:
            logger.info("  🔍 No emails found - trying orphan founder search...")
            
            founder_info = self.search_client.find_founder_by_company(company_name, city)

            if founder_info.get('full_name') and founder_info.get('full_name') not in seen_names:
                if len(contacts) < 10:
                    row = base_row.copy()
                    row['email'] = '' 
                    row['primary_contact'] = founder_info['full_name']
                    row['job_title'] = founder_info.get('job_title', '')
                    row['contact_linkedin'] = founder_info.get('contact_linkedin', '')
                    row['personal_instagram'] = ''
                    contacts.append(row)
                    logger.info(f"  ★ Added Decision Maker: {founder_info['full_name']} - {founder_info.get('job_title')}")

        logger.info(f"✓ Total contacts found: {len(contacts)}")
        return contacts

    def enrich_all_decision_makers(self, leads: List[Dict]) -> List[Dict]:
        """
        Parallel contact enrichment for all companies.
        v3.3: Process ALL companies (founder search for those without emails)
        """
        if not self.search_client:
            logger.warning("⚠️ No RapidAPI keys - skipping contact enrichment")
            return []

        # v3.3: Process ALL companies (not just those with emails)
        companies_with_emails = sum(1 for l in leads if l.get('emails'))
        companies_without_emails = len(leads) - companies_with_emails

        logger.info(f"\n🔍 Enriching contacts for {len(leads)} companies (15 workers)...")
        logger.info(f"  → {companies_with_emails} companies with emails")
        logger.info(f"  → {companies_without_emails} companies without emails (will search founders)")

        all_contacts = []

        # 15 workers optimized for dual API keys
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_lead = {
                executor.submit(self.enrich_decision_makers_for_company, lead): lead
                for lead in leads  # v3.3: Process ALL leads (not just those with emails)
            }

            completed = 0
            total = len(leads)

            for future in as_completed(future_to_lead):
                lead = future_to_lead[future]
                try:
                    contacts = future.result()
                    
                    if contacts:
                        all_contacts.extend(contacts)
                    else:
                        # User Request: Keep leads even if no contact found
                        # Create generic company row
                        generic_email = lead.get('emails', [''])[0] if lead.get('emails') else ''
                        fallback_row = {
                            'business_name': lead.get('company_name'),
                            'primary_contact': '',
                            'phone': lead.get('phone'),
                            'email': generic_email,
                            'city': '',  # City extracted in enrichment usually
                            'job_title': '',
                            'contact_linkedin': '',
                            'website': lead.get('website'),
                            'full_address': lead.get('address'),
                            'type': lead.get('category'),
                            'quadrant': '',
                            'company_social': '',
                            'personal_instagram': ''
                        }
                        all_contacts.append(fallback_row)

                except Exception as e:
                    logger.error(f"Error processing lead {lead.get('company_name')}: {e}")

                completed += 1
                if completed % max(1, total // 10) == 0:
                    progress = (completed / total) * 100
                    logger.info(f"\n⏳ Progress: {completed}/{total} ({progress:.0f}%)")

        logger.info(f"\n✅ Total contacts found: {len(all_contacts)}")
        return all_contacts

    def export_to_google_sheets(self, rows: List[Dict], title: str) -> str:
        """
        Step 7: Export → Google Sheets (13 columns)
        """
        logger.info("📊 Exporting...")

        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("❌ credentials.json not found")
                    return ""

                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
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

            if not rows:
                return spreadsheet_url

            # 13 columns as per MD file (updated order: name/contact/phone/email/city first)
            headers = [
                "Business Name", "Primary Contact", "Phone", "Email", "City",
                "Job Title", "Contact LinkedIn", "Website", "Full Address",
                "Type", "Quadrant", "Company Social", "Personal Instagram"
            ]

            values = [headers]

            for row in rows:
                values.append([
                    row.get('business_name', ''),
                    row.get('primary_contact', ''),
                    row.get('phone', ''),
                    row.get('email', ''),
                    row.get('city', ''),
                    row.get('job_title', ''),
                    row.get('contact_linkedin', ''),
                    row.get('website', ''),
                    row.get('full_address', ''),
                    row.get('type', ''),
                    row.get('quadrant', ''),
                    row.get('company_social', ''),
                    row.get('personal_instagram', '')
                ])

            body = {'values': values}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            # Format
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

            logger.info(f"✓ Exported {len(rows)} rows")

            return spreadsheet_url

        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return ""

    def export_to_csv(self, rows: List[Dict], filename: str) -> str:
        """Export to CSV as fallback."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_path = f".tmp/leads_{filename}_{timestamp}.csv"

            headers = [
                "Business Name", "Primary Contact", "Phone", "Email", "City",
                "Job Title", "Contact LinkedIn", "Website", "Full Address",
                "Type", "Quadrant", "Company Social", "Personal Instagram"
            ]

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

                for row in rows:
                    writer.writerow({
                        "Business Name": row.get('business_name', ''),
                        "Primary Contact": row.get('primary_contact', ''),
                        "Phone": row.get('phone', ''),
                        "Email": row.get('email', ''),
                        "City": row.get('city', ''),
                        "Job Title": row.get('job_title', ''),
                        "Contact LinkedIn": row.get('contact_linkedin', ''),
                        "Website": row.get('website', ''),
                        "Full Address": row.get('full_address', ''),
                        "Type": row.get('type', ''),
                        "Quadrant": row.get('quadrant', ''),
                        "Company Social": row.get('company_social', ''),
                        "Personal Instagram": row.get('personal_instagram', '')
                    })

            logger.info(f"✓ Exported {len(rows)} rows to CSV: {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"❌ CSV export failed: {e}")
            return ""

    def execute(
        self,
        search_queries: List[str],
        location: str,
        max_results: int = 50,
        skip_email_enrichment: bool = False,
        skip_dm_enrichment: bool = False,
        exclude_csv: str = None,
        skip_first: int = 0
    ) -> Dict:
        """Execute workflow following MD file steps."""
        start_time = time.time()

        print("\n" + "="*70)
        print("🚀 GOOGLE MAPS LEAD SCRAPER v3.3 - SKIP LOGIC")
        print(f"Searches: {search_queries}")
        print(f"Location: {location}")
        print(f"Target: {max_results} results per search")
        if skip_first:
            print(f"Skipping first {skip_first} results per search")
        if exclude_csv:
            print(f"📋 Excluding leads from: {exclude_csv}")
        print("="*70 + "\n")

        # Load exclusions
        exclude_domains = set()
        if exclude_csv:
            exclude_domains = self.load_existing_domains(exclude_csv)

        all_clean_data = []

        for query in search_queries:
            # 1. Scrape
            try:
                # Fetch EXTRA results if we need to skip some
                limit_to_fetch = max_results + skip_first
                raw_data = self.scrape_google_maps([query], location, max_results=limit_to_fetch)
            except Exception as e:
                logger.error(f"Failed to scrape '{query}': {e}")
                continue

            # SKIP LOGIC
            if skip_first > 0:
                if len(raw_data) > skip_first:
                    logger.info(f"⏭️  Skipping top {skip_first} results...")
                    raw_data = raw_data[skip_first:]
                else:
                    logger.warning(f"⚠️  Only found {len(raw_data)} results, skipping all (skip_first={skip_first})")
                    raw_data = []

            # 2. Clean & Filter
            cleaned_data = self.clean_data(raw_data, [query], exclude_domains)
            all_clean_data.extend(cleaned_data)
            
            # Add new domains to exclusion set (dedup within session)
            for item in cleaned_data:
                if item.get('domain'):
                    exclude_domains.add(item['domain'])

        # Deduplicate total list
        unique_data = []
        seen_domains = set()
        for item in all_clean_data:
            d = item.get('domain')
            if d and d in seen_domains:
                continue
            if d:
                seen_domains.add(d)
            unique_data.append(item)

        total_scraped = len(unique_data)
        logger.info(f"\n✅ Total Valid Unique Leads: {total_scraped}")

        if total_scraped == 0:
            logger.warning("No leads found. Exiting.")
            return {"success": False, "error": "No leads found"}

        # 3. Enrich Emails
        if not skip_email_enrichment:
            enriched_with_emails = self.enrich_emails(unique_data)
        else:
            enriched_with_emails = unique_data

        # 4. Enrich Decision Makers
        if not skip_dm_enrichment:
            final_data = self.enrich_all_decision_makers(enriched_with_emails)
        else:
            final_data = enriched_with_emails

        # 5. Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_loc = location.replace(',', '_').replace(' ', '_')
        
        # CSV Export
        csv_file = self.export_to_csv(final_data, f"{safe_loc}_{timestamp}")
        
        # Google Sheet Export
        sheet_title = f"Leads - {location} - {timestamp}"
        sheet_url = self.export_to_google_sheets(final_data, sheet_title)

        # Notify
        duration = time.time() - start_time
        msg = f"See: {sheet_url}" if sheet_url else f"CSV: {csv_file}"
        notify_success(f"Scraped {len(final_data)} leads in {location}\n{msg}")

        return {
            "success": True,
            "count": len(final_data),
            "csv": csv_file,
            "sheet": sheet_url,
            "duration": duration
        }


def main():
    """Main CLI - Following MD file usage."""
    parser = argparse.ArgumentParser(description='Google Maps Lead Scraper v3.2 - All Contacts')
    parser.add_argument('--location', type=str, required=True, help='Location (e.g., "Calgary, Canada")')
    parser.add_argument('--searches', nargs='+', required=True, help='Search queries (e.g., "medical aesthetic clinic" "med spa")')
    parser.add_argument('--limit', type=int, default=50, help='Max results per search (default: 50)')
    parser.add_argument('--skip_first', type=int, default=0, help='Skip the first N results (default: 0)')
    parser.add_argument('--exclude', type=str, default=None, help='CSV file with existing leads to exclude (avoids duplicates)')

    args = parser.parse_args()

    scraper = GoogleMapsLeadScraper()

    result = scraper.execute(
        search_queries=args.searches,
        location=args.location,
        max_results=args.limit,
        skip_email_enrichment=False,
        skip_dm_enrichment=False,
        exclude_csv=args.exclude,
        skip_first=args.skip_first
    )

    if not result['success']:
        print(f"\n❌ Failed: {result.get('error')}")
        notify_error()
        sys.exit(1)

    # Success - play notification sound
    notify_success()


if __name__ == "__main__":
    main()
