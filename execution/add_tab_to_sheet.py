#!/usr/bin/env python3
"""
Add a new tab to an existing Google Sheet and populate with CSV data
Usage: python execution/add_tab_to_sheet.py --csv "file.csv" --sheet-id "SHEET_ID" --tab-name "Tab Name"
"""

import os
import sys
import csv
import argparse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except:
            pass

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

def add_tab_and_upload(csv_path: str, sheet_id: str, tab_name: str):
    # Read CSV
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    print(f"✓ Read CSV: {len(rows)-1} data rows + header")

    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)

    # Check if tab already exists
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing_tabs = [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]

    if tab_name in existing_tabs:
        print(f"⚠️  Tab '{tab_name}' already exists. Clearing and updating...")
        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A1:ZZ"
        ).execute()
    else:
        # Create new tab
        request_body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': tab_name
                    }
                }
            }]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body=request_body
        ).execute()
        print(f"✓ Created new tab: '{tab_name}'")

    # Upload data
    body = {'values': rows}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body=body
    ).execute()

    print(f"✓ Uploaded {len(rows)-1} rows to '{tab_name}'")
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    print(f"\n🔗 URL: {sheet_url}\n")

    return sheet_url

def main():
    parser = argparse.ArgumentParser(description='Add tab to existing Google Sheet')
    parser.add_argument('--csv', required=True, help='CSV file path')
    parser.add_argument('--sheet-id', required=True, help='Google Sheet ID')
    parser.add_argument('--tab-name', required=True, help='Tab name')
    args = parser.parse_args()

    try:
        add_tab_and_upload(args.csv, args.sheet_id, args.tab_name)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
