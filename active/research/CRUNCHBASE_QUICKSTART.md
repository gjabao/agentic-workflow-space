# Crunchbase Scraper - Quick Start Guide

## What This Does
Scrapes company data from Crunchbase (startups, funding info, founders) and enriches with contact details via Apollo/AnyMailFinder.

**Output:** Google Sheet with 17 columns (company info + founder contacts)

---

## Setup (One-Time)

### 1. Install Dependencies
```bash
pip install apify-client requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Crunchbase Pro Account
- Subscribe at https://www.crunchbase.com/buy/select-product ($29/month minimum)
- Login to Crunchbase Pro

### 3. Export Cookies (CRITICAL)
1. Install Cookie-Editor extension:
   - **Chrome:** https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
   - **Firefox:** https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/
2. Login to Crunchbase Pro
3. Click Cookie-Editor icon → **Export** → Copy JSON
4. Cookies already added to `.env` ✅

### 4. Verify Setup
```bash
# Check .env has these keys
grep "CRUNCHBASE_COOKIES" .env   # Should show JSON array
grep "APIFY_API_KEY" .env         # Should show apify_api_xxx
```

---

## Usage

### Test Mode (ALWAYS START HERE)
```bash
python execution/scrape_crunchbase.py \
  --search-url "YOUR_CRUNCHBASE_SEARCH_URL" \
  --test
```

**What it does:**
- Scrapes 25 records only
- Validates quality (must be ≥80% valid companies)
- Shows cost estimate
- Safe to test without big charges

### Production Scrape (After Test Passes)
```bash
python execution/scrape_crunchbase.py \
  --search-url "YOUR_CRUNCHBASE_SEARCH_URL" \
  --limit 100
```

### No Enrichment (Crunchbase Data Only - Faster)
```bash
python execution/scrape_crunchbase.py \
  --search-url "YOUR_CRUNCHBASE_SEARCH_URL" \
  --limit 200 \
  --enrich=false
