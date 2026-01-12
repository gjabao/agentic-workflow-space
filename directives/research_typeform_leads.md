# Directive: Research Typeform Leads & Generate Apollo URLs

> **Version:** 1.0
> **Last Updated:** 2025-12-26
> **Status:** Active

## Goal/Objective

Analyze client profile data from Typeform submissions (or markdown profiles), extract Ideal Customer Profile (ICP) details, and generate Apollo.io search URLs for multiple target audiences (direct end users, partners, agencies, etc.).

---

## Required Inputs

| Input | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| `profile_text` | string/file | Yes | Client profile markdown or text | Can be file path or raw text |
| `output_format` | string | No | "markdown" (default), "json" | Output format |
| `max_audiences` | integer | No | 3 | Maximum number of target audiences to generate |

---

## Execution Tools

**Primary Script:** `execution/research_typeform_lead.py`

**Dependencies:**
- Azure OpenAI API (ICP extraction & analysis)
- urllib.parse (Apollo URL encoding)

---

## Expected Outputs

### ICP Analysis Structure

For each client profile, generate:

1. **Company Overview**
   - Company name, website, contact info
   - Business model & average deal size
   - Location & company size

2. **Target Audiences (1-3 personas)**
   - Audience name (e.g., "Direct End Users", "Conference Organizers")
   - Job titles to target
   - Company criteria (size, industry, location)
   - Pain points & trigger signals
   - Apollo.io search URL (fully encoded)

3. **Messaging Framework**
   - Core positioning
   - Key value propositions
   - Connector angle

---

## Output Format Example

```markdown
# [Company Name] - ICP Research

## Company Overview
- **Company:** [Name]
- **Website:** [URL]
- **Business Model:** [Description]
- **Average Deal Size:** [Range]

## Target Audience #1: [Persona Name]

**Job Titles:**
- [Title 1]
- [Title 2]
- [Title 3]

**Company Criteria:**
- Size: [Range]
- Industry: [Keywords]
- Location: [Regions]

**Pain Points:**
- [Pain 1]
- [Pain 2]

**Apollo Search URL:**
[Encoded Apollo URL]

---

## Target Audience #2: [Persona Name]
[Same structure]

---

## Messaging Framework
[Key positioning & value props]
```

---

## Process Flow

### 1. Input Validation
- Check if input is file path or raw text
- If file path → read file content
- Validate profile has minimum required info (company name, business model)

### 2. ICP Extraction (Azure OpenAI)
- **Prompt strategy:** Extract structured ICP data from unstructured profile
- **Model:** gpt-4o
- **Temperature:** 0.3 (high precision for data extraction)
- **Output format:** JSON with structured fields

**Extraction targets:**
- Company info (name, website, size, location)
- Business model & deal size
- Target audiences (personas)
- Job titles per persona
- Company criteria (size ranges, industries, locations)
- Pain points & value propositions

### 3. Apollo URL Generation
For each target audience, construct Apollo.io search URL with:
- **Job titles** → `personTitles[]`
- **Locations** → `personLocations[]`
- **Company size** → `organizationNumEmployeesRanges[]`
- **Industry keywords** → `qOrganizationKeywordTags[]`
- **Email verification** → `contactEmailStatusV2[]=verified`
- **Sorting** → `sortByField=recommendations_score&sortAscending=false`

**URL encoding:** Use `urllib.parse.quote()` for special characters

### 4. Output Formatting
- Generate markdown report with all audiences
- Include clickable Apollo URLs
- Show company overview & messaging framework
- Optional: Export as JSON for programmatic use

---

## Apollo URL Structure

**Base URL:**
```
https://app.apollo.io/#/people?page=1
```

**Required Parameters:**
- `contactEmailStatusV2[]=verified` (verified emails only)
- `personTitles[]=[Title]` (job titles, URL encoded)
- `personLocations[]=[Location]` (countries/regions)
- `organizationNumEmployeesRanges[]=[Range]` (e.g., "101,500")
- `qOrganizationKeywordTags[]=[Keyword]` (industry keywords)
- `sortByField=recommendations_score&sortAscending=false`

**Company Size Ranges:**
- 1-10
- 11-50
- 51-100
- 101-500
- 501-1000
- 1001-5000
- 5001-10000
- 10001+

---

## Edge Cases & Constraints

### Profile Quality
- **Missing company name:** Return error, ask for clarification
- **Vague business model:** AI will infer from context (flag uncertainty)
- **No target audience:** AI will suggest based on business model

### Apollo URL Length
- **Max URL length:** ~2000 characters (browser limit)
- **Mitigation:** Limit to 5 job titles + 3 keywords per URL
- **Alternative:** Generate multiple URLs if criteria too complex

