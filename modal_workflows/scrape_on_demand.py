"""
On-Demand Lead Scraper
Run from terminal with custom parameters

Usage:
    python3 -m modal run modal_workflows/scrape_on_demand.py \
        --query "dentists in New York" \
        --limit 100
"""

import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=1800,
    cpu=2.0
)
def scrape_leads(query: str, limit: int = 100):
    """
    Scrape leads from Apollo/Apify on-demand

    Args:
        query: Search query (e.g., "dentists in New York")
        limit: Number of leads to scrape (default: 100)
    """
    import os
    import requests
    from datetime import datetime

    print(f"🔍 Scraping leads: '{query}' (limit: {limit})")
    print(f"⏰ Started at: {datetime.now()}")

    apify_key = os.environ["APIFY_API_KEY"]

    # Example: Run Apify actor
    # Replace with your actual actor ID
    response = requests.post(
        "https://api.apify.com/v2/acts/YOUR_ACTOR_ID/runs",
        json={
            "query": query,
            "maxResults": limit
        },
        params={"token": apify_key},
        timeout=30
    )

    if response.status_code == 201:
        run_id = response.json()["data"]["id"]
        print(f"✅ Actor started: {run_id}")
        print(f"📊 Will scrape {limit} leads for: {query}")

        # In real implementation, wait for results and return them
        return {
            "status": "success",
            "run_id": run_id,
            "query": query,
            "limit": limit
        }
    else:
        print(f"❌ Failed to start actor: {response.status_code}")
        return {"status": "failed", "error": response.text}


@app.local_entrypoint()
def main(query: str = "dentists in New York", limit: int = 100):
    """
    Entry point for CLI execution

    Run with:
        python3 -m modal run modal_workflows/scrape_on_demand.py \
            --query "dentists in New York" \
            --limit 100
    """
    result = scrape_leads.remote(query, limit)
    print("\n" + "="*50)
    print(f"✅ Result: {result}")
