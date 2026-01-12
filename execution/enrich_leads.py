#!/usr/bin/env python3
"""
Enrich Leads Script
Enriches a Google Sheet with Decision Maker info, Emails, and Personalized Messages (SSM SOP).
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
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv
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

class LeadEnricher:
    # API Config
    ANYMAILFINDER_URL = "https://api.anymailfinder.com/v5.1/find-email/person"
    RAPIDAPI_GOOGLE_SEARCH_URL = "https://google-search116.p.rapidapi.com/"
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        # 1. API Keys
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY")
        self.anymail_key = os.getenv("ANYMAILFINDER_API_KEY")
        self.azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        # 2. Azure OpenAI
        if self.azure_key and self.azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=self.azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=self.azure_endpoint
            )
        else:
            self.openai_client = None
            logger.warning("⚠️ Azure OpenAI keys missing. Personalization will be skipped.")

        # Rate Limiting
        self.rapidapi_lock = Lock()
        self.last_rapidapi_call = 0
        self.rapidapi_delay = 0.5

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

    def find_decision_maker(self, company_name: str) -> Dict:
        """Find Decision Maker via RapidAPI."""
        query = f'site:linkedin.com/in/ ("founder" OR "co-founder" OR "ceo" OR "owner" OR "managing partner") "{company_name}"'
        
        if not self.rapidapi_key:
            return {}

        try:
            with self.rapidapi_lock:
                elapsed = time.time() - self.last_rapidapi_call
                if elapsed < self.rapidapi_delay:
                    time.sleep(self.rapidapi_delay - elapsed)
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
            
            if response.status_code != 200:
                logger.warning(f"Search failed for {company_name}: {response.status_code}")
                return {}

            data = response.json()
            results = data.get('results', [])
            if not results:
                return {}

            top = results[0]
            title = top.get('title', '')
            link = top.get('url', '')
            desc = top.get('description', '')

            # Parse Name/Title
            # e.g. "John Doe - CEO - Company | LinkedIn"
            parts = title.split('-')
            name = parts[0].strip()
            role = parts[1].strip() if len(parts) > 1 else ""
            
            # Simple name split
            name_parts = name.split()
            first = name_parts[0] if name_parts else ""
            last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

            return {
                'full_name': name,
                'first_name': first,
                'last_name': last,
                'title': role,
                'linkedin': link,
                'description': desc
            }

        except Exception as e:
            logger.error(f"Error finding DM for {company_name}: {e}")
            return {}

    def find_email(self, first: str, last: str, domain: str) -> str:
        """Find email via Anymailfinder."""
        if not self.anymail_key or not first or not domain:
            return ""

        try:
            # Clean domain
            domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            
            payload = {
                'domain': domain,
                'first_name': first,
                'last_name': last
            }
            headers = {
                'Authorization': self.anymail_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.ANYMAILFINDER_URL,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('email', '')
            
            return ""
        except Exception as e:
            logger.error(f"Error finding email: {e}")
            return ""

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
        """Process a single row."""
        # Company and Website passed as args since we mapped them in execute
        
        if not company:
            return

        logger.info(f"Processing row {row_index+1}: {company}")

        # 1. Find DM
        dm = self.find_decision_maker(company)
        if not dm:
            logger.warning(f"  ❌ No DM found for {company}")
            return

        logger.info(f"  ✓ Found DM: {dm['full_name']}")

        # 2. Find Email
        email = ""
        # Use provided website or search for it if missing (simplified here to use row data or skip)
        domain = website if website else ""
        if domain and dm['first_name']:
            email = self.find_email(dm['first_name'], dm['last_name'], domain)
            if email:
                logger.info(f"  ✓ Found Email: {email}")
            else:
                logger.info(f"  ❌ No Email found")

        # 3. Generate Personalization
        msg = self.generate_personalization(company, dm, domain) # passing domain as proxy for context if desc missing
        
        # 4. Prepare Updates
        # Use col_map to map internal keys (first name) to actual sheet headers (FirstName)
        updates = {
            col_map['first name']: dm['first_name'],
            col_map['last name']: dm['last_name'],
            col_map['job title']: dm['title'],
            col_map['email']: email,
            col_map['personalization']: msg
        }
        
        if not dry_run:
            self.update_sheet_row(sheet_id, grid_id, row_index, updates, headers)
            logger.info("  ✓ Sheet updated")
        else:
            logger.info(f"  [DRY RUN] Would update: {updates}")

    def execute(self, sheet_id: str, limit: int = 10, dry_run: bool = False):
        """Main execution flow."""
        print(f"🚀 Starting Enrichment (Limit: {limit}, Dry Run: {dry_run})")
        
        data, headers, grid_id = self.read_sheet(sheet_id)
        logger.info(f"Generated headers: {headers}")
        print(f"📄 Found headers: {headers}")
        print(f"📄 Grid ID: {grid_id}")
        
        # Verify headers exist and map them
        target_cols = {
            'first name': 'FirstName',
            'last name': 'LastName',
            'job title': 'Title',
            'email': 'Email',
            'personalization': 'Personalization'
        }
        
        lower_headers = [h.lower() for h in headers]
        for key, actual in target_cols.items():
            if actual.lower() not in lower_headers:
                 logger.error(f"❌ Missing column: {actual} (for {key})")

        processed = 0
        for i, row in enumerate(data):
            if processed >= limit:
                break
            
            company = row.get('company', '').strip()
            website = row.get('corporate website', '').strip()
            
            # Row index calculation:
            # Sheet Row 1 = Headers
            # Data array starts at Row 2
            # So data[0] is Row 2
            # updateCells uses 0-based index. 
            # So Row 2 is index 1.
            # i=0 -> index=1 (i+1)
            
            # Pass grid_id
            self.process_row(row, i + 1, sheet_id, grid_id, headers, target_cols, company, website, dry_run)
            processed += 1

        print("✅ Done!")
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
