#!/usr/bin/env python3
"""
Research Typeform Leads & Generate Apollo URLs

Analyzes client profile data from Typeform submissions, extracts ICP details,
and generates Apollo.io search URLs for multiple target audiences.

Usage:
    python3 execution/research_typeform_lead.py --profile_text "Client profile..."
    python3 execution/research_typeform_lead.py --profile_file profile.md
    python3 execution/research_typeform_lead.py --profile_file profile.md --output_format json
"""

import os
import sys
import json
import argparse
import time
from urllib.parse import urlencode, quote
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from utils_notifications import notify_success, notify_error

# Load environment variables
load_dotenv()

# Azure OpenAI setup
try:
    from openai import AzureOpenAI

    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    if not AZURE_OPENAI_KEY or not AZURE_OPENAI_ENDPOINT:
        print("⚠️ Warning: Azure OpenAI credentials not found in .env")
        print("Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT to use this tool")
        sys.exit(1)

    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version="2024-08-01-preview",
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
except ImportError:
    print("❌ Error: openai package not installed")
    print("Install: pip install openai")
    sys.exit(1)

# Apollo company size ranges mapping
COMPANY_SIZE_RANGES = {
    "1-10": "1,10",
    "11-50": "11,50",
    "51-100": "51,100",
    "101-500": "101,500",
    "501-1000": "501,1000",
    "1001-5000": "1001,5000",
    "5001-10000": "5001,10000",
    "10001+": "10001,99999"
}

# Location normalization
LOCATION_MAPPING = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "uae": "United Arab Emirates"
}


def normalize_location(location: str) -> str:
    """Normalize location names for Apollo."""
    location_lower = location.lower().strip()
    return LOCATION_MAPPING.get(location_lower, location.title())


def extract_icp_from_profile(profile_text: str, max_audiences: int = 3) -> Dict[str, Any]:
    """
    Use Azure OpenAI to extract structured ICP data from unstructured profile text.

    Returns:
        Dict with company info, target audiences, job titles, company criteria, etc.
    """
    extraction_prompt = f"""You are an expert B2B sales researcher specializing in Apollo.io search optimization. Analyze the following client profile and extract structured ICP (Ideal Customer Profile) data.

Extract the following information in JSON format:

1. **company_info**: {{
    "name": "Company name",
    "website": "Company website URL",
    "business_model": "What they do (1-2 sentences)",
    "deal_size": "Average deal size or range",
    "location": "Primary location (country/region)",
    "company_size": "Employee count or range"
}}

2. **target_audiences**: [
    {{
        "audience_name": "E.g., Direct End Users, Conference Organizers, etc.",
        "description": "Who they are (1 sentence)",
        "job_titles": ["Title 1", "Title 2", "Title 3", ...],  // 3-8 titles max, use EXACT job titles that exist in Apollo
        "company_criteria": {{
            "size_ranges": ["101-500", "501-1000"],  // Use ranges: 1-10, 11-50, 51-100, 101-500, 501-1000, 1001-5000, 5001-10000, 10001+
            "industries": ["keyword 1", "keyword 2"],  // 3-8 SPECIFIC Apollo keywords (see instructions below)
            "locations": ["United States", "Canada"]  // Full country names
        }},
        "pain_points": ["Pain 1", "Pain 2", ...]
    }},
    // Max {max_audiences} audiences
]

3. **messaging_framework**: {{
    "core_positioning": "One-sentence positioning statement",
    "value_propositions": ["Value prop 1", "Value prop 2", ...]
}}

**CRITICAL INSTRUCTIONS FOR APOLLO KEYWORD OPTIMIZATION:**

1. **Job Titles - Be PRECISE:**
   - Use exact titles that appear in Apollo (e.g., "VP of Marketing" not "Marketing VP")
   - Include seniority variations: "Manager", "Senior Manager", "Director", "VP", "Head of"
   - Include both formal and informal versions: "Chief Marketing Officer" AND "CMO"
   - For trade shows: "Trade Show Manager", "Event Manager", "Tradeshow Coordinator", "Exhibits Manager", "Event Marketing Manager"

2. **Industry Keywords - Be SPECIFIC & BEHAVIORAL:**
   - ❌ AVOID generic industries: "Technology", "Healthcare", "Finance" (too broad, millions of results)
   - ✅ USE behavioral signals: "trade show exhibitor", "event marketing", "conference sponsor"
   - ✅ USE niche descriptors: "SaaS", "B2B software", "medical devices", "fintech"
   - ✅ USE activity-based keywords: "attends trade shows", "hosts conferences", "sponsors events"

3. **For Trade Show/Event Businesses:**
   - Keywords should signal: "exhibits at trade shows", "trade show marketing", "event exhibitor", "conference exhibitor"
   - Target companies WITH trade show budgets: "enterprise sales", "B2B marketing", "field marketing"
   - Industry-specific events: "tech conferences", "healthcare conferences", "financial services events"

4. **Keyword Quantity:**
   - Use 3-8 keywords per audience (not just 2-5)
   - Mix behavioral + industry + company type keywords
   - Example: ["trade show marketing", "B2B SaaS", "enterprise software", "attends conferences", "field marketing"]

5. **Company Size Logic:**
   - Fortune 500 = 1001-5000, 5001-10000, 10001+
   - Mid-market = 101-500, 501-1000
   - SMB = 11-50, 51-100

**EXAMPLE FOR TRADE SHOW CLIENTS:**

Instead of:
  "industries": ["Technology", "Healthcare", "Finance"]

Use:
  "industries": ["trade show exhibitor", "B2B SaaS", "enterprise software", "field marketing", "event marketing", "tech conferences", "healthcare conferences"]

Return ONLY valid JSON, no markdown formatting.

---

CLIENT PROFILE:
{profile_text}
"""

    try:
        print("⏳ Analyzing profile with Azure OpenAI...")
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a B2B sales research expert. Extract structured ICP data from client profiles. Return only valid JSON."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0.3,  # High precision for data extraction
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]

        result_text = result_text.strip()

        icp_data = json.loads(result_text)
        print("✓ ICP extraction complete")
        return icp_data

    except json.JSONDecodeError as e:
        print(f"❌ Error: Failed to parse AI response as JSON: {e}")
        print(f"Raw response: {result_text[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during ICP extraction: {e}")
        sys.exit(1)


