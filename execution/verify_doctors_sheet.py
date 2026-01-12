#!/usr/bin/env python3
"""
Verify Doctors in Google Sheet
- Reads existing sheet
- Checks job title and contact name for "Dr" prefix
- Adds "Is Doctor" column
"""

import os
import sys
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]


def get_credentials():
    """Get Google OAuth credentials."""
    creds = None

    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"⚠️  Existing token invalid: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Opening browser for OAuth authorization...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("✓ Credentials saved to token.json")

    return creds


def is_doctor(job_title: str, contact_name: str) -> bool:
    """
    Determine if a contact is a Doctor/Medical Professional.

    Doctor criteria:
    - Name starts with "Dr" or "Dr."
    - Job title contains medical titles (MD, Physician, Dermatologist, etc.)
    """
    # Check name prefix (Dr, Dr.)
    if contact_name:
        name_lower = contact_name.lower().strip()
        if name_lower.startswith('dr ') or name_lower.startswith('dr.'):
            return True

    # Check job title for medical credentials
    if job_title:
        medical_titles = [
            # Credentials
            'md', 'm.d.', 'do', 'd.o.', 'mbbs', 'phd', 'dds', 'dmd',
            # Specialties
            'physician', 'surgeon', 'dermatologist', 'doctor',
            'plastic surgeon', 'cosmetic surgeon', 'medical director',
            'aesthetician', 'nurse practitioner', 'np', 'pa-c',
            'registered nurse', 'rn', 'family doctor', 'gp',
            'general practitioner', 'specialist', 'clinician'
        ]
        title_lower = job_title.lower()
        for med_title in medical_titles:
            if med_title in title_lower:
                return True

    return False


def verify_doctors_in_sheet(spreadsheet_id: str):
    """
    Read sheet, verify doctors, add Is Doctor column.
    """
    print(f"\n📊 Processing sheet: {spreadsheet_id}")

    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)

    # Read all data
    print("📖 Reading sheet data...")
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range='A:Z'  # Read all columns
    ).execute()

    values = result.get('values', [])
    if not values:
        print("❌ Sheet is empty!")
        return

    headers = values[0]
    print(f"   Headers: {headers}")
    print(f"   Rows: {len(values) - 1}")

    # Find column indices
    try:
        contact_name_idx = headers.index('Contact Name') if 'Contact Name' in headers else -1
        job_title_idx = headers.index('Job Title') if 'Job Title' in headers else -1
    except ValueError:
        print("❌ Required columns not found!")
        return

    print(f"   Contact Name column: {contact_name_idx + 1}")
    print(f"   Job Title column: {job_title_idx + 1}")

    # Check if Is Doctor column exists
    if 'Is Doctor' in headers:
        is_doctor_idx = headers.index('Is Doctor')
        print(f"   Is Doctor column exists at: {is_doctor_idx + 1}")
    else:
        # Add Is Doctor column after Decision Maker (or at end)
        if 'Decision Maker' in headers:
            dm_idx = headers.index('Decision Maker')
            is_doctor_idx = dm_idx + 1
        else:
            is_doctor_idx = len(headers)
        print(f"   Adding Is Doctor column at: {is_doctor_idx + 1}")

    # Process each row
    print("\n🔍 Verifying doctors...")
    doctor_count = 0
    updates = []

    for i, row in enumerate(values[1:], start=2):  # Skip header, 1-indexed
        # Pad row if needed
        while len(row) <= max(contact_name_idx, job_title_idx, is_doctor_idx):
            row.append('')

        contact_name = row[contact_name_idx] if contact_name_idx >= 0 and contact_name_idx < len(row) else ''
        job_title = row[job_title_idx] if job_title_idx >= 0 and job_title_idx < len(row) else ''

        is_doc = is_doctor(job_title, contact_name)
        is_doc_str = 'Yes' if is_doc else 'No'

        if is_doc:
            doctor_count += 1
            print(f"   ✓ Row {i}: {contact_name} - {job_title}")

        # Store update
        updates.append({
            'row': i,
            'value': is_doc_str
        })

    print(f"\n📊 Found {doctor_count} doctors out of {len(values) - 1} contacts")

    # Update sheet - add header if needed
    if 'Is Doctor' not in headers:
        # Insert header
        col_letter = chr(ord('A') + is_doctor_idx)
        header_range = f"Leads!{col_letter}1"
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=header_range,
            valueInputOption='RAW',
            body={'values': [['Is Doctor']]}
        ).execute()
        print(f"   ✓ Added 'Is Doctor' header at column {col_letter}")

    # Update all Is Doctor values in batch
    col_letter = chr(ord('A') + is_doctor_idx)

    # Prepare batch update
    doctor_values = [[u['value']] for u in updates]
    update_range = f"Leads!{col_letter}2:{col_letter}{len(updates) + 1}"

    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=update_range,
        valueInputOption='RAW',
        body={'values': doctor_values}
    ).execute()

    print(f"   ✓ Updated {len(updates)} rows")

    print("\n" + "="*60)
    print("✅ COMPLETE!")
    print("="*60)
    print(f"📊 Sheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    print(f"👨‍⚕️ Doctors found: {doctor_count}")
    print("="*60)


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_doctors_sheet.py <spreadsheet_id_or_url>")
        print("Example: python verify_doctors_sheet.py 1MYUDuMg2WuaQkI9K63p5L8QuBGW2koiTK8zWgb3jq84")
        sys.exit(1)

    # Extract spreadsheet ID from URL or use directly
    input_id = sys.argv[1]
    if 'docs.google.com' in input_id:
        # Extract ID from URL
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', input_id)
        if match:
            spreadsheet_id = match.group(1)
        else:
            print("❌ Invalid Google Sheets URL")
            sys.exit(1)
    else:
        spreadsheet_id = input_id

    verify_doctors_in_sheet(spreadsheet_id)


if __name__ == '__main__':
    main()
