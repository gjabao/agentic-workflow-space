# Generate_Personalize Message for Sheet.md — Personalization Generator (v1.0)

## Goal
Read leads from an existing Google Sheet, generate personalized cold email pieces using OpenAI, and write results back to the same sheet. Supports 3 agency types with different output columns.

## Tool
`execution/enrich_sheet_personalization.py`

## Input

### Command
```bash
python execution/enrich_sheet_personalization.py \
  --sheet_id "YOUR_SHEET_ID_OR_URL" \
  --agency_type recruitment \
  --limit 10 \
  --dry-run
```

### Arguments

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--sheet_id` | Yes | — | Google Sheet ID or full URL |
| `--agency_type` | No | `universal` | `recruitment` / `marketing` / `universal` |
| `--limit` | No | `0` (all) | Max rows to process |
| `--dry-run` | No | `false` | Preview results without writing to sheet |

### Accepts Full URLs
The script auto-extracts the sheet ID from a full URL:
```
https://docs.google.com/spreadsheets/d/1EShHkc9Kn9Nczd08Z6h_JFdsaBbBTuEGDcXtt_qREfY/edit?gid=0#gid=0
→ extracts: 1EShHkc9Kn9Nczd08Z6h_JFdsaBbBTuEGDcXtt_qREfY
```

### Required Google Sheet Columns (Input)

**Required (at least one):**
- `Company` or `Company Name` — company to personalize for

**Recommended (improves output quality):**
- `Job Title` / `Title` / `Position` / `Job Description`
- `Industry` / `Sector` / `Vertical`
- `Description` / `Company Description` / `LinkedIn Description` / `Summary` / `About`
- `Headline` / `Tagline`
- `Skills` / `Expertise`
- `First Name` / `FirstName`
- `Website` / `URL`

**Note:** Column names are case-insensitive. The script auto-maps common variations. Multiple description fields (summary, headline, skills) are combined for richer context.

### API Keys (.env)
```bash
OPENAI_API_KEY=sk-xxxxx              # Preferred — OpenAI API
# OR
AZURE_OPENAI_API_KEY=xxxxx           # Fallback — Azure OpenAI
AZURE_OPENAI_ENDPOINT=xxxxx          # Fallback — Azure endpoint
AZURE_OPENAI_DEPLOYMENT=gpt-4o       # Fallback — Azure model
```

### Google Auth
- `credentials.json` — Google OAuth client ID (from Google Cloud Console)
- `token.json` — auto-generated after first OAuth flow

## Agency Types & Output Columns

### 1. Recruitment (`--agency_type recruitment`)

For recruitment/staffing agencies. Used with email template:
```
Hey {{firstName}}, {{RANDOM |thanks for taking a look |appreciate you checking this out}},

Are you at capacity right now or still taking on new roles?

Know this out of left field–a few I'm working with are hiring {{Roles}} rn — budgets approved, just need the right partner.

