---
description: Scrape Indeed jobs and find decision makers with emails
---

# Indeed Job Scraper & Decision Maker Outreach

This workflow scrapes Indeed job postings, finds decision makers (Founder/CEO), enriches with emails, and generates personalized outreach messages.

## Prerequisites

Ensure these API keys are set in `.env`:
- `APIFY_API_KEY` - For job scraping and Google Search
- `ANYMAILFINDER_API_KEY` - For email enrichment
- `AZURE_OPENAI_API_KEY` - For message generation
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint
- Google Sheets credentials (`credentials.json`)

## Steps

### 1. Configure Search Parameters

Edit `execution/scrape_jobs.py` in the `main()` function:

```python
def main():
    scraper = LinkedInJobScraper() # Class name kept for compatibility, but uses Indeed
    scraper.execute(
        query="AI Engineering",        # Job title / Position
        location="United States",      # Location
        max_jobs=10,                   # Number of jobs to scrape
        days_posted=7                  # (Not used by Indeed scraper currently)
    )
```

### 2. Clear Google Sheets Token (if needed)

If you encounter authentication errors:

```bash
rm -f token.json
```

### 3. Run the Scraper

// turbo
```bash
python3 execution/scrape_jobs.py
```

The script will:
1. Scrape jobs from Indeed using `misceres/indeed-scraper`
2. Deduplicate companies
3. For each company:
   - Find decision maker (Founder/CEO) via Google Search
   - Extract DM's LinkedIn description
   - Find company website via Google Search
   - Extract company description
   - Find DM's email using AnyMailFinder
   - Generate personalized message using Azure OpenAI (GPT-4o)
4. Export all data to Google Sheets

### 4. Review Output

The script will output a Google Sheets URL with columns:
- Company Name, Website
- Job Title, Job URL
- DM Name, Title, LinkedIn, Email
- Personalized Message
- Email Status

## Customization

### Change Job Search
Modify `query` and `location` in `main()` function.

### Adjust Personalization
Edit the `generate_message()` method to change the tone or structure of outreach messages.

## Troubleshooting

- **Apify Monthly Limit**: Upgrade Apify plan or wait for monthly reset
- **Google Sheets Auth**: Delete `token.json` and re-authenticate
- **Email Not Found**: AnyMailFinder may not have the email; marked as "not_found"
