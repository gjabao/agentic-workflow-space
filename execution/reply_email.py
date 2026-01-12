#!/usr/bin/env python3
"""
Auto-Reply Email Script (Connector Replies Framework)
Reads unread Gmail replies, classifies them, and generates appropriate responses.
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
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify',
]

# The 14 Connector Reply Scenarios
SCENARIOS = """
### 1. Standard Positive ("Yeah, intro me.", "Yes", "Sure", "Interested")
**Reply:** Sure — what role are you trying to fill and how soon?

### 2. Qualified (They give role + timeline, e.g., "Looking for SDR, need ASAP")
**Reply:** Got it. Give me 15 mins on a quick call so I don't intro you to the wrong person.

### 3. Want Intro but Refuse Call (e.g., "Just send the intro, no call needed")
**Reply:** No worries — if you want the intro done properly, I just need 15 mins to make sure it's a fit on both sides. Otherwise the match is usually off.

### 4. Ask "Who are you connected with?" or "What's your network like?"
**Reply:** Depends what you're hiring for — I don't blast intros. I only match when the timing, role, and pressure line up. What role are you trying to fill and how soon?

### 5. Ask "Is this paid?" or "What's the cost?"
**Reply:** Our systems are not free, since only step in when there's a live need on both sides. What role are you trying to fill?

### 6. Try to Turn You Into Vendor ("Can you guarantee X hires?" "How many intros?")
**Reply:** I don't promise volume — I promise relevance. That's why I ask about timing first. What are you trying to fill this month?

### 7. Cagey ("Why do you need to know the role?")
**Reply:** Because the quality of the match depends entirely on the specifics. I don't shotgun intros — I only match when it's right. What role & timeline are you working with?

### 9. Ignore Question, Repeat "Send intro." (Not serious)
**Reply:** No problem — when the need becomes active again, let me know and I'll connect you.

### 10. Ask for Website/Pitch/Info
**Reply:** Happy to explain — but first, what role are you trying to fill and how soon? The context changes the answer.

### 11. Full Breakdown (Great Prospect - they explain their need in detail)
**Reply:** Perfect — let's sync for 15 mins so I don't intro you to the wrong person. What's your availability?

### 12. Ask About Fees Early
**Reply:** The intro itself isn't paid. If there's ongoing value, we can talk later. For now — what role are you trying to fill?

### 13. Cancel Call or Go Cold After Research
**Reply:** No stress — timing might just be off. When the role becomes active again, tell me and I'll handle the connection properly.

### 14. Extremely Warm ("Yes let's talk!", "Love to connect!")
**Reply:** Great — before we sync, what role are you filling and how soon? Just want to come prepared.

### 0. Negative/Unsubscribe/Not Interested
**Reply:** [DO NOT REPLY]
"""


class EmailReplier:
    def __init__(self):
        # Azure OpenAI
        self.azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if self.azure_key and self.azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=self.azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=self.azure_endpoint
            )
            logger.info("✓ Azure OpenAI initialized")
        else:
            self.openai_client = None
            logger.error("❌ Azure OpenAI keys missing. Cannot classify replies.")

    def get_credentials(self):
        """Get Google OAuth credentials."""
        creds = None
        if os.path.exists('token.json'):
            try:
                with open('token.json', 'r') as f:
                    token_data = json.load(f)
                
                current_scopes = token_data.get('scopes', [])
                if 'https://www.googleapis.com/auth/gmail.readonly' not in current_scopes:
                    logger.warning("⚠️ Current token missing Gmail read scope. Forcing re-authentication.")
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
                    creds = None

            if not creds:
                if not os.path.exists('credentials.json'):
                    logger.error("❌ credentials.json not found.")
                    sys.exit(1)
                
                logger.info("🔐 Initiating Authentication Flow...")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                logger.info("✓ Token saved to token.json")

        return creds

    def get_unread_replies(self, service, max_results=10):
        """Fetch unread messages from inbox."""
        try:
            results = service.users().messages().list(
                userId='me',
                q='is:unread in:inbox',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
            logger.error(f"❌ Error fetching messages: {error}")
            return []

    def get_message_content(self, service, msg_id):
        """Get full message content."""
        try:
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            thread_id = msg.get('threadId', '')
            
            # Get body
            body = ""
            payload = msg.get('payload', {})
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data', '')
                        if data:
                            body = base64.urlsafe_b64decode(data).decode('utf-8')
                            break
            elif 'body' in payload:
                data = payload['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
            
            return {
                'id': msg_id,
                'thread_id': thread_id,
                'subject': subject,
                'from': from_email,
                'body': body[:1000]  # Limit body length
            }
        except HttpError as error:
            logger.error(f"❌ Error getting message: {error}")
            return None

    def classify_and_respond(self, message_content):
        """Use LLM to classify the reply and generate response."""
        if not self.openai_client:
            return None, None

        prompt = f"""
