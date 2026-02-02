#!/usr/bin/env python3
"""
Upload Clutch Lead CSV to Google Sheets
Utility script to upload existing Clutch lead CSV files to Google Sheets
Based on: upload_csv_to_sheets_crunchbase.py
"""

import os
import sys
import csv
import argparse
import logging
from typing import List, Dict
from datetime import datetime

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']


def read_csv(csv_path: str) -> List[Dict]:
    """Read CSV file and return list of dictionaries"""
    logger.info(f"📄 Reading CSV: {csv_path}")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    leads = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    logger.info(f"✓ Loaded {len(leads)} leads from CSV")
    return leads


def upload_to_google_sheets(leads: List[Dict], sheet_title: str) -> str:
    """Upload leads to new Google Sheet"""
    logger.info("📊 Uploading to Google Sheets...")

    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"❌ OAuth token refresh failed: {e}")
                return ""
        else:
            if not os.path.exists('credentials.json'):
                logger.error("❌ credentials.json not found")
                logger.error("Please download OAuth credentials from Google Cloud Console")
                return ""

            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Create new spreadsheet
        spreadsheet = {
            'properties': {'title': sheet_title}
        }
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        spreadsheet_id = spreadsheet.get('spreadsheetId')
        spreadsheet_url = spreadsheet.get('spreadsheetUrl')

        logger.info(f"✓ Created sheet: {sheet_title}")

        if not leads:
            logger.warning("⚠️  No leads to upload")
            return spreadsheet_url

        # Prepare data
        headers = list(leads[0].keys())
        values = [headers]

        for lead in leads:
            values.append([str(lead.get(h, '')) for h in headers])

        # Upload data
        body = {'values': values}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body=body
        ).execute()

        logger.info(f"✓ Uploaded {len(leads)} rows")

        # Format header row (bold + blue background)
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

        logger.info("✓ Applied formatting")

        return spreadsheet_url

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return ""


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Upload Clutch Lead CSV to Google Sheets"
    )
    parser.add_argument(
        "csv_file",
        help="Path to CSV file (e.g., clutch_leads_20260130.csv)"
    )
    parser.add_argument(
        "--title",
        help="Google Sheet title (default: auto-generated from filename)"
    )

    args = parser.parse_args()

    # Generate title from filename if not provided
    if args.title:
        sheet_title = args.title
    else:
        base_name = os.path.basename(args.csv_file).replace('.csv', '')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        sheet_title = f"Clutch Leads - {base_name} - {timestamp}"

    try:
        # Read CSV
        leads = read_csv(args.csv_file)

        # Upload to Google Sheets
        sheet_url = upload_to_google_sheets(leads, sheet_title)

        if sheet_url:
            logger.info("=" * 70)
            logger.info("UPLOAD COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Google Sheet: {sheet_url}")
            logger.info("=" * 70)
        else:
            logger.error("❌ Upload failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Upload interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()