```

---

## How to Get Search URL

### Step 1: Go to Crunchbase Discover
https://www.crunchbase.com/discover/organization.companies

### Step 2: Apply Filters
- **Funding Stage:** Seed, Series A, Series B, etc.
- **Categories:** SaaS, AI, Marketing, etc.
- **Location:** United States, San Francisco, etc.
- **Employee Count:** 1-10, 11-50, etc.
- **Funding Date:** Last 6 months, Last year, etc.

### Step 3: Switch to Table Mode and Add Columns ⚠️ CRITICAL

**Why this matters:** The Apify scraper can ONLY extract fields that are visible in Crunchbase's table view. Without this step, you'll only get basic data (company name, categories, employee count) and miss all the valuable fields like website, funding, location, investors, etc.

**How to do it:**

1. **Switch to Table View**
   - After applying filters, click the **"Table"** icon (top right corner, looks like a grid)
   - You should see a table with rows instead of company cards

2. **Add Columns You Want to Scrape**
   - Click the **"Columns"** button (right side of the table)
   - Select ALL fields you need (checked boxes = will be scraped):
     - ✅ **Website** (REQUIRED for enrichment)
     - ✅ **Description** (company overview)
     - ✅ **Funding Total** (total funding raised)
     - ✅ **Funding Stage** (Seed, Series A, B, C, etc.)
     - ✅ **Last Funding Date** (when they last raised money)
     - ✅ **Last Funding Amount** (size of last round)
     - ✅ **Investors** (who funded them)
     - ✅ **Location** (HQ location)
     - ✅ **LinkedIn** (company LinkedIn URL)
     - ✅ **Twitter** (company Twitter handle)
     - ✅ **Number of Employees** (team size)
     - ✅ **Categories** (industry tags)

3. **Click "Apply"** to save your column selections

4. **Verify the columns are visible** in the table (you should see all selected fields as column headers)

**⚠️ WARNING:** If you skip this step:
- ❌ Website: Empty (can't enrich contacts without it)
- ❌ Funding data: Empty (no investment info)
- ❌ Description: Empty (no company context)
- ❌ Location: Empty (can't filter by geography)
- ❌ Investors: Empty (can't identify who's backing them)

### Step 4: Copy URL
After switching to table mode and adding columns, copy the **full URL** from address bar.

**Example URLs:**

**AI Companies (Series A+):**
```
https://www.crunchbase.com/discover/organization.companies?fundingStage=series_a,series_b&categories=artificial_intelligence,machine_learning&location=United%20States
```

**Recently Funded SaaS (Seed/Series A):**
```
https://www.crunchbase.com/discover/organization.companies?lastFundingDate=2024-01-01,2026-01-15&fundingStage=seed,series_a&categories=saas,software
```

**Marketing Tech (Bay Area):**
```
https://www.crunchbase.com/discover/organization.companies?categories=marketing,advertising&location=San%20Francisco%20Bay%20Area
```

---

## Expected Results

### Per 100 Companies Scraped:
| Metric | Expected Rate |
|--------|---------------|
| Valid Crunchbase data | 95-100% |
| Websites found | 90-95% |
| Founder emails | 50-70% |
| Founder names | 60-80% |
| LinkedIn profiles | 40-60% |
| **Usable leads** | **70-85%** |

### Cost Breakdown:
- **Apify scraping:** $0.50 per 100 companies
- **Enrichment:** $1-2 per 100 companies (Apollo + AnyMailFinder)
- **Total:** $1.50-$2.50 per 100 leads

### Processing Time:
- **Test (25 records):** ~2-3 minutes
- **Production (100 records):** ~10-15 minutes
- **Large (500 records):** ~45-60 minutes

---

## Output Columns (Google Sheet)

| Column | Source | Example |
|--------|--------|---------|
| Company Name | Crunchbase | "OpenAI" |
| Website | Crunchbase | "https://openai.com" |
| Description | Crunchbase | "AI research and deployment company" |
| Categories | Crunchbase | "Artificial Intelligence, Machine Learning" |
| Location | Crunchbase | "San Francisco, California" |
| Employee Count | Crunchbase | "251-500" |
| Funding Stage | Crunchbase | "Series C" |
| Total Funding | Crunchbase | "$1.3B" |
| Last Funding Date | Crunchbase | "2023-04-28" |
| Last Funding Amount | Crunchbase | "$300M" |
| Investors | Crunchbase | "Microsoft, Sequoia Capital" |
| **Founder Name** | **Apollo/Crunchbase** | **"Sam Altman"** |
| **Founder Email** | **AnyMailFinder** | **"sam@openai.com"** |
| **Founder LinkedIn** | **Apollo** | **"linkedin.com/in/sam-altman"** |
| **Founder Title** | **Apollo** | **"CEO & Co-Founder"** |
| Company LinkedIn | Crunchbase | "linkedin.com/company/openai" |
| Company Twitter | Crunchbase | "twitter.com/OpenAI" |

---

## Common Issues & Solutions

### ❌ "401 Unauthorized" or "Authentication failed"
**Cause:** Cookies expired (24-48 hour lifespan)

**Fix:**
1. Login to Crunchbase Pro
2. Cookie-Editor → Export → Copy JSON
3. Update `.env`: `CRUNCHBASE_COOKIES=<paste new JSON>`
4. Re-run script

---

### ❌ "No results found"
**Cause:** Search URL empty or filters too narrow

**Fix:**
- Check URL is complete (starts with `https://www.crunchbase.com/discover/...`)
- Try broader filters (remove location, increase funding stages)
- Test URL in browser first (should show results)

---

### ❌ "Quality too low (<80%)"
**Cause:** Search returning irrelevant companies

**Fix:**
- Make categories more specific (e.g., "SaaS" instead of "Software")
- Add funding stage filter (removes dead companies)
- Filter by location (focus on specific markets)

