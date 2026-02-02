#!/usr/bin/env python3
"""
Upload Crunchbase CSV to Google Sheets
Handles OAuth token refresh and creates new sheet
"""

import os
import sys
import csv
import logging
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_credentials():
    """Get valid Google Sheets credentials"""
    creds = None

    # Try to load existing token
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            logger.warning(f"Could not load token.json: {e}")
            if os.path.exists('token.json'):
                os.remove('token.json')
                logger.info("Removed invalid token.json")

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired OAuth token...")
                creds.refresh(Request())
                logger.info("✓ Token refreshed successfully")
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                logger.info("Creating new token...")
                creds = None

        if not creds:
            if not os.path.exists('credentials.json'):
                logger.error("❌ credentials.json not found")
                sys.exit(1)

            logger.info("Opening browser for OAuth authentication...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
            logger.info("✓ Authentication successful")

        # Save credentials
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        logger.info("✓ Credentials saved to token.json")

    return creds

def upload_csv_to_sheets(csv_file: str, sheet_title: str = None):
    """Upload CSV to new Google Sheet"""

    if not os.path.exists(csv_file):
        logger.error(f"❌ CSV file not found: {csv_file}")
        return None

    # Read CSV data
    logger.info(f"📄 Reading CSV: {csv_file}")
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    logger.info(f"✓ Loaded {len(rows)} rows (including header)")

    # Get credentials
    creds = get_credentials()

    # Create Google Sheets service
    service = build('sheets', 'v4', credentials=creds)

    # Create new spreadsheet
    if not sheet_title:
        sheet_title = f"Crunchbase Leads - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    logger.info(f"📊 Creating Google Sheet: {sheet_title}")

    spreadsheet = {
        'properties': {'title': sheet_title}
    }
    spreadsheet = service.spreadsheets().create(
        body=spreadsheet,
        fields='spreadsheetId,spreadsheetUrl'
    ).execute()

    spreadsheet_id = spreadsheet.get('spreadsheetId')
    spreadsheet_url = spreadsheet.get('spreadsheetUrl')

    logger.info(f"✓ Sheet created: {spreadsheet_url}")

    # Upload data
    logger.info(f"⏳ Uploading {len(rows)} rows...")

    body = {
        'values': rows
    }

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range='A1',
        valueInputOption='RAW',
        body=body
    ).execute()

    # Format header row
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
                        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "bold": True
                        }
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)"
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
        body={'requests': requests}
    ).execute()

    logger.info(f"✓ Uploaded {len(rows)-1} decision-makers to Google Sheets")
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"✅ SUCCESS! Google Sheet URL:")
    logger.info(f"{spreadsheet_url}")
    logger.info("=" * 70)

    return spreadsheet_url

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Upload Crunchbase CSV to Google Sheets")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument("--title", help="Sheet title (optional)")

    args = parser.parse_args()

    upload_csv_to_sheets(args.csv_file, args.title)

if __name__ == "__main__":
    main()
