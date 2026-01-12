# Quick Workflow Prompts
> Copy-paste templates để gọi 12 workflows của Anti-Gravity Framework

---

## 📊 LEAD GENERATION WORKFLOWS

### 1. Scrape Leads (Apify + Email Verification)

**Template:**
```
Scrape [NUMBER] [INDUSTRY] leads in [LOCATION]
```

**Examples:**
```
Scrape 50 marketing agency leads in United States
Scrape 100 IT recruitment companies in United Arab Emirates
Scrape 30 dentist leads in New York, valid emails only
```

**Modifiers:**
- Add `skip test` to skip 25-lead validation
- Add `valid only` to export only verified emails
- Add `with icebreakers` for AI-generated openers

**Output:** Google Sheet with verified emails + personalized icebreakers

**Script:** `execution/scrape_apify_leads.py`
**Directive:** [directives/scrape_leads.md](directives/scrape_leads.md)

---

### 2. Scrape Google Maps Leads

**Template:**
```
Scrape [NUMBER] [BUSINESS_TYPE] from Google Maps in [LOCATION]
```

**Examples:**
```
Scrape 100 medical spas from Google Maps in Los Angeles
Scrape 50 aesthetic clinics from Google Maps in Miami
Scrape recruitment agencies from Google Maps in London UK
```

**Output:** Google Sheet with business info + enriched emails (AnyMailFinder)

**Script:** `execution/scrape_google_maps.py`
**Directive:** [directives/scrape_google_maps_leads.md](directives/scrape_google_maps_leads.md)

---

### 3. Scrape Indeed Jobs

**Template:**
```
Scrape [NUMBER] [JOB_TITLE] jobs from Indeed and find decision makers
```

**Examples:**
```
Scrape 50 software engineer jobs from Indeed
Find 30 sales manager positions with hiring manager contacts
Scrape 100 marketing jobs with CEO info
```

**Output:** Jobs + decision maker info (CEO/Founder/HR Director)

**Script:** `execution/scrape_indeed_jobs.py`
**Directive:** [directives/scrape_jobs_Indeed_decision_makers.md](directives/scrape_jobs_Indeed_decision_makers.md)

---

### 4. Scrape LinkedIn Jobs

**Template:**
```
Scrape [NUMBER] LinkedIn jobs for [JOB_TITLE] in [LOCATION]
```

**Examples:**
```
Scrape 100 LinkedIn jobs for marketing manager in San Francisco
Find 50 software engineer positions on LinkedIn in New York
Scrape remote product manager jobs
```

**Output:** LinkedIn job postings with company info

**Script:** `execution/scrape_linkedin_jobs.py`
**Directive:** [directives/scrape_linkedin_jobs.md](directives/scrape_linkedin_jobs.md)

---

## ✉️ EMAIL & OUTREACH WORKFLOWS

### 5. Generate Custom Cold Email Copy

**Template:**
```
Generate cold email copy for [CLIENT_WEBSITE]
Targeting: [ICP/INDUSTRY]
Framework: [Anti-Fragile | Connector Angle | Both]
```

**Examples:**
```
Generate connector angle emails for wellcopy.co targeting ecommerce brands
Create anti-fragile email templates for myoprocess.com targeting dental clinics
Write custom copy for gtvseo.com using both frameworks
```

**Output:** 3+ email variants with follow-ups optimized for 15-25% reply rates

**Frameworks:**
- **Anti-Fragile Method:** AI fills variables in human-written templates
- **Connector Angle:** Position as helpful introducer, not seller

**Script:** `execution/generate_custom_copy.py`
**Directive:** [directives/generate_custom_copy.md](directives/generate_custom_copy.md)

---

### 6. Enrich Leads (Google Sheet)

**Template:**
```
Enrich Google Sheet [SHEET_ID] with decision makers and emails
```

**Examples:**
```
Enrich sheet 1abc123xyz with decision maker info and personalized openers
Add CEO contacts and emails to sheet 1def456uvw
Find founders and generate messages for sheet 1ghi789rst
```

**Process:**
1. Find CEO/Founder via LinkedIn search
2. Get emails via AnyMailFinder
3. Generate personalized messages (5 opener families)

**Output:** Updated Google Sheet with DM info + emails + personalized openers

**Script:** `execution/enrich_leads.py`
**Directive:** [directives/enrich_leads.md](directives/enrich_leads.md)

---

### 7. Send Email (Gmail API)

**Template:**
```
Draft email to [EMAIL] about [SUBJECT]
```

**Examples:**
```
Draft email to john@company.com introducing our service
Send email to leads@startup.com with proposal
Create draft for partnership inquiry to ceo@agency.com
```

**Safety:**
- **Default:** DRAFT mode (safe, creates Gmail draft)
- **Send mode:** Use "send" keyword explicitly (requires confirmation)

