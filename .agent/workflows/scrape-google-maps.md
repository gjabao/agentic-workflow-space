---
description: Scrape Google Maps leads and enrich with emails
---

# Google Maps Lead Scraper Workflow

This workflow scrapes leads from Google Maps using Apify, enriches emails with AnyMailFinder, and exports to Google Sheets.

## Prerequisites

1. **API Keys** (in `.env`):
   - `APIFY_API_KEY` - Your Apify API token
   - `ANYMAILFINDER_API_KEY` - Your AnyMailFinder API key

2. **Google Sheets** (optional):
   - `credentials.json` - OAuth credentials from Google Cloud Console
   - `token.json` - Will be created automatically on first run

3. **Python Dependencies**:
   ```bash
   pip install apify-client python-dotenv google-auth-oauthlib google-api-python-client
   ```

## Usage

### Basic Usage (Scrape 100 leads)

// turbo
```bash
cd /Users/nguyengiabao/Downloads/Claude\ skill/Anti-Gravity\ Workspace
python execution/scrape_google_maps.py
```

### Custom Search Query

Edit `execution/scrape_google_maps.py` and modify the `main()` function:

```python
result = scraper.execute(
    search_query="YOUR_SEARCH_QUERY",
    max_results=100,
    location="YOUR_LOCATION"
)
```

Then run:

// turbo
```bash
cd /Users/nguyengiabao/Downloads/Claude\ skill/Anti-Gravity\ Workspace
python execution/scrape_google_maps.py
```

### Python API Usage

```python
from execution.scrape_google_maps import GoogleMapsLeadScraper

scraper = GoogleMapsLeadScraper()

result = scraper.execute(
    search_query="recruitment agency London UK",
    max_results=100,
    location="London, UK",
    skip_email_enrichment=False  # Set to True to skip email enrichment
)

if result['success']:
    print(f"Scraped {result['metrics']['total_leads']} leads")
    print(f"Google Sheet: {result['sheet_url']}")
```

## Workflow Phases

1. **Scrape Google Maps** - Uses Apify to scrape business data
2. **Clean Data** - Removes duplicates, formats fields, validates quality
3. **Enrich Emails** - Uses AnyMailFinder to find contact emails
4. **Export to Google Sheets** - Creates formatted spreadsheet with results

## Output

- **JSON Files**: Saved to `.tmp/scraped_data/`
  - `raw_google_maps_YYYYMMDD_HHMMSS.json` - Raw scraped data
  - `enriched_google_maps_YYYYMMDD_HHMMSS.json` - Cleaned & enriched data
  
- **Google Sheet**: Created automatically with formatted data

- **Logs**: `.tmp/google_maps_scraper.log`

## Quality Thresholds

- ✅ Minimum 80% valid data (name + website)
- ✅ Email enrichment rate: 60%+ expected
- ✅ No duplicate companies (by website domain)

## Edge Cases Handled

- **No Website**: Email enrichment skipped, flagged in sheet
- **Duplicate Domain**: Keeps first occurrence only
- **API Rate Limits**: Built-in delays and error handling
- **Invalid Emails**: Flagged with "⚠️ REVIEW:" prefix

## Example: Recruitment Agencies with High Pain Signals

```python
result = scraper.execute(
    search_query="recruitment agency London UK job posting 60 days",
    max_results=200,
    location="London, UK"
)
```

## Troubleshooting

**Issue**: Google Sheets export fails
- **Solution**: Ensure `credentials.json` is in project root
- Download from: Google Cloud Console → APIs → Credentials → OAuth 2.0 Client IDs

**Issue**: Email enrichment rate too low
- **Solution**: Check AnyMailFinder credit balance
- Alternative: Set `skip_email_enrichment=True` and use generic emails

**Issue**: Apify actor fails
- **Solution**: Check APIFY_API_KEY is valid
- Verify credit balance at apify.com
