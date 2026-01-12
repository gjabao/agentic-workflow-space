#!/usr/bin/env python3
"""
Simple script to trigger the Apify webhook
"""

import requests
import json

# Your webhook URL
WEBHOOK_URL = "https://giabaongb0305--anti-gravity-webhook-scrape-webhook.modal.run"

def trigger_scrape(industry, fetch_count=30, **kwargs):
    """
    Trigger lead scraping via webhook

    Args:
        industry: Target industry (required)
        fetch_count: Number of leads to scrape
        **kwargs: Additional filters (location, job_title, company_keywords, etc.)
    """
    payload = {
        "industry": industry,
        "fetch_count": fetch_count,
        **kwargs
    }

    print(f"🚀 Triggering webhook for: {industry}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(WEBHOOK_URL, json=payload)

    print(f"\n📊 Response ({response.status_code}):")
    print(json.dumps(response.json(), indent=2))

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Success! Job ID: {result.get('job_id')}")
        return result
    else:
        print(f"\n❌ Error: {response.text}")
        return None


if __name__ == "__main__":
    # Example 1: Simple scrape
    trigger_scrape("Marketing Agency", fetch_count=5)

    # Example 2: Full scrape with filters
    # trigger_scrape(
    #     industry="Marketing Agency",
    #     fetch_count=30,
    #     location="united states",
    #     company_keywords=["digital marketing", "PPC"],
    #     job_title=["CEO", "Founder"]
    # )
