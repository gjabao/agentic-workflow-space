#!/usr/bin/env python3
"""
Send/Draft Email Script
Uses Gmail API to create drafts or send emails directly.
"""

import os
import sys
import json
import base64
import logging
import argparse
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/spreadsheets', # Maintain existing scopes if we want to read sheets later
    'https://www.googleapis.com/auth/drive'
]

def get_credentials():
    """Get Google OAuth credentials."""
    creds = None
    # Check if token exists and has correct scopes? 
    # Actually, we rely on the user to re-auth if scopes changed.
    if os.path.exists('token.json'):
        try:
            # Manual load to bypass potential refresh token issues seen in other scripts
            with open('token.json', 'r') as f:
                token_data = json.load(f)
            
            # Check if current scopes include gmail (simple check)
            current_scopes = token_data.get('scopes', [])
            if 'https://www.googleapis.com/auth/gmail.compose' not in current_scopes:
                logger.warning("⚠️ Current token missing Gmail scope. Forcing re-authentication.")
                creds = None
            else:
                creds = Credentials(
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri'),
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=token_data.get('scopes')
                )
        except Exception as e:
            logger.warning(f"Error loading token: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logger.warning("Refresh failed. Re-authenticating.")
                creds = None

        if not creds:
            if not os.path.exists('credentials.json'):
                logger.error("❌ credentials.json not found. Please download it from Google Cloud Console.")
                sys.exit(1)
            
            logger.info("🔐 Initiating Authentication Flow...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save credentials
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            logger.info("✓ Token saved to token.json")

    return creds

def create_message(to, subject, body):
    """Create an email message."""
    message = EmailMessage()
    message.set_content(body)
    message['To'] = to
    message['Subject'] = subject
    
    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': encoded_message}

def draft_message(service, user_id, message):
    """Create a draft email."""
    try:
        draft = service.users().drafts().create(userId=user_id, body={'message': message}).execute()
        logger.info(f"✅ Draft created: {draft['id']}")
        return draft
    except HttpError as error:
        logger.error(f"❌ An error occurred: {error}")
        return None

def send_message(service, user_id, message):
    """Send an email immediately."""
    try:
        msg = service.users().messages().send(userId=user_id, body=message).execute()
        logger.info(f"🚀 Email sent: {msg['id']}")
        return msg
    except HttpError as error:
        logger.error(f"❌ An error occurred: {error}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Send or Draft Emails via Gmail API')
    parser.add_argument('--to', required=True, help='Recipient email')
    parser.add_argument('--subject', required=True, help='Email subject')
    parser.add_argument('--body', required=True, help='Email body text')
    parser.add_argument('--mode', choices=['draft', 'send'], default='draft', help='Mode: draft or send')
    
    args = parser.parse_args()
    
    creds = get_credentials()
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = create_message(args.to, args.subject, args.body)
        
        if args.mode == 'draft':
            draft_message(service, 'me', message)
        else:
            send_message(service, 'me', message)
            
    except HttpError as error:
        logger.error(f"❌ An error occurred: {error}")

if __name__ == '__main__':
    main()
