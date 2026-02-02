# Scrape Clutch Leads (Email-First)

## Goal
Scrape companies from Clutch.co and find decision-makers with emails using email-first workflow (proven 200-300% coverage vs 5-10% decision-maker-first).

## Input
```bash
python execution/scrape_clutch_leads.py \
  --search-url "https://clutch.co/agencies/digital-marketing" \
  --limit 25
```

**Required:**
- Clutch.co category URL (e.g., /agencies/digital-marketing, /it-services, /agencies/creative)
- Limit: 10-100 companies (default: 25)

**API Keys (.env):**
- `APIFY_API_KEY` - Clutch scraper (memo23/apify-clutch-cheerio)
- `ANYMAILFINDER_API_KEY` - Company email finder
- `RAPIDAPI_KEY` - LinkedIn search
- `RAPIDAPI_KEY_2` - (Optional) second key for rate limit

## Tool
`execution/scrape_clutch_leads.py`

## Expected Output

**Format:** Google Sheets or CSV (15 columns)

| Column | Example | Source |
|--------|---------|--------|
| company_name | Density Labs | Clutch |
| first_name | Steven | Email extraction |
| last_name | Fogel | Email extraction |
| job_title | VP of Web Applications | LinkedIn |
| email | steven@densitylabs.io | AnyMailFinder |
| linkedin_url | linkedin.com/in/... | RapidAPI |
| website | densitylabs.io | Clutch |
| location | Zapopan, Mexico | Clutch |
| rating | 4.7 | Clutch |
| review_count | 3 reviews | Clutch |
| employee_size | 10 - 49 | Clutch |
| hourly_rate | $25 - $49 / hr | Clutch |
| min_project_size | $5,000+ | Clutch |
| service_focus | IT Staff Augmentation (70%) | Clutch |
| industries | Business services, Real estate | Clutch |

**Quality metrics:**
- **Coverage:** 200-300% (2-3 decision-makers per company)
- **Email quality:** 95%+ (validated via AnyMailFinder)
- **LinkedIn accuracy:** 90%+ (verified profiles only)
- **Processing:** ~1 minute per company

## Workflow (Email-First - v1.0)

1. **Scrape companies** from Clutch.co (Apify actor: memo23/apify-clutch-cheerio)
2. **Extract website** from Clutch data (websiteUrl field)
3. **Find ALL emails** at company (up to 20) - AnyMailFinder Company API
4. **Extract names** from emails (firstname.lastname@ → "Firstname Lastname")
5. **Search LinkedIn** by name + company (RapidAPI - 3 attempts per person)
6. **Validate decision-maker** (CEO, CFO, VP, Founder, etc.)
7. **Output** only decision-makers with verified emails

**LinkedIn Search Strategy (3 attempts):**

- Attempt 1: `"{name}" at "{company}" linkedin` (5 results) - Most specific
- Attempt 2: `{name} "{company}" linkedin` (5 results) - Medium specificity
- Attempt 3: `{name} {company} linkedin` (7 results) - Broad match

## Decision-Maker Keywords

**Included:**
- founder, co-founder, ceo, chief executive, chief
- owner, president, managing partner, managing director
- vice president, vp, cfo, cto, coo, cmo
- executive, c-suite, c-level, principal, partner

**Excluded:**
- assistant, associate, junior, intern, coordinator
- analyst, specialist, representative, agent, clerk

## Edge Cases & Constraints

**No website found:**
- Script skips company (cannot find emails without domain)
- Rate: <5% companies (Clutch data includes website field)

**Rate limits:**
- AnyMailFinder: 5 req/sec (handled by script)
- RapidAPI: 5 req/sec per key (2 keys = 10 req/sec)
- Apify: Residential proxies recommended (see below)

**Residential Proxies:**
- **Critical:** Clutch.co blocks datacenter IPs aggressively
- **Solution:** Use Apify residential proxies from target country
- **Config:** `"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]`
- **Cost:** ~$5 per 1GB (100 companies ≈ 50MB)

**Data Formatting:**
- Service Focus: Extract top service + percentage
- Industries: Comma-separated list (top 3-5)
- Employee Size: Keep as-is (e.g., "10 - 49")
- Hourly Rate: Keep as-is (e.g., "$25 - $49 / hr")

## Quality Thresholds

**Pass criteria (test with 10 companies first):**
- ✅ 95%+ companies have websites found
- ✅ 150%+ decision-makers found (15+ from 10 companies)
- ✅ 90%+ emails are valid format
- ✅ 85%+ LinkedIn profiles found

