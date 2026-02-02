# Scrape Crunchbase Leads (Email-First)

## Goal
Scrape companies from Crunchbase and find decision-makers with emails using email-first workflow (proven 200-300% coverage vs 5-10% decision-maker-first).

## Input
```bash
python execution/scrape_crunchbase.py \
  --search-url "https://www.crunchbase.com/discover/..." \
  --limit 25
```

**Required:**
- Crunchbase search URL (must be in Table Mode with columns: Website, Description, Funding, Location)
- Limit: 10-100 companies (default: 25)

**API Keys (.env):**
- `APIFY_API_KEY` - Crunchbase scraper
- `CRUNCHBASE_COOKIES` - Pro account session (JSON array)
- `ANYMAILFINDER_API_KEY` - Company email finder
- `RAPIDAPI_KEY` - LinkedIn search
- `RAPIDAPI_KEY_2` - (Optional) second key for rate limit

## Tool
`execution/scrape_crunchbase.py`

## Expected Output

**Format:** Google Sheets or CSV (13 columns)

| Column | Example | Source |
|--------|---------|--------|
| company_name | Phantom | Crunchbase |
| first_name | Brandon | Email extraction |
| last_name | Millman | Email extraction |
| job_title | CEO & Co | LinkedIn |
| email | brandon@phantom.com | AnyMailFinder |
| linkedin_url | linkedin.com/in/... | RapidAPI |
| website | phantom.com | Crunchbase/Search |
| location | San Francisco, CA | Crunchbase |
| funding_stage | Series B | Crunchbase (formatted) |
| total_funding | $109M | Crunchbase (formatted) |
| last_funding_date | 2022-01-18 | Crunchbase |
| description | Digital wallet... | Crunchbase |
| categories | Cryptocurrency, FinTech | Crunchbase (formatted) |

**Quality metrics:**
- **Coverage:** 200-300% (2-3 decision-makers per company)
- **Email quality:** 95%+ (validated via AnyMailFinder)
- **LinkedIn accuracy:** 90%+ (verified profiles only)
- **Processing:** ~1 minute per company

## Workflow (Email-First - v4.0)

1. **Scrape companies** from Crunchbase (Apify actor)
2. **Find website** (from Crunchbase or Google Search with 3-attempt strategy)
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

**Cookie expiration:**
- Crunchbase cookies expire after 24-48 hours
- Script detects 401 errors
- Solution: Refresh cookies via Cookie-Editor extension

**No website found:**
- Script skips company (cannot find emails)
- Rate: 5-10% companies have no findable website

**Rate limits:**
- AnyMailFinder: 5 req/sec (handled by script)
- RapidAPI: 5 req/sec per key (2 keys = 10 req/sec)
- Apify: 1-5s delay between pages (automatic)

**Formatting:**
- Funding stage: `series_b` → `Series B`
- Funding amount: `1000000` → `$1M`
- Categories: Extract from dict/list → comma-separated string

## Quality Thresholds

**Pass criteria (test with 10 companies first):**
- ✅ 80%+ companies have websites found
- ✅ 150%+ decision-makers found (15+ from 10 companies)
- ✅ 90%+ emails are valid format
- ✅ 85%+ LinkedIn profiles found

**Fail → Adjust:**
- Low websites (<80%) → Check if Table Mode was used, add Website column
- Low DMs (<150%) → Check industry (B2C has lower rates)
- Low LinkedIn (<85%) → Normal for small startups (<10 employees)

## Self-Annealing Notes

**v4.1 (2026-01-16) - Parallel Email Processing:**

- **Bottleneck identified:** Sequential email processing (20 emails × 6s = 120s per company)
- **Solution:** Nested ThreadPoolExecutor with 5 workers for parallel email processing
- **Implementation:**
  - Process 5 emails simultaneously per company (20 emails / 5 workers = 4 batches)
  - Thread-safe duplicate detection with Lock()
  - Maintains API rate limits (10 req/sec across all workers)
- **Performance gain:** 2-3x faster per company (33s → 10-15s expected)
- **Speed calculation:**
  - Before: 20 emails sequential = 120s LinkedIn searches + 10s other = 130s
  - After: 20 emails / 5 parallel = 24s LinkedIn searches + 10s other = 34s
  - Net gain: ~75% faster on email processing (biggest bottleneck)

**v4.0 (2026-01-15) - Email-First Approach:**
- **OLD:** Find decision-maker first → search email (5-10% success)
- **NEW:** Find emails first → extract names → search LinkedIn → validate DM (200-300% success)
- **Why:** AnyMailFinder Company API finds 10-20 emails/company vs 0-1 email/person
- **Pattern:** Proven from Google Maps scraper (70-80% coverage)

**Formatting improvements:**
- Added `_format_funding_stage()` - series_b → Series B
- Added `_format_funding_amount()` - 1000000 → $1M
- Added `_format_categories()` - Extract from Crunchbase dict/list

**Cost per 100 companies:**
- Apify: $0.50
- AnyMailFinder: $0.50
- RapidAPI: Free (5000 req/month)
- **Total:** ~$1 per 100 companies

**Critical setup:**
- Must use Table Mode on Crunchbase (Grid mode = missing data)
- Must add Website column (REQUIRED for enrichment)
- Cookies must be from Pro account (Basic account = limited access)
