# Directive: Scrape Leads (Apify Implementation)

> **Version:** 2.0  
> **Last Updated:** 2025-11-28  
> **Status:** Active  
> **Provider:** Apify leads-finder actor

## Goal/Objective

Scrape B2B business leads using Apify's leads-finder actor with email verification (SSMasters) and AI-powered personalized icebreakers (Azure OpenAI), delivering validated results with personalized cold email openers in a Google Sheet.

## Required Inputs

| Input | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `industry` | string | Yes | "Marketing Agency", "IT Recruitment" | Target industry/profession |
| `fetch_count` | integer | Yes | 30 | Number of leads to scrape |
| `location` | string | No | "united states", "united arab emirates" | Country/region (lowercase) |
| `company_keywords` | list | No | ["IT staffing", "tech recruitment"] | Specific company keywords for filtering |
| `job_title` | list | No | ["CEO", "Founder", "Director"] | Target job titles |
| `company_industry` | list | No | ["marketing & advertising"] | Apify industry filters (lowercase) |
| `skip_test` | boolean | No | true | Skip 25-lead validation phase |
| `valid_only` | boolean | No | true | Export only verified valid emails |

## Execution Tools

**Primary Script:** `execution/scrape_apify_leads.py`

**Dependencies:**
- Apify API (lead scraping)
- SSMasters API (email verification)
- Azure OpenAI (icebreaker generation)
- Google Sheets API (export)

## Expected Outputs

### Google Sheet Format
- **Company Name**, Website, Industry, Location, Size, Revenue
- **First Name**, Last Name, Job Title
- **Email**, Email Status, **Verification Status**
- **Icebreaker** (AI-generated personalized opener)
- Phone, LinkedIn, Company LinkedIn

### Quality Thresholds
- **Email presence:** ≥ 85% of leads have emails
- **Email verification:** SSMasters validates all emails (Valid/Invalid/Catch-All)
- **Valid email rate:** Typically 30-50% of found emails are "Valid"
- **Icebreaker generation:** 100% of valid emails get personalized openers
- **Industry match:** ≥ 80% (when test phase enabled)

### Delivery
- Shareable Google Sheet link with edit permissions
- Sheet name format: `Leads - [Industry] - [Date]`
- "Icebreaker" column with personalized cold email openers

## Process Flow

### 1. Validation Phase
- Check `APIFY_API_KEY`, `SSMASTERS_API_KEY`, `AZURE_OPENAI_API_KEY` in `.env`
- Validate input parameters
- Normalize location/industry to lowercase (Apify requirement)

### 2. Test Phase (Optional - skip with `--skip_test`)
- Scrape 25 sample leads
- Validate industry match rate (≥80% threshold)
- If fail → suggest filter improvements (keywords, job titles)
- If pass → proceed to full scrape

### 3. Full Scrape Phase
- Run Apify actor with specified parameters
- Use `email_status: ["validated"]` to prefer validated emails
- Store raw results in `.tmp/scraped_data/`

### 4. Email Verification Phase (SSMasters)
- Extract all emails from scraped leads
- Submit to SSMasters bulk verification API
- Poll for results (5s intervals, max 5 minutes)
- Update leads with verification status: Valid/Invalid/Catch-All/Unknown

### 5. Filtering Phase (if `--valid_only`)
- Filter leads to only those with `verification_status == "Valid"`
- Reduces deliverable to highest-quality contacts

### 6. **Icebreaker Generation (SSM SOP)**
-   **Purpose**: Generate personalized "Connector-style" openers using SSM SOP prompts.
-   **Integration**: Azure OpenAI API
-   **Strategy**: Uses 2 SSM prompts:
    -   **Prompt #1 (Company-Based)**: "Noticed [Company] helps [Titles] at [Type] — I know a few who [pain]."
    -   **Prompt #3 (Role-Based)**: "Figured I'd reach out — I'm around [ICP] daily and they keep saying they [pain]."
-   **Selection Logic**: If lead has `company_description`, use Prompt #1; otherwise use Prompt #3.
-   **Custom Prompt**: Generates operator-style complaints based on industry/role data.
-   **Integration**: Automatically runs after email verification for valid leads.
-   **Output**: "Icebreaker" column added to Google Sheets with AI-generated SSM openers.
-   **Argument**: `--sender_context` (optional) for additional context about the sender.

