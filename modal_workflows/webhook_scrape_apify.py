"""
Apify Lead Scraping Webhook - Modal Serverless
Deploy to get a public HTTPS URL for triggering lead scraping workflows

Deploy:
    modal deploy modal_workflows/webhook_scrape_apify.py

Usage:
    curl -X POST https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/webhook/scrape-apify-leads \
        -H "Content-Type: application/json" \
        -H "X-Webhook-Secret: your-secret" \
        -d '{"industry": "Marketing Agency", "fetch_count": 30, "skip_test": true, "valid_only": true}'
"""

import modal
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List

# Initialize Modal app
app = modal.App("anti-gravity-webhook")
web_app = FastAPI(title="Anti-Gravity Webhook API", version="1.0")

# Define Modal image with dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
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


# ===== Data Models =====

class ApifyLeadRequest(BaseModel):
    """Request model for Apify lead scraping"""
    industry: str = Field(..., description="Target industry (required)")
    fetch_count: int = Field(30, description="Number of leads to scrape")
    location: Optional[str] = Field(None, description="Target location (lowercase)")
    city: Optional[str] = Field(None, description="Target city")
    job_title: Optional[List[str]] = Field(None, description="Job titles to filter")
    company_size: Optional[List[str]] = Field(None, description="Company size ranges")
    company_keywords: Optional[List[str]] = Field(None, description="Keywords for filtering")
    company_industry: Optional[List[str]] = Field(None, description="Apify industry filters")
    skip_test: bool = Field(False, description="Skip 25-lead validation phase")
    valid_only: bool = Field(False, description="Export only verified valid emails")
    sender_context: str = Field("", description="Context for SSM icebreakers")

    class Config:
        json_schema_extra = {
            "example": {
                "industry": "Marketing Agency",
                "fetch_count": 30,
                "location": "united states",
                "company_keywords": ["digital marketing", "PPC agency"],
                "job_title": ["CEO", "Founder"],
                "company_industry": ["marketing & advertising"],
                "skip_test": True,
                "valid_only": True,
                "sender_context": "We help marketing agencies scale their PPC campaigns"
            }
        }


# ===== Volume for persistent storage =====
volume = modal.Volume.from_name("anti-gravity-data", create_if_missing=True)
VOLUME_PATH = "/data"


# ===== Core Scraping Function =====

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    volumes={VOLUME_PATH: volume},
    timeout=3600,  # 1 hour max
    cpu=2.0,
    memory=2048
)
def scrape_apify_leads_modal(
    industry: str,
    fetch_count: int,
    location: Optional[str] = None,
    city: Optional[str] = None,
    job_title: Optional[List[str]] = None,
    company_size: Optional[List[str]] = None,
    company_keywords: Optional[List[str]] = None,
    company_industry: Optional[List[str]] = None,
    skip_test: bool = False,
    valid_only: bool = False,
    sender_context: str = ""
):
    """
    Execute Apify lead scraping workflow in Modal serverless environment
    """
    import os
    import json
    from datetime import datetime
    from pathlib import Path
    from apify_client import ApifyClient

    print("="*60)
    print(f"🚀 Apify Lead Scraping Started (Modal Serverless)")
    print(f"📅 Timestamp: {datetime.now().isoformat()}")
    print(f"🎯 Industry: {industry}")
    print(f"📊 Fetch Count: {fetch_count}")
    print(f"🌍 Location: {location or 'Not specified'}")
    print(f"✅ Valid Only: {valid_only}")
    print(f"⏭️  Skip Test: {skip_test}")
    print("="*60)

    # Get API keys from Modal secrets
    apify_key = os.environ.get("APIFY_API_KEY")
    if not apify_key:
        raise ValueError("APIFY_API_KEY not found in Modal secrets")

    # Initialize Apify client
    client = ApifyClient(apify_key)

    # Build actor input
    actor_input = {
        "fetch_count": fetch_count,
        "email_status": ["validated"]
    }

    # Add filters
    if location:
        actor_input["contact_location"] = [location.lower()]
    if city:
        actor_input["contact_city"] = [city]
    if job_title:
        actor_input["contact_job_title"] = job_title
    if company_size:
        actor_input["size"] = company_size
    if company_keywords:
        actor_input["company_keywords"] = company_keywords
    if company_industry:
        actor_input["company_industry"] = [ind.lower() for ind in company_industry]

    # Execute scrape
    print(f"\n⏳ Running Apify actor (code_crafter/leads-finder)...")
    print(f"   Input: {json.dumps(actor_input, indent=2)}")

    run = client.actor("code_crafter/leads-finder").call(run_input=actor_input)
    dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items

    print(f"✅ Scraped {len(dataset_items)} leads")

    # Save results to volume
    results_dir = Path(VOLUME_PATH) / "scraped_data"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = results_dir / f"apify_leads_{industry.replace(' ', '_')}_{timestamp}.json"

    with open(result_file, 'w') as f:
        json.dump(dataset_items, f, indent=2)

    print(f"💾 Saved results to: {result_file}")

    # Calculate metrics
    total_leads = len(dataset_items)
    emails_count = len([l for l in dataset_items if l.get('email')])
    validated_count = len([l for l in dataset_items if l.get('email_status') == 'validated'])

    metrics = {
        "total_leads": total_leads,
        "emails_found": emails_count,
        "email_rate": f"{emails_count/total_leads*100:.1f}%" if total_leads > 0 else "0%",
        "validated_emails": validated_count,
        "result_file": str(result_file),
        "industry": industry,
        "location": location,
        "timestamp": datetime.now().isoformat()
    }

    # Commit volume changes
    volume.commit()

    print("\n" + "="*60)
    print("✅ Scraping completed successfully!")
    print(f"📊 Total leads: {total_leads}")
    print(f"📧 With emails: {emails_count} ({metrics['email_rate']})")
    print(f"✅ Validated emails: {validated_count}")
    print(f"💾 Results saved to Modal volume")
    print("="*60)

    return metrics


