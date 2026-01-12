"""
Apify Lead Scraping Webhook - Modal Serverless (Simplified)
Deploy to get a public HTTPS URL for triggering lead scraping workflows

Deploy:
    modal deploy modal_workflows/webhook_apify_simple.py

Usage:
    curl -X POST https://YOUR_URL.modal.run/scrape \
        -H "Content-Type: application/json" \
        -d '{"industry": "Marketing Agency", "fetch_count": 30}'
"""

import modal

app = modal.App("anti-gravity-webhook")

# Define Modal image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi",
        "pydantic",
        "apify-client",
        "openai",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "google-api-python-client",
        "requests",
        "fuzzywuzzy",
        "python-Levenshtein",
        "nest-asyncio"
    )
)

# Volume for persistent storage
volume = modal.Volume.from_name("anti-gravity-data", create_if_missing=True)
VOLUME_PATH = "/data"


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    volumes={VOLUME_PATH: volume},
    timeout=3600,
    cpu=2.0,
    memory=2048
)
def scrape_leads(industry: str, fetch_count: int = 30, **kwargs):
    """Execute Apify lead scraping"""
    import os
    import json
    from datetime import datetime
    from pathlib import Path
    from apify_client import ApifyClient

    print(f"🚀 Scraping {fetch_count} leads for: {industry}")

    apify_key = os.environ.get("APIFY_API_KEY")
    if not apify_key:
        return {"error": "APIFY_API_KEY not found"}

    # Initialize client
    client = ApifyClient(apify_key)

    # Build input
    actor_input = {
        "fetch_count": fetch_count,
        "email_status": ["validated"]
    }

    # Add optional filters
    if kwargs.get("location"):
        actor_input["contact_location"] = [kwargs["location"].lower()]
    if kwargs.get("company_keywords"):
        actor_input["company_keywords"] = kwargs["company_keywords"]
    if kwargs.get("job_title"):
        actor_input["contact_job_title"] = kwargs["job_title"]

    # Run scraper
    print(f"⏳ Running Apify actor...")
    run = client.actor("code_crafter/leads-finder").call(run_input=actor_input)
    leads = client.dataset(run["defaultDatasetId"]).list_items().items

    print(f"✅ Scraped {len(leads)} leads")

    # Save to volume
    results_dir = Path(VOLUME_PATH) / "scraped_data"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = results_dir / f"leads_{industry.replace(' ', '_')}_{timestamp}.json"

    with open(result_file, 'w') as f:
        json.dump(leads, f, indent=2)

    volume.commit()

    return {
        "success": True,
        "total_leads": len(leads),
        "industry": industry,
        "result_file": str(result_file),
        "timestamp": timestamp
    }


@app.function(image=image)
@modal.web_endpoint(method="POST")
def scrape_webhook(data: dict):
    """
    Webhook endpoint for lead scraping

    Example:
        curl -X POST https://YOUR_URL.modal.run \
            -H "Content-Type: application/json" \
            -d '{"industry": "Marketing Agency", "fetch_count": 30}'
    """
    industry = data.get("industry")
    if not industry:
        return {"error": "Missing required field: industry"}, 400

    fetch_count = data.get("fetch_count", 30)

    # Trigger async scraping
    call = scrape_leads.spawn(
        industry=industry,
        fetch_count=fetch_count,
        location=data.get("location"),
        company_keywords=data.get("company_keywords"),
        job_title=data.get("job_title")
    )

    return {
        "status": "accepted",
        "message": "Lead scraping triggered",
        "job_id": call.object_id,
        "industry": industry,
        "fetch_count": fetch_count
    }
