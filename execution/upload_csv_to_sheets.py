#!/usr/bin/env python3
"""
Upload CSV to Google Sheets
Quick utility to upload any CSV file to Google Sheets
"""

import os
import sys
import csv
import argparse
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def upload_csv_to_sheets(csv_file: str, sheet_name: str = None):
    """
    Upload CSV to Google Sheets

    Args:
        csv_file: Path to CSV file
        sheet_name: Optional name for the sheet

    Returns:
        Google Sheets URL
    """
    # Load credentials from token.json
    token_path = 'token.json'
    if not os.path.exists(token_path):
        print("❌ Error: token.json not found. Please authenticate first.")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(token_path)

    # Build service
    service = build('sheets', 'v4', credentials=creds)

    # Generate sheet name if not provided
    if not sheet_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sheet_name = f"Crunchbase_Leads_{timestamp}"

    print(f"⏳ Creating Google Sheet: {sheet_name}...")

    # Create spreadsheet
    spreadsheet = {
        'properties': {'title': sheet_name}
    }

    try:
        spreadsheet = service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()
    except HttpError as e:
        print(f"❌ Error creating spreadsheet: {e}")
        sys.exit(1)

    spreadsheet_id = spreadsheet.get('spreadsheetId')
    spreadsheet_url = spreadsheet.get('spreadsheetUrl')

    print(f"✓ Spreadsheet created: {spreadsheet_id}")

    # Read CSV data
    rows = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            rows.append(row)

    print(f"⏳ Uploading {len(rows)} rows to Google Sheets...")

    # Write data to sheet
    body = {
        'values': rows
    }

    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
    except HttpError as e:
        print(f"❌ Error uploading data: {e}")
        sys.exit(1)

    # Format header row (bold)
    try:
        requests = [
            {
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {'bold': True},
                            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                        }
                    },
                    'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                }
            },
            {
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': 0,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': len(rows[0]) if rows else 22
                    }
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests}
        ).execute()
    except HttpError as e:
        print(f"⚠️ Warning: Could not format header: {e}")

    # Make sheet publicly viewable (anyone with link can view)
    try:
        from googleapiclient.discovery import build as build_drive
        drive_service = build_drive('drive', 'v3', credentials=creds)

        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={
                'type': 'anyone',
                'role': 'reader'
            }
        ).execute()
        print("✓ Sheet is now publicly viewable (anyone with link)")
    except Exception as e:
        print(f"⚠️ Warning: Could not share sheet publicly: {e}")

    print(f"\n✅ Upload complete!")
    print(f"📊 Google Sheet: {spreadsheet_url}")
    print(f"   Total rows: {len(rows):,}")

    return spreadsheet_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Upload CSV to Google Sheets')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--name', help='Sheet name (optional)')

    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ Error: CSV file not found: {args.csv}")
        sys.exit(1)

    upload_csv_to_sheets(args.csv, args.name)
