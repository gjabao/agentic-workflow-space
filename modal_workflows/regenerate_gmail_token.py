#!/usr/bin/env python3
"""
Regenerate Gmail token with refresh_token for Modal

This script will open your browser to re-authenticate Gmail.
It will generate a token.json with refresh_token that can be used in Modal.
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

def main():
    print("🔐 Gmail Token Regeneration for Modal")
    print("=" * 50)
    print()

    # Check if credentials.json exists
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found!")
        print("Please download it from Google Cloud Console")
        return

    # Remove old token
    if os.path.exists('token.json'):
        print("🗑️  Removing old token.json...")
        os.remove('token.json')

    print("🌐 Opening browser for Gmail authentication...")
    print("   ⚠️  IMPORTANT: Click 'Allow' to grant offline access")
    print("   This will generate a refresh_token needed for Modal")
    print()

    # Run OAuth flow with access_type='offline' to get refresh_token
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES,
        redirect_uri='http://localhost:8080'
    )

    # Force to get refresh_token
    creds = flow.run_local_server(
        port=8080,
        access_type='offline',
        prompt='consent'  # Force consent screen to get refresh_token
    )

    # Save credentials
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    with open('token.json', 'w') as f:
        json.dump(token_data, f, indent=2)

    print()
    print("✅ Token saved successfully!")
    print()

    # Verify refresh_token exists
    if token_data.get('refresh_token'):
        print("✅ Refresh token found! This token can be used in Modal.")
    else:
        print("⚠️  Warning: No refresh_token found. Try running again.")
        return

    print()
    print("📤 Now upload the new token to Modal:")
    print("   bash modal_workflows/setup_modal_secrets.sh")
    print()

if __name__ == '__main__':
    main()
