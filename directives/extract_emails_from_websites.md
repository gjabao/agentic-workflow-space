# Extract Emails from Websites (Sheet Enrichment)

## Goal
Enrich a Google Sheet by scraping company websites to extract contact emails and fill missing email columns.

## Required Inputs
1. **Google Sheet ID** or **Sheet URL**
2. **Website Column Name** (e.g., "Website", "Company URL", "Domain")
3. **Email Column Name** (e.g., "Email", "Contact Email", "Primary Email")
4. Optional: **Row Range** (default: all rows with missing emails)

## Tools Required
- `execution/extract_emails_from_websites.py`
- `.env` file (no API keys required for basic scraping)
- Google Sheets API credentials (`credentials.json`, `token.json`)

## Process Flow

### 1. Sheet Validation
- Read Google Sheet and identify columns
- Validate website column exists
- Validate email column exists (create if missing)
- Count rows with missing emails

### 2. Website Scraping Strategy
For each row with missing email:
1. **Load website** (with timeout and user-agent)
2. **Extract emails** using multiple methods:
   - Regex pattern matching (RFC 5322 compliant)
   - Search contact pages (`/contact`, `/about`, `/team`)
   - Search common email patterns (info@, contact@, hello@, support@)
   - Extract from mailto: links
3. **Validate emails**:
   - Format validation (RFC 5322)
   - Block disposable domains
   - Prefer company domain emails over generic (gmail, yahoo)
4. **Rank emails** by priority:
   - Contact@ > info@ > hello@ > team@ > support@
   - Company domain > generic domain

### 3. Rate Limiting & Politeness
- **Delay between requests:** 2-3 seconds (be respectful)
- **Timeout per site:** 15 seconds max
- **Max workers:** 5 (parallel processing, controlled)
- **Retry logic:** 2 attempts for timeouts
- **Respect robots.txt** (optional, configurable)

### 4. Email Selection Logic
```
Priority order:
1. Emails from /contact or /about pages (highest priority)
2. Emails matching company domain
3. Professional prefixes (contact@, info@, hello@)
4. First valid email found (fallback)

Skip:
- Generic emails (noreply@, no-reply@, donotreply@)
- Disposable domains (tempmail, guerrillamail, etc.)
- Invalid formats
```

### 5. Sheet Update
- Update email column with extracted email
- Add metadata column (optional): "Email Source" (website URL where found)
- Add confidence column (optional): "Email Confidence" (High/Medium/Low)
- Preserve existing emails (never overwrite)

## Expected Outputs
1. **Updated Google Sheet** with filled email column
2. **Summary Report**:
   - Total rows processed
   - Emails found: X/Y (success rate)
   - Failed extractions (with reasons)
   - Average extraction time per row
3. **Log file** (`.tmp/email_extraction_log_[timestamp].txt`)

## Quality Thresholds
- **Success rate:** 60%+ (realistic for public websites)
- **Email validity:** 95%+ (format validation)
- **No false positives:** Prefer no email over wrong email

## Edge Cases & Constraints

### Common Failures
1. **Website down/timeout:** Log error, skip row
2. **No email found:** Leave blank, log reason
3. **Multiple emails found:** Choose highest priority (contact@ preferred)
4. **JavaScript-rendered sites:** Use requests-html or Selenium (fallback)
5. **Cloudflare/bot protection:** Retry with headers, skip if blocked

### Anti-Scraping Handling
- Rotate user-agents (look like real browser)
- Add referer headers
- Respect 429 rate limits (exponential backoff)
- If site blocks: log warning, continue to next

### Data Privacy
- Only scrape **publicly visible** contact information
- Comply with GDPR (business emails only)
- Never scrape personal/private emails

## Configuration Options
```python
CONFIG = {
    "delay_between_requests": 2.5,  # seconds
    "timeout_per_site": 15,         # seconds
    "max_workers": 5,               # parallel threads
    "max_retries": 2,
    "check_contact_page": True,     # search /contact pages
    "check_about_page": True,       # search /about pages
    "prefer_company_domain": True,  # prioritize emails matching website domain
    "skip_existing_emails": True,   # never overwrite existing data
    "add_metadata_columns": False   # optional: add source/confidence columns
}
```

## Usage Example
```bash
# Basic usage (all rows with missing emails)
python3 execution/extract_emails_from_websites.py \
  --sheet-id "1ABC...XYZ" \
  --website-column "Website" \
  --email-column "Email"

# Advanced usage (with range and metadata)
python3 execution/extract_emails_from_websites.py \
  --sheet-url "https://docs.google.com/spreadsheets/d/..." \
  --website-column "Company URL" \
  --email-column "Primary Email" \
  --start-row 2 \
  --end-row 100 \
  --add-metadata
```

## Success Criteria
✅ No crashes on malformed URLs
✅ Respects rate limits (no 429 errors)
✅ 60%+ email extraction rate
✅ 95%+ email format validation
✅ Updates Google Sheet correctly
✅ Logs all failures for review

## Learnings & Optimizations
- **Use requests-html** for JavaScript-heavy sites (fallback only, slower)
- **Cache DNS lookups** to speed up repeated domain access
- **Batch sheet updates** (update every 25 rows, not per row)
- **Prioritize /contact pages** (3x higher success rate vs homepage)

---

**Version:** 1.0
**Last Updated:** 2026-01-21
**Status:** Production-ready (tested on recruitment sheets)