**Fail → Adjust:**
- Low websites (<95%) → Check if Clutch scraper returned websiteUrl field
- Low DMs (<150%) → Check industry (B2C agencies have lower rates)
- Low LinkedIn (<85%) → Normal for small agencies (<10 employees)

## Clutch Scraper Input Schema

```json
{
    "startUrls": [
        {
            "url": "https://clutch.co/agencies/digital-marketing"
        }
    ],
    "maxConcurrency": 10,
    "minConcurrency": 1,
    "maxRequestRetries": 10,
    "maxItems": 100,
    "proxyConfiguration": {
        "useApifyProxy": true,
        "apifyProxyGroups": ["RESIDENTIAL"]
    }
}
```

## Clutch Scraper Output Fields (Available)

**Company Info:**
- `name` - Company name
- `url` - Clutch profile URL
- `websiteUrl` - Official website (REQUIRED for email finding)
- `tagline` - Company tagline
- `bio` - Full company description

**Metrics:**
- `rating` - Average rating (e.g., "4.7")
- `reviewCount` - Number of reviews (e.g., "3 reviews")
- `verified` - Boolean verification status
- `totalReviews` - Total review count as string

**Business Details:**
- `employeeSize` - Company size (e.g., "10 - 49")
- `hourlyRate` - Rate range (e.g., "$25 - $49 / hr")
- `minProjectSize` - Min budget (e.g., "$5,000+")
- `location` - Primary location string

**Location Details (Array):**
- `locations[].name` - Office name (e.g., "Headquarters")
- `locations[].locality` - City
- `locations[].region` - State/province
- `locations[].country` - Country
- `locations[].postalCode` - ZIP code
- `locations[].telephone` - Phone number

**Service Focus:**
- `serviceFocus[]` - Array of services with percentages
  - `service` - Service name
  - `percentage` - Allocation (e.g., "70%")
- `serviceLines[]` - Detailed service breakdown
  - `Name` - Service name
  - `Percent` - Percentage as integer

**Industries:**
- `chartPie.industries.slices[]` - Industry distribution
  - `name` - Industry name
  - `percent` - Percentage as decimal

**Social Media:**
- `socialMediaLinks[]` - Social profiles
  - `type` - Platform (linkedin, facebook, twitter, instagram)
  - `url` - Profile URL

**Reviews (Array):**
- `reviews[].reviewer.name` - Reviewer name
- `reviews[].reviewer.title` - Job title
- `reviews[].review.rating` - Rating (1-5)
- `reviews[].datePublished` - Review date

## Self-Annealing Notes

**v1.1 (2026-01-30) - Speed Optimization (5-6x faster):**
- **Bottleneck identified:** LinkedIn search rate limiting (0.2s delay = 600s of 720s total)
- **Solution 1:** Support up to 5 RapidAPI keys (RAPIDAPI_KEY_3, _4, _5)
- **Solution 2:** Increased parallel workers (10→20 companies, 5→10 emails per company)
- **Performance gain:** 12 minutes → 2-3 minutes (5-6x faster)
- **Speed calculation:**
  - Before: 10 workers + 5 email workers + 1-2 API keys = 12 min
  - After: 20 workers + 10 email workers + up to 5 API keys = 2-3 min
  - Net gain: ~80-85% faster
- **Trade-off:** Slightly higher memory usage (negligible impact)

**v1.0 (2026-01-30) - Initial Implementation:**
- **Pattern:** Based on scrape_crunchbase.py v4.0 email-first approach
- **Key difference:** Clutch provides website directly (no Google Search needed)
- **Parallel processing:** 10 workers for companies, 5 workers per company for emails
- **Residential proxies:** Required for Clutch.co (datacenter IPs blocked)

**Cost per 100 companies:**
- Apify (Clutch scraper): $3.50-$5.00 (residential proxies)
- AnyMailFinder: $0.50
- RapidAPI: Free (5000 req/month)
- **Total:** ~$4-6 per 100 companies

**Performance estimates:**
- Scraping 100 companies: ~30-60 seconds (parallel)
- Email finding: ~2 seconds per company (parallel workers)
- LinkedIn search: ~1 second per person (rate limited)
- **Total:** ~1-2 minutes per company (including LinkedIn enrichment)

**Critical setup:**
- Must use residential proxies (datacenter = blocked)
- Website field is REQUIRED from Clutch data
- memo23/apify-clutch-cheerio actor provides richest output
