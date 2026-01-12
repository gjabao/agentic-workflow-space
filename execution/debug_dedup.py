
import os
import pickle
import time
from typing import Set, List, Dict, Any
from urllib.parse import urlparse
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# HARDCODED IDs for debugging
EXCLUSION_ID = "15OItOUZNla-hyCaoYa4LiRm6otEkHlUVHqKHLIIHRak" # Sheet B
CLEANED_ID = "1Ah4QlxkpaJGQbT7ikjQCaA1o-yhas6Q470vW-WTs_jQ"   # The sheet we just made

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
    
    # Debug raw
    # print(f"DEBUG RAW: {url}")
    
    url = url.strip().lower()
    
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""

def get_sheet_tabs(service, spreadsheet_id: str):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

def get_sheet_values(service, spreadsheet_id: str, range_name: str):
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name).execute()
    return result.get('values', [])

def extract_domains(service, sheet_id, label):
    tabs = get_sheet_tabs(service, sheet_id)
    print(f"\nScanning {label} ({sheet_id}) - {len(tabs)} tabs")
    
    domains = {} # domain -> location info (Tab Name + Raw URL)
    
    for tab in tabs:
        rows = get_sheet_values(service, sheet_id, tab)
        if not rows: continue
        
        headers = [str(h).lower() for h in rows[0]]
        website_idx = -1
        for col in ['website', 'url', 'site', 'domain', 'web']:
            if col in headers:
                website_idx = headers.index(col)
                break
        
        # fallback
        if website_idx == -1:
             for i, row in enumerate(rows[1:5]):
                for j, cell in enumerate(row):
                    if isinstance(cell, str) and ('http' in cell or 'www.' in cell):
                        website_idx = j
                        break
                if website_idx != -1:
                    break
                    
        if website_idx != -1:
            for row in rows[1:]:
                if len(row) > website_idx:
                    raw = row[website_idx]
                    norm = normalize_domain(raw)
                    if norm:
                        if norm not in domains:
                            domains[norm] = []
                        domains[norm].append(f"[{label}] {tab}: {raw}")
    return domains

def main():
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    print("Extracting Exclusion Domains (Sheet B)...")
    exclusion_map = extract_domains(service, EXCLUSION_ID, "EXCLUSION")
    
    print("Extracting Cleaned Domains (Result Sheet)...")
    cleaned_map = extract_domains(service, CLEANED_ID, "CLEANED")
    
    print("\n--- COMPARISON ---")
    
    leakage = 0
    for domain, sources in cleaned_map.items():
        if domain in exclusion_map:
            leakage += 1
            print(f"\n🚨 LEAK FOUND: {domain}")
            print(f"   Found in Exclusion: {exclusion_map[domain][0]}")
            print(f"   Found in Cleaned:   {sources[0]}")
            
            if leakage >= 20:
                print("... stopping after 20 leaks.")
                break
                
    if leakage == 0:
        print("\n✅ No direct domain intersection found based on normalization logic.")
        print("This implies the issue might be:")
        print("1. The 'duplicate' is a different domain redirecting to same place?")
        print("2. The 'duplicate' has extremely different URL format?")
        print("3. Phone number matches?")
        print("4. Company Name matches?")

if __name__ == '__main__':
    main()
