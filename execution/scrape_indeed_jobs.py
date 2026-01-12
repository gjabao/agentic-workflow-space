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
from typing import Dict, List, Optional, Any, Generator
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

        # 2. RapidAPI for Google Search
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY")
        if not self.rapidapi_key:
            logger.warning("⚠️ RAPIDAPI_KEY not found. Decision maker search will be slower.")

        # 2. AnyMailFinder
        self.anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        if not self.anymail_key:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found. Email finding will be skipped.")

        # 3. Azure OpenAI
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
        """Simplify job title by removing unnecessary details."""
        if not job_title:
            return ""

        # Remove everything after common delimiters
        # Examples:
        # "Senior Research Software Engineer - Security & Cryptography" → "Senior Research Software Engineer"
        # "Senior iOS Engineer, Music" → "Senior iOS Engineer"
        # "Product Manager (Remote)" → "Product Manager"

        for delimiter in [' - ', ' – ', ' — ', ',', ' (']:
            if delimiter in job_title:
                job_title = job_title.split(delimiter)[0].strip()
                break

        return job_title.strip()

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
        if not title:
            return False

        title_lower = title.lower()

        # Web3-specific keywords (must match at least one)
        web3_keywords = [
            'web3', 'blockchain', 'crypto', 'cryptocurrency',
            'defi', 'nft', 'solidity', 'ethereum', 'smart contract',
            'dao', 'dapp', 'token', 'layer 2', 'l2',
            'polygon', 'avalanche', 'arbitrum', 'optimism',
            'rust blockchain', 'move developer', 'substrate'
        ]

        return any(keyword in title_lower for keyword in web3_keywords)

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

                    yield {
                        'company_name': normalized_company if normalized_company else company,
                        'job_title': normalized_title if normalized_title else title,
                        'job_url': item.get('url', ''),
                        'job_description': item.get('description', ''),
                        'posted_date': item.get('postedAt', ''),
                        'location': item.get('location', '')
                    }

                offset += len(items)
                poll_delay = self.APIFY_POLL_INTERVAL_START  # Reset delay when we get data

            if status in ["SUCCEEDED", "FAILED", "ABORTED"] and len(items) == 0:
                break

            # Exponential backoff polling
            time.sleep(poll_delay)
            poll_delay = min(poll_delay * 1.5, self.APIFY_POLL_INTERVAL_MAX)

    def find_decision_maker(self, company_name: str) -> Dict:
        """Find Founder/CEO using RapidAPI Google Search with retry logic and caching."""
        # Check cache first
        if company_name in self._dm_cache:
            return self._dm_cache[company_name]

        query = f'site:linkedin.com/in/ ("founder" OR "co-founder" OR "ceo" OR "owner") "{company_name}"'

        if not self.rapidapi_key:
            return {}

        max_retries = 3
        for attempt in range(max_retries):
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
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
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

                # Parse name/title logic...
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

                result = {
                    'full_name': name_part,
                    'first_name': first_name,
                    'last_name': last_name,
                    'title': dm_title,
                    'linkedin_url': link,
                    'description': description,
                    'source': 'RapidAPI Google Search'
                }

                # Cache the result
                self._dm_cache[company_name] = result
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return {}
        return {}

    def find_email(self, first_name: str, last_name: str, company_domain: str) -> Dict:
        """Find email using AnyMailFinder Person API."""
        if not self.anymail_key or not company_domain or not first_name:
            return {'email': '', 'status': 'skipped'}
            
        try:
            headers = {
                'Authorization': self.anymail_key,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'domain': company_domain,
                'first_name': first_name,
                'last_name': last_name
            }
            
            response = requests.post(
                self.ANYMAILFINDER_URL,
                headers=headers,
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('email_class') == 'personal' or data.get('email'):
                    return {
                        'email': data.get('email'),
                        'status': 'found',
                        'confidence': data.get('confidence', 0)
                    }
            
            return {'email': '', 'status': 'not_found'}
            
        except Exception as e:
            return {'email': '', 'status': 'error'}

    def find_company_website(self, company_name: str) -> Dict:
        """Find company website using RapidAPI Google Search with retry logic and caching."""
        # Check cache first
        if company_name in self._website_cache:
            return self._website_cache[company_name]

        query = f'"{company_name}" official website'

        if not self.rapidapi_key:
            return {'url': '', 'description': ''}

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

                for result in organic_results:
                    url = result.get('url', '')
                    if any(skip in url.lower() for skip in ['linkedin.com', 'facebook.com', 'twitter.com', 'indeed.com', 'glassdoor.com']):
                        continue
                    website_result = {
                        'url': url,
                        'description': result.get('description', '')
                    }
                    # Cache the result
                    self._website_cache[company_name] = website_result
                    return website_result

                empty_result = {'url': '', 'description': ''}
                self._website_cache[company_name] = empty_result
                return empty_result

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
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return "" 

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

    def process_single_company(self, job: Dict) -> Dict:
        """Process a single company: Find DM -> Find Website -> Find Email -> Generate Message."""
        company = job['company_name']
        
        # 1. Find Decision Maker
        dm = self.find_decision_maker(company)
        job.update({
            'dm_name': dm.get('full_name', ''),
            'dm_first': dm.get('first_name', ''),
            'dm_last': dm.get('last_name', ''),
            'dm_title': dm.get('title', ''),
            'dm_linkedin': dm.get('linkedin_url', '')
        })
        
        # 2. Find Company Website
        website_data = self.find_company_website(company)
        website = website_data.get('url', '')
        company_desc = website_data.get('description', '')
        domain = self.extract_domain(website) if website else ""
        
        job['company_website'] = website
        job['company_domain'] = domain
        job['company_description'] = company_desc
        job['dm_description'] = dm.get('description', '')
        
        # 3. Find Email
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
            
        # 4. Generate Message
        if job['dm_name']:
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
                "Company Name", "Company Website", "Job Title", "Job URL", "Location",
                "DM Name", "DM Title", "DM First", "DM Last", "DM LinkedIn",
                "DM Email", "Email Status", "Message", "Scraped Date"
            ]
            
            values = [headers]
            for row in rows:
                values.append([
                    row.get('company_name', ''),
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

    def execute(self, query: str, location: str = "", country: str = "United States", max_jobs: int = 10, days_posted: int = 14):
        start_time = time.time()

        print("\n" + "="*70)
        print("🚀 INDEED JOB SCRAPER & OUTREACH SYSTEM (STREAMING MODE)")
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
                    result = future.result()
                    processed_jobs.append(result)
                    # Visual progress indicator
                    email_status = "✅ Email" if result.get('dm_email') else "❌ No Email"
                    print(f"   ✓ [{completed}/{len(futures)}] {result['company_name']} ({email_status})")
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
    
    args = parser.parse_args()
    
    try:
        scraper = IndeedJobScraper()
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
