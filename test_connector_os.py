#!/usr/bin/env python3
"""
Test script for Connector OS API integration
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_connector_os_api():
    """Test the Connector OS email finding API"""

    api_key = os.getenv('CONNECTOR_OS_API_KEY')
    if not api_key:
        print("❌ CONNECTOR_OS_API_KEY not found in .env")
        return

    print(f"✓ API Key loaded: {api_key[:15]}... (length: {len(api_key)})")
    print()

    # Test endpoint
    url = 'https://api.connector-os.com/api/email/v2/find'

    # Test payload - using a known solar company
    test_cases = [
        {
            'firstName': 'Lynn',
            'lastName': 'Jurich',
            'domain': 'sunrun.com',
            'description': 'Sunrun CEO'
        },
        {
            'firstName': 'John',
            'lastName': 'Smith',
            'domain': 'tesla.com',
            'description': 'Generic test'
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"--- Test {i}: {test['description']} ---")
        print(f"Looking for: {test['firstName']} {test['lastName']} @ {test['domain']}")

        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json'
        }

        payload = {
            'firstName': test['firstName'],
            'lastName': test['lastName'],
            'domain': test['domain']
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")

            if response.status_code == 200:
                data = response.json()
                if data.get('email'):
                    print(f"✓ Email found: {data['email']}")
                else:
                    print("⚠️ No email found in response")
            elif response.status_code == 401:
                print("❌ Authentication failed")
                print("Possible issues:")
                print("  1. API key is invalid or expired")
                print("  2. API key format is incorrect")
                print("  3. Wrong endpoint URL")
                print()
                print("Please verify:")
                print("  - API key starts with 'ssm_live_' or similar")
                print("  - API key is active and not expired")
                print("  - You have credits/access to Connector OS API")
            else:
                print(f"⚠️ Unexpected status code: {response.status_code}")

        except requests.Timeout:
            print("❌ Request timed out")
        except Exception as e:
            print(f"❌ Error: {e}")

        print()

if __name__ == "__main__":
    print("=" * 60)
    print("Connector OS API Test")
    print("=" * 60)
    print()

    test_connector_os_api()

    print("=" * 60)
    print()
    print("📝 Next Steps:")
    print("  1. Verify your API key is correct and active")
    print("  2. Check if you have access to Connector OS API")
    print("  3. Contact Connector OS support if authentication fails")
    print("  4. Alternative: Use a different email verification service")
