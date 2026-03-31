#!/usr/bin/env python3
"""
Enrich Google Sheet leads with personalized messages using OpenAI.

Reads leads from an existing Google Sheet, generates personalization using
the IcebreakerGenerator (OpenAI), and writes results back to the sheet.

Supports 3 modes:
  - recruitment: outputs Personalization + Roles
  - marketing:   outputs Personalization + ICP + Their Service
  - universal:   outputs Personalization + ICP + Their Service

Usage:
  python execution/enrich_sheet_personalization.py \
    --sheet_id "1EShHkc9Kn9Nczd08Z6h_JFdsaBbBTuEGDcXtt_qREfY" \
    --agency_type recruitment \
    --limit 10 \
    --dry-run
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import re
import time
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Import IcebreakerGenerator from scrape_apify_leads
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_apify_leads import IcebreakerGenerator

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async coroutine safely (handles nested event loops)."""
    try:
        loop = asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class SheetPersonalizer:
    """Reads leads from Google Sheet, generates personalization, writes back."""

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    # Flexible column name mappings (lowercase key → list of accepted variations)
    COLUMN_MAP = {
        'company_name': ['company', 'company name', 'company_name', 'companyname'],
        'first_name': ['first name', 'firstname', 'first_name', 'fname', 'prénom'],
        'last_name': ['last name', 'lastname', 'last_name', 'lname', 'nom'],
        'job_title': ['job title', 'title', 'job_title', 'jobtitle', 'position'],
        'industry': ['industry', 'company_industry', 'linkedin industry', 'sector', 'vertical'],
        'description': ['description', 'company description', 'company_description',
                        'linkedin description', 'linkedin_description', 'summary', 'about',
                        'job description'],
        'headline': ['headline', 'tagline'],
        'skills': ['skills', 'skill', 'expertise', 'linkedin specialities', 'specialities'],
        'website': ['website', 'url', 'company website', 'corporate website'],
    }

    def __init__(self):
        # Initialize OpenAI-powered IcebreakerGenerator
        openai_key = os.getenv("OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if openai_key:
            self.generator = IcebreakerGenerator(None, openai_key, "gpt-4o", provider="openai")
            logger.info("✓ Using OpenAI API for personalization")
        elif azure_endpoint and azure_key:
            self.generator = IcebreakerGenerator(azure_endpoint, azure_key, azure_deployment, provider="azure")
            logger.info("✓ Using Azure OpenAI for personalization")
        else:
            raise ValueError("❌ OPENAI_API_KEY or AZURE_OPENAI_API_KEY+ENDPOINT required in .env")

        self._sheets_service = None
        logger.info("✓ SheetPersonalizer initialized")

    def _get_sheets_service(self):
        """Get cached Google Sheets service."""
        if not self._sheets_service:
            creds = self.get_credentials()
            self._sheets_service = build('sheets', 'v4', credentials=creds)
        return self._sheets_service

    def get_credentials(self):
        """Get Google OAuth credentials from token.json."""
        creds = None
        if os.path.exists('token.json'):
            try:
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
            except Exception as e:
                logger.warning(f"Error loading token.json: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing token...")
                creds.refresh(Request())
            elif creds:
                return creds
            else:
                raise Exception("❌ No valid credentials. Run enrich_leads.py locally first to authenticate.")

        return creds

    def read_sheet(self, sheet_id: str) -> Tuple[List[Dict], List[str], int]:
        """Read all data from a Google Sheet.

        Returns:
            (data_rows, headers, grid_sheet_id)
        """
        service = self._get_sheets_service()

        # Get spreadsheet metadata
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = meta.get('sheets', [])
        if not sheets:
            raise Exception("No sheets found in spreadsheet")

        grid_id = sheets[0]['properties']['sheetId']
        sheet_title = sheets[0]['properties']['title']
        logger.info(f"Reading sheet: '{sheet_title}' (gid: {grid_id})")

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A:Z"
        ).execute()
        values = result.get('values', [])

        if not values:
            return [], [], grid_id

        headers = values[0]
        data = []
        for row in values[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            data.append(dict(zip(headers, padded_row)))

        logger.info(f"✓ Read {len(data)} rows with {len(headers)} columns")
        return data, headers, grid_id

    def _find_column(self, headers: List[str], field: str) -> Optional[str]:
        """Find the actual column header name for a given field (case-insensitive)."""
        variations = self.COLUMN_MAP.get(field, [])
        headers_lower = {h.lower().strip(): h for h in headers}

        for variation in variations:
            if variation in headers_lower:
                return headers_lower[variation]

        return None

    def _map_row_to_lead(self, row: Dict, headers: List[str]) -> Dict:
        """Map a sheet row to the lead dict format expected by IcebreakerGenerator."""
        lead = {}

        # Map simple fields using flexible column detection
        simple_mappings = {
            'company_name': 'company_name',
            'first_name': 'first_name',
            'last_name': 'last_name',
            'job_title': 'job_title',
            'industry': 'company_industry',
            'website': 'company_website',
        }

        for sheet_field, lead_field in simple_mappings.items():
            col_name = self._find_column(headers, sheet_field)
            if col_name and row.get(col_name):
                lead[lead_field] = row[col_name]

        # Build a rich description by scanning ALL description-like columns in the row
        # This catches: summary, linkedin description, job description, headline, skills, etc.
        desc_columns = [
            'summary', 'linkedin description', 'job description', 'description',
            'company description', 'about', 'linkedin specialities', 'headline',
        ]
        headers_lower = {h.lower().strip(): h for h in headers}
        desc_parts = []
        for col_lower in desc_columns:
            actual_col = headers_lower.get(col_lower)
            if actual_col and row.get(actual_col):
                desc_parts.append(row[actual_col])
        if desc_parts:
            lead['company_description'] = ' | '.join(desc_parts)

        return lead

    def _ensure_output_columns(self, sheet_id: str, grid_id: int, headers: List[str],
                                agency_type: str) -> List[str]:
        """Add output columns to the sheet if they don't exist. Returns updated headers."""
        service = self._get_sheets_service()

        if agency_type == "recruitment":
            needed_cols = ["Personalization", "Roles"]
        else:
            needed_cols = ["Personalization", "ICP", "Their Service"]

        missing_cols = [c for c in needed_cols if c not in headers]

        if not missing_cols:
            return headers

        # Append missing columns as new headers
        new_headers = headers + missing_cols
        col_start = len(headers)

        # Write new header cells
        requests = []
        for i, col_name in enumerate(missing_cols):
            col_idx = col_start + i
            requests.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": col_name},
                                          "userEnteredFormat": {"textFormat": {"bold": True}}}]}],
                    "fields": "userEnteredValue,userEnteredFormat.textFormat.bold",
                    "range": {
                        "sheetId": grid_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }
                }
            })

        if requests:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id, body={"requests": requests}
            ).execute()
            logger.info(f"✓ Added columns: {missing_cols}")

        return new_headers

    def _write_row(self, sheet_id: str, grid_id: int, row_index: int,
                   updates: Dict[str, str], headers: List[str]):
        """Write values to specific columns of a row (with rate limit retry)."""
        service = self._get_sheets_service()

        requests = []
        for col_name, value in updates.items():
            if col_name not in headers:
                continue
            col_idx = headers.index(col_name)
            requests.append({
                "updateCells": {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": str(value)}}]}],
                    "fields": "userEnteredValue",
                    "range": {
                        "sheetId": grid_id,
                        "startRowIndex": row_index,
                        "endRowIndex": row_index + 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    }
                }
            })

        if requests:
            for attempt in range(5):
                try:
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id, body={"requests": requests}
                    ).execute()
                    break
                except Exception as e:
                    if '429' in str(e) and attempt < 4:
                        wait = 2 ** attempt + 5
                        logger.warning(f"  ⚠️ Rate limited, waiting {wait}s (attempt {attempt+1}/5)...")
                        time.sleep(wait)
                    else:
                        raise

    def execute(self, sheet_id: str, agency_type: str = "universal",
                limit: int = 0, dry_run: bool = False):
        """Main execution flow.

        Args:
            sheet_id: Google Sheet ID (or full URL)
            agency_type: recruitment / marketing / universal
            limit: Max rows to process (0 = all)
            dry_run: If True, print results without writing to sheet
        """
        # Extract sheet ID from URL if needed
        sheet_id = self._extract_sheet_id(sheet_id)

        logger.info(f"\n{'='*60}")
        logger.info(f"Sheet Personalization — mode: {agency_type}")
        logger.info(f"Sheet ID: {sheet_id}")
        logger.info(f"{'='*60}\n")

        # 1. Read sheet
        data, headers, grid_id = self.read_sheet(sheet_id)
        if not data:
            logger.error("❌ Sheet is empty")
            return

        # 2. Ensure output columns exist
        if not dry_run:
            headers = self._ensure_output_columns(sheet_id, grid_id, headers, agency_type)

        # 3. Apply limit
        rows_to_process = data[:limit] if limit > 0 else data
        logger.info(f"⏳ Processing {len(rows_to_process)} leads...")

        # 4. Convert rows to lead format
        leads = []
        for i, row in enumerate(rows_to_process):
            lead = self._map_row_to_lead(row, headers)
            lead['_row_index'] = i + 1  # 1-indexed (row 0 = headers, row 1 = first data)
            lead['_original_row'] = row
            leads.append(lead)

        # Skip rows without company name
        valid_leads = [l for l in leads if l.get('company_name')]
        skipped = len(leads) - len(valid_leads)
        if skipped > 0:
            logger.warning(f"⚠️  Skipped {skipped} rows without company name")

        # 5. Generate personalization
        logger.info(f"\n⏳ Generating personalization for {len(valid_leads)} leads (mode: {agency_type})...")
        processed_leads = run_async(self.generator.generate_bulk(valid_leads, agency_type=agency_type))

        # 6. Output results — collect all updates, then batch write
        success_count = 0
        all_requests = []
        for lead in processed_leads:
            personalization = lead.get('icebreaker_1', '')
            row_idx = lead['_row_index']
            company = lead.get('company_name', 'Unknown')

            if not personalization:
                logger.warning(f"  ⚠️  Row {row_idx + 1}: {company} — no personalization generated")
                continue

            success_count += 1

            if agency_type == "recruitment":
                roles = lead.get('icebreaker_2', '')
                updates = {"Personalization": personalization, "Roles": roles}
            else:
                icp = lead.get('icebreaker_2', '')
                service_val = lead.get('icebreaker_3', '')
                updates = {"Personalization": personalization, "ICP": icp, "Their Service": service_val}

            if dry_run:
                logger.info(f"\n  Row {row_idx + 1}: {company}")
                for k, v in updates.items():
                    logger.info(f"    {k}: {v}")
            else:
                # Build requests for this row
                for col_name, value in updates.items():
                    if col_name not in headers:
                        continue
                    col_idx = headers.index(col_name)
                    all_requests.append({
                        "updateCells": {
                            "rows": [{"values": [{"userEnteredValue": {"stringValue": str(value)}}]}],
                            "fields": "userEnteredValue",
                            "range": {
                                "sheetId": grid_id,
                                "startRowIndex": row_idx,
                                "endRowIndex": row_idx + 1,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            }
                        }
                    })

        # Batch write all updates in chunks of 50 rows (~100-150 requests)
        if not dry_run and all_requests:
            svc = self._get_sheets_service()
            chunk_size = 150  # ~50 rows × 2-3 columns
            for i in range(0, len(all_requests), chunk_size):
                chunk = all_requests[i:i + chunk_size]
                for attempt in range(5):
                    try:
                        svc.spreadsheets().batchUpdate(
                            spreadsheetId=sheet_id, body={"requests": chunk}
                        ).execute()
                        rows_done = min(i + chunk_size, len(all_requests))
                        pct = (rows_done / len(all_requests)) * 100
                        logger.info(f"  ⏳ Written: {rows_done}/{len(all_requests)} cells ({pct:.0f}%)")
                        break
                    except Exception as e:
                        if '429' in str(e) and attempt < 4:
                            wait = 2 ** attempt + 5
                            logger.warning(f"  ⚠️ Rate limited, waiting {wait}s...")
                            time.sleep(wait)
                        else:
                            raise
                # Small delay between chunks to avoid rate limits
                if i + chunk_size < len(all_requests):
                    time.sleep(2)

        # 7. Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"✓ Complete!")
        logger.info(f"  Total rows: {len(rows_to_process)}")
        logger.info(f"  Personalized: {success_count}/{len(valid_leads)}")
        logger.info(f"  Mode: {agency_type}")
        if dry_run:
            logger.info(f"  ⚠️  DRY RUN — no changes written to sheet")
        else:
            logger.info(f"  → Sheet updated: https://docs.google.com/spreadsheets/d/{sheet_id}")
        logger.info(f"{'='*60}\n")

    @staticmethod
    def _extract_sheet_id(sheet_id_or_url: str) -> str:
        """Extract sheet ID from a full Google Sheets URL or return as-is."""
        # Match: https://docs.google.com/spreadsheets/d/SHEET_ID/edit...
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_id_or_url)
        if match:
            return match.group(1)
        return sheet_id_or_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Enrich Google Sheet leads with personalized messages using OpenAI'
    )
    parser.add_argument('--sheet_id', required=True,
                        help='Google Sheet ID or full URL')
    parser.add_argument('--agency_type', choices=['recruitment', 'marketing', 'universal'],
                        default='universal',
                        help='Agency type for personalization style (default: universal)')
    parser.add_argument('--limit', type=int, default=0,
                        help='Max rows to process (0 = all)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print results without writing to sheet')

    args = parser.parse_args()

    personalizer = SheetPersonalizer()
    personalizer.execute(
        sheet_id=args.sheet_id,
        agency_type=args.agency_type,
        limit=args.limit,
        dry_run=args.dry_run,
    )
