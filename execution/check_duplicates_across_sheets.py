#!/usr/bin/env python3
"""
Check for duplicates between Sheet A and Sheet B
- Downloads all tabs from both sheets
- Identifies duplicates based on: Email, Business Name, Phone
- Generates comprehensive report
- DOES NOT modify Sheet B (read-only)

Usage: python execution/check_duplicates_across_sheets.py \
    --sheet-a-id "SHEET_A_ID" \
    --sheet-b-id "SHEET_B_ID" \
    --output "duplicates_report.csv"
"""

import os
import sys
import csv
import argparse
import re
from typing import Dict, List, Set, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from fuzzywuzzy import fuzz

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

def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, remove special chars)"""
    if not text or text.strip() == '':
        return ''
    # Remove special characters, convert to lowercase
    text = re.sub(r'[^\w\s]', '', str(text).lower().strip())
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)
    return text

def normalize_phone(phone: str) -> str:
    """Normalize phone number (remove all non-digits)"""
    if not phone or phone.strip() == '':
        return ''
    # Keep only digits
    return re.sub(r'\D', '', str(phone))

def normalize_email(email: str) -> str:
    """Normalize email (lowercase, strip whitespace)"""
    if not email or email.strip() == '':
        return ''
    return str(email).lower().strip()

def get_all_tabs(service, sheet_id: str) -> List[Dict]:
    """Get all tab names from a Google Sheet"""
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    return [{'title': s['properties']['title'], 'gid': s['properties']['sheetId']} for s in sheets]

def download_tab_data(service, sheet_id: str, tab_name: str) -> List[Dict]:
    """Download all data from a specific tab"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A:Z"
        ).execute()

        rows = result.get('values', [])
        if not rows:
            return []

        # First row is header
        headers = rows[0]
        data = []

        for row in rows[1:]:
            # Pad row to match header length
            while len(row) < len(headers):
                row.append('')

            # Create dict
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''

            data.append(row_dict)

        return data
    except Exception as e:
        print(f"⚠️  Warning: Could not read tab '{tab_name}': {e}")
        return []

def check_duplicates(sheet_a_data: List[Dict], sheet_b_data: List[Dict],
                     sheet_a_tab: str, sheet_b_tab: str) -> List[Dict]:
    """
    Check for duplicates between two datasets
    Returns list of duplicate matches with details
    """
    duplicates = []

    # Build lookup indices for Sheet B (for fast matching)
    email_index = {}
    phone_index = {}
    business_name_index = {}

    for idx, row_b in enumerate(sheet_b_data):
        # Index by email
        email = normalize_email(row_b.get('Email', ''))
        if email:
            if email not in email_index:
                email_index[email] = []
            email_index[email].append((idx, row_b))

        # Index by phone
        phone = normalize_phone(row_b.get('Phone', ''))
        if phone:
            if phone not in phone_index:
                phone_index[phone] = []
            phone_index[phone].append((idx, row_b))

        # Index by business name
        business_name = normalize_text(row_b.get('Business Name', ''))
        if business_name:
            if business_name not in business_name_index:
                business_name_index[business_name] = []
            business_name_index[business_name].append((idx, row_b))

    # Check each row in Sheet A against Sheet B
    for row_a in sheet_a_data:
        email_a = normalize_email(row_a.get('Email', ''))
        phone_a = normalize_phone(row_a.get('Phone', ''))
        business_name_a = normalize_text(row_a.get('Business Name', ''))

        # Skip if all fields are empty
        if not email_a and not phone_a and not business_name_a:
            continue

        match_found = False
        match_type = []
        matched_row_b = None

        # Check email match (exact)
        if email_a and email_a in email_index:
            match_found = True
            match_type.append('Email')
            matched_row_b = email_index[email_a][0][1]

        # Check phone match (exact)
        if phone_a and phone_a in phone_index:
            match_found = True
            if 'Email' not in match_type:
                matched_row_b = phone_index[phone_a][0][1]
            match_type.append('Phone')

        # Check business name match (fuzzy, 85% similarity)
        if business_name_a:
            for bn, rows in business_name_index.items():
                similarity = fuzz.ratio(business_name_a, bn)
                if similarity >= 85:
                    match_found = True
                    if not matched_row_b:
                        matched_row_b = rows[0][1]
                    match_type.append(f'Business Name ({similarity}%)')
                    break

        if match_found and matched_row_b:
            duplicates.append({
                'Sheet A Tab': sheet_a_tab,
                'Sheet B Tab': sheet_b_tab,
                'Match Type': ', '.join(match_type),
                'A - Business Name': row_a.get('Business Name', ''),
                'B - Business Name': matched_row_b.get('Business Name', ''),
                'A - Email': row_a.get('Email', ''),
                'B - Email': matched_row_b.get('Email', ''),
                'A - Phone': row_a.get('Phone', ''),
                'B - Phone': matched_row_b.get('Phone', ''),
                'A - Primary Contact': row_a.get('Primary Contact', ''),
                'B - Primary Contact': matched_row_b.get('Primary Contact', ''),
                'A - Website': row_a.get('Website', ''),
                'B - Website': matched_row_b.get('Website', ''),
            })

    return duplicates

