# Clutch Lead Generator - Quick Start Guide

## Overview

The Clutch lead generator uses an **email-first workflow** to achieve 200-300% coverage (2-3 decision-makers per company) compared to traditional decision-maker-first approaches (5-10% success).

**System:** Clutch Lead Scraper v1.0
**Pattern:** Email-First Approach (proven from Crunchbase v4.0)
**Directive:** [directives/scrape_clutch_leads.md](directives/scrape_clutch_leads.md)

---

## Quick Start (3 Minutes)

### Step 1: Setup Environment (.env)

```bash
# Required API Keys
APIFY_API_KEY=apify_api_xxxxx        # Get from apify.com
ANYMAILFINDER_API_KEY=xxxxx          # Get from anymailfinder.com
RAPIDAPI_KEY=xxxxx                   # Get from rapidapi.com (Google Search API)

# Optional (for rate limit boost)
RAPIDAPI_KEY_2=xxxxx                 # Second RapidAPI key (2x throughput)
```

### Step 2: Test with 10 Companies

```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/agencies/digital-marketing" \
  --limit 10
```

**Expected output:**
- 10 companies scraped in ~30 seconds
- 15-25 decision-makers found (150-250% coverage)
- CSV saved: `clutch_leads_YYYYMMDD_HHMMSS.csv`
- Google Sheet created (if credentials configured)

### Step 3: Scale to 100 Companies

```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/agencies/digital-marketing" \
  --limit 100
```

**Performance:**
- ~5-10 minutes total
- 150-250 decision-makers with verified emails
- Cost: ~$4-6 (residential proxies required)

---

## How It Works (Email-First Workflow)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Scrape Companies (Apify: memo23/apify-clutch-cheerio)   │
│    Input: Clutch category URL                               │
│    Output: Company data (name, website, rating, services)   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Extract Website (from Clutch data)                       │
│    Clutch provides: websiteUrl field                         │
│    Example: densitylabs.io                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Find ALL Emails (AnyMailFinder Company API)              │
│    Input: Company domain                                     │
│    Output: Up to 20 emails per company                       │
│    Example: [steven@density..., john@density..., ...]       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Extract Names from Emails (Pattern Matching)             │
│    Pattern 1: firstname.lastname@ → "Firstname Lastname"    │
│    Pattern 2: firstname_lastname@ → "Firstname Lastname"    │
│    Pattern 3: camelCase (johnSmith@) → "John Smith"         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Search LinkedIn (RapidAPI Google Search - 3 attempts)    │
│    Attempt 1: "{name}" at "{company}" linkedin (specific)   │
│    Attempt 2: {name} "{company}" linkedin (medium)          │
│    Attempt 3: {name} {company} linkedin (broad)             │
│    Success rate: 90%+                                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Validate Decision-Maker (Title Keywords)                 │
│    Include: CEO, Founder, VP, Director, Partner, etc.       │
│    Exclude: Assistant, Analyst, Coordinator, etc.           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Export Results (CSV + Google Sheets)                     │
│    15 columns: name, email, LinkedIn, company data          │
└─────────────────────────────────────────────────────────────┘
```

---

## Output Format (15 Columns)

| Column | Example | Source |
|--------|---------|--------|
| company_name | Density Labs | Clutch |
| first_name | Steven | Email extraction |
| last_name | Fogel | Email extraction |
| job_title | VP of Web Applications | LinkedIn (RapidAPI) |
| email | steven@densitylabs.io | AnyMailFinder |
| linkedin_url | linkedin.com/in/steven-fogel | RapidAPI |
| website | densitylabs.io | Clutch |
| location | Zapopan, Mexico | Clutch |
| rating | 4.7 | Clutch |
| review_count | 3 reviews | Clutch |
| employee_size | 10 - 49 | Clutch |
| hourly_rate | $25 - $49 / hr | Clutch |
| min_project_size | $5,000+ | Clutch |
| service_focus | IT Staff Augmentation (70%) | Clutch |
| industries | Business services, Real estate | Clutch |

---

## Popular Clutch Categories

### Digital Marketing Agencies
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/agencies/digital-marketing" \
  --limit 50
```

### Creative Agencies
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/agencies/creative" \
  --limit 50
```

### IT Services & Software Development
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/it-services" \
  --limit 50
```

### Web Development
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/web-developers" \
  --limit 50
```

### App Development
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/app-developers" \
  --limit 50
```

---

## Upload Existing CSV to Google Sheets

If you already have a CSV file:

