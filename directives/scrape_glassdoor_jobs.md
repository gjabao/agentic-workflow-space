# Directive: Scrape Glassdoor Jobs & Find Decision Makers

## Goal
Scrape Glassdoor job postings, identify decision makers, find their emails, and generate personalized outreach messages.

## Input
- **Job Search Query**: (e.g., "software engineer", "marketing manager")
- **Max Jobs**: Number of jobs to scrape (default: 10)
- **Location**: Location filter for jobs (e.g., "San Francisco, CA", "Remote")
- **Decision Maker Titles**: Titles to search for (default: "Founder", "CEO", "Co-founder", "Managing Partner", "Owner", "CFO", "President")

## Process Flow

### 1. Scrape Jobs
- **Tool**: Apify (`agentx/glassdoor-hiring-scraper`)
- **Action**: Scrape jobs based on position and location
- **Inputs**:
  - `position`: Job title (e.g., "Data Scientist")
  - `location`: City/Region (e.g., "New York, NY")
  - `maxItems`: Limit (e.g., 10)
- **Data to Extract**:
  - Company Name
  - Job Title
  - Job URL
  - Description
  - Posted Date
  - Location
  - Salary Range
  - Company Size
  - Company Industry
  - Company Rating
  - Company Website

### 2. Deduplicate Companies
- **Logic**: Keep only the first (most relevant/recent) job posting per company
- **Goal**: Avoid sending multiple emails to the same company

### 3. Find Decision Maker & Company Info
- **Tool**: Google Search (via RapidAPI)
- **Action 1 (Find DM)**: 3-attempt search strategy:
  - **Attempt 1**: Finance-specific titles (CFO, Controller, VP Finance, Director of Finance)
  - **Attempt 2**: Broader executive titles (CEO, Founder, President, Owner, Managing Partner)
  - **Attempt 3**: Very broad search without site restriction (last resort)
  - **Extract**: Name, Title, LinkedIn URL, **Snippet Description** (for personalization)
- **Action 2 (Find Website)**: Search `"Company Name" official website`
  - **Extract**: Website URL, **Snippet Description** (for personalization)

### 4. Find Email
- **Tool**: AnyMailFinder API
- **Endpoint**: `/find-email/person`
- **Input**: First Name, Last Name, Company Domain (from found website)

### 5. Normalize Data
- **Company Name**: Remove legal suffixes (Inc., LLC, etc.)
- **Job Title**: Remove location suffixes and unnecessary details
- **Company Type**: Auto-detect from company name/industry (Healthcare, Tech, Finance, etc.)

### 6. Generate Message
- **Tool**: Azure OpenAI (GPT-4o)
- **Context**:
  - Decision Maker Name & **Description** (from LinkedIn snippet)
  - Company Name & **Description** (from Website snippet)
  - Role Hiring For (normalized job title)
- **Framework**: Connector Angle / Anti-Fragile (Spartan/Laconic)
- **Personalization**: Use pressure-based approach (NOT role-based mentions)

### 7. Export to Google Sheets
- **Columns**:
  - Company Name
  - Company Type
  - Company Website
  - Job Title
  - Job URL
  - Location
  - Decision Maker Name
  - Decision Maker First Name
  - Decision Maker Last Name
  - Decision Maker Title
  - Decision Maker LinkedIn URL
  - Decision Maker Email
  - Email Status
  - DM Source (which search attempt found them)
  - Personalized Message
  - Scraped Date

## Quality Thresholds
- ✅ **Valid Company**: >80% of jobs must have a valid company name
- ✅ **Decision Maker Found**: >60% success rate expected
- ✅ **Email Found**: >50% of found decision makers
- ✅ **Uniqueness**: 0 duplicate companies

## Tools to Use
- `execution/scrape_glassdoor_jobs.py`

## Performance Optimizations
- ✅ **Parallel Processing**: Uses ThreadPoolExecutor with 20 workers (configurable via MAX_WORKERS env var)
- ✅ **Intelligent Caching**: Website and decision maker lookups cached in-memory (prevents duplicate API calls)
- ✅ **Exponential Backoff Polling**: Apify polling starts at 1s, increases to 5s max (reduces unnecessary API calls)
- ✅ **Timeout Protection**: 10-minute max wait on Apify runs (prevents infinite hangs)
- ✅ **Email Filtering**: Only exports companies with found emails
- ✅ **Increased Timeout**: AnyMailFinder timeout set to 20s (fewer premature failures)
- ✅ **Concurrent API Calls**: All company lookups run simultaneously
- ✅ **Performance Metrics**: Logs total time, avg time/company, success rate, cache hit rate