### Location Normalization
- "USA" → "United States"
- "Canada" → "Canada"
- "UK" → "United Kingdom"
- Apollo uses full country names

### Company Size Mapping
- "101-500" → `organizationNumEmployeesRanges[]=101,500`
- "Fortune 500" → `organizationNumEmployeesRanges[]=1001,5000&organizationNumEmployeesRanges[]=5001,10000`
- "Small businesses" → `organizationNumEmployeesRanges[]=1,10&organizationNumEmployeesRanges[]=11,50`

---

## Quality Thresholds

- **ICP extraction accuracy:** ≥90% (manual validation on test cases)
- **Apollo URL validity:** 100% (all URLs must be clickable & functional)
- **Target audiences:** 1-3 per profile (avoid overwhelming user)
- **Job titles per audience:** 3-6 (Apollo sweet spot)
- **Keywords per audience:** 2-5 (precise targeting)

---

## Error Recovery

| Error Type | Detection | Recovery Action |
|-----------|-----------|-----------------|
| Missing Azure API key | Env var check | Show error with .env setup instructions |
| Invalid profile format | Parsing failure | Request structured input (company name, business model required) |
| OpenAI rate limit | 429 response | Retry with exponential backoff (3 attempts) |
| OpenAI content filter | 400 + jailbreak error | Sanitize input text, remove special chars |
| Empty extraction | No ICP data returned | Prompt user for more details in profile |

---

## Performance Targets

| Profile Complexity | Expected Duration | Breakdown |
|-------------------|-------------------|-----------|
| Simple (1 audience) | 5-8s | OpenAI: 4s, URL gen: 1s, Format: 1s |
| Medium (2 audiences) | 8-12s | OpenAI: 6s, URL gen: 2s, Format: 2s |
| Complex (3 audiences) | 12-18s | OpenAI: 10s, URL gen: 3s, Format: 3s |

---

## Usage Example

**User input:**
```
"Research this Typeform lead: [paste Beaumont Exhibits profile]"
```

**Agent execution:**
```bash
python3 execution/research_typeform_lead.py \
  --profile_text "Beaumont Exhibits - Client Profile..." \
  --output_format markdown \
  --max_audiences 3
```

**Output:**
```
✓ Profile analyzed
✓ Extracted 3 target audiences
✓ Generated 3 Apollo URLs

# Beaumont Exhibits - ICP Research

## Target Audience #1: Direct End Users (Trade Show Managers)
Apollo URL: https://app.apollo.io/#/people?page=1&contactEmailStatusV2[]=verified&personTitles[]=Trade%20Show%20Manager...

## Target Audience #2: Conference Organizers
Apollo URL: https://app.apollo.io/#/people?page=1&contactEmailStatusV2[]=verified&personTitles[]=CEO&personTitles[]=Founder...

## Target Audience #3: Marketing Agencies
Apollo URL: https://app.apollo.io/#/people?page=1&contactEmailStatusV2[]=verified...
```

---

## Learnings & Optimizations

### 2025-12-26: Version 1.0 - Initial Implementation
- **Created:** Directive + execution script for Typeform lead research
- **AI-powered ICP extraction:** Azure OpenAI parses unstructured profiles
- **Multi-audience support:** Generates 1-3 Apollo URLs per profile
- **URL encoding:** Proper handling of special characters in titles/keywords
- **Deliverable format:** Markdown output with clickable URLs

### Best Practices
- Include as much detail in profile as possible (business model, deal size, pain points)
- Specify target audience hints if known (e.g., "They sell to Fortune 500")
- Review AI-extracted ICP before using Apollo URLs (validate job titles match reality)
- For complex ICPs, generate separate URLs per sub-audience (better Apollo performance)

---

## Integration with Existing Workflows

### Typeform → Lead Research → Apollo Scraping
1. **Typeform submission** → Webhook triggers this workflow
2. **Research workflow** → Generates Apollo URLs (this directive)
3. **Scrape workflow** → Use `directives/scrape_leads.md` with Apollo URLs to get leads
4. **Enrichment workflow** → Use `directives/enrich_leads.md` to validate emails
5. **Campaign workflow** → Use `directives/email_workflow.md` to send cold emails

### Manual Usage
1. User submits Typeform with client profile
2. User pastes profile text to agent: "Research this lead"
3. Agent generates ICP + Apollo URLs
4. User clicks Apollo URL → exports leads → imports to CRM

---

**Next Steps:** Build execution script (`execution/research_typeform_lead.py`)