Make sense to connect you?
```

**Output columns:**

| Column | Description | Example |
|--------|-------------|---------|
| `Personalization` | "Saw you specialize/focus on..." icebreaker | Saw you focus on executive search for SaaS companies |
| `Roles` | The ONE specific role they place (2-4 words) | healthcare CFO |

**Personalization rules:**
- Starts with "Saw you..." (NOT "Saw {CompanyName}...")
- Spartan/laconic tone, no punctuation at end
- Focus on WHAT they recruit (roles/industries), not HOW
- Shorten company names (XYZ Recruiting → XYZ)
- Examples: "Saw you specialize in placing senior finance roles", "Saw you focus on healthcare leadership recruiting"

**Roles extraction rules:**
- 2-4 words, maximum specificity
- Uppercase ONLY: CEO, CFO, COO, CTO, CIO, CMO, VP, SVP, EVP
- Everything else lowercase
- Add industry qualifier when specific: "healthcare CFO" > "CFO" (if they only do healthcare)
- No generic phrases: "role", "position", "executive search", "talent"
- Valid: `healthcare CFO`, `VP sales`, `SaaS CTO`, `logistics manager`, `finance director`
- Invalid: `executive search`, `finance roles`, `senior talent`, `C-suite`

### 2. Marketing (`--agency_type marketing`)

For marketing/creative/digital agencies.

**Output columns:**

| Column | Description | Example |
|--------|-------------|---------|
| `Personalization` | "Saw your {work/portfolio}..." icebreaker | Saw your portfolio regarding branding for finance companies |
| `ICP` | Their ONE specific client type (2-5 words, all lowercase) | Series A fintech teams |
| `Their Service` | ONE service, action-oriented (3-6 words, all lowercase) | revamping their brand identity |

**Personalization rules:**
- Starts with "Saw your..." (NOT "Saw {CompanyName}...")
- Format: "Saw your {work/portfolio/projects} {regarding/on/around} {specific service} for {specific client type}"
- Examples: "Saw your work on paid social campaigns for DTC brands", "Saw your projects around content strategy for B2B SaaS"

**ICP extraction rules:**
- 2-5 words, all lowercase, maximum specificity
- MUST be DIFFERENT from what appears in the Personalization to avoid repetition
- Include qualifiers: funding stage, sub-vertical, role, business model
- Valid: `Series A fintech teams`, `Shopify store owners`, `dental practice owners`
- Invalid: `finance teams`, `tech companies`, `startups`

**Their Service extraction rules:**
- 3-6 words, all lowercase, action-oriented
- MUST be DIFFERENT from what appears in the Personalization
- Use action verbs: revamping, building, launching, rebuilding, overhauling, scaling
- AVOID: hiring, bringing on, onboarding
- Valid: `revamping their brand identity`, `building a paid social system`, `rebuilding their email funnel`
- Invalid: `brand strategy`, `paid social`, `email marketing`

### 3. Universal (`--agency_type universal` — default)

For any lead type. Combines best of recruitment + marketing prompts.

**Output columns:**

| Column | Description | Example |
|--------|-------------|---------|
| `Personalization` | "Saw you/your..." icebreaker (picks best format) | Saw you focus on healthcare leadership recruiting |
| `ICP` | Their ONE specific client type (2-5 words) | mid-market logistics firms |
| `Their Service` | ONE service, action-oriented (3-6 words) | placing senior engineering talent |

## Workflow

### ALWAYS write results back to the SAME sheet
This script reads from AND writes to the same Google Sheet. Output columns (Personalization, Roles/ICP, Their Service) are written directly into the source sheet — never to a separate file or console only. If output columns don't exist, the script adds them automatically.

### Step-by-step:

1. **Read sheet** — read all rows, auto-map columns (Company, Job Title, Description, etc.)
2. **Ensure output columns** — add `Personalization` + `Roles`/`ICP`/`Their Service` columns if missing
3. **Build context per row** — combine ALL description-like columns (summary, linkedin description, job description, headline, linkedin specialities) for maximum context
4. **Clean company name** — strip suffixes (LLC, Inc, Agency, Recruiting, Marketing, etc.)
5. **Generate via OpenAI** — call IcebreakerGenerator with agency-specific prompt
6. **Post-process** — strip trailing punctuation, remove LLM prefixes, clean placeholders
7. **Write back to sheet** — update each row's output columns in the SAME sheet immediately

### Batching
- Processes 10 leads in parallel per batch
- Progress logged every 5 completions
- Rate limiting built into IcebreakerGenerator (2 retry attempts per lead)

### Always test first, then run full
```bash
# Step 1: Dry run to preview (no writes)
python execution/enrich_sheet_personalization.py \
  --sheet_id "SHEET_URL" --agency_type recruitment --limit 5 --dry-run

# Step 2: Write 5 rows to verify in sheet
python execution/enrich_sheet_personalization.py \
  --sheet_id "SHEET_URL" --agency_type recruitment --limit 5

# Step 3: Run all rows
python execution/enrich_sheet_personalization.py \
  --sheet_id "SHEET_URL" --agency_type recruitment
