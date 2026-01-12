
import os
import pickle
import argparse
import time
import re
from typing import Set, List, Dict, Any, Tuple
from urllib.parse import urlparse
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import datetime

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        try:
            with open('token.json', 'rb') as token:
                creds = pickle.load(token)
        except Exception:
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def normalize_domain(url: str) -> str:
    if not isinstance(url, str) or not url:
        return ""
    if url.strip().upper() == 'N/A':
        return ""
    if not url.startswith('http'):
        url = 'https://' + url.strip()
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""

def normalize_name(name: str) -> str:
    """Lowercase + Alphanumeric Only"""
    if not isinstance(name, str) or not name:
        return ""
    # Removing 'inc', 'ltd', etc might be too risky without careful regex
    # Stick to alphanumeric lowercase
    return re.sub(r'[^a-z0-9]', '', name.lower())

def normalize_phone(phone: str) -> str:
    """Digits only"""
    if not isinstance(phone, str) or not phone:
        return ""
    return re.sub(r'\D', '', phone)

def get_sheet_tabs(service, spreadsheet_id: str) -> List[Dict[str, Any]]:
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    tabs = []
    for sheet in sheet_metadata.get('sheets', []):
        props = sheet.get('properties', {})
        tabs.append({'title': props.get('title'), 'id': props.get('sheetId')})
    return tabs

def get_sheet_values(service, spreadsheet_id: str, range_name: str) -> List[List[str]]:
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name).execute()
    return result.get('values', [])