**Usage:**
```bash
# Draft Mode (Recommended)
python3 execution/send_email.py --to "lead@example.com" --subject "Hello" --body "Hi there" --mode draft

# Send Mode (Careful!)
python3 execution/send_email.py --to "lead@example.com" --subject "Hello" --body "Hi there" --mode send
```

**Script:** `execution/send_email.py`
**Directive:** [directives/email_workflow.md](directives/email_workflow.md)

---

### 8. Reply to Email

**Template:**
```
Reply to [EMAIL_ID] with [MESSAGE]
```

**Examples:**
```
Reply to latest email from john@company.com
Draft response to email thread about partnership
Reply to inquiry from yesterday with proposal details
```

**Script:** `execution/reply_email.py`
**Directive:** [directives/email_workflow.md](directives/email_workflow.md)

---

### 9. Connector Replies (Response Framework)

**Template:**
```
Generate connector-style reply for [SITUATION]
```

**Examples:**
```
Write connector reply for interested prospect
Draft follow-up for no response after 3 days
Create response for "not interested right now"
Reply to "tell me more about your service"
```

**Strategy:** Helpful introducer positioning (not sales-y)

**Directive:** [directives/connector_replies.md](directives/connector_replies.md)

---

## 🔍 VERIFICATION & ANALYTICS WORKFLOWS

### 10. Verify Apollo Emails (Google Sheet)

**Template:**
```
Verify emails in Google Sheet [SHEET_ID] using Apollo
```

**Examples:**
```
Verify all emails in sheet 1abc123xyz
Check email validity for Apollo export sheet
Validate email list in sheet 1def456uvw
```

**Output:** Email status (Valid/Invalid/Catch-All/Unknown)

**Script:** `execution/verify_apollo_sheet.py`
**Directive:** [directives/verify_apollo_emails.md](directives/verify_apollo_emails.md)

---

### 11. Instantly Campaign Analytics Report

**Template:**
```
Get analytics report for Instantly campaign [CAMPAIGN_ID]
```

**Examples:**
```
Show me stats for all active campaigns
Generate report for campaign abc123
Analytics for campaign "Q4 Outreach"
```

**Metrics:**
- Opens, clicks, replies
- Bounces, unsubscribes
- Conversion rates
- Reply rate trends

**Script:** `execution/email_campaign_report.py`
**Directive:** [directives/instantly_analytics_report.md](directives/instantly_analytics_report.md)

---

### 12. Single Campaign Deep Dive

**Template:**
```
Detailed analytics for campaign [CAMPAIGN_ID]
```

**Examples:**
```
Deep dive into campaign performance for abc123
Show reply rate and conversion funnel for latest campaign
Analyze email sequence performance for "Winter Campaign"
```

**Output:** Comprehensive performance breakdown with optimization suggestions

**Script:** `execution/single_campaign_report.py`
**Directive:** [directives/instantly_analytics_report.md](directives/instantly_analytics_report.md)

---

## 🎯 COMBO WORKFLOWS (Multi-Step Sequences)

### Full Lead Gen → Outreach Pipeline

```
1. Scrape 100 marketing agencies in US
2. Verify emails
3. Generate custom copy for [my_website]
4. Draft emails to top 20 valid leads
```

*4-step combo - I'll execute sequentially with progress updates*

---

### Google Maps → Enrichment → Email

```
1. Scrape 50 medical spas from Google Maps in LA
2. Enrich with decision maker info
3. Generate personalized openers
4. Export to Google Sheet with all data
```

*Full pipeline from search to enriched export*

---

### Indeed Jobs → Decision Makers → Outreach

```
1. Scrape 100 software engineer jobs from Indeed
2. Find hiring managers for each company
3. Generate connector angle emails
4. Create Gmail drafts for top 30 targets
```

*Recruitment outreach automation*

---

## 🔧 SUB-AGENT PROMPTS

### First Agent (API Research)

**Template:**
```
Research [API_NAME] API documentation

Focus on:
- Authentication method
- [SPECIFIC_ENDPOINTS] endpoints
- Rate limits
- Required parameters
```

**Examples:**
```
Research Apollo API documentation
Research SSMasters API focusing on email verification endpoints
Research Apify Leads Finder actor API
```

---

### Code Reviewer (Quality Audit)

**Template:**
```
Review execution/[SCRIPT_NAME].py against directives/[DIRECTIVE_NAME].md

Focus on:
- Security vulnerabilities (API key exposure, injection risks)
- Efficiency opportunities (parallelization, batch APIs)
- Directive alignment (does code match SOP?)
- Production readiness (error handling, timeouts)
```

**Examples:**
```
Review execution/scrape_apify_leads.py
Audit execution/enrich_leads.py for security issues
Check execution/generate_custom_copy.py before commit
```

---

### Documentation Agent (Capture Learning)

