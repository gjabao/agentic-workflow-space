#!/usr/bin/env python3
"""
Helper script to upload CSV to a new Google Sheet
Usage: python execution/upload_csv_to_new_sheet.py --csv "file.csv" --title "Sheet Title"
"""

import os
import sys
import pandas as pd
import argparse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise ValueError("❌ credentials.json not found")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def create_sheet_and_upload(csv_path: str, title: str):
    # Read CSV (keep empty strings, don't convert to NaN)
    df = pd.read_csv(csv_path, keep_default_na=False)
    print(f"✓ Read CSV: {len(df)} rows, {len(df.columns)} columns")

    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)

    # Create new spreadsheet
    spreadsheet = {
        'properties': {'title': title},
        'sheets': [{'properties': {'title': 'Sheet1'}}]
    }

    spreadsheet = service.spreadsheets().create(
        body=spreadsheet,
        fields='spreadsheetId,spreadsheetUrl'
    ).execute()

    sheet_id = spreadsheet.get('spreadsheetId')
    sheet_url = spreadsheet.get('spreadsheetUrl')

    print(f"✓ Created sheet: {sheet_url}")

    # Upload data (convert to list, replace NaN with empty string)
    values = [df.columns.tolist()]
    for _, row in df.iterrows():
        values.append([str(v) if pd.notna(v) else '' for v in row.tolist()])

    body = {'values': values}

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body=body
    ).execute()

    print(f"✓ Uploaded {len(df)} rows")
    print(f"\n📋 SHEET ID: {sheet_id}")
    print(f"🔗 URL: {sheet_url}\n")

    return sheet_id, sheet_url

def main():
    parser = argparse.ArgumentParser(description='Upload CSV to new Google Sheet')
    parser.add_argument('--csv', required=True, help='CSV file path')
    parser.add_argument('--title', required=True, help='Sheet title')
    args = parser.parse_args()

    try:
        sheet_id, sheet_url = create_sheet_and_upload(args.csv, args.title)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
