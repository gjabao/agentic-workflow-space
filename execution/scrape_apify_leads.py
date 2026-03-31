#!/usr/bin/env python3
"""
Apify Lead Scraper - DO Architecture Execution Script
Scrapes B2B leads using Apify's leads-finder with test-first validation.

Test-first workflow:
1. Run test scrape (25 leads)
2. Validate industry match rate (≥80% required)
3. If pass: proceed with full scrape
4. If fail: suggest filter refinements
5. Export to Google Sheets
"""

import os
import sys
import json
import logging
import time
import requests
import csv
import io
import asyncio
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from apify_client import ApifyClient
from openai import AzureOpenAI, OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils_notifications import notify_success, notify_error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/execution.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
REQUESTS_TIMEOUT = 30  # seconds - timeout for all HTTP requests
VERIFICATION_MAX_RETRIES = 120  # 5 minutes max with adaptive polling
VERIFICATION_FAST_POLL_COUNT = 10  # First 10 attempts at 2s intervals
VERIFICATION_SLOW_POLL_INTERVAL = 3  # Seconds after fast polling
AI_VALIDATION_BATCH_SIZE = 10  # OpenAI rate limit friendly
ICEBREAKER_BATCH_SIZE = 10  # OpenAI rate limit friendly

# Valid company size values for Apify API
VALID_COMPANY_SIZES = {
    "1-10", "11-20", "21-50", "51-100", "101-200", "201-500",
    "501-1000", "1001-2000", "2001-5000", "5001-10000",
    "10001-20000", "20001-50000", "50000+"
}

# Company size auto-correction mappings
COMPANY_SIZE_CORRECTIONS = {
    "1-50": ["1-10", "11-20", "21-50"],
    "50-100": ["51-100"],
    "100-200": ["101-200"],
    "100-500": ["101-200", "201-500"],
    "500-1000": ["501-1000"],
    "1000-5000": ["1001-2000", "2001-5000"],
    "5000-10000": ["5001-10000"],
    "10000+": ["10001-20000", "20001-50000", "50000+"]
}


def sanitize_error(error_str: str) -> str:
    """
    Remove API keys and sensitive data from error messages.

    Args:
        error_str: Raw error string that may contain secrets

    Returns:
        Sanitized error string with secrets redacted
    """
    if not error_str:
        return error_str

    # Remove common API key patterns
    error_str = re.sub(
        r'(api[_-]?key["\s:=]+)[a-zA-Z0-9_\-\.]+',
        r'\1[REDACTED]',
        error_str,
        flags=re.IGNORECASE
    )
    error_str = re.sub(
        r'(bearer\s+)[a-zA-Z0-9_\-\.]+',
        r'\1[REDACTED]',
        error_str,
        flags=re.IGNORECASE
    )
    error_str = re.sub(
        r'(token["\s:=]+)[a-zA-Z0-9_\-\.]+',
        r'\1[REDACTED]',
        error_str,
        flags=re.IGNORECASE
    )
    error_str = re.sub(
        r'(sk_[a-zA-Z0-9_\-\.]+)',
        r'[REDACTED_API_KEY]',
        error_str
    )
    error_str = re.sub(
        r'(apify_api_[a-zA-Z0-9_\-\.]+)',
        r'[REDACTED_APIFY_KEY]',
        error_str
    )

    return error_str