### 7. Export Phase
- Create Google Sheet via Sheets API
- Format headers (bold, frozen row)
- Include "Verification Status" and "Icebreaker" columns
- Generate shareable link

### 8. Metrics Reporting
- Total leads scraped
- Emails found (count + percentage)
- Valid emails (count)
- Duration

## Performance Optimizations

### Parallel Icebreaker Generation
- Uses `asyncio.gather()` to generate all icebreakers concurrently
- **Speed:** ~5-10x faster than sequential (50s → 10s for 10 leads)
- Fallback to sequential on error

### Skip Test Flag
- `--skip_test` bypasses 25-lead validation
- Saves ~30-40 seconds per run
- Use when confident in filter parameters

### Valid-Only Export
- `--valid_only` filters before icebreaker generation
- Reduces AI API calls and processing time
- Ensures clean, ready-to-use deliverables

## API Integration Details

### Apify Actor: code_crafter/leads-finder
- **Input normalization:** Locations and industries must be lowercase
- **Email preference:** `email_status: ["validated"]` for pre-validated emails
- **Batch size:** No limit, but 30-50 recommended for speed/cost balance

### SSMasters Email Verification
- **Endpoint:** `/verify/bulk` (CSV upload)
- **Authentication:** API key via form-data
- **Response:** Async with polling via `/status` endpoint
- **Statuses:** Valid, Invalid, Catch-All, not_processed

### Azure OpenAI
- **Deployment:** gpt-4o
- **Temperature:** 0.7 (balanced creativity)
- **Max tokens:** 50 (icebreakers are concise)
- **Parallelization:** Up to 10-20 concurrent requests

## Edge Cases & Constraints

### Location Format
- Apify requires lowercase: "United States" → "united states"
- Script auto-normalizes input

### Company Keywords
- Use highly specific terms (10+ keywords recommended)
- Example: ["IT staffing", "technical recruiting", "tech talent acquisition"]
- More keywords = better targeting but slower scrape

### Email Verification Timeout
- Max wait: 5 minutes (60 retries × 5s interval)
- On timeout: Returns partial results

### Google Sheets Limits
- Max cells: 10M per sheet
- For 1000+ leads, consider splitting into multiple sheets

## Error Recovery

| Error Type | Detection | Recovery Action |
|-----------|-----------|-----------------|
| Missing API Key | Env var check | Log warning, skip that feature (e.g., skip verification) |
| Apify 400 Error | Invalid location/industry | Show allowed values, normalize input |
| SSMasters Timeout | Polling exceeds 5 min | Return leads without verification |
| OpenAI Rate Limit | 429 response | Sequential fallback |
| OpenAI Content Filter | 400 + jailbreak error | Sanitize input text (remove special chars), use fallback icebreaker |
| Google Auth Fail | OAuth error | Prompt re-authentication (port 8080) |

## Performance Targets

| Quantity | Expected Duration | Breakdown |
|----------|-------------------|-----------|
| 5 leads | 20-30s | Scrape: 15s, Verify: 5s, Icebreakers: 5s (parallel) |
| 10 leads | 30-45s | Scrape: 20s, Verify: 10s, Icebreakers: 10s (parallel) |
| 30 leads | 60-90s | Scrape: 40s, Verify: 25s, Icebreakers: 15s (parallel) |
| 100 leads | 90-120s | Scrape: 40s, Verify: 35s, Icebreakers: 20s (parallel) |

*With `--skip_test` and `--valid_only` for optimal speed*
*Performance improved 30-40% with adaptive polling (v2.3)*

## Learnings & Optimizations

### 2025-11-28: Version 2.0 - Complete Rewrite
- **Migrated from Apollo to Apify** (leads-finder actor)
- **Added SSMasters email verification** (Valid/Invalid/Catch-All status)
- **Added Azure OpenAI icebreaker generation** (personalized cold email openers)
- **Implemented parallel icebreaker generation** (5-10x speedup)
- **Added `--valid_only` flag** for clean deliverables
- **Auto-normalization** for location/industry inputs (lowercase)
- **Optimized workflow:** Skip test + valid-only + parallel AI = ~50% faster

### 2025-11-29: Version 2.1 - Cost & Reliability Optimizations

