"""
Digital Marketing Agency Lead Scraper
Scrapes 10 leads every 5 minutes and saves to Google Sheets

Schedule: Every 5 minutes
Query: "digital marketing agency"
Limit: 10 leads per run

Deploy:
    python3 -m modal deploy modal_workflows/scrape_digital_marketing.py

Test manually:
    python3 -m modal run modal_workflows/scrape_digital_marketing.py

View logs:
    python3 -m modal app logs anti-gravity-workflows --follow
"""

import modal
import os
import json
import time
from datetime import datetime

app = modal.App("anti-gravity-workflows")

# Container image with required dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "requests",
        "apify-client",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib"
    )
)

@app.function(
    image=image,
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600  # 10 minutes max
)
def scrape_digital_marketing_agencies():
    """
    Scrape 10 digital marketing agency leads every 5 minutes
    Saves results to Google Sheets
    """
    from apify_client import ApifyClient
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    print(f"🔍 Starting lead scrape - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Query: 'digital marketing agency'")
    print(f"Limit: 10 leads")

    # Initialize Apify client
    apify_key = os.environ["APIFY_API_KEY"]
    client = ApifyClient(apify_key)

    try:
        # Run the Apify actor
        print("\n⏳ Running Apify actor...")

        # Using Google Maps scraper
        actor_id = "compass/crawler-google-places"

        run_input = {
            "searchStringsArray": ["digital marketing agency"],
            "maxCrawledPlacesPerSearch": 10,
            "language": "en",
            "includeReviews": False
        }

        run = client.actor(actor_id).call(run_input=run_input)

        print(f"✓ Actor run completed: {run['id']}")

        # Get results
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(item)

        print(f"✓ Found {len(results)} leads")

        if not results:
            print("⚠️  No results found")
            return {"status": "no_results", "count": 0}

        # Process and save to Google Sheets
        save_to_sheets(results)

        return {
            "status": "success",
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def save_to_sheets(leads: list):
    """Save leads to Google Sheets"""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    print("\n📊 Saving to Google Sheets...")

    # Load credentials from Modal secrets
    credentials_json = os.environ.get('GMAIL_CREDENTIALS_JSON')
    token_json = os.environ.get('GMAIL_TOKEN_JSON')

    if not credentials_json or not token_json:
        print("⚠️  Google credentials not found, skipping Sheets upload")
        return

    # Parse credentials
    token_data = json.loads(token_json)

    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes')
    )

    service = build('sheets', 'v4', credentials=creds)

    # Create or get sheet ID
    # For now, print results (you can create a new sheet or use existing)
    sheet_id = os.environ.get('LEADS_SHEET_ID', 'CREATE_NEW')

    if sheet_id == 'CREATE_NEW':
        # Create new sheet
        spreadsheet = {
            'properties': {
                'title': f'Digital Marketing Leads - {datetime.now().strftime("%Y-%m-%d")}'
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet).execute()
        sheet_id = spreadsheet['spreadsheetId']
        print(f"✓ Created new sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")

    # Prepare data
    values = [['Timestamp', 'Company', 'Location', 'Phone', 'Website', 'Rating']]

    for lead in leads:
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            lead.get('title', ''),
            lead.get('address', ''),
            lead.get('phone', ''),
            lead.get('website', ''),
            lead.get('totalScore', '')
        ]
        values.append(row)

    # Append to sheet
    try:
        body = {'values': values}
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        print(f"✓ Added {len(values)-1} rows to sheet")
        print(f"📊 View sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")

    except Exception as e:
        print(f"⚠️  Could not save to sheets: {e}")
        # Print results to logs instead
        print("\n📋 Results:")
        for i, lead in enumerate(leads, 1):
            print(f"{i}. {lead.get('title', 'Unknown')} - {lead.get('address', 'N/A')}")


# Manual trigger entry point
@app.local_entrypoint()
def main():
    """
    Run manually: python3 -m modal run modal_workflows/scrape_digital_marketing.py
    """
    print("🚀 Manual trigger - Scraping digital marketing agencies...")
    result = scrape_digital_marketing_agencies.remote()
    print(f"\n✅ Complete! Result: {result}")
