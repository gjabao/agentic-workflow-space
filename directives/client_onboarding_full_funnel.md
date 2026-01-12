---
name: client-onboarding-full-funnel
description: End-to-end client onboarding workflow. Use when a new client fills out the onboarding form (Typeform). Automatically processes client profile, generates ICP research with Apollo URLs, scrapes qualified leads, generates personalized cold email copy, and prepares campaign-ready deliverables. Transforms client intake → campaign-ready assets in one command.
---

# Client Onboarding Full Funnel Workflow

> **Version:** 1.0
> **Last Updated:** 2025-12-29
> **Status:** Active
> **Trigger:** Client fills out onboarding form (Typeform/Manual submission)

## Goal/Objective

Transform a raw client onboarding form into campaign-ready deliverables in a single automated workflow:

1. **Research** → Extract ICP, generate Apollo URLs
2. **Scrape** → Get qualified leads with verified emails
3. **Copywrite** → Generate personalized cold email copy
4. **Deliver** → Export to Google Sheets + Markdown files ready for Instantly

---

## Required Inputs

| Input | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `client_profile` | string/file | Yes | Onboarding form text or file path | From Typeform or manual input |
| `leads_per_audience` | integer | No | 50 (default) | Leads to scrape per target audience |
| `num_email_variants` | integer | No | 3 (default) | Email copy variants to generate |
| `skip_scrape` | boolean | No | false | Skip scraping (research only) |
| `valid_only` | boolean | No | true | Export only verified emails |

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT ONBOARDING FORM                               │
│                    (Typeform / Manual Submission)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: ICP RESEARCH                                                       │
│  ────────────────────                                                        │
│  Script: execution/research_typeform_lead.py                                 │
│                                                                              │
│  Input:  Client profile text                                                 │
│  Output:                                                                     │
│    • Company overview                                                        │
│    • 1-3 Target audiences with:                                              │
│      - Job titles                                                            │
│      - Company criteria (size, industry, location)                           │
│      - Pain points                                                           │
│      - Apollo.io search URLs (fully encoded)                                 │
│    • Messaging framework                                                     │
│                                                                              │
│  Saved to: .tmp/icp_research_{client_name}.md                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: LEAD SCRAPING (Per Audience)                                       │
│  ─────────────────────────────────────                                       │
│  Script: execution/scrape_apify_leads.py                                     │
│                                                                              │
│  For EACH target audience from Phase 1:                                      │
│    • Extract filters from ICP (job titles, industries, locations, sizes)     │
│    • Run Apify leads-finder with filters                                     │
│    • Verify emails with SSMasters (Valid/Invalid/Catch-All)                  │
│    • Generate SSM Connector icebreakers for valid emails                     │
│    • AI-filter for industry relevance                                        │
│                                                                              │
│  Output per audience:                                                        │
│    • Google Sheet with leads + icebreakers                                   │
│    • CSV backup in .tmp/                                                     │
│                                                                              │
│  Quality thresholds:                                                         │
│    • Email presence: ≥85%                                                    │
│    • Valid email rate: 30-50%                                                │
│    • Industry match: ≥80%                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: COPY GENERATION                                                    │
│  ────────────────────────                                                    │
│  Script: execution/generate_custom_copy.py (or manual with directive)        │
│                                                                              │
│  Input:                                                                      │
│    • Client website URL                                                      │
│    • ICP pain points from Phase 1                                            │
│    • Target audience context                                                 │
│                                                                              │
│  Process:                                                                    │
│    1. Analyze client website                                                 │
│    2. Research 5-10 competitors                                              │
│    3. Synthesize pain points (operator-style)                                │
│    4. Generate 3+ email variants using:                                      │
│       - Connector Angle (matchmaker positioning)                             │
│       - SSM SOP openers (6 rotation patterns)                                │
│       - Spartan/Laconic tone (no jargon, <100 words)                         │
│       - Anti-Fragile Method (AI fills variables)                             │
│                                                                              │
│  Output:                                                                     │
│    • Markdown file: custom_copy_{client_name}.md                             │
│    • Contains: Subject lines, bodies, follow-ups (Day 3, Day 7)              │
│                                                                              │
│  Saved to: .tmp/custom_copy_{client_name}.md                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: DELIVERABLES SUMMARY                                               │
│  ────────────────────────────────                                            │
│                                                                              │
│  Final outputs for client:                                                   │
│                                                                              │
│  1. ICP Research Document                                                    │
│     └─ .tmp/icp_research_{client_name}.md                                    │
│        • Company overview                                                    │
│        • Target audiences with Apollo URLs                                   │
│        • Messaging framework                                                 │
│                                                                              │
│  2. Lead Sheets (per audience)                                               │
│     └─ Google Sheet: "Leads - {Audience} - {Date}"                           │
│        • Company, Contact, Email, Verification Status                        │
│        • SSM Icebreaker (personalized opener)                                │
│        • LinkedIn, Phone, Website                                            │
│                                                                              │
│  3. Cold Email Copy                                                          │
│     └─ .tmp/custom_copy_{client_name}.md                                     │
│        • 3+ email variants with subjects                                     │
│        • Follow-up sequences (Day 3, Day 7)                                  │
│        • Ready for Instantly upload                                          │
│                                                                              │
│  4. Campaign Summary                                                         │
│     └─ .tmp/campaign_summary_{client_name}.md                                │
│        • Total leads scraped                                                 │
│        • Valid emails count                                                  │
│        • Estimated campaign value                                            │
│        • Next steps                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Execution Tools

