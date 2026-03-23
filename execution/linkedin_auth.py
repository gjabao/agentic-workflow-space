#!/usr/bin/env python3
"""
LinkedIn OAuth2 Helper — DO Architecture Execution Script
One-time setup to authenticate with LinkedIn API for posting.

Usage:
    python3 execution/linkedin_auth.py

Prerequisites:
    1. Create LinkedIn Developer App at https://www.linkedin.com/developers/
    2. Add products: "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"
    3. Set redirect URL to: http://localhost:8080/callback
    4. Add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET to .env

Directive: directives/linkedin_parasite.md
"""

import os
import sys
import json
import re
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "openid profile w_member_social"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
PROFILE_URL = "https://api.linkedin.com/v2/userinfo"


def sanitize_error(error_str: str) -> str:
    """Remove secrets from error messages."""
    if not error_str:
        return error_str
    error_str = re.sub(
        r'(client_secret[=:]\s*)[a-zA-Z0-9_\-\.]+',
        r'\1[REDACTED]',
        error_str, flags=re.IGNORECASE
    )
    error_str = re.sub(
        r'(bearer\s+)[a-zA-Z0-9_\-\.]+',
        r'\1[REDACTED]',
        error_str, flags=re.IGNORECASE
    )
    return error_str


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth2 callback."""

    authorization_code = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if 'code' in params:
            OAuthCallbackHandler.authorization_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                <h2>LinkedIn Authorization Successful</h2>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        elif 'error' in params:
            error = params.get('error', ['unknown'])[0]
            desc = params.get('error_description', [''])[0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                <h2>Authorization Failed</h2>
                <p>Error: {error}</p>
                <p>{desc}</p>
                </body></html>
            """.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def exchange_code_for_token(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange authorization code for access token."""
    response = requests.post(TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': client_id,
        'client_secret': client_secret,
    }, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {sanitize_error(response.text)}")

    return response.json()


def get_person_urn(access_token: str) -> str:
    """Get the authenticated user's LinkedIn person URN."""
    response = requests.get(PROFILE_URL, headers={
        'Authorization': f'Bearer {access_token}',
    }, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Profile fetch failed: {sanitize_error(response.text)}")

    data = response.json()
    sub = data.get('sub', '')
    return f"urn:li:person:{sub}"


def update_env_file(key: str, value: str):
    """Update or add a key in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()

        pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f'{key}={value}', content)
        else:
            content = content.rstrip('\n') + f'\n{key}={value}\n'

        with open(env_path, 'w') as f:
            f.write(content)
    else:
        with open(env_path, 'w') as f:
            f.write(f'{key}={value}\n')


def main():
    client_id = os.getenv('LINKEDIN_CLIENT_ID')
    client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env")
        print()
        print("Setup steps:")
        print("1. Go to https://www.linkedin.com/developers/")
        print("2. Create a new app (or use existing)")
        print("3. Add products: 'Share on LinkedIn' + 'Sign In with LinkedIn using OpenID Connect'")
        print("4. Under Auth tab, set redirect URL to: http://localhost:8080/callback")
        print("5. Copy Client ID and Client Secret to your .env file:")
        print("   LINKEDIN_CLIENT_ID=your_client_id")
        print("   LINKEDIN_CLIENT_SECRET=your_client_secret")
        sys.exit(1)

    # Build authorization URL
    auth_params = (
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES}"
        f"&state=linkedin_parasite_auth"
    )
    full_auth_url = AUTH_URL + auth_params

    print("LinkedIn OAuth2 Authorization")
    print("=" * 50)
    print()
    print("Opening browser for authorization...")
    print(f"If browser doesn't open, visit: {full_auth_url}")
    print()

    # Start local server
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)

    # Open browser
    webbrowser.open(full_auth_url)

    print("Waiting for authorization callback...")
    while OAuthCallbackHandler.authorization_code is None:
        server.handle_request()

    code = OAuthCallbackHandler.authorization_code
    server.server_close()
    print("Authorization code received")

    # Exchange code for token
    print("Exchanging code for access token...")
    token_data = exchange_code_for_token(client_id, client_secret, code)

    access_token = token_data.get('access_token', '')
    refresh_token = token_data.get('refresh_token', '')
    expires_in = token_data.get('expires_in', 0)

    if not access_token:
        print("Failed to get access token")
        sys.exit(1)

    print(f"Access token obtained (expires in {expires_in // 86400} days)")

    # Get person URN
    print("Fetching LinkedIn profile...")
    person_urn = get_person_urn(access_token)
    print(f"Person URN: {person_urn}")

    # Save to .env
    print("Saving credentials to .env...")
    update_env_file('LINKEDIN_ACCESS_TOKEN', access_token)
    if refresh_token:
        update_env_file('LINKEDIN_REFRESH_TOKEN', refresh_token)
    update_env_file('LINKEDIN_PERSON_URN', person_urn)

    print()
    print("=" * 50)
    print("LinkedIn authentication complete!")
    print(f"  Person URN: {person_urn}")
    print(f"  Token expires in: {expires_in // 86400} days")
    print()
    print("You can now run the LinkedIn Parasite System.")


if __name__ == '__main__':
    main()
