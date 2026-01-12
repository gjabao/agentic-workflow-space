---
description: Scrape B2B leads with Apify (test-first validation)
---

# Scrape Leads Workflow

This workflow scrapes B2B leads using Apify's leads-finder with automatic quality validation.

## How It Works

1. **Test run**: Scrapes 25 leads first
2. **Validation**: Checks if ≥80% match your target industry
3. **Full scrape**: Only proceeds if test passes
4. **Export**: Creates Google Sheet with results

## Quick Start

Tell the agent what you want to scrape:

```
"Scrape 100 dentists in California"
```

## Advanced Usage

Specify additional filters:

```
"Scrape 200 SaaS marketing managers in United States with company size 50-200 employees"
```

## Available Filters

- **Industry** (required): Target industry for validation
- **Location**: Region/Country/State (e.g., "United States", "California", "EMEA")
- **City**: Specific cities (e.g., "San Francisco", "New York")
- **Job Title**: Filter by role (e.g., "CEO", "Marketing Manager")
- **Company Size**: Employee ranges (e.g., "11-50", "51-200", "201-500")
- **Seniority Level**: C-Level, VP, Director, Manager, etc.
- **Company Revenue**: Min/max revenue filters

## What You'll Get

Google Sheet with:
- ✅ Person details (name, title, email, LinkedIn)
- ✅ Company info (name, industry, size, revenue, website)
- ✅ Validated emails prioritized
- ✅ Formatted and ready for outreach

## Examples

### Example 1: Dentists in California
```
Scrape 100 dentists in California
```

### Example 2: Tech Executives
```
Scrape 500 C-Level executives in SaaS companies in United States with revenue over $10M
```

### Example 3: Local Businesses
```
Scrape 50 restaurant owners in San Francisco
```

## Troubleshooting

**"Test validation failed"**
- Industry match rate was < 80%
- Agent will suggest filter improvements
- Adjust filters and retry

**"Error: APIFY_API_KEY missing"**
- Add your Apify API key to `.env` file:
  ```
  APIFY_API_KEY=apify_api_xxxxx
  ```
- Get key from: https://console.apify.com/account/integrations

## Cost

- $1.50 per 1,000 leads
- Free tier: 100 leads max per run
- Mobile numbers: Requires paid Apify plan
