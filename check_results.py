from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import os

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Force re-authentication
if os.path.exists('token.json'):
    os.remove('token.json')

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=8080)

with open('token.json', 'w') as token:
    token.write(creds.to_json())

service = build('sheets', 'v4', credentials=creds)

sheet_id = '1Dv55JczfJ88VK716ERFu6dXq8FI-nExY7xIGvN0-JMM'
tab_name = 'Airdrie PARALLEL TEST'

result = service.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range=f'{tab_name}!A1:M11'
).execute()

values = result.get('values', [])

print("=" * 80)
print("ENRICHMENT RESULTS - AIRDRIE PARALLEL TEST")
print("=" * 80)

phone_count = website_count = contact_count = job_title_count = 0

for i, row in enumerate(values[1:], 1):
    business = row[0] if row else ""
    email = row[1] if len(row) > 1 else ""
    phone = row[4] if len(row) > 4 else ""
    contact = row[6] if len(row) > 6 else ""
    job_title = row[7] if len(row) > 7 else ""
    website = row[8] if len(row) > 8 else ""
    
    if phone: phone_count += 1
    if website: website_count += 1
    if contact: contact_count += 1
    if job_title: job_title_count += 1
    
    print(f"\nRow {i}: {business[:50]}")
    print(f"  Primary Contact: {'✓ ' + contact if contact else '✗ EMPTY'}")
    print(f"  Job Title: {'✓ ' + job_title if job_title else '✗ EMPTY'}")
    print(f"  Phone: {'✓ ' + phone if phone else '✗ EMPTY'}")
    print(f"  Website: {'✓ ' + (website[:50] + '...' if len(website) > 50 else website) if website else '✗ EMPTY'}")

total = len(values) - 1
print("\n" + "=" * 80)
print("SUCCESS RATES")
print("=" * 80)
print(f"Phone: {phone_count}/{total} ({phone_count*100//total}%)")
print(f"Website: {website_count}/{total} ({website_count*100//total}%)")
print(f"Primary Contact: {contact_count}/{total} ({contact_count*100//total}%)")
print(f"Job Title: {job_title_count}/{total} ({job_title*100//total}%)")
print("=" * 80)
