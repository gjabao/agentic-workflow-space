#!/usr/bin/env python3
"""
Update Instantly campaigns with exact copy from markdown file
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Campaign IDs from creation
CAMPAIGNS = {
    "044164a7-5f5d-4047-9ccb-f228fbecef0d": "Variant A - Edmonton Local",
    "00749e47-b523-460b-a5ae-1b28ef222567": "Variant B - Training + Revenue",
    "56dbce4a-b5bf-40e1-8642-2d6ab2c8c631": "Variant C - Differentiation",
    "cb882a25-5b3b-408e-b279-66723753f5bd": "Variant D - Premium Signal"
}

# Exact copy from .tmp/custom_copy_beautyconnectshop.md
COPY_VARIANTS = {
    "044164a7-5f5d-4047-9ccb-f228fbecef0d": {
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
        }]
    },
    "00749e47-b523-460b-a5ae-1b28ef222567": {
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
        }]
    },
    "56dbce4a-b5bf-40e1-8642-2d6ab2c8c631": {
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
        }]
    },
    "cb882a25-5b3b-408e-b279-66723753f5bd": {
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
        }]
    }
}

def update_campaign(campaign_id: str, payload: dict, api_key: str):
    """Update campaign via Instantly API"""
    url = f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Add required fields for update
    payload["campaign_schedule"] = {
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
    }
    payload["email_gap"] = 10
    payload["daily_limit"] = 50
    payload["stop_on_reply"] = True
    payload["stop_on_auto_reply"] = True
    payload["link_tracking"] = True
    payload["open_tracking"] = True

    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✓ Updated campaign {campaign_id}: {CAMPAIGNS[campaign_id]}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to update {campaign_id}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"  Response: {e.response.text}")
        return False

def main():
    api_key = os.getenv("INSTANTLY_API_KEY_CLIENT")
    if not api_key:
        print("❌ INSTANTLY_API_KEY_CLIENT not found in .env")
        return

    print("=" * 80)
    print("Updating Instantly Campaigns with Exact Copy from Markdown File")
    print("=" * 80)

    for campaign_id, payload in COPY_VARIANTS.items():
        print(f"\nUpdating: {CAMPAIGNS[campaign_id]}")
        update_campaign(campaign_id, payload, api_key)

    print("\n" + "=" * 80)
    print("✓ All campaigns updated!")
    print("=" * 80)

if __name__ == "__main__":
    main()
