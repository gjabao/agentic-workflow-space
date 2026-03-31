#!/usr/bin/env python3
"""
Fix Google Sheets authentication with refresh_token
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

print('⏳ Starting Google OAuth flow...')
print('✓ Your browser will open automatically')
print('✓ Please authorize with bao@smartmarketingflow.com')
print()

try:
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)

    # IMPORTANT: Request offline access to get refresh_token
    try:
        creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
    except:
        creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

    # Save credentials with refresh_token
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    print()
    print('✅ Authentication successful!')
    print('✅ Token saved with refresh_token')
    print('✅ You can now run the Crunchbase scraper')

except Exception as e:
    print(f'\n❌ Authentication failed: {e}')
    print('\n📌 Manual steps:')
    print('1. Make sure credentials.json is valid')
    print('2. Check that http://localhost:8080 is in OAuth redirect URIs')
    print('3. Try running this script again')
