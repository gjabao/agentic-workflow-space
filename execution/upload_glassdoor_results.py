#!/usr/bin/env python3
"""
Quick script to upload Glassdoor results to Google Sheets
"""

import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime
import os
import sys

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_credentials():
    """Get Google OAuth credentials"""
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"⚠️  Token file issue: {e}")
            os.remove('token.json')
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Starting Google authentication...")
            print("📌 A browser window will open - please authorize the application")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)  # Use port 0 for automatic port selection

        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("✅ Authentication successful!")

    return creds

def upload_to_sheets(csv_path, sheet_name):
    """Upload CSV to Google Sheets"""

    # Read CSV and clean data
    print(f"📊 Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    df = df.fillna('')  # Replace NaN with empty strings
    print(f"✅ Found {len(df)} rows")

    # Get credentials
    creds = get_credentials()

    # Build services
    service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # Create spreadsheet
    print(f"📝 Creating Google Sheet: {sheet_name}")
    spreadsheet = {
        'properties': {'title': sheet_name}
    }
    spreadsheet = service.spreadsheets().create(
        body=spreadsheet,
        fields='spreadsheetId,spreadsheetUrl,sheets.properties.sheetId'
    ).execute()

    spreadsheet_id = spreadsheet.get('spreadsheetId')
    spreadsheet_url = spreadsheet.get('spreadsheetUrl')
    sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']

    # Prepare data
    headers = [
        'Company Name', 'Company Type', 'Company Website', 'Job Title', 'Job URL', 'Location',
        'DM Name', 'DM Title', 'DM First', 'DM Last', 'DM LinkedIn',
        'DM Email', 'Email Status', 'DM Source', 'Message', 'Scraped Date'
    ]

    values = [headers]
    for _, row in df.iterrows():
        values.append([
            str(row.get('company_name', '')),
            str(row.get('company_type', 'Other')),
            str(row.get('company_website', '')),
            str(row.get('job_title', '')),
            str(row.get('job_url', '')),
            str(row.get('location', '')),
            str(row.get('dm_name', '')),
            str(row.get('dm_title', '')),
            str(row.get('dm_first', '')),
            str(row.get('dm_last', '')),
            str(row.get('dm_linkedin', '')),
            str(row.get('dm_email', '')),
            str(row.get('email_status', '')),
            str(row.get('dm_source', '')),
            str(row.get('message', '')),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ])

    # Upload data
    print("⬆️  Uploading data to Google Sheets...")
    body = {'values': values}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range='A1',
        valueInputOption='RAW',
        body=body
    ).execute()

    # Format header
    print("🎨 Formatting header...")
    requests_format = [
        {
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': 0,
                    'endRowIndex': 1
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {'bold': True},
                        'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9}
                    }
                },
                'fields': 'userEnteredFormat(textFormat,backgroundColor)'
            }
        },
        {
            'updateSheetProperties': {
                'properties': {
                    'sheetId': sheet_id,
                    'gridProperties': {'frozenRowCount': 1}
                },
                'fields': 'gridProperties.frozenRowCount'
            }
        }
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests_format}
    ).execute()

    # Make public
    print("🔓 Making sheet publicly readable...")
    permission = {'type': 'anyone', 'role': 'reader'}
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body=permission
    ).execute()

    # Success!
    print("\n" + "="*70)
    print("✅ SUCCESS!")
    print("="*70)
    print(f"🔗 Google Sheet: {spreadsheet_url}")
    print(f"📊 Total Leads: {len(df)}")
    print("="*70)

    return spreadsheet_url

if __name__ == "__main__":
    csv_path = ".tmp/glassdoor_jobs_20260117_182222.csv"
    sheet_name = f"Glassdoor Finance Jobs - Canada - {datetime.now().strftime('%Y-%m-%d')}"

    try:
        upload_to_sheets(csv_path, sheet_name)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
