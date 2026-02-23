# Directive: Scrape Reed.co.uk Jobs & Find Decision Makers

## Goal

Scrape job postings from Reed.co.uk, identify hiring decision makers, find verified emails, and generate personalized outreach messages using the email-first workflow (200-300% coverage vs 40-50% with LinkedIn-first approach).

---

## Required Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keyword` | String | Required | Job search keyword (e.g., "Account Manager", "Software Engineer") |
| `location` | String | "" | Location filter (e.g., "London", "Manchester", "Remote") |
| `posted_date` | String | "last14days" | Date filter: `last24hours`, `last3days`, `last7days`, `last14days`, `lastMonth` |
| `limit` | Integer | 10 | Maximum number of jobs to scrape (1-500) |
| `max_pages` | Integer | 20 | Maximum pages to scrape (each page ~25 jobs) |

---

## Architecture Pattern (Email-First v2.0)

### Core Design Principles

1. **Email-First**: Find ALL emails at company first, then validate decision-makers
2. **Parallel Processing**: Use ThreadPoolExecutor for concurrent API calls
3. **4-Strategy Website Finding**: 90%+ success rate for company websites
4. **Real-time Feedback**: Show progress to user immediately
5. **Smart Rate Limiting**: Prevent API throttling with intelligent delays

### Data Flow (Pipeline)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Scrape Reed.co.uk Jobs (Apify)                           │
│    → keyword, location, date filter                         │
│    → Returns: title, company, location, salary, url         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Deduplicate Companies                                    │
│    → Keep first job per company                             │
│    → Normalize company names (remove Inc, Ltd, etc.)        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. For Each Company (Parallel - 10 workers):                │
│                                                             │
│    Step 3.1: Find Website (4-strategy, 90%+ success)        │
│    ├─ Strategy 1: Google Search + UK keywords               │
│    ├─ Strategy 2: Google Search without keywords            │
│    ├─ Strategy 3: Domain guessing (.co.uk, .com, .org.uk)   │
│    └─ Strategy 4: Wildcard Google Search                    │
│                                                             │
│    Step 3.2: Find ALL Emails (AnyMailFinder Company API)    │
│    → Returns up to 20 emails per company                    │
│                                                             │
│    Step 3.3: For Each Email (Parallel - 5 workers):         │
│    ├─ Extract name from email (firstname.lastname@)         │
│    ├─ Search LinkedIn by name + company (3 attempts)        │
│    ├─ Validate decision-maker title                         │
│    └─ Generate personalized message (OpenAI)                │
│                                                             │
│    → Returns: 2-3+ decision-makers per company              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Export Results                                           │
│    → CSV backup: .tmp/reed_jobs_YYYYMMDD_HHMMSS.csv        │
│    → Google Sheets (shareable link)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Execution Flow

### Phase 1: Scrape Reed.co.uk Jobs (Apify)

**Actor**: `lexis-solutions/reed-co-uk-scraper`

**Input Configuration**:

```python
{
    "keyword": "Account Manager",
    "location": "London",
    "posted_date": "last14days",
    "results_wanted": 10,
    "max_pages": 20,
    "collectDetails": True
}
```

**Output Fields**:

| Field | Example |
|-------|---------|
| title | "Account Manager" |
| company | "Compass Group UK & Ireland Ltd" |
| location | "London" |
| salary | "£30,000 - £50,000" |
| employmentType | "Permanent" |
| datePosted | "2026-02-05T16:09:11" |
| url | "https://www.reed.co.uk/jobs/account-manager/56432273" |

---

### Phase 2: Find Company Website (4-Strategy Approach)

**Strategy 1: Google Search WITH UK Keywords (3 attempts)**

```python
queries = [
    f'"{company_name}" {location} UK official website',
    f'{company_name} {location} UK website',
    f'{company_name} UK home'
]
```

**Strategy 2: Google Search WITHOUT Keywords (3 attempts)**

```python
queries = [
    f'"{company_name}" official website',
    f'{company_name} company website',
    f'{company_name} homepage'
]
```

**Strategy 3: Domain Guessing (UK-focused TLDs)**

```python
# Clean company name → try TLDs in order:
tld_options = ['.co.uk', '.com', '.org.uk', '.uk', '.io', '.net']

# Validate with HTTP HEAD request
for tld in tld_options:
    domain = f"{clean_name}{tld}"
    if validate_domain(domain):
        return domain
```

**Strategy 4: Wildcard Google Search (last resort)**

```python
queries = [
    f'{company_name} UK',
    f'{company_name} company',
    company_name
]
```

**Filtering Logic**:

- Skip: linkedin.com, facebook.com, twitter.com, reed.co.uk, indeed.com, glassdoor.com
- Prefer homepage over subpages (/careers, /about, /jobs)

---

### Phase 3: Find ALL Emails (AnyMailFinder Company API)

**Endpoint**: `/v5.1/find-email/company`

**Request**:

```python
payload = {
    "domain": "company.co.uk",
    "email_type": "any"  # Get all types: generic + personal
}
```

**Response**:

```python
{
    "emails": [
        "john.smith@company.co.uk",
        "jane.doe@company.co.uk",
        "sales@company.co.uk",
        # ... up to 20 emails
    ],
    "status": "found",
    "count": 15
}
```

---

### Phase 4: Extract Names from Emails

**Pattern Recognition**:

