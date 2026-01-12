#!/usr/bin/env python3
"""
Email Verification from Google Sheets
--------------------------------------
Reads Apollo leads from Google Sheets, verifies emails with SSMasters,
exports ONLY valid emails to a new Google Sheet.

Usage:
    python execution/verify_apollo_sheet.py <google_sheet_url>

Example:
    python execution/verify_apollo_sheet.py "https://docs.google.com/spreadsheets/d/1abc..."
"""

import os
import sys
import logging
import time
import requests
import csv
import io
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils_notifications import notify_success, notify_error

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_google_creds():
    """Get Google Sheets credentials."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                logger.error("❌ credentials.json not found")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def extract_sheet_id(url: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL."""
    if '/d/' in url:
        return url.split('/d/')[1].split('/')[0]
    return url


def read_sheet(sheet_url: str) -> List[Dict]:
    """
    Read leads from Google Sheets.

    Args:
        sheet_url: Google Sheets URL or ID

    Returns:
        List of lead dictionaries
    """
    logger.info("📂 Reading Google Sheet...")

    creds = get_google_creds()
    if not creds:
        return []

    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_id = extract_sheet_id(sheet_url)

        # Read all data from first sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range='A1:ZZ'  # Read all columns
        ).execute()

        values = result.get('values', [])
        if not values:
            logger.error("❌ Sheet is empty")
            return []

        # First row is headers
        headers = values[0]
        leads = []

        for row in values[1:]:
            # Pad row to match header length
            row = row + [''] * (len(headers) - len(row))
            lead = dict(zip(headers, row))
            leads.append(lead)

        logger.info(f"✓ Read {len(leads)} leads from sheet")
        return leads

    except HttpError as e:
        logger.error(f"❌ Error reading sheet: {e}")
        return []


def verify_single_batch(batch_emails: List[str], api_key: str, batch_num: int, total_batches: int) -> Dict[str, str]:
    """
    Verify a single batch of emails using SSMasters bulk API.

    Args:
        batch_emails: List of email addresses (max 50)
        api_key: SSMasters API key
        batch_num: Current batch number
        total_batches: Total number of batches

    Returns:
        Dict mapping email -> status (Valid, Invalid, Catch-All, etc.)
    """
    if not batch_emails:
        return {}

    logger.info(f"   📦 Batch {batch_num}/{total_batches}: Verifying {len(batch_emails)} emails...")

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['email'])
    for email in batch_emails:
        writer.writerow([email])
    csv_content = output.getvalue()

    # Upload for verification
    try:
        files = {
            'csvFile': (f'batch_{batch_num}.csv', csv_content, 'text/csv')
        }
        data = {'apiKey': api_key}

        response = requests.post(
            "https://ssmasters.com/api/v1/public/verify/bulk",
            files=files,
            data=data,
            timeout=30
        )

        if response.status_code != 202:
            logger.error(f"      ❌ Batch {batch_num} upload failed: {response.status_code}")
            return {}

        result = response.json()
        if not result.get('success'):
            logger.error(f"      ❌ Batch {batch_num} failed: {result.get('message')}")
            return {}

        request_id = result['requestId']

        # Poll for results with exponential backoff
        max_retries = 60
        poll_interval = 2  # Start with 2 seconds

        for attempt in range(max_retries):
            time.sleep(poll_interval)
            try:
                status_response = requests.get(
                    f"https://ssmasters.com/api/v1/public/request/{request_id}/status",
                    params={'apiKey': api_key},
                    timeout=30
                )

                if status_response.status_code != 200:
                    continue

                data = status_response.json()
                status = data['request']['status']

                if status == 'completed':
                    results = {}
                    for item in data['request']['results']:
                        results[item['email'].lower()] = item['status']
                    logger.info(f"      ✓ Batch {batch_num} complete ({len(results)} emails)")
                    return results

                if status == 'failed':
                    logger.error(f"      ❌ Batch {batch_num} failed during processing")
                    return {}

                # Exponential backoff: increase poll interval gradually
                if attempt > 10:
                    poll_interval = min(10, poll_interval * 1.2)

            except Exception as e:
                continue

        logger.error(f"      ❌ Batch {batch_num} timed out")
        return {}

    except Exception as e:
        logger.error(f"      ❌ Batch {batch_num} error: {e}")
        return {}


def verify_emails_batch(emails: List[str], api_key: str) -> Dict[str, str]:
    """
    Verify emails using SSMasters bulk API with batching and parallel processing.

    Args:
        emails: List of email addresses
        api_key: SSMasters API key

    Returns:
        Dict mapping email -> status (Valid, Invalid, Catch-All, etc.)
    """
    if not emails:
        return {}

    logger.info(f"⏳ Verifying {len(emails)} emails...")

    # Deduplicate emails
    unique_emails = list(set([e.strip().lower() for e in emails if e]))
    logger.info(f"   ({len(unique_emails)} unique emails after deduplication)")

    # Split into batches of 50
    batch_size = 50
    batches = [unique_emails[i:i+batch_size] for i in range(0, len(unique_emails), batch_size)]
    total_batches = len(batches)

    logger.info(f"   Processing {total_batches} batches in parallel (up to 5 concurrent)...\n")

    # Process batches in parallel
    all_results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all batch jobs
        future_to_batch = {
            executor.submit(verify_single_batch, batch, api_key, i+1, total_batches): i+1
            for i, batch in enumerate(batches)
        }

        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                batch_results = future.result()
                all_results.update(batch_results)
            except Exception as e:
                logger.error(f"      ❌ Batch {batch_num} exception: {e}")

    logger.info(f"\n✓ All batches complete: {len(all_results)} emails verified")
    return all_results


