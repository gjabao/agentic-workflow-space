"""
On-Demand Copy Generator
Generate personalized email copy for any company

Usage:
    python3 -m modal run modal_workflows/generate_copy_on_demand.py \
        --company-name "ABC Dental" \
        --industry "dental" \
        --location "New York"
"""

import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=300
)
def generate_copy(
    company_name: str,
    industry: str = "general",
    location: str = "USA",
    tone: str = "professional"
):
    """
    Generate personalized cold email copy

    Args:
        company_name: Name of the target company
        industry: Industry (e.g., "dental", "real estate")
        location: Location (e.g., "New York", "California")
        tone: Tone of voice (e.g., "professional", "casual", "friendly")
    """
    import os
    import requests
    from datetime import datetime

    print(f"✍️  Generating copy for: {company_name}")
    print(f"   Industry: {industry}")
    print(f"   Location: {location}")
    print(f"   Tone: {tone}")
    print()

    # Use Azure OpenAI (you already have the key)
    api_key = os.environ["AZURE_OPENAI_API_KEY"]

    prompt = f"""
    Generate a personalized cold email for:
    Company: {company_name}
    Industry: {industry}
    Location: {location}
    Tone: {tone}

    Make it compelling, specific to their industry, and include a clear CTA.
    Keep it under 150 words.
    """

    # Example using Azure OpenAI
    # Replace with your actual endpoint
    print("🤖 Generating with AI...")

    # Placeholder - replace with actual API call
    generated_copy = f"""
Subject: Quick win for {company_name}

Hi [First Name],

I noticed {company_name} is doing great work in the {industry} space in {location}.

I wanted to reach out because we've helped similar companies in {industry} increase their lead flow by 40% in just 90 days.

Would you be open to a quick 15-minute call to see if we could do the same for you?

Best regards,
[Your Name]
    """.strip()

    print("\n" + "="*50)
    print("✅ Generated Copy:")
    print("="*50)
    print(generated_copy)
    print("="*50)

    return {
        "company_name": company_name,
        "industry": industry,
        "location": location,
        "copy": generated_copy,
        "generated_at": datetime.now().isoformat()
    }


@app.local_entrypoint()
def main(
    company_name: str,
    industry: str = "general",
    location: str = "USA",
    tone: str = "professional"
):
    """
    CLI entry point

    Examples:
        python3 -m modal run modal_workflows/generate_copy_on_demand.py \
            --company-name "ABC Dental"

        python3 -m modal run modal_workflows/generate_copy_on_demand.py \
            --company-name "XYZ Realty" \
            --industry "real estate" \
            --location "California" \
            --tone "casual"
    """
    result = generate_copy.remote(company_name, industry, location, tone)

    # Save to file (optional)
    filename = f".tmp/copy_{company_name.replace(' ', '_').lower()}.txt"
    import os
    os.makedirs('.tmp', exist_ok=True)
    with open(filename, 'w') as f:
        f.write(result['copy'])

    print(f"\n💾 Saved to: {filename}")