def run_async(coro):
    """
    Safely run async function from sync context.
    Handles nested event loop scenarios.

    Args:
        coro: Coroutine to execute

    Returns:
        Result of coroutine execution
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running - safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # Event loop is running - use nest_asyncio
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except ImportError:
            logger.warning("nest_asyncio not installed. Using asyncio.run() anyway.")
            return asyncio.run(coro)


class AnyMailFinderVerifier:
    """Handles email verification using AnyMailFinder API."""

    BASE_URL = "https://api.anymailfinder.com/v5.1/verify-email"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify_bulk(self, emails: List[str], leads: List[Dict] = None) -> Dict[str, str]:
        """
        Verify a list of emails using AnyMailFinder API.

        Args:
            emails: List of email addresses to verify
            leads: Original lead data (not used for AnyMailFinder, kept for compatibility)

        Returns:
            Dict mapping email -> status (Valid, Invalid, Catch-All, Unknown)
        """
        if not emails:
            return {}

        logger.info(f"Verifying {len(emails)} emails with AnyMailFinder...")

        results = {}
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }

        # Process emails one by one (AnyMailFinder charges 0.2 credits per verification)
        for i, email in enumerate(emails):
            if not email or not email.strip():
                continue

            email = email.strip().lower()

            try:
                payload = {'email': email}

                response = requests.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=REQUESTS_TIMEOUT
                )

                if response.status_code == 200:
                    data = response.json()

                    # Parse AnyMailFinder response
                    # Actual format: {"email_status": "valid|invalid|catch-all|unknown", ...}
                    status = data.get('email_status', 'unknown').lower()

                    # Map to our standard statuses
                    if status == 'valid':
                        results[email] = 'Valid'
                    elif status == 'invalid':
                        results[email] = 'Invalid'
                    elif status in ['catch-all', 'catch_all', 'catchall']:
                        results[email] = 'Catch-All'
                    else:
                        results[email] = 'Unknown'

                    # Log individual results
                    if results[email] == 'Valid':
                        logger.debug(f"  ✓ {email}: Valid")
                    elif results[email] == 'Invalid':
                        logger.debug(f"  ✗ {email}: Invalid")
                    else:
                        logger.debug(f"  ? {email}: {results[email]}")

                elif response.status_code == 401:
                    logger.error("❌ AnyMailFinder authentication failed. Check API key.")
                    results[email] = 'Unknown'
                else:
                    logger.warning(f"  ⚠️ Error {response.status_code} for {email}")
                    results[email] = 'Unknown'

                # Log progress every 10 emails
                if (i + 1) % 10 == 0:
                    valid_so_far = sum(1 for s in results.values() if s == 'Valid')
                    logger.info(f"  Progress: {i + 1}/{len(emails)} ({valid_so_far} valid)")

                # Small delay to respect rate limits
                time.sleep(0.1)

            except requests.Timeout:
                logger.warning(f"  ⚠️ Timeout for {email}")
                results[email] = 'Unknown'
            except Exception as e:
                sanitized_error = sanitize_error(str(e))
                logger.warning(f"  ⚠️ Error verifying {email}: {sanitized_error}")
                results[email] = 'Unknown'

        valid_count = sum(1 for status in results.values() if status == 'Valid')
        invalid_count = sum(1 for status in results.values() if status == 'Invalid')
        catchall_count = sum(1 for status in results.values() if status == 'Catch-All')

        logger.info(f"✓ Verification complete: {valid_count} valid, {invalid_count} invalid, {catchall_count} catch-all")

        return results


class ApifyLeadScraper:
    """
    Scrape B2B leads using Apify leads-finder with test-first validation.
    
    Attributes:
        api_key (str): Apify API key
        client (ApifyClient): Initialized Apify client
        actor_id (str): Apify actor ID for leads-finder
        test_count (int): Number of leads for test run
        match_threshold (float): Minimum industry match rate (0-1)
    """
    
    ACTOR_ID = "code_crafter/leads-finder"
    TEST_COUNT = 25
    MATCH_THRESHOLD = 0.80
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    def __init__(self):
        """Initialize the scraper with API credentials."""
        self.apify_token = os.getenv("APIFY_API_KEY")
        self.anymailfinder_token = os.getenv("ANYMAILFINDER_API_KEY")

        if not self.apify_token:
            raise ValueError("APIFY_API_KEY not found in environment variables")

        self.client = ApifyClient(self.apify_token)
        self.verifier = AnyMailFinderVerifier(self.anymailfinder_token) if self.anymailfinder_token else None
        # Initialize icebreaker generator — prefer OpenAI API, fallback to Azure OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if openai_key:
            self.icebreaker_gen = IcebreakerGenerator(None, openai_key, "gpt-4o", provider="openai")
            logger.info("✓ Using OpenAI API for icebreaker generation")
        elif azure_endpoint and azure_key:
            self.icebreaker_gen = IcebreakerGenerator(azure_endpoint, azure_key, azure_deployment, provider="azure")
            logger.info("✓ Using Azure OpenAI for icebreaker generation")
        else:
            self.icebreaker_gen = None

        if not self.verifier:
            logger.warning("⚠️ ANYMAILFINDER_API_KEY not found. Email verification will be skipped.")

        if not self.icebreaker_gen:
            logger.warning("⚠️ No OpenAI credentials found. Icebreaker generation will be skipped.")
        
        self.output_dir = '.tmp/scraped_data'
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f'{self.output_dir}/archive', exist_ok=True)
        
        logger.info("ApifyLeadScraper initialized")
    
    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate input parameters.
        
        Args:
            **kwargs: Must include 'industry' and 'fetch_count'
            
        Returns:
            bool: True if validation passes
            
        Raises:
            ValueError: If required fields missing or invalid
        """
        logger.info("Validating inputs...")
        
        if 'industry' not in kwargs or not kwargs['industry']:
            raise ValueError("Required field 'industry' is missing")
        
        if 'fetch_count' not in kwargs or not kwargs['fetch_count']:
            raise ValueError("Required field 'fetch_count' is missing")
        
        fetch_count = kwargs['fetch_count']
        if not isinstance(fetch_count, int) or fetch_count < 1:
            raise ValueError(f"fetch_count must be a positive integer, got: {fetch_count}")
        
        logger.info("✓ Input validation passed")
        return True
    
    def validate_company_size(self, sizes: List[str]) -> List[str]:
        """
        Validate and auto-correct company size values for Apify API.

        Args:
            sizes: List of company size strings

        Returns:
            List of valid, corrected company sizes

        Raises:
            ValueError: If size cannot be corrected
        """
        corrected = []
        for size in sizes:
            if size in VALID_COMPANY_SIZES:
                corrected.append(size)
            elif size in COMPANY_SIZE_CORRECTIONS:
                # Auto-correct common mistakes
                corrections = COMPANY_SIZE_CORRECTIONS[size]
                logger.warning(f"Auto-correcting company_size '{size}' → {corrections}")
                corrected.extend(corrections)
            else:
                # Unknown size - provide helpful error
                logger.error(f"Invalid company_size '{size}'")
                logger.error(f"Allowed values: {sorted(VALID_COMPANY_SIZES)}")
                raise ValueError(
                    f"Invalid company_size: '{size}'. "
                    f"Use one of: {', '.join(sorted(VALID_COMPANY_SIZES))}"
                )
        return corrected

    def build_actor_input(self, fetch_count: int, **filters) -> Dict[str, Any]:
        """
        Build input configuration for Apify actor.

        Args:
            fetch_count: Number of leads to fetch
            **filters: Additional filters (job_title, location, etc.)

        Returns:
            Dict with actor input configuration
        """
        actor_input = {
            "fetch_count": fetch_count,
            "email_status": ["validated"]  # Prefer validated emails
        }

        # Map common filter names to Apify fields
        filter_mapping = {
            'job_title': 'contact_job_title',
            'location': 'contact_location',
            'city': 'contact_city',
            'company_size': 'size',
            'company_industry': 'company_industry',
            'seniority_level': 'seniority_level',
            'functional_level': 'functional_level',
            'min_revenue': 'min_revenue',
            'max_revenue': 'max_revenue',
            'company_keywords': 'company_keywords',
            'company_not_industry': 'company_not_industry'
        }

        # Add filters to actor input
        for user_key, apify_key in filter_mapping.items():
            if user_key in filters and filters[user_key]:
                value = filters[user_key]

                # Validate company_size before processing
                if user_key == 'company_size':
                    if not isinstance(value, list):
                        value = [value]
                    value = self.validate_company_size(value)

                # Convert single values to arrays for Apify
                if not isinstance(value, list) and apify_key in ['contact_job_title', 'contact_location', 'contact_city', 'company_industry', 'company_not_industry', 'company_keywords']:
                    value = [value]

                # Lowercase specific fields that require it
                if apify_key in ['contact_location', 'company_industry']:
                    value = [v.lower() if isinstance(v, str) else v for v in value]

                actor_input[apify_key] = value

        return actor_input
    
    def run_scrape(self, fetch_count: int, **filters) -> List[Dict]:
        """
        Run Apify actor to scrape leads.
        
        Args:
            fetch_count: Number of leads to scrape
            **filters: Scraping filters
            
        Returns:
            List of lead dictionaries
            
        Raises:
            Exception: If actor run fails
        """
        actor_input = self.build_actor_input(fetch_count, **filters)
        
        logger.info(f"Running Apify actor: {self.ACTOR_ID}")
        logger.info(f"Input: {json.dumps(actor_input, indent=2)}")
        
        # Run the actor and wait for it to finish
        run = self.client.actor(self.ACTOR_ID).call(run_input=actor_input)
        
        # Fetch results from the actor's dataset
        dataset_items = self.client.dataset(run["defaultDatasetId"]).list_items().items
        
        logger.info(f"✓ Scraped {len(dataset_items)} leads")
        return dataset_items
    
    def validate_industry_match(self, leads: List[Dict], target_industries: List[str]) -> Dict:
        """
        Validate if the scraped leads match the target industries using AI (parallel).

        Args:
            leads: List of scraped leads
            target_industries: List of target industries

        Returns:
            Dict with match rate and details
        """
        if not leads:
            return {'match_rate': 0.0, 'matches': [], 'mismatches': []}

        matches = []
        mismatches = []
        needs_ai_validation = []  # Track leads that need AI validation

        # Use AI for intelligent filtering if available
        use_ai_filter = self.icebreaker_gen is not None

        # Phase 1: Fast fuzzy matching
        for lead in leads:
            lead_industry = lead.get('company_industry') or lead.get('industry') or ""

            if not lead_industry:
                mismatches.append(lead)
                continue

            is_match = False

            # Try fuzzy matching first (fast)
            for target in target_industries:
                score = fuzz.partial_ratio(target.lower(), lead_industry.lower())
                if score >= 80:
                    is_match = True
                    break

            if is_match:
                matches.append(lead)
            else:
                # Queue for AI validation if available
                if use_ai_filter:
                    needs_ai_validation.append(lead)
                else:
                    mismatches.append(lead)

        # Phase 2: Parallel AI validation for fuzzy match failures
        if needs_ai_validation and use_ai_filter:
            logger.info(f"Running AI validation for {len(needs_ai_validation)} leads (parallel)...")
            ai_results = run_async(self._ai_validate_bulk(needs_ai_validation, target_industries))

            for lead, is_match in zip(needs_ai_validation, ai_results):
                if is_match:
                    matches.append(lead)
                else:
                    mismatches.append(lead)

        match_rate = len(matches) / len(leads)

        return {
            'match_rate': match_rate,
            'matches': matches,
            'mismatches': mismatches
        }

    async def _ai_validate_bulk(self, leads: List[Dict], target_industries: List[str]) -> List[bool]:
        """
        Validate multiple leads in parallel using Azure OpenAI.

        Args:
            leads: List of leads to validate
            target_industries: Target industries

        Returns:
            List of booleans (True = match, False = no match)
        """
        async def validate_one(lead):
            company_name = lead.get('company_name', '')
            lead_industry = lead.get('company_industry') or lead.get('industry') or ""
            company_desc = lead.get('company_description', '')

            return await asyncio.to_thread(
                self._ai_validate_industry,
                company_name,
                lead_industry,
                company_desc,
                target_industries
            )

        # Process in batches of 10 to avoid rate limits
        batch_size = 10
        results = []
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            batch_results = await asyncio.gather(*[validate_one(lead) for lead in batch])
            results.extend(batch_results)

        return results

    def _ai_validate_industry(self, company_name: str, company_industry: str,
                              company_desc: str, target_industries: List[str]) -> bool:
        """
        Use Azure OpenAI to intelligently validate if a company matches target industries.

        Args:
            company_name: Name of the company
            company_industry: Stated industry of the company
            company_desc: Company description
            target_industries: List of target industries

        Returns:
            bool: True if company matches target, False otherwise
        """
        if not self.icebreaker_gen:
            return False

        prompt = f"""
        You are an industry classification expert.

        TARGET INDUSTRIES: {', '.join(target_industries)}

        COMPANY DATA:
        - Name: {company_name}
        - Industry: {company_industry}
        - Description: {(company_desc or '')[:200]}

        TASK: Does this company belong to any of the target industries?

        Answer ONLY "YES" or "NO". Consider:
        - Business model alignment
        - Service/product relevance
        - Industry terminology matches

        Output only YES or NO.
        """

        try:
            response = self.icebreaker_gen.client.chat.completions.create(
                model=self.icebreaker_gen.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert at classifying companies by industry. Output ONLY 'YES' or 'NO'."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temp for more consistent classification
                max_tokens=10
            )
            
            if not response or not response.choices:
                logger.warning(f"AI validation returned empty response for {company_name}")
                return False

            answer = response.choices[0].message.content.strip().upper()
            return "YES" in answer
        except Exception as e:
            logger.warning(f"AI validation failed for {company_name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False  # Conservative: reject if AI fails
    
    def suggest_filter_improvements(self, non_matching_leads: List[Dict]) -> List[str]:
        """
        Generate suggestions for improving filter quality.
        
        Args:
            non_matching_leads: Leads that did not match the target industry
            
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # Analyze non-matching industries to find patterns
        non_matching_industries = [d.get('company_industry') or d.get('industry') for d in non_matching_leads if d.get('company_industry') or d.get('industry')]
        
        if non_matching_industries:
            # Get top 5 unique non-matching industries
            top_non_matching = list(set(non_matching_industries))[:5]
            suggestions.append(
                f"Consider adding these to 'company_not_industry' filter: {top_non_matching}\n"
                f"   Example: company_not_industry=['{', '.join(top_non_matching[:3])}']"
            )
        
        # General suggestions if no specific patterns found or if filters are missing
        if not suggestions:
            suggestions.append(
                "Refine your 'company_industry' filter to be more specific or include common variations."
            )
        
        # These suggestions are now more general, as we don't have `current_filters` here
        suggestions.append(
            "Consider adding 'job_title' filter to target specific roles (e.g., job_title=['CEO', 'Founder'])."
        )
        suggestions.append(
        "Add 'company_keywords' to refine by business type (e.g., company_keywords=['SaaS', 'Fintech'])."
        )
        
        return suggestions

    def export_to_csv(self, leads: List[Dict], industry: str, agency_type: str = "universal") -> str:
        """
        Export leads to CSV file as fallback when Google Sheets fails.

        Args:
            leads: List of leads to export
            industry: Target industry name for filename

        Returns:
            str: Path to CSV file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_industry = industry.replace(' ', '_').replace('/', '_')[:30]
        filename = f".tmp/leads_{safe_industry}_{timestamp}.csv"

        # Dynamic headers based on agency type
        icp_header = "Roles" if agency_type == "recruitment" else "ICP"
        headers = [
            "Company Name", "Website", "Industry", "Location", "Size", "Revenue",
            "First Name", "Last Name", "Job Title", "Email", "Email Status",
            "Verification Status", "Personalization", icp_header, "Their Service",
            "Phone", "LinkedIn", "Company LinkedIn"
        ]

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for lead in leads:
                writer.writerow({
                    "Company Name": lead.get('company_name', ''),
                    "Website": lead.get('company_website', ''),
                    "Industry": lead.get('company_industry', '') or lead.get('industry', ''),
                    "Location": lead.get('company_full_address', '') or f"{lead.get('city', '')}, {lead.get('state', '')}, {lead.get('country', '')}",
                    "Size": lead.get('company_size', ''),
                    "Revenue": lead.get('company_annual_revenue', ''),
                    "First Name": lead.get('first_name', ''),
                    "Last Name": lead.get('last_name', ''),
                    "Job Title": lead.get('job_title', ''),
                    "Email": lead.get('email', ''),
                    "Email Status": lead.get('email_status', ''),
                    "Verification Status": lead.get('verification_status', 'Not Checked'),
                    "Personalization": lead.get('icebreaker_1', ''),
                    icp_header: lead.get('icebreaker_2', ''),
                    "Their Service": lead.get('icebreaker_3', ''),
                    "Phone": lead.get('mobile_number', '') or lead.get('company_phone', ''),
                    "LinkedIn": lead.get('linkedin', ''),
                    "Company LinkedIn": lead.get('company_linkedin', '')
                })

        logger.info(f"✓ CSV export complete: {filename}")
        return filename

    def export_to_google_sheets(self, leads: List[Dict], title: str, agency_type: str = "universal") -> str:
        """
        Export leads to a new Google Sheet.
        
        Args:
            leads: List of leads to export
            title: Title of the new sheet
            
        Returns:
            str: URL of the created Google Sheet
        """
        logger.info("Exporting to Google Sheets...")
        
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.warning("⚠️ credentials.json not found. Skipping Google Sheets export.")
                    logger.warning("To enable: Download OAuth client ID JSON from Google Cloud Console,")
                    logger.warning("save as 'credentials.json' in project root.")
                    return ""
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                # Use fixed port 8080 to match Google Cloud Console configuration
                creds = flow.run_local_server(port=8080)
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        try:
            service = build('sheets', 'v4', credentials=creds)

            # Create a new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                        fields='spreadsheetId,spreadsheetUrl').execute()
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
            
            logger.info(f"Created spreadsheet: {spreadsheet_url}")

            # Prepare data
            if not leads:
                return spreadsheet_url

            # Define headers based on the first lead or a standard schema
            # We'll use a standard schema for consistency
            # Dynamic headers based on agency type
            icp_header = "Roles" if agency_type == "recruitment" else "ICP"
            headers = [
                "Company Name", "Website", "Industry", "Location", "Size", "Revenue",
                "First Name", "Last Name", "Job Title", "Email", "Email Status", "Verification Status",
                "Personalization", icp_header, "Their Service",
                "Phone", "LinkedIn", "Company LinkedIn"
            ]

            values = [headers]

            for lead in leads:
                row = [
                    lead.get('company_name', ''),
                    lead.get('company_website', ''),
                    lead.get('company_industry', '') or lead.get('industry', ''),
                    lead.get('company_full_address', '') or f"{lead.get('city', '')}, {lead.get('state', '')}, {lead.get('country', '')}",
                    lead.get('company_size', ''),
                    lead.get('company_annual_revenue', ''),
                    lead.get('first_name', ''),
                    lead.get('last_name', ''),
                    lead.get('job_title', ''),
                    lead.get('email', ''),
                    lead.get('email_status', ''),
                    lead.get('verification_status', 'Not Checked'),
                    lead.get('icebreaker_1', ''),
                    lead.get('icebreaker_2', ''),
                    lead.get('icebreaker_3', ''),
                    lead.get('mobile_number', '') or lead.get('company_phone', ''),
                    lead.get('linkedin', ''),
                    lead.get('company_linkedin', '')
                ]
                values.append(row)

            # Write data
            body = {
                'values': values
            }
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="A1",
                valueInputOption="RAW", body=body).execute()
                
            logger.info(f"{result.get('updatedCells')} cells updated.")
            
            # Format header row (Bold)
            requests = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold"
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 0,
                            "gridProperties": {
                                "frozenRowCount": 1
                            }
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                }
            ]
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return spreadsheet_url

        except HttpError as err:
            logger.error(f"Google Sheets API Error: {err}")
            return ""
        except Exception as e:
            logger.error(f"Error exporting to Google Sheets: {e}")
            return ""

    def save_results(self, leads: List[Dict], prefix: str = "results") -> str:
        """
        Save leads to JSON file.
        
        Args:
            leads: List of leads to save
            prefix: Filename prefix
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(leads, f, indent=2)
        
        logger.info(f"✓ Results saved to: {filepath}")
        return filepath
    
    def execute(self, industry: str, fetch_count: int, skip_test: bool = False, valid_only: bool = False, sender_context: str = "", agency_type: str = "universal", **filters) -> Dict:
        """
        Execute the full scraping workflow.

        Args:
            industry: Target industry
            fetch_count: Number of leads to fetch
            skip_test: Whether to skip the test run
            valid_only: Whether to export only valid emails
            sender_context: Context about the sender for SSM prompts
            agency_type: One of 'recruitment', 'marketing', 'universal'
            **filters: Additional filters for the actor

        Returns:
            Dict with execution results
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("Starting Apify lead scraping workflow...")
        logger.info(f"Target industry: {industry}")
        logger.info(f"Target count: {fetch_count}")
        if skip_test:
            logger.info("⚠️  Skipping test run (Validation Phase skipped)")
        logger.info("=" * 60)
        
        try:
            # Validate inputs
            logger.info("Validating inputs...")
            self.validate_inputs(industry=industry, fetch_count=fetch_count, **filters)
            logger.info("✓ Input validation passed")
            
            test_leads = []
            validation = {'match_rate': 1.0, 'matches': [], 'mismatches': []} # Default if skipped
            test_file = None # Initialize test_file
            
            if not skip_test:
                # PHASE 1: Test Scrape
                logger.info(f"\n⏳ PHASE 1: Test scrape ({self.TEST_COUNT} leads)...")
                
                # Run test scrape
                test_leads = self.run_scrape(self.TEST_COUNT, **filters)
                
                if not test_leads:
                    logger.error("❌ Test scrape returned no results. Stopping.")
                    return {'success': False, 'phase': 'test', 'error': 'No results found'}
                
                # Save test results
                test_file = self.save_results(test_leads, prefix="test")
                
                # PHASE 2: Validation
                logger.info("\n⏳ PHASE 2: Validating results...")
                
                # Determine target industries for validation
                target_industries = filters.get('company_industry', [industry])
                if isinstance(target_industries, str):
                    target_industries = [target_industries]
                    
                validation = self.validate_industry_match(test_leads, target_industries)
                logger.info(f"Industry match: {len(validation['matches'])}/{len(test_leads)} ({validation['match_rate']:.1%})")
                
                if validation['match_rate'] < self.MATCH_THRESHOLD:
                    logger.info(f"Threshold: {self.MATCH_THRESHOLD:.1%} - ❌ FAIL")
                    logger.warning("=" * 60)
                    logger.warning(f"❌ Test validation failed: {validation['match_rate']:.1%} < {self.MATCH_THRESHOLD:.1%}")
                    
                    suggestions = self.suggest_filter_improvements(validation['mismatches'])
                    logger.warning("\nSuggestions:")
                    for i, suggestion in enumerate(suggestions, 1):
                        logger.warning(f"\n{i}. {suggestion}")
                    logger.warning("=" * 60)
                    
                    # Save test results anyway for inspection
                    test_file = self.save_results(test_leads, prefix="test_failed")
                    logger.info(f"Test results saved to: {test_file}")
                    
                    return {
                        'success': False,
                        'phase': 'validation',
                        'test_results': test_leads,
                        'validation': validation,
                        'test_file': test_file
                    }
                
                logger.info(f"Threshold: {self.MATCH_THRESHOLD:.1%} - ✓ PASS")
            
            # PHASE 3: Full Scrape
            logger.info(f"\n⏳ PHASE 3: Running full scrape ({fetch_count} leads)...")
            full_leads = self.run_scrape(fetch_count, **filters)

            # PHASE 3.4: AI Industry Filtering (Remove irrelevant companies)
            if self.icebreaker_gen and full_leads:
                logger.info("\n⏳ PHASE 3.4: AI-powered industry filtering...")
                target_industries = filters.get('company_industry', [industry])
                if isinstance(target_industries, str):
                    target_industries = [target_industries]

                try:
                    validation_result = self.validate_industry_match(full_leads, target_industries)
                    filtered_count = len(validation_result['matches'])
                    removed_count = len(validation_result['mismatches'])
                    match_rate = validation_result['match_rate']

                    # Safety check: if match rate is suspiciously low, keep all leads
                    if match_rate < 0.20:  # Less than 20% match
                        logger.warning(f"⚠️  AI filter match rate is very low: {match_rate:.1%}")
                        logger.warning(f"⚠️  This suggests target industry '{target_industries}' may not match scraped data.")
                        logger.warning(f"⚠️  Proceeding with ALL {len(full_leads)} leads to avoid data loss.")
                        logger.warning(f"⚠️  Consider refining 'company_industry' filter in next run.")
                        # Keep all leads - don't waste API credits
                    elif match_rate < 0.50:  # 20-50% match - borderline
                        logger.warning(f"⚠️  AI filter match rate is moderate: {match_rate:.1%}")
                        logger.info(f"✓ Keeping {filtered_count} matching leads, discarding {removed_count}")
                        full_leads = validation_result['matches']
                    else:
                        # High confidence - proceed with filtering
                        if removed_count > 0:
                            logger.info(f"✓ Filtered out {removed_count} irrelevant companies")
                            logger.info(f"✓ Kept {filtered_count} matching companies ({match_rate:.1%} match rate)")
                            full_leads = validation_result['matches']
                        else:
                            logger.info(f"✓ All {filtered_count} companies match target industry")
                except Exception as e:
                    sanitized_error = sanitize_error(str(e))
                    logger.warning(f"⚠️  AI filtering failed: {sanitized_error}. Continuing with all {len(full_leads)} leads.")

            # PHASE 3.5: Email Verification
            if self.verifier and full_leads:
                logger.info("\n⏳ PHASE 3.5: Verifying emails...")
                # Only verify emails that are NOT already validated by Apify (cost optimization)
                emails_to_verify = [
                    l['email'] for l in full_leads
                    if l.get('email') and l.get('email_status') != 'validated'
                ]
                already_validated = [
                    l['email'] for l in full_leads
                    if l.get('email') and l.get('email_status') == 'validated'
                ]

                if emails_to_verify:
                    logger.info(f"Verifying {len(emails_to_verify)} non-validated emails (skipping {len(already_validated)} already validated)")
                    verification_results = self.verifier.verify_bulk(emails_to_verify)
                else:
                    verification_results = {}
                    logger.info(f"All {len(already_validated)} emails already validated by Apify, skipping verification")

                # Update leads with verification status
                for lead in full_leads:
                    email = lead.get('email')
                    if not email:
                        lead['verification_status'] = 'No Email'
                    elif lead.get('email_status') == 'validated':
                        lead['verification_status'] = 'Valid'  # Trust Apify validation
                    else:
                        lead['verification_status'] = verification_results.get(email, 'Unknown')

                valid_count = sum(1 for l in full_leads if l.get('verification_status') == 'Valid')
                logger.info(f"✓ Verification complete. Valid emails: {valid_count}")
            
            # PHASE 3.6: Generate Icebreakers (SSM)
            if self.icebreaker_gen and full_leads:
                logger.info("\n⏳ PHASE 3.6: Generating SSM Icebreakers...")
                # Filter for leads with VALID emails only (directive requirement)
                leads_to_process = [
                    l for l in full_leads
                    if l.get('email') and l.get('verification_status') == 'Valid'
                ]

                if not leads_to_process:
                    logger.warning("⚠️  No valid emails found for icebreaker generation")
                else:
                    # Run async generation (safely handles nested event loops)
                    processed_leads = run_async(self.icebreaker_gen.generate_bulk(leads_to_process, sender_context, agency_type=agency_type))
                
                    # Update full_leads with new icebreakers
                    # (processed_leads are references to objects in full_leads, so this might be redundant but safe)
                    email_map = {l['email']: l for l in processed_leads}
                    for lead in full_leads:
                        if lead.get('email') in email_map:
                            src = email_map[lead['email']]
                            lead['icebreaker'] = src.get('icebreaker', '')
                            lead['icebreaker_1'] = src.get('icebreaker_1', '')
                            lead['icebreaker_2'] = src.get('icebreaker_2', '')
                            lead['icebreaker_3'] = src.get('icebreaker_3', '')
                            lead['icebreaker_4'] = src.get('icebreaker_4', '')

                    logger.info(f"✓ Generated icebreakers for {len(processed_leads)} leads")
            
            # Save full results locally
            full_file = self.save_results(full_leads, prefix="full")
            
            # Filter for valid emails and websites (Strict Mode)
            leads_to_export = full_leads
            if valid_only:
                logger.info("\n⏳ Filtering for valid emails and websites...")
                leads_to_export = [
                    l for l in full_leads 
                    if l.get('verification_status') == 'Valid' and l.get('company_website')
                ]
                logger.info(f"✓ Filtered: {len(leads_to_export)} high-quality leads (Valid Email + Website) from {len(full_leads)} total")
            
            # Export to Google Sheets (with CSV fallback)
            logger.info("\n⏳ Exporting to Google Sheets...")
            sheet_title = f"Leads - {industry} - {datetime.now().strftime('%Y-%m-%d')}"
            sheet_url = ""
            csv_file = ""

            try:
                sheet_url = self.export_to_google_sheets(leads_to_export, sheet_title, agency_type=agency_type)
            except Exception as sheet_error:
                logger.warning(f"⚠️  Google Sheets export failed: {sheet_error}")
                logger.info("📄 Falling back to CSV export...")
                csv_file = self.export_to_csv(leads_to_export, industry, agency_type=agency_type)
            
            # PHASE 4: Final Metrics
            logger.info("\n⏳ PHASE 4: Calculating metrics...")
            
            emails_count = sum(1 for lead in full_leads if lead.get('email'))
            validated_emails = sum(1 for lead in full_leads if lead.get('email') and lead.get('email_status') == 'validated')
            
            duration = time.time() - start_time
            
            # Calculate metrics
            total_leads = len(full_leads)
            emails_count = len([l for l in full_leads if l.get('email')])
            validated_emails = len([l for l in full_leads if l.get('verification_status') == 'Valid'])
            
            metrics = {
                'total': total_leads,
                'emails': emails_count,
                'email_rate': emails_count / total_leads if total_leads > 0 else 0,
                'validated': validated_emails,
                'duration': duration
            }
            
            logger.info("=" * 60)
            logger.info("✓ Scraping completed successfully!")
            logger.info(f"📊 Total leads: {total_leads}")
            logger.info(f"📧 With emails: {emails_count} ({metrics['email_rate']:.1%})")
            logger.info(f"✅ Validated emails: {validated_emails}")
            if not skip_test:
                logger.info(f"🎯 Industry match (test): {validation['match_rate']:.1%}")
            if sheet_url:
                logger.info(f"🔗 Google Sheet: {sheet_url}")
            elif csv_file:
                logger.info(f"📄 CSV File: {csv_file}")
            logger.info(f"⏱️  Duration: {duration:.1f}s")
            logger.info("=" * 60)
            
            return {
                'success': True,
                'phase': 'complete',
                'test_results': test_leads,
                'full_results': full_leads,
                'validation': validation,
                'metrics': metrics,
                'test_file': test_file,
                'full_file': full_file,
                'sheet_url': sheet_url,
                'csv_file': csv_file
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error("=" * 60)
            logger.error(f"❌ Execution failed after {duration:.1f}s")
            import traceback
            # Sanitize error messages to prevent API key leakage
            sanitized_error = sanitize_error(str(e))
            sanitized_trace = sanitize_error(traceback.format_exc())
            logger.error(f"Error: {sanitized_error}")
            logger.error(f"Traceback:\n{sanitized_trace}")
            logger.error("=" * 60)
            
            return {
                'success': False,
                'phase': 'error',
                'error': str(e),
                'duration_seconds': duration
            }



class IcebreakerGenerator:
    """Generates personalized icebreakers using Azure OpenAI or OpenAI.

    Supports 3 agency types: recruitment, marketing, universal (default).
    Always outputs 3 pieces: Personalization, ICP, Their Service.
    """

    def __init__(self, azure_endpoint: str, api_key: str, deployment_name: str, provider: str = "azure"):
        self.provider = provider
        if provider == "azure":
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version="2024-02-15-preview"
            )
        else:
            self.client = OpenAI(api_key=api_key)
        self.deployment_name = deployment_name

    def _sanitize_text(self, text: str) -> str:
        """Sanitize input text to prevent Azure content filter triggers."""
        if not text:
            return ""
        text = text.replace('{{', '').replace('}}', '')
        text = text[:200]
        return text.strip()

    def _has_raw_placeholders(self, text: str) -> bool:
        """Check if text contains unfilled template placeholders."""
        bracket_pattern = r'\[[\w_]+\]'
        curly_pattern = r'\{\{[\w_]+\}\}'
        return bool(re.search(bracket_pattern, text)) or bool(re.search(curly_pattern, text))

    def _clean_icebreaker_output(self, text: str, clean_name: str, industry: str) -> str:
        """Best-effort regex cleanup of remaining placeholders."""
        replacements = {
            r'\[company_name\]': clean_name,
            r'\[clean_name\]': clean_name,
            r'\[industry_type\]': industry,
            r'\[target_icp\]': industry,
            r'\[function_area\]': 'business development',
            r'\[relevant_function\]': 'business development',
            r'\[relevant function\]': 'business development',
            r'\[target_department\]': 'growth',
            r'\[relevant department\]': 'growth',
            r'\[opportunity_description\]': 'companies actively looking for partners',
            r'\{\{company_name\}\}': clean_name,
            r'\{\{industry_type\}\}': industry,
            r'\{\{target_icp\}\}': industry,
            r'\{\{function_area\}\}': 'business development',
            r'\{\{opportunity_description\}\}': 'companies actively looking for partners',
        }
        result = text
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _build_recruitment_prompt(self, first_name, company_name, clean_name, job_title, industry, description) -> tuple:
        """Build prompt for recruitment agency leads. Returns (system_msg, user_prompt)."""
        system_msg = "You are an expert at analyzing recruitment agencies and writing personalized cold email pieces. Output ONLY the 3 pieces separated by |||. No explanations. No brackets or placeholder text."

        user_prompt = f"""You are generating 3 pieces for a cold email to a recruitment agency. Use the provided data (from LinkedIn) as context.

INPUT DATA:
- First Name: {first_name}
- Company: {company_name} (shortened: {clean_name})
- Job Title: {job_title}
- Industry: {industry}
- Description: {description if description else 'recruitment services'}

Output EXACTLY 3 pieces separated by "|||":

=== PIECE 1: PERSONALIZATION ===

Write a personalized icebreaker to be used in a cold email. Use the provided data (from LinkedIn) as context. Be succinct, casual, and use a very spartan tone of voice. Try to integrate a compliment on the agency's recruiting work, from the perspective of someone who doesn't know the details but recognizes their niche. No frills. Respond in plaintext only.

Rules:
- Write a Spartan/Laconic tone of voice
- Keep it short, simple, and professional
- Imply familiarity wherever possible. If you see an opportunity to imply that I like the same things, believe the same things, or want the same things as they do, go for it
- If you see an opportunity to shorten and normalize the company name (say, XYZ instead of XYZ Recruiting), do so wherever possible. More examples: "Love AMS" instead of "Love AMS Professional Services", etc
- No punctuation at the end
- Use simple language - avoid corporate jargon
- Focus on WHAT they recruit (roles/industries), not HOW they do it (process/methodology)
- Output is "Saw you..." not "Saw {{CompanyName}}..."

Follow the provided format exactly: "Saw you specialize/focus on {{specific recruiting niche or role type}}"

- Keep it in plain, professional English
- Make it sound like a real person wrote it, not a template or AI
- Be specific about the roles or industry vertical they recruit for

Example outputs (match this style):
ex1: Saw you focus on executive search for SaaS companies
ex2: Saw you specialize in placing senior finance roles
ex3: Saw you focus on healthcare leadership recruiting
ex4: Saw you specialize in filling engineering roles for startups
ex5: Saw you focus on permanent placement for logistics companies
ex6: Saw you specialize in recruiting C-suite talent for tech firms

Analysis Priority (what to look for in LinkedIn data):
- Job titles they commonly place (e.g., "CFO", "VP Engineering", "Operations Manager")
- Industries they serve (e.g., "healthcare", "fintech", "logistics", "SaaS")
- Level of roles (e.g., "executive search", "senior leadership", "mid-level", "high-volume")
- Specialization keywords (e.g., "permanent placement", "contract staffing", "retained search")
- Niche combinations (e.g., "tech sales roles for B2B companies")

Output Guidelines:
- If they recruit multiple role types, pick the most senior or specialized
- If they serve multiple industries, pick the most prominent one mentioned
- Combine role + industry when possible (e.g., "finance leaders for PE firms")
- Use professional recruiting terms: "executive search", "placing", "recruiting", "filling"
- Avoid generic phrases like "talent acquisition" or "staffing solutions"

|||

=== PIECE 2: ROLE EXTRACTION (ICP) ===

You are analyzing a recruitment agency's specialization. Extract the ONE specific role they most commonly place for their clients with MAXIMUM SPECIFICITY.

Context:
This will complete the sentence:
"I know 3 companies that need [ROLE] right now (budget approved, just need the right firm)"

This is used in cold outreach to recruitment agencies - showing you have clients seeking the exact roles they specialize in placing. The more specific the role, the more credible you sound.

Task:
Identify the ONE role this agency most frequently places for their clients (not the roles they hire internally). Be AS SPECIFIC AS POSSIBLE.

Analysis Priority:
1. Look for phrases like: "we place", "we recruit", "specializing in", "executive search for", "focused on placing"
2. Focus on their client-facing services, not internal operations
3. Identify their niche or most common placement type
4. If they place multiple roles, choose the most senior, specialized, or frequently mentioned
5. Include industry qualifier when it makes the role more specific (e.g., "healthcare CFO" vs just "CFO")

Output Rules:
Length: Exactly 2-4 words
Format:
- Uppercase ONLY: CEO, CFO, COO, CTO, CIO, CMO, VP, SVP, EVP
- Everything else: lowercase
- Industry qualifiers: lowercase (e.g., "healthcare CFO", "SaaS VP sales")

Style:
- No punctuation
- No articles (a, an, the)
- No generic phrases: "role", "position", "executive search", "talent", "professional"
- Be specific: "finance director" not "finance roles"
- Add industry/function when it adds specificity

Valid Examples (GOOD - specific):
healthcare CFO, VP sales, SaaS CTO, head of operations, finance director, senior accountant, logistics manager, warehouse supervisor, tech recruiter, pharma sales rep, supply chain director

Invalid Examples (BAD - too vague):
executive search, finance roles, senior talent, leadership positions, IT talent, C-suite

Special Cases:
If executive search firm: Use C-suite or VP-level titles (CEO, CFO, CTO, VP engineering)
If high-volume/contingent recruiting: Use mid-level or specialist titles (operations manager, sales rep, accountant)
If RPO/embedded recruiting: Focus on most common role mentioned (software engineer, product manager)
If industry-specific: Add industry qualifier when it creates specificity ("healthcare CFO" > "CFO" if they only do healthcare)

Level Hierarchy (when choosing between multiple):
1. C-Suite: CEO, CFO, COO, CTO, CMO, CIO
2. EVP/SVP level
3. VP level
4. Director level
5. Manager level
6. Specialist/Individual contributor

|||

=== PIECE 3: THEIR SERVICE ===

Based on the company data, extract ONE specific phrase describing what type of recruiting service they provide.

Output Rules:
Length: 2-5 words
Format: All lowercase
Style: No punctuation, no articles at start

Focus on their recruiting METHOD or NICHE:
- Type of search: "executive search", "retained search", "contingent recruiting", "contract staffing"
- Combined with vertical when specific: "healthcare executive search", "tech contract staffing"
- Or placement style: "permanent placement", "interim staffing", "RPO services"

Valid Examples:
executive search, retained search for tech, healthcare contract staffing, permanent placement, contingent recruiting, interim executive staffing, embedded talent acquisition

CRITICAL: Output ONLY the 3 pieces separated by |||. No labels, no "PIECE 1:" prefixes, no explanations. Plain text only."""

        return system_msg, user_prompt

    def _build_marketing_prompt(self, first_name, company_name, clean_name, job_title, industry, description) -> tuple:
        """Build prompt for marketing agency leads. Returns (system_msg, user_prompt)."""
        system_msg = "You are an expert at analyzing marketing agencies and writing personalized cold email pieces. Output ONLY the 3 pieces separated by |||. No explanations. No brackets or placeholder text."

        user_prompt = f"""You are generating 3 pieces for a cold email to a marketing agency. Use the provided data (from LinkedIn) as context.

INPUT DATA:
- First Name: {first_name}
- Company: {company_name} (shortened: {clean_name})
- Job Title: {job_title}
- Industry: {industry}
- Description: {description if description else 'marketing services'}

Output EXACTLY 3 pieces separated by "|||":

=== PIECE 1: PERSONALIZATION ===

Write a personalized icebreaker to be used in a cold email. Use the provided data (from LinkedIn) as context. Be succinct, casual, and use a very spartan tone of voice. Try to integrate a compliment on the agency's work, from the perspective of someone who doesn't know the details but recognizes their focus area. No frills. Respond in plaintext only.

Rules:
- Write a Spartan/Laconic tone of voice
- Keep it short, simple, and professional
- Imply familiarity wherever possible. If you see an opportunity to imply that I like the same things, believe the same things, or want the same things as they do, go for it
- If you see an opportunity to shorten and normalize the company name (say, XYZ instead of XYZ Marketing Agency), do so wherever possible. More examples: "Love AMS" instead of "Love AMS Digital", etc
- No punctuation at the end
- Use simple language - avoid corporate jargon
- Focus on WHAT they do (services/deliverables), not HOW they do it (process/methodology)
- Output is "Saw your..." not "Saw {{CompanyName}}..."

Follow the provided format exactly: "Saw your {{work/portfolio/projects}} {{regarding/on/around}} {{specific service}} for {{specific client type}}"

- Keep it in plain, professional English
- Make it sound like a real person wrote it, not a template or AI
- Use variations like "work on", "portfolio regarding", "projects around" to keep it natural

Example outputs (match this style):
ex1: Saw your portfolio regarding branding for finance companies
ex2: Saw your work on paid social campaigns for DTC brands
ex3: Saw your projects around content strategy for B2B SaaS
ex4: Saw your work regarding email automation for ecommerce stores
ex5: Saw your portfolio on performance marketing for startups

|||

=== PIECE 2: ICP EXTRACTION ===

You are analyzing a marketing agency's target market. Extract the ONE specific type of client they most commonly serve with MAXIMUM SPECIFICITY.

Context:
This will complete the sentence in a cold email where you're offering to connect the agency with potential clients. The ICP you extract must be:

DIFFERENT from what appears in the personalization line to avoid repetition
AS SPECIFIC AS POSSIBLE to sound like you have real leads (not generic)
Example flow:

Personalization: "Saw your portfolio regarding branding for finance companies"
Body: "I've had conversations with Series A fintech teams who need [service]"
(NOT "finance teams" - too vague. USE "Series A fintech teams" - specific and credible)

Task:
Identify the ONE client type this agency serves with MAXIMUM SPECIFICITY. Include stage/size/sub-niche whenever possible.

Analysis Priority:
First, check the Personalization (PIECE 1) to see what language was already used
Then extract ICP with MAXIMUM detail:
Add funding stage: "Series A fintech teams" not "fintech companies"
Add sub-vertical: "crypto startups" not "blockchain companies"
Add role/function: "VP marketing at SaaS startups" not "SaaS companies"
Add business model: "subscription box brands" not "ecommerce brands"
Look for phrases like: "we work with", "clients include", "specializing in", "helping", "we serve"
Prioritize SPECIFIC sub-niches over broad categories
Choose the most granular descriptor that doesn't repeat the personalization

Output Rules:
Length: Exactly 2-5 words
Format: All lowercase (no exceptions)
Style:
No punctuation
No articles (a, an, the)
ALWAYS include qualifiers (stage/size/sub-niche/role) when possible
Be as specific as credibly possible

Valid Examples (GOOD - specific):
Series A fintech teams, crypto exchange startups, wealth management firms, VP marketing at SaaS startups, Shopify store owners, B2B SaaS founders, dental practice owners, subscription box brands, mobile gaming studios, wellness brand founders

Invalid Examples (BAD - too vague):
finance teams, tech companies, ecommerce brands, startups, healthcare businesses

Special Cases:
If personalization mentions broad industry - extract specific sub-vertical + stage
"finance companies" -> "Series A fintech teams" or "crypto exchange startups"
"tech startups" -> "B2B SaaS founders" or "mobile app developers"
"ecommerce brands" -> "subscription box brands" or "Shopify store owners"
If personalization mentions stage - extract specific industry vertical + role
"early-stage startups" -> "pre-seed AI founders" or "seed-stage SaaS teams"
If personalization mentions service type - extract client descriptor with specificity
"paid social campaigns" -> "DTC fashion brands" or "Shopify store owners"

|||

=== PIECE 3: THEIR SERVICE (ACTION-ORIENTED) ===

You are analyzing a marketing agency's core service offering. Extract the ONE specific service they provide using ACTION-ORIENTED language.

Context:
This will complete the sentence in a cold email where you're offering to connect the agency with potential clients. The service you extract must be:
1. DIFFERENT from what appears in the personalization line to avoid repetition
2. ACTION-FOCUSED to sound like a real project/need (not generic capability)
3. AVOID overusing "hiring" - use more natural project-based language

Example flow:
- Personalization: "Saw your portfolio regarding branding for finance companies"
- Body: "I've had conversations with Series A fintech teams who are actively looking at revamping their brand identity"
  (NOT "need branding" - USE "revamping their brand identity" - specific action)

Task:
Identify the ONE service this agency delivers using ACTION-ORIENTED language that sounds like a real project or need.

Analysis Priority:
1. First, check the Personalization (PIECE 1) to see what service language was already used
2. Then extract service using ACTION-FOCUSED phrasing:
   - Use project language: "revamping their brand identity" not "brand strategy"
   - Use building language: "building a paid social system" not "paid social"
   - Use active needs: "looking for creative production help" not "creative services"
   - Use outcome language: "rebuilding their email funnel" not "email automation"

Look for phrases like: "we offer", "specializing in", "experts in", "delivering", "our services include"
Choose language that sounds like a REAL PROJECT or ACTIVE NEED

Output Rules:
Length: Exactly 3-6 words
Format: All lowercase (no exceptions)
Style:
No punctuation
No articles at the start (can use "a/an/the" within phrase)
Use ACTION verbs: revamping, building, launching, rebuilding, overhauling, looking for, scaling
Sound like a real project or active business need
AVOID overusing "hiring" - prioritize project-based language

Valid Examples (GOOD - action-oriented):
revamping their brand identity, building a paid social system, launching paid acquisition campaigns, rebuilding their email funnel, overhauling their content strategy, scaling their paid media, looking for creative production help, building brand strategy infrastructure, launching a rebranding project, rebuilding their organic presence

Invalid Examples (BAD - too generic/static):
brand strategy, paid social, email marketing, content creation, growth marketing

Special Cases:
If personalization mentions tactical service - extract project/building angle
"branding" -> "revamping their brand identity"
"paid ads" -> "launching paid acquisition campaigns"
If personalization mentions broad category - extract specific project/action
"content strategy" -> "overhauling their content engine"
"email automation" -> "rebuilding their email funnel"
If personalization mentions platform - extract project-based language
"Meta ads" -> "scaling their paid social"
"SEO work" -> "rebuilding their organic presence"

Action Verbs to Prioritize:
- revamping (identity/system/strategy)
- building (system/program/infrastructure)
- launching (campaign/project/initiative)
- rebuilding (funnel/system/presence)
- overhauling (strategy/approach/engine)
- scaling (media/channels/campaigns)
- looking for (help/partner/support) - use sparingly

Action Verbs to AVOID:
- hiring (too formal, overused)
- bringing on (sounds like HR)
- onboarding (too corporate)

CRITICAL: Output ONLY the 3 pieces separated by |||. No labels, no "PIECE 1:" prefixes, no explanations. Plain text only."""

        return system_msg, user_prompt

    def _build_universal_prompt(self, first_name, company_name, clean_name, job_title, industry, description) -> tuple:
        """Build prompt for universal/any lead type. Returns (system_msg, user_prompt)."""
        system_msg = "You are an expert at analyzing companies and writing personalized cold email pieces. Output ONLY the 3 pieces separated by |||. No explanations. No brackets or placeholder text."

        user_prompt = f"""You are generating 3 pieces for a cold email. Use the provided data (from LinkedIn) as context.

INPUT DATA:
- First Name: {first_name}
- Company: {company_name} (shortened: {clean_name})
- Job Title: {job_title}
- Industry: {industry}
- Description: {description if description else 'business services'}

Output EXACTLY 3 pieces separated by "|||":

=== PIECE 1: PERSONALIZATION ===

Write a personalized icebreaker to be used in a cold email. Use the provided data (from LinkedIn) as context. Be succinct, casual, and use a very spartan tone of voice. Try to integrate a compliment on the company's work, from the perspective of someone who doesn't know the details but recognizes their focus area. No frills. Respond in plaintext only.

Rules:
- Write a Spartan/Laconic tone of voice
- Keep it short, simple, and professional
- Imply familiarity wherever possible
- If you see an opportunity to shorten and normalize the company name (say, XYZ instead of XYZ Solutions Inc), do so wherever possible
- No punctuation at the end
- Use simple language - avoid corporate jargon
- Focus on WHAT they do (services/deliverables/specialization), not HOW they do it (process/methodology)
- Output starts with "Saw you..." or "Saw your..." depending on what sounds more natural

Format options (pick whichever fits best):
- "Saw you specialize/focus on {{specific niche or service}}"
- "Saw your {{work/portfolio/projects}} {{regarding/on/around}} {{specific service}} for {{specific client type}}"

Example outputs (match this style):
ex1: Saw you focus on executive search for SaaS companies
ex2: Saw your portfolio regarding branding for finance companies
ex3: Saw you specialize in placing senior finance roles
ex4: Saw your work on paid social campaigns for DTC brands
ex5: Saw you focus on healthcare leadership recruiting
ex6: Saw your projects around content strategy for B2B SaaS

- Keep it in plain, professional English
- Make it sound like a real person wrote it, not a template or AI
- Be specific about their niche, vertical, or specialization

|||

=== PIECE 2: ICP EXTRACTION ===

Extract the ONE specific type of client/customer they most commonly serve with MAXIMUM SPECIFICITY.

This will be used in a cold email body — it must be DIFFERENT from what appears in PIECE 1 to avoid repetition.

Analysis Priority:
- Determine WHO their ideal customers/clients are (not their own industry — the businesses or people they SERVE)
- Add qualifiers for maximum specificity: funding stage, sub-vertical, role/function, business model
- Look for phrases like: "we work with", "clients include", "specializing in", "helping", "we serve", "we place", "we recruit"

Output Rules:
Length: Exactly 2-5 words
Format: All lowercase (no exceptions)
Style:
No punctuation
No articles (a, an, the)
ALWAYS include qualifiers (stage/size/sub-niche/role) when possible
Be as specific as credibly possible
MUST be different from the language used in PIECE 1

Valid Examples: Series A fintech teams, crypto exchange startups, Shopify store owners, B2B SaaS founders, dental practice owners, subscription box brands, mobile gaming studios, wellness brand founders, mid-market logistics firms

Invalid Examples: finance teams, tech companies, ecommerce brands, startups, healthcare businesses

|||

=== PIECE 3: THEIR SERVICE (ACTION-ORIENTED) ===

Extract the ONE specific service/offering they provide using ACTION-ORIENTED language.

This will be used in a cold email body — it must be DIFFERENT from what appears in PIECE 1 to avoid repetition.

Analysis Priority:
- Use project language: "revamping their brand identity" not "brand strategy"
- Use building language: "building a paid social system" not "paid social"
- Use active needs: "looking for creative production help" not "creative services"
- Use outcome language: "rebuilding their email funnel" not "email automation"

Output Rules:
Length: Exactly 3-6 words
Format: All lowercase (no exceptions)
Style:
No punctuation
No articles at the start (can use "a/an/the" within phrase)
Use ACTION verbs: revamping, building, launching, rebuilding, overhauling, scaling, placing, filling, recruiting
Sound like a real project or active business need
MUST be different from the language used in PIECE 1

Valid Examples: revamping their brand identity, building a paid social system, launching paid acquisition campaigns, rebuilding their email funnel, scaling their paid media, placing senior engineering talent, filling executive leadership roles

Invalid Examples: brand strategy, paid social, email marketing, content creation, talent acquisition

CRITICAL: Output ONLY the 3 pieces separated by |||. No labels, no "PIECE 1:" prefixes, no explanations. Plain text only."""

        return system_msg, user_prompt

    async def generate_bulk(self, leads: List[Dict], sender_context: str = "", agency_type: str = "universal") -> List[Dict]:
        """
        Generate personalized cold email pieces for a list of leads.

        Args:
            leads: List of lead dicts
            sender_context: Context about the sender
            agency_type: One of 'recruitment', 'marketing', 'universal'
        """
        logger.info(f"Generating personalized messages for {len(leads)} leads (mode: {agency_type})...")

        async def process_lead(lead):
            if not lead.get('company_name') or not lead.get('job_title'):
                return lead

            # Sanitize inputs to prevent content filter issues
            first_name = self._sanitize_text(lead.get('first_name', ''))
            company_name = self._sanitize_text(lead.get('company_name', ''))
            job_title = self._sanitize_text(lead.get('job_title', ''))
            industry = self._sanitize_text(lead.get('company_industry') or lead.get('industry', 'marketing'))
            description = self._sanitize_text(lead.get('company_description', ''))

            # Clean company name (remove LLC, Inc, etc.)
            clean_name = company_name
            for suffix in [' Agency', ' Inc.', ' Inc', ' LLC', ' Ltd.', ' Ltd', ' B.V.', ' BV', ' Corp.', ' Corp',
                           ' Recruiting', ' Staffing', ' Search', ' Marketing', ' Digital', ' Media', ' Group',
                           ' Partners', ' Consulting', ' Services', ' Professional Services']:
                if clean_name.endswith(suffix):
                    clean_name = clean_name[:-len(suffix)].strip()
                    break

            # Dispatch to the right prompt builder
            if agency_type == "recruitment":
                system_msg, prompt_text = self._build_recruitment_prompt(
                    first_name, company_name, clean_name, job_title, industry, description)
            elif agency_type == "marketing":
                system_msg, prompt_text = self._build_marketing_prompt(
                    first_name, company_name, clean_name, job_title, industry, description)
            else:
                system_msg, prompt_text = self._build_universal_prompt(
                    first_name, company_name, clean_name, job_title, industry, description)

            max_attempts = 2
            raw = None

            for attempt in range(max_attempts):
                try:
                    response = await asyncio.to_thread(
                        self.client.chat.completions.create,
                        model=self.deployment_name,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt_text}
                        ],
                        temperature=0.7 if attempt == 0 else 0.5,
                        max_tokens=300
                    )
                    raw = response.choices[0].message.content.strip()

                    if not self._has_raw_placeholders(raw):
                        break  # Clean output

                    if attempt == 0:
                        logger.warning(f"Icebreaker for {lead.get('email')} contains raw placeholders, retrying...")

                except Exception as e:
                    logger.error(f"Error generating icebreaker for {lead.get('email')} (attempt {attempt+1}): {e}")
                    raw = None

            if raw:
                # Post-process: clean any remaining placeholders as last resort
                raw = self._clean_icebreaker_output(raw, clean_name, industry)

                # Strip common LLM prefixes like "PIECE 1:" or "1."
                parts = [p.strip() for p in raw.split('|||')]
                parts = [re.sub(r'^(PIECE\s*\d+[:\s]*|\d+[.\):\s]+)', '', p).strip() for p in parts]
                # Strip trailing punctuation from all pieces
                parts = [re.sub(r'[.!?,;:]+$', '', p).strip() for p in parts]

                lead['icebreaker_1'] = parts[0] if len(parts) > 0 else ''
                lead['icebreaker_2'] = parts[1] if len(parts) > 1 else ''
                lead['icebreaker_3'] = parts[2] if len(parts) > 2 else ''
                lead['icebreaker_4'] = ''
                lead['icebreaker'] = lead['icebreaker_1']
            else:
                # Fallback templates per agency type
                if agency_type == "recruitment":
                    lead['icebreaker_1'] = f"Saw you specialize in placing {industry} professionals"
                    lead['icebreaker_2'] = "senior manager"
                    lead['icebreaker_3'] = "executive search"
                elif agency_type == "marketing":
                    lead['icebreaker_1'] = f"Saw your work regarding digital marketing for {industry} companies"
                    lead['icebreaker_2'] = f"{industry} business owners"
                    lead['icebreaker_3'] = "revamping their brand strategy"
                else:
                    lead['icebreaker_1'] = f"Saw you focus on {industry} services"
                    lead['icebreaker_2'] = f"{industry} business owners"
                    lead['icebreaker_3'] = "scaling their operations"
                lead['icebreaker_4'] = ''
                lead['icebreaker'] = lead['icebreaker_1']

            return lead

        # Process in batches to avoid rate limits
        batch_size = 10
        results = []
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            batch_results = await asyncio.gather(*[process_lead(lead) for lead in batch])
            results.extend(batch_results)

        return results