def export_to_sheet(leads: List[Dict], title: str) -> str:
    """
    Export leads to new Google Sheet.

    Args:
        leads: List of leads to export
        title: Sheet title

    Returns:
        URL of created sheet
    """
    logger.info("\n⏳ Exporting to Google Sheets...")

    creds = get_google_creds()
    if not creds:
        return ""

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Create spreadsheet
        spreadsheet = {
            'properties': {'title': title}
        }
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        spreadsheet_id = spreadsheet.get('spreadsheetId')
        spreadsheet_url = spreadsheet.get('spreadsheetUrl')

        if not leads:
            return spreadsheet_url

        # Prepare data with headers
        headers = list(leads[0].keys())
        values = [headers]

        for lead in leads:
            row = [lead.get(h, '') for h in headers]
            values.append(row)

        # Write data
        body = {'values': values}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='RAW',
            body=body
        ).execute()

        # Format header row (bold)
        requests_body = {
            'requests': [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True}
                            }
                        },
                        'fields': 'userEnteredFormat.textFormat.bold'
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=requests_body
        ).execute()

        logger.info(f"✓ Export complete!")
        return spreadsheet_url

    except HttpError as e:
        logger.error(f"❌ Export error: {e}")
        return ""


def main():
    if len(sys.argv) < 2:
        logger.error("❌ Usage: python verify_apollo_sheet.py <google_sheet_url>")
        sys.exit(1)

    sheet_url = sys.argv[1]

    logger.info("="*60)
    logger.info("🔍 Email Verification System")
    logger.info("="*60)

    # Read leads from sheet
    leads = read_sheet(sheet_url)
    if not leads:
        logger.error("❌ No leads found in sheet")
        return

    # Extract emails
    # Try common column names for email
    email_columns = ['Email', 'email', 'EMAIL', 'Email Address', 'email_address']
    email_key = None

    for col in email_columns:
        if col in leads[0]:
            email_key = col
            break

    if not email_key:
        logger.error(f"❌ No email column found. Looking for one of: {email_columns}")
        logger.info(f"   Available columns: {list(leads[0].keys())}")
        return

    logger.info(f"📧 Found email column: '{email_key}'")

    # Filter leads with emails
    leads_with_emails = [l for l in leads if l.get(email_key, '').strip()]
    logger.info(f"📧 Leads with emails: {len(leads_with_emails)} / {len(leads)}")

    if not leads_with_emails:
        logger.error("❌ No leads with email addresses found")
        return

    # Get API key
    api_key = os.getenv("SSMASTERS_API_KEY")
    if not api_key:
        logger.error("❌ SSMASTERS_API_KEY not found in .env file")
        return

    # Verify emails
    emails = [l[email_key] for l in leads_with_emails]
    verification_results = verify_emails_batch(emails, api_key)

    if not verification_results:
        logger.error("❌ Verification failed")
        return

    # Add verification status to leads
    for lead in leads_with_emails:
        email = lead[email_key].strip().lower()
        lead['Verification Status'] = verification_results.get(email, 'Unknown')

    # Filter to VALID emails only
    valid_leads = [l for l in leads_with_emails if l['Verification Status'] == 'Valid']

    # Calculate stats
    valid_count = len(valid_leads)
    invalid_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Invalid')
    catchall_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Catch-All')
    unknown_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Unknown')

    logger.info("\n" + "="*60)
    logger.info("📊 Verification Results")
    logger.info("="*60)
    logger.info(f"Total leads: {len(leads)}")
    logger.info(f"Leads with emails: {len(leads_with_emails)}")
    logger.info(f"✅ Valid: {valid_count} ({valid_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"⚠️  Catch-All: {catchall_count} ({catchall_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"❌ Invalid: {invalid_count} ({invalid_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"❓ Unknown: {unknown_count}")
    logger.info("="*60)

    if not valid_leads:
        logger.warning("\n⚠️  No valid emails found. Nothing to export.")
        return

    # Export valid leads only
    sheet_title = f"Valid Emails - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    sheet_url = export_to_sheet(valid_leads, sheet_title)

    if sheet_url:
        logger.info("\n" + "="*60)
        logger.info("✓ SUCCESS!")
        logger.info("="*60)
        logger.info(f"📊 Exported {len(valid_leads)} valid emails")
        logger.info(f"🔗 Google Sheet: {sheet_url}")
        logger.info("="*60 + "\n")
        notify_success()
    else:
        logger.error("❌ Export failed")
        notify_error()
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)
