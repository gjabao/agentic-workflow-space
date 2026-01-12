#!/usr/bin/env python3
"""
Remove duplicates from Sheet A based on duplicates report
- Reads duplicates_report.csv
- Removes duplicate rows from Sheet A tabs
- Preserves all non-duplicate data
- DOES NOT touch Sheet B

Usage: python execution/remove_duplicates_from_sheet_a.py \
    --sheet-a-id "SHEET_A_ID" \
    --duplicates-report "duplicates_report.csv"
"""

import os
import sys
import csv
import argparse
from typing import Dict, List, Set
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

def normalize_for_comparison(value: str) -> str:
    """Normalize value for comparison"""
    if not value:
        return ''
    return str(value).strip().lower()

def load_duplicates_to_remove(duplicates_csv: str) -> Dict[str, Set[tuple]]:
    """
    Load duplicates report and create a set of rows to remove
    Returns: {tab_name: set of (business_name, email, phone) tuples}
    """
    duplicates_by_tab = {}

    with open(duplicates_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tab = row['Sheet A Tab']
            business_name = normalize_for_comparison(row['A - Business Name'])
            email = normalize_for_comparison(row['A - Email'])
            phone = normalize_for_comparison(row['A - Phone'])

            # Create unique identifier tuple
            identifier = (business_name, email, phone)

            if tab not in duplicates_by_tab:
                duplicates_by_tab[tab] = set()

            duplicates_by_tab[tab].add(identifier)

    return duplicates_by_tab

def download_tab_data(service, sheet_id: str, tab_name: str) -> tuple[List[str], List[List[str]]]:
    """Download all data from a specific tab, returns (headers, rows)"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A:Z"
        ).execute()

        rows = result.get('values', [])
        if not rows:
            return [], []

        # First row is header
        headers = rows[0]
        data_rows = rows[1:]

        return headers, data_rows
    except Exception as e:
        print(f"⚠️  Warning: Could not read tab '{tab_name}': {e}")
        return [], []

def remove_duplicates_from_tab(headers: List[str], rows: List[List[str]],
                                duplicates_to_remove: Set[tuple]) -> List[List[str]]:
    """Remove duplicate rows from dataset"""

    # Find column indices
    business_name_idx = None
    email_idx = None
    phone_idx = None

    for i, header in enumerate(headers):
        if header.lower() == 'business name':
            business_name_idx = i
        elif header.lower() == 'email':
            email_idx = i
        elif header.lower() == 'phone':
            phone_idx = i

    # Filter rows
    kept_rows = []
    removed_count = 0

    for row in rows:
        # Pad row to match header length
        while len(row) < len(headers):
            row.append('')

        # Extract values for comparison
        business_name = normalize_for_comparison(row[business_name_idx] if business_name_idx is not None else '')
        email = normalize_for_comparison(row[email_idx] if email_idx is not None else '')
        phone = normalize_for_comparison(row[phone_idx] if phone_idx is not None else '')

        identifier = (business_name, email, phone)

        # Check if this row is a duplicate
        if identifier in duplicates_to_remove:
            removed_count += 1
        else:
            kept_rows.append(row)

    return kept_rows, removed_count

def update_sheet_tab(service, sheet_id: str, tab_name: str, headers: List[str], rows: List[List[str]]):
    """Update a sheet tab with new data"""
    # Clear existing data first
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A:Z"
    ).execute()

    # Write header + data
    all_data = [headers] + rows

    body = {'values': all_data}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body=body
    ).execute()

def main():
    parser = argparse.ArgumentParser(description='Remove duplicates from Sheet A')
    parser.add_argument('--sheet-a-id', required=True, help='Sheet A ID')
    parser.add_argument('--duplicates-report', default='duplicates_report.csv', help='Duplicates CSV report')
    parser.add_argument('--tabs', help='Comma-separated list of tabs to process (default: all with duplicates)')
    args = parser.parse_args()

    print("🗑️  Duplicate Remover - Sheet A")
    print("=" * 60)

    # Load duplicates to remove
    print(f"\n📋 Loading duplicates from {args.duplicates_report}...")
    duplicates_by_tab = load_duplicates_to_remove(args.duplicates_report)

    total_duplicates = sum(len(dups) for dups in duplicates_by_tab.values())
    print(f"   Found {total_duplicates} unique duplicate rows across {len(duplicates_by_tab)} tabs")

    # Filter tabs if specified
    if args.tabs:
        tab_filter = [t.strip() for t in args.tabs.split(',')]
        duplicates_by_tab = {k: v for k, v in duplicates_by_tab.items() if k in tab_filter}
        print(f"\n🔎 Filtering to {len(tab_filter)} tabs: {', '.join(tab_filter)}")

    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)

    # Process each tab
    print(f"\n🔧 Processing {len(duplicates_by_tab)} tabs...")
    total_removed = 0

    for tab_name, duplicates_set in sorted(duplicates_by_tab.items()):
        print(f"\n   Processing '{tab_name}'...")

        # Download current data
        headers, rows = download_tab_data(service, args.sheet_a_id, tab_name)

        if not headers or not rows:
            print(f"      ⚠️  Skipped (empty or not found)")
            continue

        print(f"      Current rows: {len(rows)}")
        print(f"      Duplicates to remove: {len(duplicates_set)}")

        # Remove duplicates
        kept_rows, removed_count = remove_duplicates_from_tab(headers, rows, duplicates_set)

        print(f"      Rows after deduplication: {len(kept_rows)}")
        print(f"      Removed: {removed_count}")

        # Update sheet
        if removed_count > 0:
            update_sheet_tab(service, args.sheet_a_id, tab_name, headers, kept_rows)
            print(f"      ✓ Updated sheet")
            total_removed += removed_count
        else:
            print(f"      ⚠️  No changes needed")

    print(f"\n✅ COMPLETE!")
    print(f"📊 Total rows removed from Sheet A: {total_removed}")
    print(f"🔗 Sheet A: https://docs.google.com/spreadsheets/d/{args.sheet_a_id}")

if __name__ == "__main__":
    main()