def create_new_sheet(service, title: str):
    spreadsheet = {
        'properties': {
            'title': title
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    return spreadsheet.get('spreadsheetId')

def add_tab_and_write_data(service, spreadsheet_id: str, tab_title: str, data: List[List[str]]):
    if not data:
        return
    
    reqs = [{'addSheet': {'properties': {'title': tab_title}}}]
    try:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': reqs}).execute()
    except Exception as e:
        print(f"   ⚠️ Warning creating tab '{tab_title}': {e}. Trying to write anyway if it exists...")

    body = {
        'values': data
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=f"'{tab_title}'!A1",
        valueInputOption='RAW', body=body).execute()

def delete_default_sheet1(service, spreadsheet_id: str):
    tabs = get_sheet_tabs(service, spreadsheet_id)
    if len(tabs) > 1:
        for t in tabs:
            if t['title'] == 'Sheet1' and t['id'] == 0:
                req = [{'deleteSheet': {'sheetId': t['id']}}]
                try:
                    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': req}).execute()
                    print("   - Deleted default 'Sheet1'")
                except:
                    pass
                break

def get_col_indices(headers: List[str]) -> Tuple[int, int, int]:
    h_lower = [str(h).lower() for h in headers]
    
    web_idx = -1
    for col in ['website', 'url', 'site', 'domain', 'web']:
        if col in h_lower:
            web_idx = h_lower.index(col)
            break
            
    name_idx = -1
    for col in ['title', 'name', 'company', 'business', 'place']:
        if col in h_lower:
            name_idx = h_lower.index(col)
            break
            
    phone_idx = -1
    for col in ['phone', 'tel', 'cell', 'mobile', 'contact']:
        if col in h_lower:
            phone_idx = h_lower.index(col)
            break
            
    return web_idx, name_idx, phone_idx

def main():
    parser = argparse.ArgumentParser(description='Deduplicate ALL A Source tabs against ALL B Exclusion tabs (Multi-Criteria).')
    parser.add_argument('--source_id', required=True, help='Spreadsheet ID of Source (Sheet A)')
    parser.add_argument('--exclusion_id', required=True, help='Spreadsheet ID of Exclusion (Sheet B)')
    
    args = parser.parse_args()
    
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # ---------------------------------------------------------
    # 1. Build Exclusion Sets
    # ---------------------------------------------------------
    print(f"🔍 [Phase 1] Building Exclusion Sets from Sheet B ({args.exclusion_id})")
    exclusion_tabs = get_sheet_tabs(service, args.exclusion_id)
    print(f"   Found {len(exclusion_tabs)} tabs in Exclusion Sheet.")
    
    ex_domains: Set[str] = set()
    ex_names: Set[str] = set()
    ex_phones: Set[str] = set()
    
    for tab in exclusion_tabs:
        title = tab['title']
        print(f"   - Reading B: '{title}'...", end='\r')
        rows = get_sheet_values(service, args.exclusion_id, title)
        if not rows: continue
            
        web_idx, name_idx, phone_idx = get_col_indices(rows[0])
        
        # Fallback detection using row scan
        if web_idx == -1 or name_idx == -1 or phone_idx == -1:
            for i, row in enumerate(rows[1:5]):
                for j, cell in enumerate(row):
                    if not isinstance(cell, str): continue
                    val = cell.lower()
                    if web_idx == -1 and ('http' in val or 'www.' in val): web_idx = j
                    if phone_idx == -1 and (sum(c.isdigit() for c in val) > 7): phone_idx = j
                    # Name is hard to fuzzy detect, rely on header or column 0 as fallback?
                    if name_idx == -1 and j == 0: name_idx = 0
        
        for row in rows[1:]:
            # Domain
            if web_idx != -1 and len(row) > web_idx:
                d = normalize_domain(row[web_idx])
                if d: ex_domains.add(d)
                
            # Name
            if name_idx != -1 and len(row) > name_idx:
                n = normalize_name(row[name_idx])
                if n and len(n) > 3: # Avoid super short noise matches
                    ex_names.add(n)
                    
            # Phone
            if phone_idx != -1 and len(row) > phone_idx:
                p = normalize_phone(row[phone_idx])
                if p and len(p) > 6: # Standard length
                    ex_phones.add(p)
                    
        time.sleep(3.0)

    print(f"\n✅ Exclusion Data Loaded:")
    print(f"   - Domains: {len(ex_domains)}")
    print(f"   - Names:   {len(ex_names)}")
    print(f"   - Phones:  {len(ex_phones)}")
    
    # ---------------------------------------------------------
    # 2. Process Source Tabs
    # ---------------------------------------------------------
    print(f"\n🔍 [Phase 2] Processing Source Sheet A ({args.source_id})")
    source_tabs = get_sheet_tabs(service, args.source_id)
    print(f"   Found {len(source_tabs)} tabs in Source Sheet.")
    
    cleaned_data_map: Dict[str, List[List[str]]] = {}
    
    total_original = 0
    total_removed = 0
    
    for tab in source_tabs:
        title = tab['title']
        print(f"   - Processing A: '{title}'...")
        rows = get_sheet_values(service, args.source_id, title)
        
        if not rows:
            print(f"     -> Empty tab, skipping.")
            continue
            
        web_idx, name_idx, phone_idx = get_col_indices(rows[0])
        
        # Fallback detection for source
        if web_idx == -1 or name_idx == -1 or phone_idx == -1:
             for i, row in enumerate(rows[1:5]):
                for j, cell in enumerate(row):
                    if not isinstance(cell, str): continue
                    val = cell.lower()
                    if web_idx == -1 and ('http' in val or 'www.' in val): web_idx = j
                    if phone_idx == -1 and (sum(c.isdigit() for c in val) > 7): phone_idx = j
                    if name_idx == -1 and j == 0: name_idx = 0

        kept_rows = [rows[0]]
        removed_local = 0
        
        for row in rows[1:]:
            keep = True
            
            # Check Domain
            if web_idx != -1 and len(row) > web_idx:
                d = normalize_domain(row[web_idx])
                if d and d in ex_domains:
                    keep = False
                    
            # Check Name (only if still keeping)
            if keep and name_idx != -1 and len(row) > name_idx:
                n = normalize_name(row[name_idx])
                if n and len(n) > 3 and n in ex_names:
                    keep = False
                    
            # Check Phone (only if still keeping)
            if keep and phone_idx != -1 and len(row) > phone_idx:
                p = normalize_phone(row[phone_idx])
                if p and len(p) > 6 and p in ex_phones:
                    keep = False
            
            if keep:
                kept_rows.append(row)
            else:
                removed_local += 1
                
        cleaned_data_map[title] = kept_rows
        
        orig_count = len(rows) - 1
        total_original += orig_count
        total_removed += removed_local
        
        print(f"     -> Removed {removed_local}/{orig_count} duplicates.")
        time.sleep(3.0)

    print(f"\n📊 Summary:")
    print(f"   - Total Source Rows: {total_original}")
    print(f"   - Total Removed:     {total_removed}")
    print(f"   - Total Kept:        {total_original - total_removed}")

    # ---------------------------------------------------------
    # 3. Export to New Sheet
    # ---------------------------------------------------------
    dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_title = f"Cleaned Leads (STRICT) - {dt_str}"
    print(f"\n🚀 [Phase 3] Uploading to New Sheet: '{new_title}'")
    
    new_sheet_id = create_new_sheet(service, new_title)
    
    print(f"   Sheet Created: https://docs.google.com/spreadsheets/d/{new_sheet_id}")
    
    # Upload tabs
    for title, data in cleaned_data_map.items():
        if len(data) > 0:
            print(f"   Upload: '{title}' ({len(data)} rows)...")
            add_tab_and_write_data(service, new_sheet_id, title, data)
            time.sleep(1.0)
            
    # Cleanup default Sheet1
    delete_default_sheet1(service, new_sheet_id)
    
    print(f"\n✅ SUCCESS! All cleaned data uploaded.")
    print(f"🔗 URL: https://docs.google.com/spreadsheets/d/{new_sheet_id}")

if __name__ == '__main__':
    main()