| Phase | Script | Purpose |
|-------|--------|---------|
| 0 | `execution/clickup_onboard_client.py` | Create client task + subtasks in ClickUp |
| 1 | `execution/research_typeform_lead.py` | ICP extraction + Apollo URL generation |
| 2 | `execution/scrape_apify_leads.py` | Lead scraping + email verification + icebreakers |
| 3 | `execution/generate_custom_copy.py` | Cold email copy generation |
| 4 | Manual summary | Compile deliverables |

---

## Phase 0: ClickUp Task Creation (NEW)

Before starting any work, create a client record in ClickUp with all onboarding subtasks:

```bash
python3 execution/clickup_onboard_client.py \
  --client "Client Name" \
  --website "https://client.com" \
  --contact "Contact Name" \
  --deal-size "$50K+" \
  --notes "Additional notes" \
  --list-id "YOUR_CLICKUP_LIST_ID" \
  --tags "client" "onboarding"
```

### Discovery Commands (Find your list ID)

```bash
# Step 1: Find workspace ID
python3 execution/clickup_onboard_client.py --list-workspaces

# Step 2: Find space ID
python3 execution/clickup_onboard_client.py --list-spaces WORKSPACE_ID

# Step 3: Find folder ID
python3 execution/clickup_onboard_client.py --list-folders SPACE_ID

# Step 4: Find list ID
python3 execution/clickup_onboard_client.py --list-lists FOLDER_ID
```

### What Gets Created

**Parent Task:** `🏢 Client Name`
- Client info (website, contact, deal size)
- Deliverables checklist with file paths
- Onboarded date

**8 Subtasks (Onboarding Workflow):**

| # | Subtask | Priority | Description |
|---|---------|----------|-------------|
| 1 | 📋 ICP Research & Apollo URLs | High | Extract target audiences from client profile, generate Apollo search URLs |
| 2 | 🎯 Scrape Leads (Audience 1) | High | Run lead scraper for primary audience, verify emails, generate icebreakers |
| 3 | 🎯 Scrape Leads (Audience 2) | Normal | Run lead scraper for secondary audience if applicable |
| 4 | 📧 Generate Cold Email Copy | High | Analyze website, research competitors, generate 3+ email variants with Connector Angle |
| 5 | ✅ Quality Check: ≥50 Valid Emails | High | Ensure at least 50 valid emails before proceeding to campaign |
| 6 | 🚀 Setup Instantly Campaign | Urgent | Import leads, create campaign, set up follow-up sequence |
| 7 | 📤 Launch Campaign | Urgent | Test deliverability, launch campaign, notify client |
| 8 | 📊 Monitor & Report (48h check) | Normal | Check opens/replies after 48h, handle positive responses |

**Total: 1 parent task + 8 subtasks = 9 tasks created**

---

## Example Usage

### Input: Client Onboarding Form

```markdown
# Beaumont Exhibits - Client Profile

## Company Information
- Company: Beaumont Exhibits
- Website: https://beaumontandco.ca
- Contact: Sean Court

## Business Model
Produce trade show exhibits for companies exhibiting at trade shows and events across Canada and the USA.

## Deal Size
- Standard booth rental: ~$50K CAD
- Large/repeat clients: $500K CAD
- ABM partnerships: $1M+ CAD potential

## Target Markets
### Primary: End Users (Direct Clients)
- Fortune 500 and high-growth companies attending large trade shows
- Booth Size: Minimum 10x20ft
- Decision Makers: Trade show managers, event managers, marketing directors

### Secondary: Partners/ABM
- Conference organizers
- Marketing agencies
- Event management companies

## Unique Value Proposition
- Fast & High-Quality Design
- Full-Service, Bespoke Client Care
- 100% Pre-Show Build Guarantee
- High-End Custom Fabrication

## Buyer Pain Points
- Urgent timelines (<90 days)
- Complex logistics management
- Quality gaps with current vendors
- Risk of booth failures
```