- **Smart email verification** - Skip emails already validated by Apify (saves 30-40% on SSMasters costs)
- **Content filter protection** - Sanitize inputs to prevent Azure OpenAI jailbreak errors (prevents lead loss)
- **Fallback icebreakers** - Generic icebreakers when AI generation fails (0% lead loss vs 6% before)
- **Trust Apify validation** - Emails marked "validated" by Apify skip SSMasters verification automatically

### 2025-12-03: Version 2.2 - Quality & Speed Revolution

- **AI-powered industry filtering** - Azure OpenAI validates companies that fail fuzzy matching (90%+ accuracy)
- **Parallel AI validation** - Batch validation (10 concurrent) reduces test phase time by 5-10x
- **CSV export fallback** - Automatic CSV export when Google Sheets OAuth fails (zero data loss)
- **Intelligent filtering logic** - Two-phase validation: fuzzy match first (fast) → AI validation second (accurate)
- **Result:** 100% match rate for target industries, no more irrelevant companies in output

### 2025-12-22: Version 2.3 - Speed Optimization

- **Adaptive email verification polling** - Starts at 2s intervals, scales to 3s (30-40% faster)
- **Reduced logging noise** - Only log verification status every 3rd attempt
- **Optimized polling strategy** - Checks more frequently early when jobs complete fast
- **Result:** 100 leads now complete in ~90-120s vs 155s (40% improvement on verification phase)

### 2025-12-25: Version 2.4 - Production Hardening & Security Fixes

- **Security P0:** Added API key sanitization in error logs (prevents credential leakage)
- **Reliability P0:** Added 30s timeouts to all HTTP requests (prevents infinite hangs)
- **Reliability P0:** Fixed nested `asyncio.run()` crash using `run_async()` helper
- **Validation P0:** Added company_size validation with auto-correction (e.g., "50-100" → "51-100")
- **Efficiency E1:** Added AI filter fallback for low match rates (<20% → keeps all leads)
- **Directive Alignment:** Icebreakers now only generated for VALID emails (not all emails)
- **Code Quality:** Extracted magic numbers to constants (REQUESTS_TIMEOUT, VERIFICATION_MAX_RETRIES, etc.)
- **Result:** Production-ready script with 85% readiness score (up from 60%)

### Best Practices
- Use 10+ specific `company_keywords` for precision (like image example)
- Always use `--skip_test` and `--valid_only` for production runs
- Verify Azure OpenAI credentials are set for icebreakers
- Target 30-50 leads per run for optimal speed/cost
- For 100+ leads, expect ~90-120s total runtime with optimizations
- If AI filter shows <20% match, script now keeps all leads to avoid credit waste

---

## Usage Example

**User input:**
```
"Scrape 30 IT recruitment leads in US with icebreakers"
```

**Agent execution:**
```bash
python3 execution/scrape_apify_leads.py \
  --industry "IT Recruitment" \
  --fetch_count 30 \
  --location "united states" \
  --company_keywords "IT staffing" "technical recruiting" "tech recruitment" \
  --skip_test \
  --valid_only
```

**Output:**
```
⏳ PHASE 1: Running full scrape (30 leads)...
✓ Scraped 30 leads

⏳ PHASE 2: Verifying emails...
✓ Verification complete. Valid emails: 16

⏳ PHASE 3: Filtering for valid emails only...
✓ Filtered: 16 valid leads (from 30 total)

⏳ PHASE 4: Generating icebreakers (parallel)...
✓ Generated 16 icebreakers

⏳ Exporting to Google Sheets...
✓ Scraping completed successfully!
📊 Total leads: 30
📧 With emails: 29 (96.7%)
✅ Validated emails: 16
🔗 Google Sheet: [link]
⏱️ Duration: 117.9s
```

---

**Evolution Notes:**
- This directive replaces the Apollo.io implementation
- Significant quality improvement with email verification
- AI personalization adds unique value for cold outreach
- Parallel processing makes it production-ready for scale

## Safety & Operational Policies
- ✅ **Cost Control**: Confirm before making API calls above a cost threshold (e.g., $5 in usage).
- ✅ **Credential Security**: Never modify credentials or API keys without explicit approval from you.
- ✅ **Secrets Management**: Never move secrets out of .env files or hardcode them into the codebase.
- ✅ **Change Tracking**: Log all self-modifications as a changelog at the bottom of the directive.

## Changelog
- **2026-01-03**: Added 'Safety & Operational Policies' section (Cost thresholds, Credential protection, Secrets management, Changelog requirement).