def main():
    parser = argparse.ArgumentParser(description='Check duplicates between two Google Sheets')
    parser.add_argument('--sheet-a-id', required=True, help='Sheet A (Client Prospects) ID')
    parser.add_argument('--sheet-b-id', required=True, help='Sheet B (Master Leads) ID')
    parser.add_argument('--output', default='duplicates_report.csv', help='Output CSV file')
    parser.add_argument('--tabs', help='Comma-separated list of tabs to check (default: all)')
    args = parser.parse_args()

    print("🔍 Duplicate Checker - Sheet A vs Sheet B")
    print("=" * 60)

    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)

    # Get all tabs from both sheets
    print("\n📋 Reading Sheet A tabs...")
    tabs_a = get_all_tabs(service, args.sheet_a_id)
    print(f"   Found {len(tabs_a)} tabs")

    print("\n📋 Reading Sheet B tabs...")
    tabs_b = get_all_tabs(service, args.sheet_b_id)
    print(f"   Found {len(tabs_b)} tabs")

    # Filter tabs if specified
    if args.tabs:
        tab_filter = [t.strip() for t in args.tabs.split(',')]
        tabs_a = [t for t in tabs_a if t['title'] in tab_filter]
        tabs_b = [t for t in tabs_b if t['title'] in tab_filter]
        print(f"\n🔎 Filtering to {len(tab_filter)} tabs: {', '.join(tab_filter)}")

    # Download all data
    print("\n⬇️  Downloading Sheet A data...")
    sheet_a_all = {}
    for tab in tabs_a:
        tab_name = tab['title']
        data = download_tab_data(service, args.sheet_a_id, tab_name)
        if data:
            sheet_a_all[tab_name] = data
            print(f"   ✓ {tab_name}: {len(data)} rows")

    print("\n⬇️  Downloading Sheet B data (read-only)...")
    sheet_b_all = {}
    for tab in tabs_b:
        tab_name = tab['title']
        data = download_tab_data(service, args.sheet_b_id, tab_name)
        if data:
            sheet_b_all[tab_name] = data
            print(f"   ✓ {tab_name}: {len(data)} rows")

    # Check duplicates
    print("\n🔍 Checking for duplicates...")
    all_duplicates = []

    for tab_a_name, data_a in sheet_a_all.items():
        # Check against matching tab in Sheet B first
        if tab_a_name in sheet_b_all:
            print(f"\n   Comparing {tab_a_name} (A) vs {tab_a_name} (B)...")
            dups = check_duplicates(data_a, sheet_b_all[tab_a_name], tab_a_name, tab_a_name)
            all_duplicates.extend(dups)
            print(f"      Found {len(dups)} duplicates")

        # Also check against all other tabs in Sheet B (cross-city duplicates)
        for tab_b_name, data_b in sheet_b_all.items():
            if tab_b_name != tab_a_name:
                dups = check_duplicates(data_a, data_b, tab_a_name, tab_b_name)
                if dups:
                    all_duplicates.extend(dups)
                    print(f"      Cross-check: {tab_a_name} (A) vs {tab_b_name} (B): {len(dups)} duplicates")

    # Write report
    print(f"\n💾 Writing report to {args.output}...")
    if all_duplicates:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            fieldnames = all_duplicates[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_duplicates)

        print(f"\n✅ SUCCESS!")
        print(f"📊 Total duplicates found: {len(all_duplicates)}")
        print(f"📄 Report saved: {args.output}")

        # Summary by match type
        match_types = {}
        for dup in all_duplicates:
            mt = dup['Match Type']
            match_types[mt] = match_types.get(mt, 0) + 1

        print(f"\n📈 Breakdown by match type:")
        for mt, count in sorted(match_types.items(), key=lambda x: -x[1]):
            print(f"   {mt}: {count}")
    else:
        print(f"\n✅ No duplicates found!")
        # Create empty report
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['No duplicates found between Sheet A and Sheet B'])

    print(f"\n⚠️  IMPORTANT: Sheet B was NOT modified (read-only mode)")

if __name__ == "__main__":
    main()