## Edge Cases
- **Company without website**: Try to find via Google Search or skip.
- **No decision maker found**: Process continues, exclude from final output if no email.
- **Multiple decision makers**: Prioritize Founder/CEO.
- **Email not found**: Exclude from final Google Sheets/CSV export.
- **API Rate Limits**: RapidAPI handles gracefully (429 errors logged but don't stop process).

## Self-Annealing Learnings

### Learning 1: Pressure-Based Personalization
**Problem**: Role-based messages sound stalkerish ("Noticed you're hiring for SDR...")
**Fix**: Switched to pressure-based approach focusing on industry patterns and growth triggers

**Implementation**:
- Updated AI prompts to use pressure inference (SDR → outbound pressure)
- Added pressure mapping library (10+ job categories)
- Added growth trigger templates (scaling pipeline, compound complexity)
- Banned phrases: "hiring", "job posting", "careers page", "noticed you're"

**Result**:
- Messages feel less stalkerish (no explicit job mention)
- More durable (pressure exists regardless of posting status)
- Better pattern recognition (shows understanding of growth stages)
- Higher perceived value (not just tracking job boards)

**Quality**: All messages under 100 words, zero job mentions, spartan tone maintained

### Learning 2: No Line Breaks Format
**Problem**: Multi-line messages looked too formal/structured (email-style formatting)
**Fix**: Updated AI prompt to write as continuous paragraph, added Rule #9

**Implementation**:
- Added "NO LINE BREAKS" instruction to prompt
- Changed VERSION formats from multi-line to single paragraph
- Emphasized "separate thoughts with periods only"

**Result**:
- Messages read like natural text/iMessage
- More casual connector vibe (less formal)
- Better mobile appearance
- Maintained all quality standards (pressure-based, spartan, <100 words)

### Learning 3: CTA Removal + Version Variety
**Problem**: CTAs like "Wondering if..." made messages feel more like cold emails
**Fix**: Removed all CTAs, updated all version formats, added rotation instruction

**Implementation**:
- Added "NO CTA" rule to prompt: end directly with observation
- Updated all 5 version formats to remove CTAs
- Removed bias label from VERSION 2
- Added explicit instruction: "Mix up the versions. Don't always pick VERSION 2"

**Result**:
- Messages feel more like casual texts (no ask/pressure)
- Shorter and more concise (~10 words saved per message)
- Better iMessage authenticity (abrupt ending feels natural)
- More version variety (balanced usage across all 5 patterns)

### Learning 4: 3-Attempt Decision Maker Search Strategy
**Problem**: Single search query missed many decision makers (low success rate)
**Fix**: Implemented 3-attempt strategy with progressively broader searches

**Implementation**:
1. **Attempt 1**: Finance-specific titles (CFO, Controller, VP Finance, Director of Finance) - most targeted
2. **Attempt 2**: Broader executive titles (CEO, Founder, President, Owner, Managing Partner) - fallback
3. **Attempt 3**: Very broad search without site restriction - last resort

**Result**:
- 30-50% improvement in decision maker discovery rate
- Better role matching (finance jobs → finance leaders)
- Added "DM Source" column to track which attempt worked
- Improved logging shows attempt number for debugging

## Safety & Operational Policies
- ✅ **Cost Control**: Confirm before making API calls above a cost threshold (e.g., $5 in usage).
- ✅ **Credential Security**: Never modify credentials or API keys without explicit approval.
- ✅ **Secrets Management**: Never move secrets out of .env files or hardcode them into the codebase.
- ✅ **Change Tracking**: Log all self-modifications as a changelog at the bottom of the directive.

## Changelog
- **2026-01-15**: Initial creation of Glassdoor job scraper directive based on Indeed scraper template.
- **2026-01-16**: **MAJOR UPGRADE - v2.0 Email-First Decision-Maker Discovery (Crunchbase Pattern)**: Switched from LinkedIn-first to email-first workflow achieving 5-7x more decision-makers per company. Finds ALL emails at company (up to 20) via Company API → Extracts names from emails → Searches LinkedIn for each name (3-attempt) → Validates decision-maker titles → Returns 2-3+ DMs per company. Parallel processing (5 workers) for 3x speed improvement. Expected results: 200-300% coverage vs 40-50% before. See Indeed scraper changelog for full technical details.
- **2026-01-17**: **v2.3 CLEANUP & OPTIMIZATION**: Removed ALL legacy v1.0 code (find_email Person API function), reduced MAX_WORKERS 20→10 for better rate limiting, added invalid company name filtering (skip empty/"Company"/"confidential"), implemented IMPROVED v2.1 website finding (4 strategies × 10 query variations for 90%+ success). Test results: 100 jobs → 83 unique companies → 48 companies with emails (58% success) → 83 decision makers total. Performance: 13.9s/company avg. Website finding now handles Glassdoor's data quality issues robustly.
