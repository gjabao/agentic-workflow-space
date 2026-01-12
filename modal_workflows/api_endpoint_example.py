"""
API Endpoint Example - Trigger via HTTP
Deploy this to get a web URL you can call from anywhere

Deploy:
    python3 -m modal deploy modal_workflows/api_endpoint_example.py

Then call via:
    curl https://your-app.modal.run/scrape?query=dentists&limit=100

Or from browser:
    https://your-app.modal.run/scrape?query=dentists&limit=100
"""

import modal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = modal.App("anti-gravity-api")
web_app = FastAPI()


# ===== Data Models =====

class ScrapeRequest(BaseModel):
    query: str
    limit: int = 100


class CopyRequest(BaseModel):
    company_name: str
    industry: str = "general"
    location: str = "USA"


# ===== Core Functions =====

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=1800
)
def scrape_leads_internal(query: str, limit: int):
    """Internal function to scrape leads"""
    import os
    print(f"🔍 Scraping: {query} (limit: {limit})")

    # Your scraping logic here
    # Example placeholder:
    return {
        "status": "success",
        "query": query,
        "limit": limit,
        "leads_found": 42  # Placeholder
    }


@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=300
)
def generate_copy_internal(company_name: str, industry: str, location: str):
    """Internal function to generate copy"""
    print(f"✍️  Generating copy for: {company_name}")

    # Your copy generation logic here
    return {
        "company_name": company_name,
        "copy": f"Personalized email for {company_name} in {industry}..."
    }


# ===== API Endpoints =====

@web_app.get("/")
async def root():
    """API documentation"""
    return {
        "name": "Anti-Gravity API",
        "version": "1.0",
        "endpoints": {
            "/scrape": "POST - Scrape leads (query, limit)",
            "/generate-copy": "POST - Generate email copy (company_name, industry, location)",
            "/health": "GET - Health check"
        },
        "examples": {
            "scrape": "curl -X POST https://your-app.modal.run/scrape -H 'Content-Type: application/json' -d '{\"query\": \"dentists\", \"limit\": 100}'",
            "copy": "curl -X POST https://your-app.modal.run/generate-copy -H 'Content-Type: application/json' -d '{\"company_name\": \"ABC Corp\", \"industry\": \"dental\"}'"
        }
    }


@web_app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@web_app.post("/scrape")
async def scrape_endpoint(request: ScrapeRequest):
    """
    Scrape leads via API

    Example:
        curl -X POST https://your-app.modal.run/scrape \
            -H 'Content-Type: application/json' \
            -d '{"query": "dentists in New York", "limit": 100}'
    """
    try:
        # Call the Modal function
        result = scrape_leads_internal.remote(request.query, request.limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@web_app.post("/generate-copy")
async def generate_copy_endpoint(request: CopyRequest):
    """
    Generate email copy via API

    Example:
        curl -X POST https://your-app.modal.run/generate-copy \
            -H 'Content-Type: application/json' \
            -d '{"company_name": "ABC Dental", "industry": "dental", "location": "New York"}'
    """
    try:
        result = generate_copy_internal.remote(
            request.company_name,
            request.industry,
            request.location
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@web_app.get("/scrape-simple")
async def scrape_simple(query: str, limit: int = 100):
    """
    Simple GET endpoint for scraping

    Example:
        https://your-app.modal.run/scrape-simple?query=dentists&limit=100
    """
    try:
        result = scrape_leads_internal.remote(query, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Mount FastAPI App =====

@app.function()
@modal.asgi_app()
def fastapi_app():
    """Serve the FastAPI app"""
    return web_app