**Template:**
```
Update directives/[DIRECTIVE_NAME].md with this learning:

Trigger: [error_fixed | script_modified | successful_workflow]
Error: [ERROR_MESSAGE]
Solution: [WHAT_WAS_CHANGED]
Script: execution/[SCRIPT_NAME].py
Impact: [MEASURABLE_IMPROVEMENT]
Title: [SHORT_DESCRIPTION]
```

**Examples:**
```
Update directives/scrape_leads.md with this learning:
Trigger: error_fixed
Error: Azure OpenAI 400 - Content filter triggered
Solution: Added sanitize_input() function
Script: execution/scrape_apify_leads.py
Impact: 0% lead loss (was 6% before)
Title: Content Filter Protection
```

---

## 📋 QUICK REFERENCE MATRIX

| Workflow | Quick Prompt | Output | Time |
|----------|--------------|--------|------|
| **Scrape Leads** | `Scrape 50 [industry] in [location]` | Google Sheet | 2-5 min |
| **Google Maps** | `Scrape [business] from Maps in [city]` | Sheet + Emails | 3-7 min |
| **Indeed Jobs** | `Scrape [number] [job] jobs from Indeed` | Jobs + DMs | 5-10 min |
| **Custom Copy** | `Generate emails for [website] targeting [ICP]` | 3+ variants | 3-5 min |
| **Enrich Sheet** | `Enrich sheet [ID] with DMs + emails` | Updated Sheet | 5-15 min |
| **Email Draft** | `Draft email to [email] about [topic]` | Gmail Draft | <1 min |
| **Verify Emails** | `Verify emails in sheet [ID]` | Valid/Invalid | 2-5 min |
| **Campaign Report** | `Analytics for campaign [ID]` | Stats Report | 1-2 min |

---

## 💡 PRO TIPS & MODIFIERS

### Workflow Modifiers

**Scraping:**
- `skip test` - Skip 25-lead validation phase (faster)
- `valid only` - Export only verified emails
- `with icebreakers` - Include AI-generated openers
- `max [number]` - Limit results

**Email:**
- `draft mode` - Safe mode, creates Gmail draft (default)
- `send now` - Actually send emails (use carefully, requires confirmation)
- `batch send` - Send to multiple recipients

**Quality:**
- `strict validation` - Higher quality thresholds
- `fast mode` - Skip enrichment steps
- `full enrichment` - Maximum data collection

---

### Specify Details for Best Results

**✅ DO:**
```
Scrape 100 marketing agency leads in United States with valid emails
Generate connector angle emails for wellcopy.co targeting ecommerce brands with $1M+ revenue
Verify emails in sheet 1abc123xyz using strict validation
```

**❌ DON'T:**
```
Get some leads
Make emails
Check the sheet
```

**Why:** Specific = faster execution, better results, fewer iterations

---

### Location Format Rules

**Apify APIs require lowercase:**
- ✅ "united states"
- ✅ "united arab emirates"
- ❌ "United States" (will fail)
- ❌ "UAE" (use full name)

**Google Maps accepts normal case:**
- ✅ "Los Angeles, CA"
- ✅ "London, UK"

---

### Chain Workflows for Complex Tasks

**Instead of 4 separate requests:**
```
1. "Scrape 100 leads"
2. "Verify the emails"
3. "Generate copy"
4. "Draft emails"
```

**Do this (1 request):**
```
Scrape 100 marketing agencies → verify emails → generate copy → draft top 20 emails
```

**I'll execute sequentially with checkpoints!**

---

## 🚨 IMPORTANT REMINDERS

### Email Sending Safety
- **Default mode:** DRAFT (creates Gmail draft, safe)
- **Send mode:** Requires explicit "send" keyword + confirmation
- **Rate limits:** Gmail ~2000/day (paid), ~500/day (free)

### API Rate Limits
- **Apify:** Depends on plan (check dashboard)
- **SSMasters:** ~30 req/min (batch mode recommended)
- **Apollo:** Credits-based (check balance)
- **AnyMailFinder:** Credits per email found

### Data Quality Thresholds
- **Email presence:** ≥85% of leads should have emails
- **Valid email rate:** Typically 30-50% of found emails
- **Industry match:** ≥80% relevance (when validation enabled)
- **Icebreaker quality:** 100% of valid emails get personalized openers

---

## 🔗 Related Documentation

- [CLAUDE.md](CLAUDE.md) - DO Framework overview
- [ARCHITECTURE.md](.claude/agents/ARCHITECTURE.md) - Sub-agent system architecture
- [directives/](directives/) - All workflow SOPs
- [execution/](execution/) - Python scripts
- [.claude/agents/](.claude/agents/) - Sub-agent definitions

---

**Version:** 1.0
**Last Updated:** 2025-12-25
**Maintainer:** Main Orchestrator Agent

**Need help?** Just ask:
- "Show me examples for [workflow]"
- "What modifiers can I use with [workflow]?"
- "How do I chain [workflow A] with [workflow B]?"
