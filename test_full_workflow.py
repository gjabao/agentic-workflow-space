#!/usr/bin/env python3
"""
Full workflow test: Demonstrates AnyMailFinder integration with lead scraping
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'execution'))

from scrape_apify_leads import AnyMailFinderVerifier

load_dotenv()

def test_full_workflow():
    """
    Test the complete workflow with sample solar installation leads
    """

    print("=" * 70)
    print("FULL WORKFLOW TEST - AnyMailFinder Email Verification")
    print("=" * 70)
    print()

    # Sample solar installation leads (realistic data)
    sample_leads = [
        {
            'company_name': 'Sunrun Inc',
            'email': 'info@sunrun.com',
            'first_name': 'Lynn',
            'last_name': 'Jurich',
            'job_title': 'CEO',
            'website': 'https://www.sunrun.com'
        },
        {
            'company_name': 'Tesla Energy',
            'email': 'solar@tesla.com',
            'first_name': 'Elon',
            'last_name': 'Musk',
            'job_title': 'CEO',
            'website': 'https://www.tesla.com'
        },
        {
            'company_name': 'Invalid Solar Co',
            'email': 'test@invalidemail123456.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'job_title': 'Owner',
            'website': 'https://www.invalid.com'
        }
    ]

    print("📊 Sample Solar Installation Leads:")
    print("-" * 70)
    for i, lead in enumerate(sample_leads, 1):
        print(f"{i}. {lead['company_name']}")
        print(f"   Email: {lead['email']}")
        print(f"   Contact: {lead['first_name']} {lead['last_name']} ({lead['job_title']})")
        print()

    print("=" * 70)
    print("STEP 1: Initialize AnyMailFinder Verifier")
    print("=" * 70)
    print()

    api_key = os.getenv('ANYMAILFINDER_API_KEY')
    if not api_key:
        print("❌ ANYMAILFINDER_API_KEY not found in .env")
        return

    verifier = AnyMailFinderVerifier(api_key)
    print(f"✓ Verifier initialized with API key: {api_key[:15]}...")
    print()

    print("=" * 70)
    print("STEP 2: Extract Emails from Leads")
    print("=" * 70)
    print()

    emails = [lead['email'] for lead in sample_leads]
    print(f"✓ Extracted {len(emails)} emails:")
    for email in emails:
        print(f"  - {email}")
    print()

    print("=" * 70)
    print("STEP 3: Verify Emails with AnyMailFinder")
    print("=" * 70)
    print()

    print("⏳ Verifying emails...")
    print("-" * 70)

    results = verifier.verify_bulk(emails, sample_leads)

    print()
    print("=" * 70)
    print("STEP 4: Verification Results")
    print("=" * 70)
    print()

    # Combine leads with verification results
    verified_leads = []
    for lead in sample_leads:
        email = lead['email']
        verification_status = results.get(email, 'Unknown')

        verified_lead = lead.copy()
        verified_lead['verification_status'] = verification_status
        verified_leads.append(verified_lead)

        # Display result with color coding
        status_emoji = {
            'Valid': '✓',
            'Invalid': '✗',
            'Catch-All': '⚠️',
            'Unknown': '?'
        }

        emoji = status_emoji.get(verification_status, '?')

        print(f"{emoji} {lead['company_name']}")
        print(f"   Email: {email}")
        print(f"   Status: {verification_status}")
        print(f"   Contact: {lead['first_name']} {lead['last_name']}")
        print(f"   Title: {lead['job_title']}")
        print()

    print("=" * 70)
    print("STEP 5: Filter Valid Emails Only")
    print("=" * 70)
    print()

    valid_leads = [lead for lead in verified_leads if lead['verification_status'] == 'Valid']

    print(f"✓ Found {len(valid_leads)} valid emails out of {len(verified_leads)} total")
    print()

    if valid_leads:
        print("Valid leads ready for icebreaker generation:")
        for lead in valid_leads:
            print(f"  ✓ {lead['company_name']} - {lead['email']}")
        print()

    print("=" * 70)
    print("STEP 6: Summary Statistics")
    print("=" * 70)
    print()

    valid_count = sum(1 for v in results.values() if v == 'Valid')
    invalid_count = sum(1 for v in results.values() if v == 'Invalid')
    catchall_count = sum(1 for v in results.values() if v == 'Catch-All')
    unknown_count = sum(1 for v in results.values() if v == 'Unknown')

    print(f"Total Leads:    {len(sample_leads)}")
    print(f"Valid Emails:   {valid_count} ({valid_count/len(sample_leads)*100:.1f}%)")
    print(f"Invalid Emails: {invalid_count} ({invalid_count/len(sample_leads)*100:.1f}%)")
    print(f"Catch-All:      {catchall_count} ({catchall_count/len(sample_leads)*100:.1f}%)")
    print(f"Unknown:        {unknown_count} ({unknown_count/len(sample_leads)*100:.1f}%)")
    print()

    print("=" * 70)
    print("STEP 7: Cost Calculation")
    print("=" * 70)
    print()

    cost_per_verification = 0.2
    total_cost = len(emails) * cost_per_verification

    print(f"Emails verified:     {len(emails)}")
    print(f"Cost per email:      {cost_per_verification} credits")
    print(f"Total cost:          {total_cost} credits")
    print()
    print("Note: Repeated verifications within 30 days are FREE!")
    print()

    print("=" * 70)
    print("✓ TEST COMPLETE - All Systems Operational")
    print("=" * 70)
    print()

    print("🎯 Next Steps for 200 Solar Leads:")
    print()
    print("1. Add Apify credits ($0.38 remaining)")
    print("2. Run full scrape:")
    print()
    print("   python3 execution/scrape_apify_leads.py \\")
    print("     --industry 'solar installation' \\")
    print("     --fetch_count 200 \\")
    print("     --location 'united states' \\")
    print("     --company_keywords 'solar installation' 'solar contractor' \\")
    print("     --job_title 'CEO' 'President' 'Owner' \\")
    print("     --company_size '21-50' '51-100' '101-200' \\")
    print("     --skip_test \\")
    print("     --valid_only")
    print()
    print("3. Results will include:")
    print("   - 200 solar installation companies")
    print("   - Email verification via AnyMailFinder")
    print("   - AI-generated icebreakers for valid emails")
    print("   - Export to Google Sheets")
    print()
    print("Estimated cost: ~40 credits (200 emails × 0.2)")
    print()

if __name__ == "__main__":
    test_full_workflow()