# ===== API Endpoints =====

@web_app.get("/")
async def root():
    """API documentation"""
    return {
        "name": "Anti-Gravity Webhook API",
        "version": "1.0",
        "endpoints": {
            "/webhook/scrape-apify-leads": "POST - Trigger Apify lead scraping (async)",
            "/webhook/scrape-apify-leads-sync": "POST - Trigger Apify lead scraping (sync)",
            "/health": "GET - Health check"
        },
        "documentation": "/docs",
        "example": {
            "url": "POST /webhook/scrape-apify-leads",
            "headers": {
                "Content-Type": "application/json",
                "X-Webhook-Secret": "your-secret-key"
            },
            "body": {
                "industry": "Marketing Agency",
                "fetch_count": 30,
                "skip_test": True,
                "valid_only": True
            }
        }
    }


@web_app.get("/health")
async def health():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "anti-gravity-webhook",
        "timestamp": datetime.now().isoformat()
    }


@web_app.post("/webhook/scrape-apify-leads")
async def webhook_scrape_apify_leads(
    request: ApifyLeadRequest,
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Webhook endpoint to trigger Apify lead scraping (ASYNC)

    Returns immediately with job ID. Job runs in background.
    """
    import os

    # Verify webhook secret if configured
    webhook_secret = os.environ.get("WEBHOOK_SECRET")
    if webhook_secret and x_webhook_secret != webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid webhook secret")

    try:
        print(f"\n{'='*60}")
        print(f"📨 Webhook Request Received (ASYNC)")
        print(f"🎯 Industry: {request.industry}")
        print(f"📊 Fetch Count: {request.fetch_count}")
        print(f"🌍 Location: {request.location or 'Not specified'}")
        print(f"{'='*60}\n")

        # Trigger async scraping job
        call = scrape_apify_leads_modal.spawn(
            industry=request.industry,
            fetch_count=request.fetch_count,
            location=request.location,
            city=request.city,
            job_title=request.job_title,
            company_size=request.company_size,
            company_keywords=request.company_keywords,
            company_industry=request.company_industry,
            skip_test=request.skip_test,
            valid_only=request.valid_only,
            sender_context=request.sender_context
        )

        return {
            "status": "accepted",
            "message": "Lead scraping workflow triggered",
            "job_id": call.object_id,
            "industry": request.industry,
            "fetch_count": request.fetch_count,
            "note": "Job is running in background. Check Modal dashboard for results."
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@web_app.post("/webhook/scrape-apify-leads-sync")
async def webhook_scrape_apify_leads_sync(
    request: ApifyLeadRequest,
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Webhook endpoint to trigger Apify lead scraping (SYNC)

    ⚠️  Waits for completion before returning. May timeout for large scrapes.
    """
    import os

    webhook_secret = os.environ.get("WEBHOOK_SECRET")
    if webhook_secret and x_webhook_secret != webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        print(f"\n{'='*60}")
        print(f"📨 Webhook Request Received (SYNC)")
        print(f"🎯 Industry: {request.industry}")
        print(f"📊 Fetch Count: {request.fetch_count}")
        print(f"{'='*60}\n")

        # Call synchronously (blocks until complete)
        result = scrape_apify_leads_modal.remote(
            industry=request.industry,
            fetch_count=request.fetch_count,
            location=request.location,
            city=request.city,
            job_title=request.job_title,
            company_size=request.company_size,
            company_keywords=request.company_keywords,
            company_industry=request.company_industry,
            skip_test=request.skip_test,
            valid_only=request.valid_only,
            sender_context=request.sender_context
        )

        return {
            "status": "completed",
            "message": "Lead scraping workflow completed",
            "results": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Mount FastAPI App =====

@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    """Serve the FastAPI app on Modal"""
    return web_app