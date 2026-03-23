"""
Google Search Console API - Connection & Query Tool
DOE Layer: Execution
"""

import os
import pickle
import argparse
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token_gsc.pickle')


def get_service():
    """Authenticate and return Search Console service."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"❌ credentials.json not found at {CREDENTIALS_FILE}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
        print("✅ Token saved to token_gsc.pickle")

    return build('searchconsole', 'v1', credentials=creds)


def list_sites(service):
    """List all verified sites."""
    result = service.sites().list().execute()
    sites = result.get('siteEntry', [])
    if not sites:
        print("⚠️ No verified sites found.")
        return []
    print(f"\n📊 Verified Sites ({len(sites)}):")
    for site in sites:
        print(f"  • {site['siteUrl']} (level: {site['permissionLevel']})")
    return sites


def query_analytics(service, site_url, start_date=None, end_date=None,
                    dimensions=None, row_limit=1000):
    """Query search analytics data."""
    if not end_date:
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not dimensions:
        dimensions = ['query', 'page']

    request_body = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': dimensions,
        'rowLimit': row_limit,
    }

    response = service.searchanalytics().query(
        siteUrl=site_url,
        body=request_body
    ).execute()

    rows = response.get('rows', [])
    print(f"\n📈 Search Analytics ({len(rows)} rows)")
    print(f"   Period: {start_date} → {end_date}")
    print(f"   Dimensions: {dimensions}\n")

    for row in rows[:20]:
        keys = ' | '.join(row['keys'])
        print(f"  {keys}")
        print(f"    Clicks: {row['clicks']}  Impressions: {row['impressions']}  "
              f"CTR: {row['ctr']:.2%}  Position: {row['position']:.1f}")

    if len(rows) > 20:
        print(f"\n  ... and {len(rows) - 20} more rows")

    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Search Console API Tool')
    parser.add_argument('--action', choices=['connect', 'sites', 'query'],
                        default='connect', help='Action to perform')
    parser.add_argument('--site', help='Site URL (e.g. https://yoursite.com/)')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--dimensions', nargs='+',
                        default=['query', 'page'],
                        help='Dimensions: query, page, country, device, date')
    parser.add_argument('--limit', type=int, default=1000, help='Row limit')
    args = parser.parse_args()

    svc = get_service()
    print("✅ Connected to Google Search Console API!")

    if args.action == 'sites' or args.action == 'connect':
        list_sites(svc)

    if args.action == 'query':
        if not args.site:
            print("❌ --site required for query action")
        else:
            query_analytics(svc, args.site, args.start, args.end,
                            args.dimensions, args.limit)