You are an expert at classifying cold email replies using the "Connector Replies" framework.

Here are the 14 scenarios and their responses:
{SCENARIOS}

---

Incoming email:
Subject: {message_content['subject']}
From: {message_content['from']}
Body:
{message_content['body']}

---

TASK:
1. Classify this email into ONE of the scenarios above (1-14, or 0 if negative/unsubscribe).
2. Return ONLY a JSON object with:
   - "scenario": number (0-14)
   - "reasoning": brief explanation
   - "reply": the exact response text (or empty string if scenario 0)

Output JSON only, no markdown fences.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.azure_deployment,
                messages=[
                    {"role": "system", "content": "You are a cold email reply classifier. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            # Clean up potential markdown fences
            if result_text.startswith('```'):
                result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]
            
            result = json.loads(result_text)
            return result.get('scenario'), result.get('reply', '')
            
        except Exception as e:
            logger.error(f"❌ Error classifying: {e}")
            return None, None

    def create_draft_reply(self, service, thread_id, to_email, subject, body):
        """Create a draft reply in the same thread."""
        try:
            message = EmailMessage()
            message.set_content(body)
            message['To'] = to_email
            message['Subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            draft_body = {
                'message': {
                    'raw': encoded_message,
                    'threadId': thread_id
                }
            }
            
            draft = service.users().drafts().create(userId='me', body=draft_body).execute()
            logger.info(f"✅ Draft created: {draft['id']}")
            return draft
        except HttpError as error:
            logger.error(f"❌ Error creating draft: {error}")
            return None

    def send_reply(self, service, thread_id, to_email, subject, body):
        """Send a reply in the same thread."""
        try:
            message = EmailMessage()
            message.set_content(body)
            message['To'] = to_email
            message['Subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            send_body = {
                'raw': encoded_message,
                'threadId': thread_id
            }
            
            sent = service.users().messages().send(userId='me', body=send_body).execute()
            logger.info(f"🚀 Reply sent: {sent['id']}")
            return sent
        except HttpError as error:
            logger.error(f"❌ Error sending: {error}")
            return None

    def execute(self, mode='draft', limit=10, message_id=None):
        """Main execution flow."""
        print(f"🚀 Starting Email Reply System (Mode: {mode}, Limit: {limit})")
        
        creds = self.get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        if message_id:
            messages = [{'id': message_id}]
        else:
            messages = self.get_unread_replies(service, limit)
        
        if not messages:
            print("📭 No unread messages found.")
            return
        
        print(f"📬 Found {len(messages)} unread message(s)")
        
        for msg in messages:
            content = self.get_message_content(service, msg['id'])
            if not content:
                continue
            
            print(f"\n--- Processing: {content['subject']} ---")
            print(f"From: {content['from']}")
            
            scenario, reply = self.classify_and_respond(content)
            
            if scenario == 0 or not reply:
                print("⏩ Skipping (negative/unsubscribe or no reply needed)")
                continue
            
            print(f"📊 Scenario: {scenario}")
            print(f"📝 Reply: {reply}")
            
            # Extract email from "Name <email>" format
            from_email = content['from']
            if '<' in from_email:
                from_email = from_email.split('<')[1].rstrip('>')
            
            if mode == 'draft':
                self.create_draft_reply(service, content['thread_id'], from_email, content['subject'], reply)
            else:
                self.send_reply(service, content['thread_id'], from_email, content['subject'], reply)
        
        print("\n✅ Done!")


def main():
    parser = argparse.ArgumentParser(description='Auto-Reply to Cold Emails (Connector Framework)')
    parser.add_argument('--mode', choices=['draft', 'send'], default='draft', help='Mode: draft or send')
    parser.add_argument('--limit', type=int, default=10, help='Max messages to process')
    parser.add_argument('--message_id', type=str, help='Process a specific message ID')
    
    args = parser.parse_args()
    
    replier = EmailReplier()
    replier.execute(mode=args.mode, limit=args.limit, message_id=args.message_id)


if __name__ == '__main__':
    main()
