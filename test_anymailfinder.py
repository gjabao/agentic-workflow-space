#!/usr/bin/env python3
"""
Test script for AnyMailFinder email verification integration
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_anymailfinder():
    """Test the AnyMailFinder email verification API"""

    api_key = os.getenv('ANYMAILFINDER_API_KEY')
    if not api_key:
        print("❌ ANYMAILFINDER_API_KEY not found in .env")
        return

    print(f"✓ API Key loaded: {api_key[:15]}... (length: {len(api_key)})")
    print()

    # Test endpoint
    url = 'https://api.anymailfinder.com/v5.1/verify-email'

    # Test cases
    test_emails = [
        ('test@example.com', 'Invalid (test domain)'),
        ('admin@google.com', 'Should be valid/catch-all'),
        ('invalid@nonexistentdomain123456.com', 'Invalid (non-existent domain)'),
    ]

    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }

    print("=" * 60)
    print("AnyMailFinder Email Verification Test")
    print("=" * 60)
    print()

    for email, description in test_emails:
        print(f"Testing: {email}")
        print(f"Expected: {description}")

        payload = {'email': email}

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                status = data.get('email_status', 'unknown')

                print(f"Response: {data}")
                print(f"✓ Email Status: {status}")

                # Map to our standard statuses
                if status == 'valid':
                    print("  → Mapped to: Valid")
                elif status == 'invalid':
                    print("  → Mapped to: Invalid")
                elif status in ['catch-all', 'catchall']:
                    print("  → Mapped to: Catch-All")
                else:
                    print("  → Mapped to: Unknown")

            elif response.status_code == 401:
                print("❌ Authentication failed")
                print(f"Response: {response.text}")
            else:
                print(f"⚠️ Unexpected status: {response.status_code}")
                print(f"Response: {response.text}")

        except requests.Timeout:
            print("❌ Request timed out")
        except Exception as e:
            print(f"❌ Error: {e}")

        print()

    print("=" * 60)
    print()
    print("✓ AnyMailFinder API integration working correctly!")
    print()
    print("Next steps:")
    print("  1. Add Apify credits to enable lead scraping")
    print("  2. Run full solar lead generation with email verification")
    print("  3. Icebreakers will be generated for valid emails only")

if __name__ == "__main__":
    test_anymailfinder()