| Email Pattern | Extracted Name | Confidence |
|---------------|----------------|------------|
| john.smith@ | "John Smith" | 95% |
| j.smith@ | "J Smith" | 90% |
| john_smith@ | "John Smith" | 90% |
| john-smith@ | "John Smith" | 90% |
| johnsmith@ | "John Smith" (camelCase detection) | 85% |
| john@ | "John" | 60% |

**Skip Generic Emails**:

- info@, contact@, hello@, support@, sales@, admin@
- office@, help@, team@, hr@, jobs@, careers@

---

### Phase 5: Search LinkedIn by Name (3-Attempt Strategy)

**Attempt 1**: Strict match

```python
f'site:linkedin.com/in/ "{person_name}" "{company_name}"'
```

**Attempt 2**: Relaxed (last name only)

```python
f'site:linkedin.com/in/ {last_name} {company_name}'
```

**Attempt 3**: Very broad

```python
f'{person_name} {company_name} linkedin'
```

---

### Phase 6: Validate Decision-Maker Title

**Include Keywords**:

- founder, co-founder, ceo, chief executive
- owner, president, managing director
- vice president, vp, cfo, cto, coo, cmo
- director, head of, partner, principal

**Exclude Keywords**:

- assistant, associate, junior, intern, coordinator
- analyst, specialist, representative, clerk, trainee

---

### Phase 7: Generate Personalized Message

**Tool**: Azure OpenAI (GPT-4o)

**Framework**: SSM Connector-style (pressure-based, not role-based)

**Rules**:

1. Spartan/Laconic tone - short, simple, direct
2. NO mention of "hiring", "job posting", "careers page"
3. Lead with THEM and their pressure, not you
4. Under 100 words, no line breaks
5. No CTA - end abruptly after observation

---

### Phase 8: Export Results

**Google Sheets Columns**:

| Column | Source |
|--------|--------|
| Company Name | Reed.co.uk |
| Company Type | Auto-detected |
| Company Website | Google Search |
| Job Title | Reed.co.uk |
| Job URL | Reed.co.uk |
| Location | Reed.co.uk |
| DM Name | LinkedIn |
| DM Title | LinkedIn |
| DM First | Parsed |
| DM Last | Parsed |
| DM LinkedIn | Google Search |
| DM Email | AnyMailFinder |
| Email Status | AnyMailFinder |
| DM Source | Search attempt |
| Message | OpenAI |
| Scraped Date | System |

---

## Quality Thresholds

| Metric | Target | Notes |
|--------|--------|-------|
| Jobs Retrieved | >80% | Should return close to requested limit |
| Website Found | >90% | 4-strategy approach |
| Emails Found | >60% | Of companies with website |
| Decision Makers | 200-300% | 2-3 DMs per company |
| Email Quality | 95%+ | Validated via AnyMailFinder |

---

## Tools to Use

- **Execution Script**: `execution/scrape_reed_jobs.py`

### Dependencies

```bash
pip install apify-client openai requests pandas google-auth-oauthlib google-api-python-client python-dotenv
```

### Required API Keys (.env)

```bash
APIFY_API_KEY=apify_api_xxxxx
RAPIDAPI_KEY=xxxxx
RAPIDAPI_KEY_2=xxxxx  # Optional - for higher throughput
ANYMAILFINDER_API_KEY=xxxxx
AZURE_OPENAI_API_KEY=xxxxx
AZURE_OPENAI_ENDPOINT=https://xxxxx.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### Google OAuth

- `credentials.json` (OAuth client credentials)
- `token.json` (Auto-generated after first run)

---

## Usage Examples

### Basic Search

```bash
python execution/scrape_reed_jobs.py \
  --keyword "Account Manager" \
  --location "London" \
  --limit 25
```

### Remote Jobs

```bash
python execution/scrape_reed_jobs.py \
  --keyword "Software Engineer" \
  --location "Remote" \
  --limit 50
```

### Recent Jobs Only

```bash
python execution/scrape_reed_jobs.py \
  --keyword "Marketing Manager" \
  --posted-date "last3days" \
  --limit 100
```

---

## Edge Cases & Error Handling

### No Website Found

```python
if not domain:
    logger.info(f"  ⊘ No website domain - skipping")
    return []
```

### No Emails Found

```python
if not emails:
    logger.info(f"  ⊘ No emails found - skipping")
    return []
```

### Rate Limiting (429)

```python
if response.status_code == 429:
    time.sleep(2 ** attempt)  # Exponential backoff
    continue
```

### Invalid Company Name

```python
if company.lower() in ['confidential', 'company', '']:
    continue  # Skip invalid companies
```

---

## Cost Estimates

| Service | Cost per 100 jobs |
|---------|-------------------|
| Apify (Reed Scraper) | $0.50-2.00 |
| RapidAPI (Google Search) | $0.10-0.30 |
| AnyMailFinder | $2.00-5.00 |
| Azure OpenAI (GPT-4o) | $0.50-1.00 |
| **Total** | **$3.10-8.30** |

---

## Safety & Operational Policies

- ✅ **Cost Control**: Confirm before scraping >100 jobs
- ✅ **Credential Security**: Never modify API keys without approval
- ✅ **Secrets Management**: Keep API keys in .env only
- ✅ **Change Tracking**: Log all modifications in changelog

---

## Self-Annealing Learnings

*(Empty - will be populated as issues are discovered and fixed)*

---

## Changelog

- **2026-02-14**: Initial creation of Reed.co.uk job scraper with full email-first decision maker enrichment workflow (based on Indeed/Glassdoor/LinkedIn scrapers v2.0)
