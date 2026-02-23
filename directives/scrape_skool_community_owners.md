# Skool Community Owner Email Finder v1.0

## Goal

Find email and contact information for Skool community owners to enable outreach. The system searches Skool for communities by keyword, scrapes owner information, finds emails using a cascade strategy, enriches with LinkedIn data, and exports to Google Sheets.

## Input

- `--keywords`: Comma-separated keywords (e.g., "marketing, coaching, crypto")
- `--max_groups`: Max groups per keyword (default: 50)
- `--skip_test`: Skip test batch validation (default: run test first)

## Output (18 columns)

| # | Column | Source |
|---|--------|--------|
| 1 | Group Name | Apify (gordian) |
| 2 | Group URL | Apify (gordian) |
| 3 | Member Count | Apify (gordian) |
| 4 | Owner Name | Email extraction OR Apify |
| 5 | Owner Email | Cascade logic |
| 6 | Email Source | skool/anymailfinder/google_search |
| 7 | Owner Website | Apify OR Google Search |
| 8 | Owner LinkedIn | Apify OR RapidAPI enrichment |
| 9 | Owner Instagram | Apify (gordian) |
| 10 | Owner YouTube | Apify (gordian) |
| 11 | Owner Twitter | Apify (gordian) |
| 12 | Owner Facebook | Apify (gordian) |
| 13 | Job Title | LinkedIn extraction |
| 14 | Owner Skool Profile | Derived from ownerName |
| 15 | Group Description | Apify (gordian) |
| 16 | Monthly Price | Apify (gordian) |
| 17 | Scraped Date | datetime |
| 18 | Status | found / social_only / not_found |

## Workflow

```
1. Parse keywords (comma-separated → list)
2. For each keyword:
   a. Apify Actor 1 → Search Skool groups (futurizerush/skool-group-scraper)
   b. Apify Actor 2 → Get group details (gordian/skool-group-scraper)
3. Email Cascade (per owner):
   - CASE 1: supportEmail exists → Use directly
   - CASE 2: ownerWebsite exists → AnyMailFinder(domain)
   - CASE 3: No website → Google Search (3-attempt) → AnyMailFinder
4. Name Extraction from email patterns (firstname.lastname@)
5. LinkedIn Enrichment (3-attempt strategy)
6. Include social profiles as fallback when no email found
7. Export → Google Sheets (18 columns)
```

## Usage

```bash
# Single keyword
python execution/scrape_skool_owners.py --keywords "marketing" --max_groups 100

# Multiple keywords (comma-separated)
python execution/scrape_skool_owners.py --keywords "marketing, coaching, crypto" --max_groups 50

# Skip test (production)
python execution/scrape_skool_owners.py --keywords "ai, saas" --max_groups 200 --skip_test
```

## API Keys Required (.env)

```
APIFY_API_KEY=apify_api_xxxxx          # For Skool scraping
ANYMAILFINDER_API_KEY=xxxxx            # For email finding
RAPIDAPI_KEY=xxxxx                      # For Google Search/LinkedIn
RAPIDAPI_KEY_2=xxxxx                    # Optional: key rotation
```

## Apify Actors

### Actor 1: futurizerush/skool-group-scraper

**Purpose:** Search Skool for groups by keyword

**Input:**
```json
{
    "query": "automation",
    "maxItems": 100,
    "language": "english",
    "includeOwnerInfo": false
}
```

**Output:**
```json
[
  {
    "groupId": "b51c57150c70495899bf4bc8aaee8166",
    "displayName": "AI Automation Society",
    "memberCount": 254011,
    "isFree": true,
    "pricePerMonth": null,
    "currency": null,
    "rank": 2,
    "groupUrl": "https://www.skool.com/ai-automation-society"
  }
]
```

### Actor 2: gordian/skool-group-scraper

**Purpose:** Get detailed group info including owner data

**Input:**
```json
{
    "startUrls": [
        {"url": "https://www.skool.com/ai-automation-society"}
    ]
}
```

