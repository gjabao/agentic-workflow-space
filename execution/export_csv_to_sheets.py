import os
import sys
import csv
import logging
import argparse
from scrape_google_maps import GoogleMapsLeadScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_csv_to_sheets(csv_path: str, sheet_title: str):
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return

    print(f"Reading {csv_path}...")
    
    contacts = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Reconstruct the dict with internal keys expected by export_to_google_sheets
            # Map CSV headers back to internal keys
            contact = {
                'business_name': row.get('Business Name'),
                'primary_contact': row.get('Primary Contact'),
                'phone': row.get('Phone'),
                'email': row.get('Email'),
                'city': row.get('City'),
                'job_title': row.get('Job Title'),
                'contact_linkedin': row.get('Contact LinkedIn'),
                'website': row.get('Website'),
                'full_address': row.get('Full Address'),
                'type': row.get('Type'),
                'quadrant': row.get('Quadrant'),
                'company_social': row.get('Company Social'),
                'personal_instagram': row.get('Personal Instagram')
            }
            contacts.append(contact)

    print(f"Loaded {len(contacts)} contacts.")

    # Auth fix: remove token if invalid (optional, rely on scraper logic)
    # But usually good to force re-auth if needed? No, let's try existing token first.
    
    print("🚀 Initializing Google Sheets Export...")
    try:
        scraper = GoogleMapsLeadScraper()
        
        print("📊 Uploading to Google Sheets...")
        url = scraper.export_to_google_sheets(contacts, sheet_title)
        
        if url:
             print(f"\n✅ SUCCESS! Sheet created:\n{url}\n")
        else:
             print("\n❌ Export failed.\n")
             
    except Exception as e:
        print(f"\n❌ Error during export: {e}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export CSV to Google Sheets')
    parser.add_argument('csv_path', help='Path to CSV file')
    parser.add_argument('--title', help='Title of the Google Sheet', default='Leads Export')
    args = parser.parse_args()

    export_csv_to_sheets(args.csv_path, args.title)