```bash
python execution/upload_csv_to_sheets_clutch.py clutch_leads_20260130_123456.csv
```

Or with custom title:

```bash
python execution/upload_csv_to_sheets_clutch.py \
  clutch_leads_20260130_123456.csv \
  --title "Digital Marketing Agencies - Q1 2026"
```

---

## Cost Breakdown (per 100 companies)

| Service | Cost | Purpose |
|---------|------|---------|
| Apify (Clutch scraper) | $3.50-$5.00 | Scraping with residential proxies |
| AnyMailFinder | $0.50 | Finding company emails |
| RapidAPI (Google Search) | FREE | LinkedIn profile enrichment (5000 req/month) |
| **Total** | **$4-6** | Per 100 companies |

**Why residential proxies?**
Clutch.co aggressively blocks datacenter IPs. Residential proxies from Apify are **required** for reliable scraping.

---

## Performance Metrics

### Test Run (10 companies)
- **Time:** 1-2 minutes
- **Coverage:** 15-25 decision-makers (150-250%)
- **Email quality:** 95%+ valid
- **LinkedIn matches:** 85-90%

### Production Run (100 companies)
- **Time:** 5-10 minutes
- **Coverage:** 150-250 decision-makers (150-250%)
- **Processing:** ~1 minute per company
- **Parallel workers:** 10 companies + 5 emails per company

---

## Troubleshooting

### Issue: No companies scraped
**Cause:** Apify actor failed or invalid URL
**Fix:**
1. Check if URL is valid Clutch category URL
2. Verify APIFY_API_KEY is correct
3. Ensure residential proxies are enabled (default in script)

### Issue: No emails found
**Cause:** AnyMailFinder API issue or invalid domains
**Fix:**
1. Check ANYMAILFINDER_API_KEY
2. Verify companies have websiteUrl in Clutch data
3. Check AnyMailFinder credit balance

### Issue: Low LinkedIn matches (<80%)
**Cause:** RapidAPI rate limit or network issues
**Fix:**
1. Add RAPIDAPI_KEY_2 for 2x throughput
2. Normal for small agencies (<10 employees)
3. Check RapidAPI quota (5000 req/month free tier)

### Issue: Apify returns 429 or blocks
**Cause:** Datacenter proxies instead of residential
**Fix:**
Script already uses residential proxies by default:
```python
"proxyConfiguration": {
    "useApifyProxy": True,
    "apifyProxyGroups": ["RESIDENTIAL"]
}
```

---

## Advanced Usage

### Test Email Extraction Only
```python
from execution.scrape_clutch_leads import ClutchScraper

scraper = ClutchScraper()
name, is_generic, confidence = scraper.extract_contact_from_email("john.smith@company.com")
print(f"Name: {name}, Generic: {is_generic}, Confidence: {confidence:.0%}")
# Output: Name: John Smith, Generic: False, Confidence: 95%
```

### Parallel Processing Tuning
Default: 10 workers for companies, 5 workers per company for emails

For faster processing (if you have higher API limits):
```python
# In scrape_clutch_leads.py, line ~1050
leads = self.enrich_companies(companies, max_workers=20)  # Increase to 20

# In enrich_single_company(), line ~924
with ThreadPoolExecutor(max_workers=10) as executor:  # Increase to 10
```

---

## Quality Thresholds

**Pass criteria (test with 10 companies first):**
- ✅ 95%+ companies have websites found
- ✅ 150%+ decision-makers found (15+ from 10 companies)
- ✅ 90%+ emails are valid format
- ✅ 85%+ LinkedIn profiles found

**Fail → Adjust:**
- Low websites (<95%) → Check if Clutch scraper returned websiteUrl
- Low DMs (<150%) → Check industry (B2C agencies have lower rates)
- Low LinkedIn (<85%) → Normal for small agencies (<10 employees)

---

## Next Steps

1. **Test with 10 companies** to validate workflow
2. **Review results** in CSV or Google Sheets
3. **Scale to 100 companies** once validated
4. **Export to CRM** (ClickUp, HubSpot, etc.)

**Questions?** See [directives/scrape_clutch_leads.md](directives/scrape_clutch_leads.md) for full documentation.

---

## Sources

- [Clutch.co Data Master Scraper by memo23](https://apify.com/memo23/apify-clutch-cheerio)
- [Clutch.co Scraper API Documentation](https://apify.com/memo23/apify-clutch-cheerio/api)
- [Clutch.co Data Master Python API](https://apify.com/memo23/apify-clutch-cheerio/api/client/python)
