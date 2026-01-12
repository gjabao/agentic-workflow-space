#!/usr/bin/env python3
"""
Python Script Example - Trigger Modal from Python

This shows how to trigger Modal workflows from a regular Python script
(not running inside Modal)
"""

import requests


def trigger_via_api(endpoint: str, data: dict):
    """
    Trigger Modal workflow via API endpoint

    First deploy: python3 -m modal deploy modal_workflows/api_endpoint_example.py
    Then get URL from Modal dashboard
    """
    url = f"https://your-app.modal.run/{endpoint}"

    response = requests.post(url, json=data, timeout=30)

    if response.status_code == 200:
        print(f"✅ Success: {response.json()}")
        return response.json()
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None


def trigger_via_modal_client():
    """
    Trigger Modal workflow using Modal Python client

    This requires Modal to be installed and authenticated locally
    """
    import modal

    # Look up the deployed app
    app = modal.App.lookup("anti-gravity-workflows")

    # Call a specific function
    scrape_leads = app.function_lookup("scrape_leads")

    # Run it
    result = scrape_leads.remote(query="dentists in New York", limit=100)
    print(f"✅ Result: {result}")

    return result


# ===== Examples =====

def example_1_scrape_leads():
    """Example: Scrape leads via API"""
    print("Example 1: Scrape leads")
    print("-" * 50)

    data = {
        "query": "dentists in New York",
        "limit": 100
    }

    result = trigger_via_api("scrape", data)
    return result


def example_2_generate_copy():
    """Example: Generate copy via API"""
    print("\nExample 2: Generate copy")
    print("-" * 50)

    data = {
        "company_name": "ABC Dental",
        "industry": "dental",
        "location": "New York"
    }

    result = trigger_via_api("generate-copy", data)
    return result


def example_3_batch_processing():
    """Example: Process multiple companies"""
    print("\nExample 3: Batch processing")
    print("-" * 50)

    companies = [
        {"company_name": "ABC Dental", "industry": "dental"},
        {"company_name": "XYZ Realty", "industry": "real estate"},
        {"company_name": "123 Law Firm", "industry": "legal"}
    ]

    results = []
    for company in companies:
        result = trigger_via_api("generate-copy", company)
        results.append(result)

    print(f"\n✅ Processed {len(results)} companies")
    return results


if __name__ == "__main__":
    print("🚀 Modal Workflow Trigger Examples")
    print("=" * 50)

    # Uncomment to run examples:

    # example_1_scrape_leads()
    # example_2_generate_copy()
    # example_3_batch_processing()

    print("\n💡 To use these examples:")
    print("1. Deploy API: python3 -m modal deploy modal_workflows/api_endpoint_example.py")
    print("2. Get URL from Modal dashboard")
    print("3. Update 'your-app.modal.run' in this script")
    print("4. Run: python3 modal_workflows/python_trigger_example.py")