### Execution Command

```bash
# Full workflow
python3 execution/research_typeform_lead.py \
  --profile_file ".tmp/beaumont_profile.md" \
  --max_audiences 3 \
  --output_file ".tmp/icp_research_beaumont.md"

# Then for each audience, run:
python3 execution/scrape_apify_leads.py \
  --industry "Trade Show" \
  --fetch_count 50 \
  --job_title "Trade Show Manager" "Event Manager" "Marketing Director" \
  --location "united states" "canada" \
  --company_size "501-1000" "1001-2000" "2001-5000" \
  --skip_test \
  --valid_only

# Then generate copy:
python3 execution/generate_custom_copy.py \
  --client_url "https://beaumontandco.ca" \
  --num_variants 3
```

### Expected Output

```
✓ PHASE 1: ICP Research Complete
  → 3 target audiences identified
  → 3 Apollo URLs generated
  → Saved: .tmp/icp_research_beaumont.md

✓ PHASE 2: Lead Scraping Complete
  → Audience 1 (Trade Show Managers): 47 leads, 22 valid emails
  → Audience 2 (Conference Organizers): 52 leads, 28 valid emails
  → Audience 3 (Marketing Agencies): 45 leads, 19 valid emails
  → Total: 144 leads, 69 valid emails (48%)
  → Google Sheets: [3 links]

✓ PHASE 3: Copy Generation Complete
  → 3 email variants generated
  → Connector angle applied
  → SSM openers ready
  → Saved: .tmp/custom_copy_beaumont.md

✓ WORKFLOW COMPLETE!
  📊 Total leads: 144
  📧 Valid emails: 69 (48%)
  📝 Email variants: 3
  ⏱️ Duration: 8m 32s

  Deliverables:
  1. ICP Research: .tmp/icp_research_beaumont.md
  2. Leads Sheet 1: [Google Sheet URL]
  3. Leads Sheet 2: [Google Sheet URL]
  4. Leads Sheet 3: [Google Sheet URL]
  5. Cold Email Copy: .tmp/custom_copy_beaumont.md
```

---

## ICP Extraction Details

### From Client Profile, Extract:

| Field | Source | Apollo Parameter |
|-------|--------|------------------|
| Job Titles | "Decision Makers" section | `personTitles[]` |
| Company Size | "Fortune 500", "high-growth" | `organizationNumEmployeesRanges[]` |
| Industries | Business model description | `qOrganizationKeywordTags[]` |
| Locations | Target markets | `personLocations[]` |
| Pain Points | Buyer pain points section | Used for copy |

### Apollo URL Structure

```
https://app.apollo.io/#/people?page=1
  &contactEmailStatusV2[]=verified
  &personTitles[]=Trade%20Show%20Manager
  &personTitles[]=Event%20Manager
  &personTitles[]=Marketing%20Director
  &personLocations[]=United%20States
  &personLocations[]=Canada
  &organizationNumEmployeesRanges[]=501,1000
  &organizationNumEmployeesRanges[]=1001,5000
  &qOrganizationKeywordTags[]=trade%20show
  &qOrganizationKeywordTags[]=exhibition
  &sortByField=recommendations_score
  &sortAscending=false
```

---

## Lead Scraping Configuration

### Beaumont Exhibits Example:

**Audience 1: Trade Show Managers**
```python
{
  "industry": "Trade Show",
  "fetch_count": 50,
  "job_title": ["Trade Show Manager", "Event Manager", "Tradeshow Coordinator", "Exhibits Manager"],
  "location": "united states",
  "company_size": ["501-1000", "1001-2000", "2001-5000", "5001-10000"],
  "company_keywords": ["trade show", "exhibition", "convention", "expo", "conference exhibitor"],
  "skip_test": true,
  "valid_only": true
}
```

**Audience 2: Conference Organizers**
```python
{
  "industry": "Events",
  "fetch_count": 50,
  "job_title": ["CEO", "Founder", "Event Director", "Conference Director"],
  "company_industry": ["events services"],
  "company_size": ["11-50", "51-100", "101-200"],
  "skip_test": true,
  "valid_only": true
}
```

**Audience 3: Marketing Agencies**
```python
{
  "industry": "Marketing Agency",
  "fetch_count": 50,
  "job_title": ["CEO", "Managing Director", "VP of Client Services"],
  "company_industry": ["marketing & advertising"],
  "company_size": ["11-50", "51-100", "101-200"],
  "skip_test": true,
  "valid_only": true
}
```

---

## Cold Email Copy Output

### Expected Format (custom_copy_beaumont.md):