**Output:**
```json
[
  {
    "displayName": "AI Automation (A-Z)",
    "name": "freegroup",
    "description": "Learn to Start, Build, and Scale...",
    "logoUrl": "https://assets.skool.com/...",
    "supportEmail": null,
    "totalMembers": 130061,
    "monthlyPrice": null,
    "createdAt": "2025-03-08T16:16:58.027198Z",
    "ownerName": "albert-olgaard",
    "ownerFirstName": "Albert",
    "ownerLastName": "Shiney",
    "ownerBio": "I build stuff with AI",
    "ownerPictureProfile": "https://assets.skool.com/...",
    "ownerFacebook": null,
    "ownerInstagram": "https://www.instagram.com/albert.olgaard/",
    "ownerLinkedin": null,
    "ownerTwitter": null,
    "ownerYoutube": "https://www.youtube.com/@albertolgaard",
    "ownerWebsite": null
  }
]
```

## Email Cascade Logic

### Priority Order

1. **supportEmail exists** → Use directly (fastest, most reliable)
2. **ownerWebsite exists** → Extract domain → AnyMailFinder (up to 20 emails)
3. **No website** → Google Search (3-attempt) → Find website → AnyMailFinder

### 3-Attempt Website Search Strategy

```
Attempt 1: "{owner_name}" website -linkedin -facebook -twitter (5 results)
Attempt 2: "{owner_name}" "{group_name}" website (5 results)
Attempt 3: "{group_name}" founder website (7 results)
```

**Valid website criteria:**
- Not social media (linkedin, facebook, twitter, instagram, youtube, tiktok)
- Not Skool URLs
- Has proper domain extension (.com, .io, .co, etc.)

## Name Extraction from Email

Extract names from discovered emails:

| Pattern | Example | Extracted Name | Confidence |
|---------|---------|----------------|------------|
| firstname.lastname@ | john.smith@company.com | John Smith | 95% |
| firstname_lastname@ | john_smith@company.com | John Smith | 90% |
| firstnamelastname@ (camelCase) | johnSmith@company.com | John Smith | 85% |
| firstname@ | john@company.com | John | 80% |

## LinkedIn Enrichment (3-Attempt Strategy)

```
Attempt 1: "{name}" at "{group_name}" linkedin (5 results) - most specific
Attempt 2: {name} "{group_name}" linkedin (5 results) - medium
Attempt 3: {name} skool community owner linkedin (7 results) - broad
```

**Validation:**
- LinkedIn URL must contain `/in/`
- Name in result must fuzzy-match extracted name (threshold: 0.6)
- Extract job title from LinkedIn title pattern

## Social Profile Fallback

When no email is found, include row with social profiles:
- Instagram (`ownerInstagram`)
- YouTube (`ownerYoutube`)
- Twitter/X (`ownerTwitter`)
- LinkedIn (`ownerLinkedin`)
- Facebook (`ownerFacebook`)

Status column will show "social_only" for these rows.

## Quality Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Test batch size | 10 groups | Validate before full run |
| Email found rate | >= 40% | Pass to proceed |
| Valid email format | 100% | RFC 5322 validation |

## Error Handling

### API Rate Limits
- RapidAPI: 5 req/sec per key (exponential backoff on 429)
- AnyMailFinder: 10 req/sec
- Apify: Polling with adaptive intervals

### Self-Annealing Protocol

```
1. DETECT - Log error with context
2. ANALYZE - Categorize: rate_limit / api_auth / empty_result
3. FIX - Apply retry with backoff OR skip
4. DOCUMENT - Update this directive with learnings
5. TEST - Verify fix
```

## Edge Cases

1. **Group has no owner info** → Skip group, log warning
2. **Owner has no website AND no social** → Status = "not_found"
3. **Duplicate groups across keywords** → Deduplicate by groupUrl
4. **AnyMailFinder returns empty** → Try Google Search fallback
5. **All attempts fail** → Include row with available data, status = "social_only" or "not_found"

## Learnings & Optimizations

(This section will be updated as the system self-anneals)

- Initial implementation: v1.0