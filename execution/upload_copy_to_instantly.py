#!/usr/bin/env python3
"""
Upload Pre-Written Copy to Instantly
Parses generated markdown copy and creates Instantly campaigns directly.
"""

import os
import sys
import json
import logging
import argparse
import requests
import re
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from utils_notifications import notify_success, notify_error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CopyParser:
    """Parses markdown copy file to extract email variants."""
    
    def parse_copy_file(self, file_path: str) -> List[Dict]:
        """Parse markdown file and extract email variants."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        variants = []
        
        # Split by variant sections
        variant_sections = re.split(r'### Variant [A-Z]:', content)
        
        for section in variant_sections[1:]:  # Skip first split (header)
            variant = {}
            
            # Extract variant name/angle
            angle_match = re.search(r'^([^\n]+)', section)
            if angle_match:
                variant['angle'] = angle_match.group(1).strip()
            
            # Extract subject
            subject_match = re.search(r'\*\*Subject:\*\*\s*(.+)', section)
            if subject_match:
                variant['subject'] = subject_match.group(1).strip()
            
            # Extract body (everything between **Body:** and **Follow-up 1**)
            body_match = re.search(r'\*\*Body:\*\*\s*\n(.*?)\n\*\*Follow-up', section, re.DOTALL)
            if body_match:
                body_text = body_match.group(1).strip()
                # Convert to HTML
                variant['body'] = self._convert_to_html(body_text)
            
            # Extract follow-ups
            followup1_match = re.search(r'\*\*Follow-up 1 \(Day 3\):\*\*\s*\n(.+)', section)
            if followup1_match:
                variant['followup_1'] = followup1_match.group(1).strip()
            
            followup2_match = re.search(r'\*\*Follow-up 2 \(Day 7\):\*\*\s*\n(.+)', section)
            if followup2_match:
                variant['followup_2'] = followup2_match.group(1).strip()
            
            if variant:
                variants.append(variant)
        
        logger.info(f"Parsed {len(variants)} variants from {file_path}")
        return variants
    
    def _convert_to_html(self, text: str) -> str:
        """Convert plain text to HTML format required by Instantly."""
        lines = text.split('\n')
        html_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Check if it's already "Sent from my iPhone"
                if 'Sent from my iPhone' in line:
                    html_lines.append('<p>Sent from my iPhone</p>')
                else:
                    html_lines.append(f'<p>{line}</p>')
        
        return '\n'.join(html_lines)


class InstantlyClient:
    """Handles interactions with Instantly API v2."""
    
    BASE_URL = "https://api.instantly.ai/api/v2"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_campaign(self, name: str, variant: Dict, dry_run: bool = False) -> Dict:
        """
        Create a campaign in Instantly with pre-written copy.
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
                                "subject": variant["subject"],
                                "body": variant["body"]
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 3,
                        "variants": [
                            {
                                "subject": "Re: " + variant["subject"],
                                "body": f"<p>{variant['followup_1']}</p>"
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 4,
                        "variants": [
                            {
                                "subject": "Re: " + variant["subject"],
                                "body": f"<p>{variant['followup_2']}</p>"
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
            logger.info(f"Payload preview:\n{json.dumps(payload, indent=2)}")
            return {"id": "dry_run_id", "name": name, "status": "simulated"}
            
        try:
            response = requests.post(
                f"{self.BASE_URL}/campaigns",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create campaign '{name}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return {}


    def update_campaign(self, campaign_id: str, name: str, variant: Dict, dry_run: bool = False) -> bool:
        """
        Update an existing campaign's sequences.
        """
        # Construct the payload (same as create, but we might need to be careful about structure)
        # For v2, we update the campaign sequences.
        # Note: The API might require getting the sequence ID first, but let's try updating the campaign object directly
        # or assuming we replace the sequences.
        
        # Based on research, we might need to use specific endpoints for subsequences.
        # However, for simplicity, let's try to update the campaign's sequences array if the main endpoint supports it.
        # If not, we might need to delete old sequences and add new ones, which is risky.
        # Let's try the PATCH /campaigns/{id} with the same payload structure as create.
        
        payload = {
            "name": name,
            "sequences": [{
                "steps": [
                    {
                        "type": "email",
                        "delay": 0,
                        "variants": [
                            {
                                "subject": variant["subject"],
                                "body": variant["body"]
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 3,
                        "variants": [
                            {
                                "subject": "Re: " + variant["subject"],
                                "body": f"<p>{variant['followup_1']}</p>"
                            }
                        ]
                    },
                    {
                        "type": "email",
                        "delay": 4,
                        "variants": [
                            {
                                "subject": "Re: " + variant["subject"],
                                "body": f"<p>{variant['followup_2']}</p>"
                            }
                        ]
                    }
                ]
            }]
        }
        
        if dry_run:
            logger.info(f"DRY RUN: Would UPDATE campaign '{name}' (ID: {campaign_id})")
            return True
            
        try:
            # First, we might need to get the campaign to see if we can just patch it.
            # Documentation suggests PATCH /api/v2/campaigns/{id}
            response = requests.patch(
                f"{self.BASE_URL}/campaigns/{campaign_id}",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update campaign '{name}' (ID: {campaign_id}): {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Upload pre-written copy to Instantly')
    parser.add_argument('--copy_file', required=True, help='Path to markdown copy file')
    parser.add_argument('--campaign_prefix', required=True, help='Prefix for campaign names')
    parser.add_argument('--dry_run', action='store_true', help='Simulate creation without API calls')
    parser.add_argument('--update_log', help='Path to JSON log file with existing campaign IDs to update')
    
    args = parser.parse_args()
    
    # Check environment
    instantly_key = os.getenv("INSTANTLY_API_KEY")
    
    if not instantly_key and not args.dry_run:
        logger.error("❌ INSTANTLY_API_KEY not found. Use --dry_run to test without it.")
        sys.exit(1)
    
    # Initialize services
    parser_obj = CopyParser()
    
    if instantly_key or args.dry_run:
        instantly = InstantlyClient(instantly_key or "dummy_key_for_dry_run")
    else:
        logger.error("❌ No API key available")
        sys.exit(1)
    
    # Parse copy file
    logger.info("=" * 60)
    logger.info(f"Parsing copy from {args.copy_file}")
    logger.info("=" * 60)
    
    variants = parser_obj.parse_copy_file(args.copy_file)
    
    if not variants:
        logger.error("❌ No variants found in copy file")
        sys.exit(1)
        
    # Load existing campaigns if updating
    existing_campaigns = {}
    if args.update_log:
        try:
            with open(args.update_log, 'r') as f:
                log_data = json.load(f)
                for camp in log_data:
                    # Map by angle or name suffix
                    # Assuming 'angle' is in the log
                    if 'angle' in camp:
                        existing_campaigns[camp['angle']] = camp['id']
            logger.info(f"Loaded {len(existing_campaigns)} existing campaigns to update")
        except Exception as e:
            logger.error(f"Failed to load update log: {e}")
            sys.exit(1)
    
    # Process campaigns
    action = "Updating" if existing_campaigns else "Creating"
    logger.info(f"\n{action} {len(variants)} campaigns...")
    processed_campaigns = []
    
    for i, variant in enumerate(variants, 1):
        angle = variant.get('angle', f'Variant {i}')
        campaign_name = f"{args.campaign_prefix} | {angle}"
        
        logger.info(f"\n⏳ {action} campaign {i}/{len(variants)}: {campaign_name}")
        logger.info(f"   Subject: {variant['subject']}")
        
        if angle in existing_campaigns:
            # Update existing
            camp_id = existing_campaigns[angle]
            success = instantly.update_campaign(camp_id, campaign_name, variant, dry_run=args.dry_run)
            if success:
                logger.info(f"✓ Campaign updated! ID: {camp_id}")
                processed_campaigns.append({
                    'id': camp_id,
                    'name': campaign_name,
                    'angle': angle
                })
        else:
            # Create new
            result = instantly.create_campaign(campaign_name, variant, dry_run=args.dry_run)
            if result:
                campaign_id = result.get('id', 'unknown')
                logger.info(f"✓ Campaign created! ID: {campaign_id}")
                processed_campaigns.append({
                    'id': campaign_id,
                    'name': campaign_name,
                    'angle': angle
                })
            else:
                logger.error(f"❌ Failed to create campaign: {campaign_name}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"✓ Workflow complete! Processed {len(processed_campaigns)}/{len(variants)} campaigns")
    logger.info("=" * 60)
    
    if processed_campaigns:
        logger.info("\nProcessed campaigns:")
        for camp in processed_campaigns:
            logger.info(f"  - {camp['name']} (ID: {camp['id']})")
    
    # Save summary
    if not args.dry_run and processed_campaigns:
        output_dir = '.tmp'
        os.makedirs(output_dir, exist_ok=True)
        summary_file = os.path.join(output_dir, f"instantly_campaigns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_file, 'w') as f:
            json.dump(processed_campaigns, f, indent=2)
        logger.info(f"\n💾 Summary saved to: {summary_file}")

    notify_success()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)
