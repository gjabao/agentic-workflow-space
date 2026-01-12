#!/usr/bin/env python3
"""
Instantly Campaign Creator
Generates and creates cold email campaigns in Instantly.ai using Azure OpenAI.
"""

import os
import sys
import json
import logging
import argparse
import asyncio
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
from utils_notifications import notify_success, notify_error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/instantly_creation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ContentGenerator:
    """Generates email content using Azure OpenAI."""
    
    def __init__(self, azure_endpoint: str, api_key: str, deployment_name: str):
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment_name = deployment_name

    def generate_campaign_content(self, client_info: Dict, offer: str) -> Dict:
        """
        Generate email sequences using SSM/Connector Angle/Anti-Fragile frameworks.
        Combines pre-generated {{icebreaker}} with Spartan-tone body copy.
        """
        prompt = f"""
        You are an expert cold email copywriter trained in SSM SOP, Connector Angle, and Anti-Fragile Method.

        CONTEXT:
        - Client: {client_info['name']}
        - Description: {client_info['description']}
        - Offer: {offer}
        - Target Audience: {client_info['target_audience']}

        TASK: Write cold email sequences following these frameworks.

        REQUIRED OUTPUT FORMAT (JSON):
        {{
            "step1_variant_a": {{ "subject": "...", "body": "..." }},
            "step1_variant_b": {{ "subject": "...", "body": "..." }},
            "step2_followup": {{ "subject": "", "body": "..." }},
            "step3_breakup": {{ "subject": "", "body": "..." }}
        }}

        CRITICAL RULES - SPARTAN/LACONIC TONE:
        1. **Short, direct** - No fluff or unnecessary words
        2. **Simple language** - NO corporate jargon (leverage, optimize, streamline, innovative, cutting-edge, etc.)
        3. **NO PUNCTUATION AT END** of sentences/CTAs - Drop ALL periods, question marks, exclamation points
        4. **Lowercase strategically** - Keep it casual where appropriate
        5. **Focus on WHAT, not HOW** - What they do, not how they do it
        6. **Shorten company names** - "{{{{companyName}}}}" not "{{{{companyName}}}} Agency"
        7. **Implied familiarity** - Show shared beliefs/interests
        8. **5-7 sentences max** - Under 100 words total per email

        STEP 1 EMAIL STRUCTURE (Connector Angle):
        - **CRITICAL**: MUST start with exactly `<p>{{{{icebreaker}}}}</p>` - do NOT replace this with custom text
        - **Line 2-3**: <p>Bridge connecting opener to offer (1-2 sentences wrapped in <p> tags)</p>
        - **Line 4**: <p>Specific outcome with numbers (e.g. "I know someone who helps clinics add 5-10 premium treatments per month")</p>
        - **Line 5**: <p>Easy CTA with NO punctuation (e.g. "Worth exploring" or "Want me to intro you")</p>
        - **End with**: `<p>Sent from my iPhone</p>`

        VARIANT A vs B ANGLES:
        - **Variant A**: Problem-solving angle (acknowledge their pain, offer solution)
        - **Variant B**: Opportunity angle (highlight what they're missing, offer access)
        - Both must be DIFFERENT approaches to the same offer

        FOLLOW-UP RULES (SSM SOP):
        - **Step 2 (Day 3)**: subject = "", body = "Hey {{{{firstName}}}}, worth intro'ing you"
        - **Step 3 (Day 7)**: subject = "", body = "Hey {{{{firstName}}}}, maybe this isn't something you're interested in — wishing you the best."

        EXAMPLES OF GOOD SPARTAN TONE:
        - ✅ "Figured I'd reach out"
        - ✅ "Worth exploring"
        - ✅ "Happy to intro if relevant"
        - ❌ "I hope this email finds you well."
        - ❌ "Would you be interested in learning more?"
        - ❌ "We leverage cutting-edge methodologies"

        SUBJECT LINE RULES:
        - Keep under 5 words
        - Personalized or curiosity-driven
        - Examples: "{{{{firstName}}}} - quick question", "idea for {{{{companyName}}}}", "thought of you"

        CRITICAL EXAMPLE FOR STEP 1 BODY FORMAT:
        <p>{{{{icebreaker}}}}</p>
        <p>I'm around clinic owners in Edmonton daily and they keep saying they didn't know Korean dermaceutical suppliers were local</p>
        <p>I know a team that helps clinics stock Korean clinical-grade brands and trains staff on protocols so you can charge $180-200 per treatment</p>
        <p>Worth intro'ing you</p>
        <p>Sent from my iPhone</p>

        NOW GENERATE THE EMAILS:
        Remember: Step 1 body MUST start with exactly `<p>{{{{icebreaker}}}}</p>`. Do NOT replace this variable with custom text.
        Each sentence MUST be wrapped in its own <p> tag.
        Follow-ups have EMPTY subject lines.
        Keep it SHORT, DIRECT, CASUAL - like texting a colleague, not writing a business proposal.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert cold email copywriter specializing in Connector Angle and SSM SOP. Output valid JSON only. Follow Spartan tone rules strictly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return {}

class InstantlyClient:
    """Handles interactions with Instantly API v2."""
    
    BASE_URL = "https://api.instantly.ai/api/v2"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_campaign(self, name: str, content: Dict, dry_run: bool = False) -> Dict:
        """
        Create a campaign in Instantly.
        """
        # Construct the payload
        payload = {
            "name": name,
            "sequences": [{
                "steps": [
                    {
                        "type": "email",
                        "delay": 0,
                        "variants": [
                            {
                                "subject": content["step1_variant_a"]["subject"],
                                "body": content["step1_variant_a"]["body"]
                            },
                            {
                                "subject": content["step1_variant_b"]["subject"],
                                "body": content["step1_variant_b"]["body"]
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 3,
                        "variants": [
                            {
                                "subject": content["step2_followup"]["subject"],
                                "body": content["step2_followup"]["body"]
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 4,
                        "variants": [
                            {
                                "subject": content["step3_breakup"]["subject"],
                                "body": content["step3_breakup"]["body"]
                            }
                        ]
                    }
                ]
            }],
            "campaign_schedule": {
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "schedules": [{
                    "name": "Weekday Schedule",
                    "days": {
                        "monday": True, "tuesday": True, "wednesday": True, 
                        "thursday": True, "friday": True
                    },
                    "timing": {"from": "09:00", "to": "17:00"},
                    "timezone": "America/Chicago"
                }]
            },
            "email_gap": 10,
            "daily_limit": 50,
            "stop_on_reply": True,
            "stop_on_auto_reply": True,
            "link_tracking": True,
            "open_tracking": True
        }
        
        if dry_run:
            logger.info(f"DRY RUN: Would create campaign '{name}'")
            logger.info(f"Payload preview: {json.dumps(payload, indent=2)}")
            return {"id": "dry_run_id", "name": name, "status": "simulated"}
            
        try:
            response = requests.post(
                f"{self.BASE_URL}/campaigns",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create campaign '{name}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return {}

    def add_leads_to_campaign(self, campaign_id: str, leads: List[Dict], dry_run: bool = False) -> int:
        """
        Add leads to a specific campaign with optimized batch processing.
        """
        if dry_run:
            logger.info(f"DRY RUN: Would add {len(leads)} leads to campaign {campaign_id}")
            return len(leads)

        success_count = 0
        failed_count = 0
        total = len(leads)
        logger.info(f"Adding {total} leads to campaign {campaign_id}...")

        # Process in smaller batches with rate limiting
        batch_size = 5  # Smaller batch to avoid rate limits
        import time

        for i, lead in enumerate(leads, 1):
            # Skip leads without email
            if not lead.get("email"):
                continue

            # Map fields to Instantly format
            payload = {
                "campaign_id": campaign_id,
                "email": lead.get("email"),
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "company_name": lead.get("company_name", ""),
                "personalization": lead.get("icebreaker", ""),  # Map icebreaker to personalization
                "website": lead.get("website", ""),
                "custom_variables": {
                    "icebreaker": lead.get("icebreaker", ""),
                    "industry": lead.get("industry", ""),
                    "location": lead.get("location", "")
                }
            }

            try:
                response = requests.post(
                    f"{self.BASE_URL}/leads",
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                success_count += 1

                # Progress updates every 10 leads
                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{total} leads ({success_count} successful, {failed_count} failed)")

            except requests.exceptions.HTTPError as e:
                failed_count += 1
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit hit at lead {i}, waiting 5 seconds...")
                    time.sleep(5)
                    # Retry once
                    try:
                        response = requests.post(
                            f"{self.BASE_URL}/leads",
                            headers=self.headers,
                            json=payload,
                            timeout=10
                        )
                        response.raise_for_status()
                        success_count += 1
                        failed_count -= 1
                    except:
                        logger.error(f"Failed to add lead {payload['email']} after retry")
                else:
                    logger.error(f"Failed to add lead {payload['email']}: HTTP {e.response.status_code}")

            except requests.exceptions.RequestException as e:
                failed_count += 1
                logger.error(f"Failed to add lead {payload['email']}: {e}")

            # Small delay between requests to avoid rate limiting
            if i % batch_size == 0:
                time.sleep(0.5)

        logger.info(f"✓ Added {success_count}/{total} leads to campaign {campaign_id} ({failed_count} failed)")
        return success_count

def main():
    parser = argparse.ArgumentParser(description='Create Instantly campaigns')
    parser.add_argument('--client_name', required=True, help='Client name')
    parser.add_argument('--description', required=True, help='Client description')
    parser.add_argument('--target_audience', required=True, help='Target audience')
    parser.add_argument('--offers', nargs='+', required=True, help='List of offers')
    parser.add_argument('--leads_file', help='Path to JSON file with leads to add')
    parser.add_argument('--dry_run', action='store_true', help='Simulate creation')
    
    args = parser.parse_args()
    
    # Check environment
    instantly_key = os.getenv("INSTANTLY_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not instantly_key and not args.dry_run:
        logger.error("❌ INSTANTLY_API_KEY not found. Use --dry_run to test without it.")
        sys.exit(1)
        
    if not (azure_endpoint and azure_key):
        logger.error("❌ Azure OpenAI credentials not found.")
        sys.exit(1)
        
    # Initialize services
    generator = ContentGenerator(azure_endpoint, azure_key, azure_deployment)
    
    if instantly_key:
        instantly = InstantlyClient(instantly_key)
    elif args.dry_run:
        logger.info("⚠️  Running in DRY RUN mode with dummy API key")
        instantly = InstantlyClient("dummy_key_for_dry_run")
    else:
        instantly = None
    
    # Load leads if provided
    leads = []
    if args.leads_file:
        try:
            with open(args.leads_file, 'r') as f:
                leads = json.load(f)
            # Filter for valid emails if possible
            leads = [l for l in leads if l.get('email') and l.get('verification_status') == 'Valid']
            logger.info(f"Loaded {len(leads)} valid leads from {args.leads_file}")
        except Exception as e:
            logger.error(f"Failed to load leads file: {e}")
            sys.exit(1)

    client_info = {
        "name": args.client_name,
        "description": args.description,
        "target_audience": args.target_audience
    }
    
    logger.info("=" * 60)
    logger.info(f"Starting Campaign Creation for {args.client_name}")
    logger.info(f"Offers: {args.offers}")
    if leads:
        logger.info(f"Leads to add: {len(leads)}")
    logger.info("=" * 60)
    
    for i, offer in enumerate(args.offers, 1):
        logger.info(f"\nProcessing Offer {i}: {offer}")
        
        # 1. Generate Content
        logger.info("⏳ Generating email sequences...")
        content = generator.generate_campaign_content(client_info, offer)
        
        if not content:
            logger.error("Failed to generate content. Skipping.")
            continue
            
        # 2. Create Campaign
        campaign_name = f"{args.client_name} | Offer {i} - {offer[:30]}"
        logger.info(f"⏳ Creating campaign: {campaign_name}")
        
        result = instantly.create_campaign(campaign_name, content, dry_run=args.dry_run) if instantly or args.dry_run else None
        
        if result:
            campaign_id = result.get('id', 'unknown')
            logger.info(f"✓ Campaign created! ID: {campaign_id}")
            
            # 3. Add Leads
            if leads and (instantly or args.dry_run):
                logger.info(f"⏳ Adding leads to campaign {campaign_id}...")
                instantly.add_leads_to_campaign(campaign_id, leads, dry_run=args.dry_run)
        else:
            logger.error("Failed to create campaign.")

    logger.info("\n" + "=" * 60)
    logger.info("✓ Workflow complete!")
    notify_success()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)
