"""
Google API Authentication Helpers for Modal
Handles Gmail, Google Sheets, Google Drive authentication
"""

import os
import json
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build


def get_gmail_service():
    """
    Build Gmail API service from Modal secrets

    Required Modal secrets:
    - GMAIL_CREDENTIALS_JSON: OAuth client credentials
    - GMAIL_TOKEN_JSON: OAuth token with refresh token

    Returns:
        Gmail API service object
    """
    credentials_json = os.environ.get('GMAIL_CREDENTIALS_JSON')
    token_json = os.environ.get('GMAIL_TOKEN_JSON')

    if not credentials_json or not token_json:
        raise ValueError(
            "Gmail credentials not found in Modal secrets. "
            "Add GMAIL_CREDENTIALS_JSON and GMAIL_TOKEN_JSON to Modal secrets."
        )

    # Parse credentials
    token_data = json.loads(token_json)

    # Create credentials object
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes')
    )

    return build('gmail', 'v1', credentials=creds)


def get_sheets_service(use_service_account=False):
    """
    Build Google Sheets API service

    Args:
        use_service_account: If True, uses service account auth (better for automation)
                           If False, uses OAuth user credentials

    Required Modal secrets (OAuth):
    - GOOGLE_CREDENTIALS_JSON
    - GOOGLE_TOKEN_JSON

    OR (Service Account):
    - GOOGLE_SERVICE_ACCOUNT_JSON

    Returns:
        Sheets API service object
    """
    if use_service_account:
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not found in Modal secrets")

        creds = ServiceAccountCredentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
    else:
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        token_json = os.environ.get('GOOGLE_TOKEN_JSON')

        if not credentials_json or not token_json:
            raise ValueError("Google credentials not found in Modal secrets")

        token_data = json.loads(token_json)
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )

    return build('sheets', 'v4', credentials=creds)


def get_drive_service(use_service_account=False):
    """
    Build Google Drive API service

    Args:
        use_service_account: If True, uses service account auth

    Returns:
        Drive API service object
    """
    if use_service_account:
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not found in Modal secrets")

        creds = ServiceAccountCredentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=['https://www.googleapis.com/auth/drive']
        )
    else:
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        token_json = os.environ.get('GOOGLE_TOKEN_JSON')

        if not credentials_json or not token_json:
            raise ValueError("Google credentials not found in Modal secrets")

        token_data = json.loads(token_json)
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )

    return build('drive', 'v3', credentials=creds)
