
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        try:
            with open('token.json', 'rb') as token:
                creds = pickle.load(token)
        except Exception:
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def inspect_sheet(name, sheet_id):
    print(f"\nExample Inspecting {name}: {sheet_id}")
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    try:
        metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        print(f"Title: {metadata.get('properties', {}).get('title')}")
        print("Tabs:")
        for sheet in metadata.get('sheets', []):
            props = sheet.get('properties', {})
            print(f" - {props.get('title')} (GID: {props.get('sheetId')})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    # Sheet A
    inspect_sheet("Sheet A (Source)", "1Dv55JczfJ88VK716ERFu6dXq8FI-nExY7xIGvN0-JMM")
    # Sheet B
    inspect_sheet("Sheet B (Exclusion)", "15OItOUZNla-hyCaoYa4LiRm6otEkHlUVHqKHLIIHRak")
