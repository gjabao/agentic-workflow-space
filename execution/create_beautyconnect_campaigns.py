#!/usr/bin/env python3
"""
Create Instantly campaigns for Beauty Connect Shop with exact copy from markdown file
"""
import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Exact copy from .tmp/custom_copy_beautyconnectshop.md
CAMPAIGNS = [
    {
        "name": "Beauty Connect Shop | Edmonton Local Awareness",
        "sequences": [{
            "steps": [
                {
                    "type": "email",
                    "delay": 0,
                    "variants": [
                        {
                            "subject": "Edmonton clinic owners",
                            "body": "<p>Hey {{firstName}},</p><p>Noticed {{companyName}} offers advanced skincare treatments in Edmonton</p><p>I'm around clinic owners in the area daily and they keep saying they didn't know we had Korean dermaceutical suppliers locally — most are still ordering from Vancouver with 2-week lead times</p><p>I know a team that helps clinics stock Korean clinical-grade brands like the ones dermatologists use in Seoul, plus they train your staff on protocols so you can charge $180-200 per treatment</p><p>Worth intro'ing you</p><p>Sent from my iPhone</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 3,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, worth intro'ing you</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 4,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best</p>"
                        }
                    ]
                }
            ]
        }],
        "campaign_schedule": {
            "start_date": "2025-12-28",
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
    },
    {
        "name": "Beauty Connect Shop | Training + Revenue Uplift",
        "sequences": [{
            "steps": [
                {
                    "type": "email",
                    "delay": 0,
                    "variants": [
                        {
                            "subject": "Korean skincare protocols",
                            "body": "<p>Hey {{firstName}},</p><p>Saw {{companyName}} is scaling their treatment menu</p><p>I talk to a lot of medical aestheticians and they keep saying they can't charge premium prices for Korean treatments because they never got proper training on protocols</p><p>I know a supplier that gives you Korean dermaceutical products plus full training on how to apply them — helped clinics go from $80 facials to $200 specialty treatments in 60 days</p><p>Want me to intro you</p><p>Sent from my iPhone</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 3,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, worth intro'ing you</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 4,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best</p>"
                        }
                    ]
                }
            ]
        }],
        "campaign_schedule": {
            "start_date": "2025-12-28",
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
    },
    {
        "name": "Beauty Connect Shop | Menu Differentiation",
        "sequences": [{
            "steps": [
                {
                    "type": "email",
                    "delay": 0,
                    "variants": [
                        {
                            "subject": "differentiate your menu",
                            "body": "<p>Hey {{firstName}},</p><p>Figured I'd reach out — I'm around spa directors in Edmonton daily and they keep saying every clinic carries the same IMAGE and SkinCeuticals lines, hard to stand out</p><p>I know someone who helps clinics add Korean dermaceutical brands that most competitors don't have access to yet — gave one clinic in Calgary exclusive treatments that book out 3 weeks in advance</p><p>Worth exploring</p><p>Sent from my iPhone</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 3,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, worth intro'ing you</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 4,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best</p>"
                        }
                    ]
                }
            ]
        }],
        "campaign_schedule": {
            "start_date": "2025-12-28",
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
    },
    {
        "name": "Beauty Connect Shop | Premium Signal Movement",
        "sequences": [{
            "steps": [
                {
                    "type": "email",
                    "delay": 0,
                    "variants": [
                        {
                            "subject": "saw some movement",
                            "body": "<p>Hey {{firstName}},</p><p>Saw some movement on my side — I'm around clinic owners in Edmonton daily and they keep saying they didn't know Korean dermaceutical suppliers were local</p><p>I know a team launching training protocols for Korean clinical skincare — helped clinics add $15-20k monthly revenue from specialty treatments they couldn't offer before</p><p>Want me to intro you</p><p>Sent from my iPhone</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 3,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, worth intro'ing you</p>"
                        }
                    ]
                },
                {
                    "type": "email",
                    "delay": 4,
                    "variants": [
                        {
                            "subject": "",
                            "body": "<p>Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best</p>"
                        }
                    ]
                }
            ]
        }],
        "campaign_schedule": {
            "start_date": "2025-12-28",
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
]

def create_campaign(payload: dict, api_key: str):
    """Create campaign via Instantly API"""
    url = "https://api.instantly.ai/api/v2/campaigns"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        logger.info(f"✓ Created: {payload['name']}")
        logger.info(f"  Campaign ID: {result.get('id', 'N/A')}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to create '{payload['name']}': {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"  Response: {e.response.text}")
        return None

def main():
    api_key = os.getenv("INSTANTLY_API_KEY_CLIENT")
    if not api_key:
        logger.error("❌ INSTANTLY_API_KEY_CLIENT not found in .env")
        return

    logger.info("=" * 80)
    logger.info("Creating Beauty Connect Shop Campaigns with Exact Copy")
    logger.info("=" * 80)

    created_ids = []
    for campaign in CAMPAIGNS:
        logger.info(f"\nCreating: {campaign['name']}")
        result = create_campaign(campaign, api_key)
        if result:
            created_ids.append(result.get('id'))

    logger.info("\n" + "=" * 80)
    logger.info(f"✓ Created {len(created_ids)} campaigns successfully!")
    logger.info("=" * 80)
    logger.info("\nCampaign IDs:")
    for i, cid in enumerate(created_ids, 1):
        logger.info(f"  {i}. {cid}")

if __name__ == "__main__":
    main()