```

## Edge Cases & Constraints

### Missing Company Name
- Row skipped entirely
- Warning logged: "Skipped X rows without company name"

### Missing Description/Job Title
- Still processes (uses whatever data is available)
- Quality may be lower — generic fallback templates used if OpenAI fails

### Output Columns Don't Exist
- Script automatically adds missing output columns (bold headers)
- No manual sheet setup needed

### OpenAI Failure
- 2 retry attempts per lead (temperature drops from 0.7 to 0.5)
- If both fail: generic fallback template used
- Recruitment fallback: `Saw you specialize in placing {industry} professionals` / `senior manager`
- Marketing fallback: `Saw your work regarding digital marketing for {industry} companies` / `{industry} business owners` / `revamping their brand strategy`

### Rate Limits
- OpenAI: handled by batch size (10 concurrent) + retry logic
- Google Sheets API: row-by-row writes (no bulk update)

## Quality Thresholds

### Test First (--dry-run --limit 5)
- ✅ 90%+ leads have Personalization generated
- ✅ Personalization starts with "Saw you" or "Saw your"
- ✅ No trailing punctuation
- ✅ No brackets/placeholders in output
- ✅ ICP is different from Personalization content
- ✅ Their Service uses action verbs (not static nouns)

### Fail → Adjust
- **Low generation rate (<80%)**: Check if Company column is properly named
- **Generic outputs**: Add more context columns (Description, Headline, Skills)
- **Repetitive ICP/Service**: Normal variation — the prompt enforces non-repetition with Personalization

## Cost Estimation

### Per 100 Leads
- **OpenAI (gpt-4o):** ~100 calls × ~300 tokens × $0.005/1K = ~$0.15
- **Google Sheets API:** Free (within quota)
- **Total:** ~$0.15 per 100 leads

## Usage Examples

### Recruitment Agency Sheet
```bash
# Dry run first (preview without writing)
python execution/enrich_sheet_personalization.py \
  --sheet_id "https://docs.google.com/spreadsheets/d/1EShHkc9Kn9Nczd08Z6h_JFdsaBbBTuEGDcXtt_qREfY/edit" \
  --agency_type recruitment \
  --limit 5 \
  --dry-run

# Production run
python execution/enrich_sheet_personalization.py \
  --sheet_id "1EShHkc9Kn9Nczd08Z6h_JFdsaBbBTuEGDcXtt_qREfY" \
  --agency_type recruitment
```

### Marketing Agency Sheet
```bash
python execution/enrich_sheet_personalization.py \
  --sheet_id "https://docs.google.com/spreadsheets/d/1cLydW299o_jwQRMOZdC-IQ3ARxU5dIufZv_uhUeWZrA/edit" \
  --agency_type marketing \
  --limit 10 \
  --dry-run
```

### Universal (Any Lead Type)
```bash
python execution/enrich_sheet_personalization.py \
  --sheet_id "YOUR_SHEET_ID" \
  --limit 20
```

## Architecture

### Dependencies
- `execution/scrape_apify_leads.py` — imports `IcebreakerGenerator` class (contains all 3 prompt builders)
- `token.json` — Google OAuth credentials
- `.env` — OpenAI API key

### Class: `SheetPersonalizer`
- `read_sheet()` — reads all data from Google Sheet
- `_find_column()` — flexible column name matching (case-insensitive)
- `_map_row_to_lead()` — converts sheet row to IcebreakerGenerator input format
- `_ensure_output_columns()` — adds missing output columns automatically
- `_write_row()` — writes values to specific cells via batchUpdate
- `execute()` — main orchestration (read → generate → write)

### Prompt Engine: `IcebreakerGenerator` (in scrape_apify_leads.py)
- `_build_recruitment_prompt()` — recruitment-specific prompt (2 pieces: Personalization + Roles)
- `_build_marketing_prompt()` — marketing-specific prompt (3 pieces: Personalization + ICP + Service)
- `_build_universal_prompt()` — universal prompt (3 pieces: Personalization + ICP + Service)
- `generate_bulk()` — async batch processing with retry logic

## Troubleshooting

### "OPENAI_API_KEY or AZURE_OPENAI_API_KEY+ENDPOINT required"
- **Fix:** Add `OPENAI_API_KEY=sk-xxxxx` to your `.env` file

### "No valid credentials"
- **Fix:** Run `python execution/enrich_leads.py` locally first to complete Google OAuth flow
- This generates `token.json` which is reused by this script

### "Sheet is empty"
- **Fix:** Verify the sheet has data and the sheet ID is correct

### "Skipped X rows without company name"
- **Fix:** Ensure your sheet has a column named `Company` or `Company Name`

### Low quality outputs
- **Fix:** Add more context columns to your sheet: `Description`, `Headline`, `Skills`, `Industry`
- The more context provided, the more specific the personalization

## TL;DR

**Input:** Google Sheet URL with company leads
**Output:** Same sheet updated with Personalization + ICP/Roles + Their Service
**Method:** OpenAI generates spartan, specific cold email icebreakers
**Modes:** `recruitment` (2 columns) / `marketing` or `universal` (3 columns)
**Cost:** ~$0.15 per 100 leads
**Test first:** `--dry-run --limit 5` before full run!
