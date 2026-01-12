import os
import csv
import logging
import argparse
from typing import Optional, List, Dict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SheetDownloader')

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheet_name_from_gid(service, spreadsheet_id: str, gid: int) -> Optional[str]:
    """Get the sheet name (title) for a specific GID."""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in spreadsheet.get('sheets', []):
            props = sheet.get('properties', {})
            if props.get('sheetId') == gid:
                return props.get('title')
        return None
    except Exception as e:
        logger.error(f"Error getting sheet name: {e}")
        return None

def resolve_sheet_name(service, spreadsheet_id: str, input_name: str) -> Optional[str]:
    """Find the exact sheet name from metadata that matches the input."""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        # 1. Try exact match
        for sheet in sheets:
            title = sheet.get('properties', {}).get('title', '')
            if title == input_name:
                return title
                
        # 2. Try case-insensitive and stripped match
        norm_input = input_name.strip().lower()
        for sheet in sheets:
            title = sheet.get('properties', {}).get('title', '')
            if title.strip().lower() == norm_input:
                logger.info(f"✓ Found partial match: '{title}' for input '{input_name}'")
                return title
                
        logger.error(f"❌ Available sheets: {[s.get('properties', {}).get('title') for s in sheets]}")
        return None
    except Exception as e:
        logger.error(f"Error listing sheets: {e}")
        return None

def download_sheet_to_csv(spreadsheet_id: str, output_csv: str, gid: int = None, sheet_name: str = None):
    """Download a specific sheet tab to CSV."""
    if not gid and not sheet_name:
        logger.error("❌ Must provide either --gid or --sheet_name")
        return

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
                logger.error("❌ credentials.json not found")
                return

            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        target_sheet_name = None
        
        # Resolve target sheet name
        if gid is not None:
             target_sheet_name = get_sheet_name_from_gid(service, spreadsheet_id, gid)
             if target_sheet_name:
                 logger.info(f"✓ Resolved GID {gid} to: '{target_sheet_name}'")
        elif sheet_name:
             target_sheet_name = resolve_sheet_name(service, spreadsheet_id, sheet_name)
             if target_sheet_name:
                 logger.info(f"✓ Resolved Name '{sheet_name}' to exact name: '{target_sheet_name}'")

        if not target_sheet_name:
             logger.error("❌ No sheet name resolved.")
             return

        # Quote sheet name if it contains spaces and isn't already quoted
        search_range = target_sheet_name
        if ' ' in target_sheet_name and not target_sheet_name.startswith("'"):
            search_range = f"'{target_sheet_name}'"

        logger.info(f"⬇️ Downloading sheet: '{target_sheet_name}' (Range: {search_range})")

        # 2. Download Data
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=search_range
        ).execute()
        values = result.get('values', [])

        if not values:
            logger.warning("⚠️ No data found in sheet.")
            # Create empty file to avoid breaking downstream scripts
            with open(output_csv, 'w') as f:
                pass
            return

        # 3. Write to CSV
        logger.info(f"💾 Saving {len(values)} rows to {output_csv}...")
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(values)

        logger.info("✅ Done!")

    except Exception as e:
        logger.error(f"❌ Download failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download Google Sheet to CSV')
    parser.add_argument('--sheet_id', required=True, help='Google Spreadsheet ID')
    parser.add_argument('--gid', type=int, help='Sheet GID')
    parser.add_argument('--sheet_name', type=str, help='Sheet Name (alternative to GID)')
    parser.add_argument('--output', required=True, help='Output CSV path')
    
    args = parser.parse_args()
    
    download_sheet_to_csv(spreadsheet_id=args.sheet_id, output_csv=args.output, gid=args.gid, sheet_name=args.sheet_name)