def get_industry_keywords(industry: str) -> List[str]:
    """
    Get comprehensive keyword list for an industry.
    Returns detailed keywords to improve lead targeting accuracy.
    """
    industry_lower = industry.lower()
    
    # Comprehensive industry keyword mappings
    keyword_map = {
        'web3': [
            "web3", "web3 infrastructure", "blockchain", "blockchain infrastructure",
            "protocol", "L1", "layer 1", "L2", "layer 2", "zero knowledge", "zk",
            "zk rollup", "DeFi", "decentralized finance", "smart contract", "crypto",
            "cryptocurrency", "web3 security", "blockchain security", "RPC provider",
            "blockchain node", "indexer", "blockchain API", "web3 API", "web3 wallet",
            "crypto wallet", "tokenization", "NFT", "DAO", "dApp"
        ],
        'blockchain': [
            "web3", "web3 infrastructure", "blockchain", "blockchain infrastructure",
            "protocol", "L1", "layer 1", "L2", "layer 2", "zero knowledge", "zk",
            "zk rollup", "DeFi", "decentralized finance", "smart contract", "crypto",
            "cryptocurrency", "web3 security", "blockchain security", "RPC provider",
            "blockchain node", "indexer", "blockchain API", "web3 API", "web3 wallet",
            "crypto wallet", "tokenization", "NFT", "DAO", "dApp"
        ],
        'law practice': [
            "law firm", "legal services", "attorney", "lawyer", "litigation",
            "trial law", "corporate law", "intellectual property", "IP law",
            "employment law", "family law", "criminal defense", "personal injury",
            "estate planning", "tax law", "immigration law", "real estate law",
            "bankruptcy law", "civil litigation", "legal counsel", "legal representation"
        ],
        'legal services': [
            "law firm", "legal services", "attorney", "lawyer", "litigation",
            "trial law", "corporate law", "intellectual property", "IP law",
            "employment law", "family law", "criminal defense", "personal injury",
            "estate planning", "tax law", "immigration law", "real estate law",
            "bankruptcy law", "civil litigation", "legal counsel", "legal representation"
        ],
        'saas': [
            "SaaS", "software as a service", "cloud software", "B2B software",
            "enterprise software", "business software", "subscription software",
            "cloud platform", "software platform", "API platform", "PaaS",
            "platform as a service", "cloud computing", "cloud-based", "web application"
        ],
        'fintech': [
            "fintech", "financial technology", "payment processing", "digital payments",
            "mobile payments", "payment gateway", "digital banking", "neobank",
            "lending platform", "peer-to-peer lending", "crowdfunding", "insurtech",
            "wealthtech", "regtech", "cryptocurrency", "blockchain finance"
        ],
        'cybersecurity': [
            "cybersecurity", "information security", "infosec", "network security",
            "cloud security", "application security", "endpoint security",
            "threat detection", "vulnerability management", "penetration testing",
            "security operations", "SOC", "SIEM", "identity management", "IAM",
            "zero trust", "data protection", "encryption", "security compliance"
        ],
        'ai': [
            "artificial intelligence", "AI", "machine learning", "ML", "deep learning",
            "neural networks", "natural language processing", "NLP", "computer vision",
            "generative AI", "LLM", "large language model", "AI platform",
            "AI infrastructure", "MLOps", "AI automation", "predictive analytics"
        ],
        'marketing': [
            "digital marketing", "marketing automation", "email marketing",
            "content marketing", "SEO", "search engine optimization", "SEM",
            "social media marketing", "influencer marketing", "growth marketing",
            "performance marketing", "marketing analytics", "CRM", "customer engagement",
            "lead generation", "demand generation", "ABM", "account-based marketing"
        ],
        'ppc': [
            "PPC", "pay per click", "paid search", "Google Ads", "Google AdWords",
            "paid advertising", "search advertising", "display advertising",
            "Facebook Ads", "social media advertising", "paid social",
            "performance marketing", "digital advertising", "paid media",
            "search engine marketing", "SEM", "campaign management",
            "ad management", "Google Partner", "Meta Partner"
        ],
        'ppc agency': [
            "PPC agency", "paid search agency", "Google Ads agency", "AdWords agency",
            "paid advertising agency", "search advertising agency",
            "PPC management", "paid search management", "Google Ads management",
            "paid media agency", "performance marketing agency",
            "Google Partner agency", "Meta Partner agency", "Facebook Ads agency",
            "PPC services", "paid search services", "ad management services"
        ],
        'ecommerce': [
            "ecommerce", "e-commerce", "online retail", "digital commerce",
            "online marketplace", "shopping platform", "retail technology",
            "payment processing", "order management", "inventory management",
            "dropshipping", "D2C", "direct-to-consumer", "omnichannel retail"
        ],
        'healthcare': [
            "healthcare", "health tech", "digital health", "telemedicine",
            "telehealth", "medical technology", "medical device", "healthtech",
            "patient care", "EHR", "electronic health records", "medical software",
            "clinical software", "healthcare IT", "medical imaging", "diagnostics"
        ],
        'real estate': [
            "real estate", "property management", "proptech", "property technology",
            "real estate investment", "commercial real estate", "residential real estate",
            "real estate development", "property listing", "real estate platform",
            "real estate CRM", "real estate marketing", "property valuation"
        ],
        'it recruitment': [
            "IT recruitment", "technical staffing", "recruitment agency", "staffing firm",
            "headhunter", "IT staffing", "tech recruiters", "technology recruitment",
            "software recruitment agency", "technical recruiter", "IT headhunter",
            "staffing agency", "employment agency", "talent acquisition"
        ]
    }
    
    # Try to find matching keywords
    for key, keywords in keyword_map.items():
        if key in industry_lower:
            logger.info(f"✓ Auto-expanded keywords for '{industry}': {len(keywords)} keywords")
            return keywords
    
    # If no match, return empty list (will use default behavior)
    return []


