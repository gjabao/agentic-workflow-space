# Directive: Instantly Campaign Creator

> **Version:** 1.0  
> **Last Updated:** 2025-11-29  
> **Status:** Active  
> **Provider:** Instantly.ai API v2 + Azure OpenAI

## Goal/Objective
Automatically create cold email campaigns in Instantly.ai based on a client description and offers. The system uses AI to generate personalized sequences (A/B variants, follow-ups) and the Instantly API to build the campaign structure.

## Required Inputs

| Input | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `client_name` | string | Yes | "Acme Corp" | Name of the client/sender |
| `client_description` | string | Yes | "We help SaaS companies..." | Context for AI generation |
| `target_audience` | string | Yes | "CTOs at Series A startups" | Who we are emailing |
| `offers` | list | Yes | ["Free Audit", "Case Study"] | List of 3 offers (or auto-generate) |
| `dry_run` | boolean | No | false | If true, skips API creation |

## Execution Tools

**Primary Script:** `execution/instantly_create_campaigns.py`

**Dependencies:**
- Instantly API v2 (Campaign creation)
- Azure OpenAI (Content generation)

## Expected Outputs

### Instantly Campaign Structure
- **Name:** `[Client] | [Offer] - [Description]`
- **Sequences:** 1 sequence per campaign containing all steps
- **Steps:**
  1. **Email 1:** 2 A/B variants (Subject + Body)
  2. **Email 2:** 1 variant (Follow-up, 3 days delay)
  3. **Email 3:** 1 variant (Breakup, 4 days delay)
- **Schedule:** "Weekday Schedule" (Mon-Fri, 9-5 Chicago time)
- **Settings:** Stop on reply, Open tracking, Link tracking enabled

### Content Guidelines (SSM SOP + Connector Angle + Anti-Fragile Method)

**Core Strategy:** Position as "connector" offering introductions, not direct seller.

**Frameworks Used:**
1. **SSM SOP**: "Connector Insight" openers pre-generated during scraping
2. **Connector Angle**: Frame as helpful introducer (18-25% reply rates vs 6-10% direct pitch)
3. **Anti-Fragile Method**: AI fills variables in human-written template

**Email Structure (5-7 sentences, <100 words):**
1. `<p>{{icebreaker}}</p>` - SSM opener from lead data
2. **Bridge** - Connect opener to their situation (1-2 sentences)
3. **Specific Outcome** - What they get with numbers (e.g. "5-10 qualified calls/month")
4. **Easy CTA** - Low-pressure ask with NO punctuation
5. `<p>Sent from my iPhone</p>` - Personal touch

**CRITICAL: Spartan/Laconic Tone Rules**
- **Short & direct** - No fluff, no unnecessary words
- **Simple language** - NO jargon (leverage, optimize, streamline, innovative, synergy, etc.)
- **NO PUNCTUATION AT END** - Drop ALL periods/question marks from sentences/CTAs
- **Lowercase strategically** - Keep casual where appropriate
- **Focus on WHAT, not HOW** - What they do, not process details
- **Shorten company names** - "{{companyName}}" not "{{companyName}} Agency"
- **Implied familiarity** - Show shared beliefs/interests

**Follow-ups (SSM SOP Standard):**
1. **Day 3**: "Hey {{firstName}}, worth intro'ing you" (no punctuation)
2. **Day 7**: "Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best"

**Format:** HTML required (`<p>`, `<br>`).

**Variant A vs B:**
- **Variant A**: Problem-solving angle (acknowledge pain → offer solution)
- **Variant B**: Opportunity angle (highlight what's missing → offer access)

## Process Flow

1.  **Validation Phase**
    - Check `INSTANTLY_API_KEY` and `AZURE_OPENAI_API_KEY`
    - Validate inputs

2.  **Generation Phase (AI)**
    - For each offer:
        - **Step 1 Body**: Start with `<p>{{icebreaker}}</p>` (from lead data).
        - AI generates bridge, offer, and CTA.
        - **Variant A vs B**: Different angles on the offer.
        - **Step 2 & 3:** Use fixed SSM follow-up templates.
        - Format text as HTML.

3.  **Creation Phase (API)**
    - Construct JSON payload matching Instantly v2 spec
    - `POST /api/v2/campaigns`
    - Handle rate limits and errors

4.  **Lead Addition Phase**
    - **Input:** JSON file from `scrape_apify_leads.py` (via `--leads_file`).
    - **Process:**
        - Filter for valid emails.
        - Map fields: `email`, `first_name`, `last_name`, `company_name`, `website`.
        - Map `icebreaker` to `personalization` and `custom_variables`.
        - `POST /api/v2/leads` for each lead.
    - **Rate Limit:** Batch processing to avoid 429s.

4.  **Verification Phase**
    - Log created campaign IDs
    - Verify structure (if possible via API or manual check)

## Lead Field Mapping

When uploading leads from `scrape_apify_leads.py` to Instantly campaigns:

| Scraped Field | Instantly Field | Custom Variable | Required | Notes |
|---------------|-----------------|-----------------|----------|-------|
| `email` | `email` | - | ✅ Yes | Primary identifier |
| `first_name` | `first_name` | - | ✅ Yes | Used in {{firstName}} |
| `last_name` | `last_name` | - | ⚠️ Recommended | Full name personalization |
| `company_name` | `company_name` | - | ✅ Yes | Used in {{companyName}} |
| `icebreaker` | `personalization` | `icebreaker` | ⚠️ Recommended | SSM opener, maps to {{icebreaker}} |
| `company_website` | `website` | - | ❌ Optional | For reference |
| `company_industry` | - | `industry` | ❌ Optional | Additional context |
| `company_full_address` | - | `location` | ❌ Optional | Geographic data |
| `job_title` | - | - | ❌ Not mapped | Available in source data |
| `verification_status` | - | - | ❌ Not uploaded | Used for filtering only |

**Key Notes:**
- `icebreaker` is mapped to BOTH `personalization` field AND `custom_variables.icebreaker` for redundancy
- Only leads with `verification_status == "Valid"` should be uploaded when using `--valid_only`
- Empty fields are sent as empty strings `""` to Instantly API

## Edge Cases & Constraints

### Instantly API v2
- **HTML Only:** Plain text is stripped. Must use `<p>` tags.
- **Timezones:** Use `America/Chicago` (strict enum).
- **Schedules:** Must include `"name"` field.
- **Sequences:** Only the first sequence in the array is used.

### AI Generation
- **Hallucinations:** AI might invent variables. Strict prompt required to use only allowed variables.
- **Formatting:** AI might output Markdown. Script must convert or enforce HTML.

## Error Recovery

| Error Type | Detection | Recovery Action |
|-----------|-----------|-----------------|
| Missing API Key | Env check | Exit early (or dry run only) |
| API Error (400) | HTTP 400 | Log payload, check formatting constraints |
| API Error (401) | HTTP 401 | Check API key validity |
| API Error (429) | HTTP 429 | Wait 5 seconds, retry once, implement rate limiting |
| Generation Fail | AI Error | Retry or skip offer |
| Lead Upload Timeout | Request timeout | Set 10s timeout, retry failed leads |

## Optimizations & Learnings

### 2025-11-29: Version 1.1 - Upload Performance & Reliability
- **Rate limit handling** - Automatic retry on 429 errors with 5s backoff
- **Request timeouts** - 10s timeout per lead upload prevents hanging
- **Better error tracking** - Count successful/failed uploads separately
- **Progress updates** - Log progress every 10 leads for visibility
- **Batch delays** - 0.5s delay every 5 leads to avoid API rate limits
