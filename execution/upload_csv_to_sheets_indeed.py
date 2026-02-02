#!/usr/bin/env python3
"""
Upload Indeed CSV to Google Sheets
Handles OAuth authentication and exports CSV data to a new Google Sheet
"""

import os
import sys
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Google OAuth Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_credentials():
    """Get Google OAuth credentials with proper token handling."""
    creds = None

    # Delete old token to force re-authentication with correct scopes
    if os.path.exists('token.json'):
        print("🔄 Removing old token to re-authenticate with correct scopes...")
        os.remove('token.json')

    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found")
        return None

    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8080)

    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    print("✓ Authentication successful!")
    return creds

def export_to_google_sheets(csv_path: str, sheet_title: str) -> str:
    """Export CSV to Google Sheets."""
    print(f"📊 Reading CSV: {csv_path}")

    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"✓ Found {len(df)} rows")

    # Get credentials
    creds = get_credentials()
    if not creds:
        return ""

    try:
        # Build services
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # Create spreadsheet
        print(f"📝 Creating Google Sheet: {sheet_title}")
        spreadsheet = {'properties': {'title': sheet_title}}
        spreadsheet = sheets_service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl,sheets.properties.sheetId'
        ).execute()

        spreadsheet_id = spreadsheet.get('spreadsheetId')
        spreadsheet_url = spreadsheet.get('spreadsheetUrl')
        sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']

        # Prepare data
        headers = list(df.columns)
        values = [headers] + df.values.tolist()

        # Upload data
        print(f"⬆️ Uploading {len(values)} rows...")
        body = {'values': values}
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body=body
        ).execute()

        # Format header
        print("🎨 Formatting sheet...")
        requests_format = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
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
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1}
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            }
        ]
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests_format}
        ).execute()

        # Make public
        print("🌐 Making sheet public...")
        permission = {'type': 'anyone', 'role': 'reader'}
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body=permission
        ).execute()

        print(f"\n✅ SUCCESS!")
        print(f"🔗 Google Sheet URL: {spreadsheet_url}\n")
        return spreadsheet_url

    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return ""

def main():
    """Main function with CLI arguments."""
    import argparse

    parser = argparse.ArgumentParser(description='Upload Indeed CSV to Google Sheets')
    parser.add_argument('--csv', type=str, required=True, help='Path to CSV file')
    parser.add_argument('--title', type=str, default=None, help='Google Sheet title')

    args = parser.parse_args()

    # Generate title if not provided
    if not args.title:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        args.title = f"Indeed Jobs - {timestamp}"

    # Export
    url = export_to_google_sheets(args.csv, args.title)

    if url:
        print(f"\n📋 RESULTS:")
        print(f"   CSV: {args.csv}")
        print(f"   Sheet: {url}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()