def main():
    """
    Main entry point for command-line usage.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape B2B leads using Apify')
    parser.add_argument('--industry', required=True, help='Target industry')
    parser.add_argument('--fetch_count', type=int, default=100, help='Number of leads to fetch')
    parser.add_argument('--location', help='Target location (Country/State/Region)')
    parser.add_argument('--city', help='Target city')
    parser.add_argument('--job_title', nargs='+', help='Job titles to filter by')
    parser.add_argument('--company_size', nargs='+', help='Company size ranges (e.g., "11-50" "51-100")')
    parser.add_argument('--company_keywords', nargs='+', help='Company keywords')
    parser.add_argument('--company_industry', nargs='+', help='Specific Apify company industries')
    parser.add_argument('--seniority_level', nargs='+', help='Seniority levels (e.g., "owner" "founder" "director" "c_suite" "vp")')
    parser.add_argument('--skip_test', action='store_true', help='Skip the test run and validation phase')
    parser.add_argument('--valid_only', action='store_true', help='Export only verified valid emails')
    parser.add_argument('--sender_context', help='Context about the sender for SSM prompts', default="")
    parser.add_argument('--agency_type', choices=['recruitment', 'marketing', 'universal'],
                        default='universal', help='Agency type for icebreaker style (recruitment/marketing/universal)')

    args = parser.parse_args()

    # Convert args to dict and remove None values
    params = {k: v for k, v in vars(args).items() if v is not None}

    # Extract required args
    industry = params.pop('industry')
    fetch_count = params.pop('fetch_count')
    skip_test = params.pop('skip_test', False)
    valid_only = params.pop('valid_only', False)
    sender_context = params.pop('sender_context', "")
    agency_type = params.pop('agency_type', 'universal')
    
    # Auto-expand keywords if not provided
    if 'company_keywords' not in params or not params['company_keywords']:
        auto_keywords = get_industry_keywords(industry)
        if auto_keywords:
            params['company_keywords'] = auto_keywords
            logger.info(f"🔍 Using auto-expanded keywords for better targeting")
    
    scraper = ApifyLeadScraper()

    result = scraper.execute(
        industry=industry,
        fetch_count=fetch_count,
        skip_test=skip_test,
        valid_only=valid_only,
        sender_context=sender_context,
        agency_type=agency_type,
        **params
    )

    # Exit with appropriate code
    if result['success']:
        notify_success()
        sys.exit(0)
    else:
        notify_error()
        sys.exit(1)


if __name__ == '__main__':
    main()
