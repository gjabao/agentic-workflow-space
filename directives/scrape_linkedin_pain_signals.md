# Scrape LinkedIn Pain Signals (Email-First)

## Goal

Monitor LinkedIn posts for pain signals (expansion, hiring, funding, launches) and enrich with decision-maker data using proven email-first workflow. Outputs verified decision-makers with emails to Google Sheets.

## Input

```bash
python execution/scrape_linkedin_pain_signals.py \
  --keywords '"expanding into" OR "new market" OR "new office"' \
  --date-filter past-month \
  --limit 50
```

**Required:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--keywords` | String | Required | Boolean OR query for pain signals |
| `--date-filter` | String | "past-month" | Filter: past-day, past-week, past-month |
| `--limit` | Integer | 50 | Maximum posts to scrape (10-200) |
| `--min-relevance` | Integer | 30 | Minimum relevance score (0-100) |

**API Keys (.env):**

- `APIFY_API_KEY` - LinkedIn posts + profile scrapers
- `ANYMAILFINDER_API_KEY` - Company email finder
- `RAPIDAPI_KEY` - Google Search for LinkedIn profiles
- `RAPIDAPI_KEY_2` - (Optional) second key for rate limit

## Tool

`execution/scrape_linkedin_pain_signals.py`

## Expected Output

**Format:** Google Sheets or CSV (14 columns)

| Column | Example | Source |
|--------|---------|--------|
| post_text | "Excited to announce we're expanding into..." | Apify |
| post_url | linkedin.com/feed/update/... | Apify |
| pain_signal_type | expansion | Classification |
| relevance_score | 75 | Calculation |
| posted_date | 2026-01-15 | Apify |
| post_author_name | John Smith | Apify |
| post_author_linkedin | linkedin.com/in/johnsmith | Apify |
| company_name | Acme Corp | Profile |
| company_website | acme.com | Google Search |
| dm_first_name | Sarah | Email extraction |
| dm_last_name | Johnson | Email extraction |
| dm_job_title | VP of Sales | LinkedIn Search |
| dm_email | sarah.johnson@acme.com | AnyMailFinder |
| dm_linkedin_url | linkedin.com/in/sarahj | LinkedIn Search |

**Quality metrics:**

- **Coverage:** 2-3 decision-makers per company
- **Email quality:** 95%+ (validated via AnyMailFinder)
- **LinkedIn accuracy:** 90%+ (verified profiles only)
- **Processing:** ~1-2 minutes per unique company

## Workflow (v1.0)

### Phase 1: Scrape LinkedIn Posts

**Actor:** `apimaestro/linkedin-posts-search-scraper-no-cookies`

**Input:**
```json
{
    "date_filter": "past-month",
    "keyword": "\"expanding into\" OR \"new market\" OR \"new office\"",
    "limit": 50,
    "page_number": 1,
    "sort_type": "date_posted"
}
```

**Output:** Post data with author info, stats, hashtags

### Phase 2: Filter Recruitment/Job Boards

Skip posts from recruitment agencies and job boards:

```python
SKIP_AUTHOR_PATTERNS = [
    'recruiter', 'recruiting', 'talent acquisition', 'staffing',
    'job board', 'jobs board', 'career', 'hiring agency',
    'hr manager', 'headhunter', 'recruitment'
]
```

### Phase 3: Scrape Author Profiles

**Actor:** `harvestapi/linkedin-profile-scraper`

**Input:** Profile URLs from posts
**Output:** Full profile data including current company

### Phase 4: Extract Company Info

From author profile:
- Current company name (from experience[0])
- Company LinkedIn URL
- Author's current position

### Phase 5: Find Website (3-Attempt Strategy)

Using RapidAPI Google Search:
1. `"{company_name}" official website`
2. `"{company_name}" company website`
3. `{company_name} site`

### Phase 6: Email-First Enrichment

**FOR EACH COMPANY (parallel, 10 workers):**
1. Find website (if missing) via 3-attempt Google Search
2. Find ALL emails at domain (AnyMailFinder, up to 20/company)

**FOR EACH EMAIL (parallel, 5 workers):**
1. Extract name from email (firstname.lastname@ patterns)
2. Search LinkedIn by name + company (3-attempt strategy)
3. Validate decision-maker title (CEO, VP, Founder, etc.)
4. Deduplicate by full name

### Phase 7: Export to Google Sheets

- Create new spreadsheet
- Add formatted headers (bold, blue background, frozen)
- Make publicly viewable
- Also save CSV backup locally

## Pain Signal Keywords

**Expansion:**
- "expanding into", "new market", "new office", "opened our office", "growing our team"

**Hiring:**
- "hiring", "looking for", "open role", "join our team", "recruiting"

**Funding:**
- "raised", "funding", "series a", "series b", "seed round", "investment"

**Launch:**
- "launching", "excited to announce", "introducing", "new product"

**Growth:**
- "scaling", "growing", "milestone", "record quarter"

**Pain:**
- "struggling with", "challenge", "looking for solution", "need help with"

## Decision-Maker Keywords

**Included:**
- founder, co-founder, ceo, chief executive, chief
- owner, president, managing partner, managing director
- vice president, vp, cfo, cto, coo, cmo
- executive, c-suite, c-level, principal, partner
- head of, director

**Excluded:**
- assistant, associate, junior, intern, coordinator
- analyst, specialist, representative, agent, clerk

## Edge Cases & Constraints

**No author profile URL:**
- Some posts may not have extractable author URLs
- Script skips these posts (logged as warning)

**Author not employed:**
- Students, job seekers may not have current company
- Script skips these authors

**Company website not found:**
- Script skips company (cannot find emails without domain)
- Rate: 5-10% companies have no findable website

**Rate limits:**
- AnyMailFinder: 5 req/sec (handled by script)
- RapidAPI: 5 req/sec per key (2 keys = 10 req/sec)
- Apify: Automatic rate limiting

**Recruitment agencies filtered:**
- Posts from recruiters/job boards are skipped
- Filter based on author name and headline

## Quality Thresholds

**Pass criteria (test with 10 posts first):**

- 80%+ posts have valid author profile URLs
- 70%+ authors have current company identified
- 60%+ companies have websites found
- 50%+ companies have at least 1 decision-maker found

**Fail -> Adjust:**

- Low profile URLs (<80%): Check Apify actor output format
- Low companies (<70%): Normal - some authors unemployed/students
- Low websites (<60%): Broaden search queries
- Low DMs (<50%): Relax title validation or check industry

## Relevance Scoring

Posts are scored 0-100 based on:

| Factor | Points | Condition |
|--------|--------|-----------|
| Author is DM | +30 | Headline contains DM keywords |
| Not a recruiter | +20 | No recruiter keywords in headline |
| High engagement | +20 | >100 likes |
| Medium engagement | +10 | 50-100 likes |
| Multiple signals | +10 each | Up to 30 points |

## Cost Estimates

**Per 50 posts:**

| Service | Cost | Notes |
|---------|------|-------|
| Apify (Posts) | $0.10-0.50 | Depends on post count |
| Apify (Profiles) | $0.20-1.00 | ~$4/1000 profiles |
| RapidAPI (Search) | $0.10-0.30 | Website + LinkedIn searches |
| AnyMailFinder | $1.00-3.00 | $0.05 per email found |
| **Total** | **$1.40-4.80** | Per 50 posts processed |

## Usage Examples

**Expansion signals (default):**
```bash
python execution/scrape_linkedin_pain_signals.py \
  --keywords '"expanding into" OR "new market" OR "new office"' \
  --limit 50
```

**Hiring signals:**
```bash
python execution/scrape_linkedin_pain_signals.py \
  --keywords '"hiring" OR "open role" OR "join our team"' \
  --date-filter past-week \
  --limit 100
```

**Funding announcements:**
```bash
python execution/scrape_linkedin_pain_signals.py \
  --keywords '"raised" OR "funding round" OR "series a" OR "series b"' \
  --min-relevance 50 \
  --limit 75
```

## Self-Annealing Notes

**v1.0 (2026-02-02) - Initial Implementation:**

- Followed email-first workflow from Crunchbase scraper v4.0
- Used parallel processing pattern from LinkedIn Jobs scraper
- Added relevance scoring to prioritize high-value posts
- Added recruitment agency/job board filtering
- Reused AnyMailFinder and RapidAPIGoogleSearch classes

## Safety & Operational Policies

- **Cost Control**: Confirm before making API calls above $5 threshold
- **Credential Security**: Never modify API keys without explicit approval
- **Secrets Management**: Never move secrets out of .env files
- **Change Tracking**: Log all modifications in changelog below

## Changelog

- **2026-02-02**: Initial v1.0 implementation

---

**Last Updated**: 2026-02-02
**Status**: Ready for Implementation
**Maintainer**: Anti-Gravity DO System