def generate_apollo_url(
    job_titles: List[str],
    locations: List[str],
    company_sizes: List[str],
    industry_keywords: List[str]
) -> str:
    """
    Generate Apollo.io search URL with proper encoding.

    Args:
        job_titles: List of job titles (e.g., ["CEO", "Founder"])
        locations: List of locations (e.g., ["United States", "Canada"])
        company_sizes: List of size ranges (e.g., ["101-500", "501-1000"])
        industry_keywords: List of industry keywords (e.g., ["marketing", "agency"])

    Returns:
        Fully encoded Apollo URL
    """
    base_url = "https://app.apollo.io/#/people?page=1"

    # Build query parameters
    params = []

    # Email verification (always verified)
    params.append("contactEmailStatusV2[]=verified")

    # Job titles (increased limit for better targeting)
    for title in job_titles[:8]:  # Limit to 8 titles
        params.append(f"personTitles[]={quote(title)}")

    # Locations
    for location in locations:
        normalized = normalize_location(location)
        params.append(f"personLocations[]={quote(normalized)}")

    # Company sizes
    for size_range in company_sizes:
        if size_range in COMPANY_SIZE_RANGES:
            params.append(f"organizationNumEmployeesRanges[]={COMPANY_SIZE_RANGES[size_range]}")

    # Industry keywords (increased limit for behavioral + industry mix)
    for keyword in industry_keywords[:8]:  # Limit to 8 keywords
        params.append(f"qOrganizationKeywordTags[]={quote(keyword)}")

    # Sorting
    params.append("sortByField=recommendations_score")
    params.append("sortAscending=false")

    # Combine all params
    full_url = base_url + "&" + "&".join(params)

    return full_url