---

### ❌ "Cost estimate too high"
**Cause:** Scraping 500+ companies

**Fix:**
- Use `--test` flag first (25 records)
- Disable enrichment: `--enrich=false` (saves 60% cost)
- Split into multiple smaller runs (100 companies each)

---

### ❌ "Low email enrichment (<30%)"
**Cause:** Privacy-focused companies or small startups

**Fix:**
- Normal for early-stage startups (<10 employees)
- Focus on LinkedIn profiles instead (higher success rate)
- Try Apollo API for better B2B contact discovery (add `APOLLO_API_KEY` to `.env`)

---

## Advanced: Apollo Integration (Optional)

**Why:** Higher contact discovery rate (70-80% vs 50-60% with AnyMailFinder only)

### Setup:
1. Get Apollo API key: https://app.apollo.io/#/settings/integrations/api
2. Add to `.env`:
   ```
   APOLLO_API_KEY=your_key_here
   ```
3. Script auto-detects and uses Apollo for founder search

**Cost:** Varies by Apollo plan (typically $0.01-0.02 per contact lookup)

---

## File Locations

| File | Purpose |
|------|---------|
| [directives/scrape_crunchbase_leads.md](directives/scrape_crunchbase_leads.md) | SOP (Standard Operating Procedure) |
| [execution/scrape_crunchbase.py](execution/scrape_crunchbase.py) | Python execution script |
| `.env` | API keys & cookies (line 64) |
| `CRUNCHBASE_QUICKSTART.md` | This guide |

---

## Workflow Summary

```
1. Get Crunchbase search URL (apply filters in browser)
   ↓
2. Run test mode (25 records)
   python execution/scrape_crunchbase.py --search-url "..." --test
   ↓
3. Validate quality (must be ≥80%)
   ↓
4. Run full scrape (100-500 records)
   python execution/scrape_crunchbase.py --search-url "..." --limit 100
   ↓
5. Get Google Sheet link
   ↓
6. Review data, export CSV if needed
```

---

## Tips for Best Results

### ✅ DO:
- **Always test first** (--test flag)
- **Keep cookies fresh** (re-export every 1-2 days if scraping frequently)
- **Use specific filters** (categories, funding stage, location)
- **Start small** (100 companies), scale up after validation
- **Monitor cost estimates** (confirm if >$5)

### ❌ DON'T:
- **Skip test mode** (waste money on bad searches)
- **Use expired cookies** (will fail immediately)
- **Scrape 1000+ records** without testing first
- **Ignore quality warnings** (garbage in = garbage out)
- **Forget to update directives** when you learn new patterns

---

## Self-Annealing Reminders

When errors occur:
1. ✅ Fix the script (add error handling, retry logic)
2. ✅ Update directive with learnings (edge cases, API limits)
3. ✅ Add to changelog at bottom of directive
4. ✅ Test to verify fix works

**Goal:** Each error makes the system STRONGER (never fails same way twice)

---

## Next Steps

1. **Test the scraper** with a small Crunchbase search (25 records)
2. **Validate output quality** (check Google Sheet)
3. **Scale up** once confident (100-500 records)
4. **Add Apollo API key** for better contact enrichment (optional)
5. **Update directive** with any learnings or edge cases you discover

---

## Support

**Questions about:**
- **Crunchbase filters:** See directive → "Search URL Examples"
- **Cookie refresh:** See directive → "Cookie Setup (CRITICAL)"
- **Cost estimates:** See directive → "Cost Breakdown"
- **Quality issues:** See directive → "Quality Thresholds"

**Full documentation:** [directives/scrape_crunchbase_leads.md](directives/scrape_crunchbase_leads.md)

---

**Ready to scrape? Start with test mode!**
```bash
python execution/scrape_crunchbase.py --search-url "YOUR_URL" --test
```