```markdown
# Custom Copy for Beaumont Exhibits

## 1. Client Overview
- **Business:** Beaumont Exhibits
- **Description:** Trade show exhibit production for Fortune 500 companies
- **Target ICP:** Trade show managers, event managers, marketing directors
- **Key Offer:** Full-service trade show management with 100% pre-show build guarantee

## 2. Competitor Analysis (5 Companies)
1. **Freeman:** Full-service event solutions, enterprise focus
2. **GES:** Global exhibition services, tech-forward
3. **Skyline:** Modular exhibit solutions, mid-market
...

## 3. ICP Pain Points (Ranked)
1. Can't find vendors who deliver quality on tight timelines
2. Waste hours managing logistics across multiple vendors
3. Risk of booth failures at critical shows
4. Struggle to get custom fabrication without enterprise pricing
5. No visibility into build progress until event day

## 4. Email Variants

### Variant A: Problem-Solving Connector

**Subject:** quick question about your next show

**Body:**
<p>Hey {{firstName}},</p>
<p>Noticed {{companyName}} exhibits at major trade shows — I know a few marketing directors who can't find vendors who deliver quality on tight timelines</p>
<p>I know someone who does pre-show builds so you see the booth before the event — recently helped a Fortune 500 cut their logistics stress by 80%</p>
<p>Worth exploring</p>
<p>Sent from my iPhone</p>

**Follow-up 1 (Day 3):**
Hey {{firstName}}, worth intro'ing you

**Follow-up 2 (Day 7):**
Hey {{firstName}}, maybe this isn't something you're interested in — wishing you the best

---

### Variant B: Opportunity Connector
[...]

### Variant C: Authority Connector
[...]
```

---

## Quality Thresholds

| Metric | Threshold | Action if Fail |
|--------|-----------|----------------|
| ICP extraction | ≥1 audience | Ask for more profile details |
| Apollo URL validity | 100% | Auto-fix URL encoding |
| Email presence | ≥85% | Refine job title filters |
| Valid email rate | ≥30% | Use SSMasters verification |
| Industry match | ≥80% | Add exclusion keywords |
| Copy usability | ≥80% | Manual review and edit |

---

## Error Recovery

| Error | Detection | Recovery |
|-------|-----------|----------|
| Missing client website | No URL in profile | Ask user for URL |
| Apollo URL too long | >2000 chars | Split into multiple URLs |
| Low email rate | <30% valid | Suggest different job titles |
| Scrape timeout | >5 min | Reduce fetch_count, retry |
| Copy generation fail | Empty variants | Manual copy using directive |

---

## Performance Targets

| Phase | Expected Duration | Notes |
|-------|-------------------|-------|
| ICP Research | 10-20s | Single API call |
| Lead Scraping (per audience) | 60-120s | Depends on fetch_count |
| Email Verification | 30-60s | Parallel processing |
| Copy Generation | 60-90s | 3 variants |
| **Total (3 audiences)** | **8-12 minutes** | End-to-end |

---

## Integration with Other Workflows

### After This Workflow:

1. **Upload to Instantly**
   - Use `execution/upload_copy_to_instantly.py`
   - Or manually copy from markdown to Instantly campaigns

2. **Reply Handling**
   - Use `directives/connector_replies.md` for reply management
   - Classify: positive, neutral, skeptical, engaged

3. **Campaign Reporting**
   - Use `directives/instantly_analytics_report.md`
   - Track opens, replies, conversions

---

## Learnings & Optimizations

### 2025-12-29: Version 1.0 - Initial Implementation

- **Unified workflow:** Combines 3 separate workflows into one
- **Client profile parsing:** AI extracts structured ICP from unstructured form
- **Multi-audience support:** Generates separate lead lists per persona
- **Apollo URL optimization:** Keywords aligned with behavioral signals
- **SSM Connector integration:** Icebreakers follow 6-prompt rotation
- **Quality gates:** Validation at each phase before proceeding

### Best Practices

1. **Get detailed profiles:** More detail = better targeting
2. **Start with 25-50 leads:** Test before scaling
3. **Review ICP before scraping:** Validate job titles match reality
4. **Test copy before sending:** Read out loud for human tone
5. **Track by audience:** Different audiences may need different angles

---

## Checklist Before Running

- [ ] Client profile has company name & website
- [ ] Target audience is defined (who they sell to)
- [ ] Deal size/budget indicator present
- [ ] Pain points or differentiators listed
- [ ] API keys configured in `.env`:
  - [ ] AZURE_OPENAI_API_KEY
  - [ ] AZURE_OPENAI_ENDPOINT
  - [ ] APIFY_API_KEY
  - [ ] SSMASTERS_API_KEY (optional)
- [ ] Google OAuth configured (credentials.json, token.json)

---

**Next Steps:** After running this workflow, upload leads + copy to Instantly and start campaign!