def format_markdown_output(icp_data: Dict[str, Any]) -> str:
    """Format ICP data as markdown report with Apollo URLs."""
    company = icp_data.get("company_info", {})
    audiences = icp_data.get("target_audiences", [])
    messaging = icp_data.get("messaging_framework", {})

    output = f"""# {company.get('name', 'Unknown Company')} - ICP Research

## 📋 Company Overview

- **Company:** {company.get('name', 'Unknown')}
- **Website:** {company.get('website', 'Unknown')}
- **Business Model:** {company.get('business_model', 'Unknown')}
- **Average Deal Size:** {company.get('deal_size', 'Unknown')}
- **Location:** {company.get('location', 'Unknown')}
- **Company Size:** {company.get('company_size', 'Unknown')}

---

"""

    # Target audiences
    for i, audience in enumerate(audiences, 1):
        audience_name = audience.get('audience_name', f'Audience {i}')
        description = audience.get('description', 'No description')
        job_titles = audience.get('job_titles', [])
        criteria = audience.get('company_criteria', {})
        pain_points = audience.get('pain_points', [])

        # Generate Apollo URL
        apollo_url = generate_apollo_url(
            job_titles=job_titles,
            locations=criteria.get('locations', []),
            company_sizes=criteria.get('size_ranges', []),
            industry_keywords=criteria.get('industries', [])
        )

        output += f"""## 🎯 Target Audience #{i}: {audience_name}

**Description:** {description}

**Job Titles:**
"""
        for title in job_titles:
            output += f"- {title}\n"

        output += f"""
**Company Criteria:**
- **Size:** {', '.join(criteria.get('size_ranges', ['Any']))}
- **Industries:** {', '.join(criteria.get('industries', ['Any']))}
- **Locations:** {', '.join(criteria.get('locations', ['Any']))}

**Pain Points:**
"""
        for pain in pain_points:
            output += f"- {pain}\n"

        output += f"""
**Apollo Search URL:**
{apollo_url}

---

"""

    # Messaging framework
    output += f"""## 💬 Messaging Framework

**Core Positioning:**
{messaging.get('core_positioning', 'Not provided')}

**Value Propositions:**
"""
    for vp in messaging.get('value_propositions', []):
        output += f"- {vp}\n"

    return output


def format_json_output(icp_data: Dict[str, Any]) -> str:
    """Format ICP data as JSON with Apollo URLs."""
    audiences = icp_data.get("target_audiences", [])

    # Add Apollo URLs to each audience
    for audience in audiences:
        criteria = audience.get('company_criteria', {})
        apollo_url = generate_apollo_url(
            job_titles=audience.get('job_titles', []),
            locations=criteria.get('locations', []),
            company_sizes=criteria.get('size_ranges', []),
            industry_keywords=criteria.get('industries', [])
        )
        audience['apollo_url'] = apollo_url

    return json.dumps(icp_data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Research Typeform leads and generate Apollo URLs"
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--profile_text",
        type=str,
        help="Client profile as text string"
    )
    input_group.add_argument(
        "--profile_file",
        type=str,
        help="Path to client profile file (markdown or text)"
    )

    # Output options
    parser.add_argument(
        "--output_format",
        type=str,
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--max_audiences",
        type=int,
        default=3,
        help="Maximum number of target audiences to generate (default: 3)"
    )
    parser.add_argument(
        "--output_file",
        type=str,
        help="Save output to file (optional)"
    )

    args = parser.parse_args()

    # Get profile text
    if args.profile_file:
        if not os.path.exists(args.profile_file):
            print(f"❌ Error: File not found: {args.profile_file}")
            sys.exit(1)

        with open(args.profile_file, 'r', encoding='utf-8') as f:
            profile_text = f.read()
        print(f"✓ Loaded profile from {args.profile_file}")
    else:
        profile_text = args.profile_text

    # Validate profile has minimum content
    if len(profile_text.strip()) < 100:
        print("❌ Error: Profile text too short (minimum 100 characters)")
        print("Include at least: company name, business model, target audience hints")
        sys.exit(1)

    # Extract ICP data
    start_time = time.time()
    icp_data = extract_icp_from_profile(profile_text, max_audiences=args.max_audiences)

    # Validate extraction
    if not icp_data.get("target_audiences"):
        print("❌ Error: No target audiences extracted from profile")
        print("Make sure profile includes information about who the company sells to")
        sys.exit(1)

    num_audiences = len(icp_data["target_audiences"])
    print(f"✓ Extracted {num_audiences} target audience(s)")

    # Format output
    if args.output_format == "markdown":
        output = format_markdown_output(icp_data)
    else:
        output = format_json_output(icp_data)

    # Print or save output
    if args.output_file:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✓ Saved output to {args.output_file}")
    else:
        print("\n" + "="*80 + "\n")
        print(output)

    duration = time.time() - start_time
    print(f"\n⏱️ Duration: {duration:.1f}s")
    print(f"✓ Research complete! Generated {num_audiences} Apollo URL(s)")
    notify_success()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        notify_error()
        sys.exit(1)
