# Onboarding Workflow - Quick Start Guide

> LinkedIn Connector Service - Automated Client Onboarding

## Overview

This workflow automates the complete client onboarding process from payment to Month 1 completion, following your SOP from the Excalidraw diagram.

---

## Setup

### 1. Install Dependencies

```bash
pip install slack-sdk google-auth google-auth-oauthlib google-api-python-client python-dotenv
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_WORKSPACE_ID=your-workspace-id

# ClickUp
CLICKUP_API_KEY=pk_your-api-key
CLICKUP_WORKSPACE_ID=your-workspace-id

# Google
GOOGLE_CREDENTIALS_PATH=credentials.json

# Email (Gmail SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Set Up API Credentials

#### Slack Bot Token:
1. Go to https://api.slack.com/apps
2. Create new app or use existing
3. Add permissions: `channels:manage`, `chat:write`, `users:read`
4. Install to workspace
5. Copy Bot User OAuth Token

#### ClickUp API Key:
1. Go to ClickUp Settings → Apps
2. Generate API Token
3. Copy to `.env`

#### Google Credentials:
1. Already configured in `credentials.json` and `token.json`
2. Ensure OAuth scopes include:
   - Google Sheets
   - Google Docs
   - Google Slides
   - Google Drive
   - Google Calendar

---

## Usage

### Start New Client Onboarding

```bash
python execution/onboarding_automation.py \
  --new-client "Acme Corporation" \
  --email "john@acmecorp.com" \
  --industry "SaaS" \
  --goals "Connect with 50 SaaS founders for partnerships"
```

This will automatically:
- ✅ Create Slack channel (#client-acme-corporation)
- ✅ Create ClickUp folder in "Active Clients"
- ✅ Generate client dashboard (Google Sheets)
- ✅ Create ICP document (Google Doc)
- ✅ Schedule onboarding call (Google Calendar)
- ✅ Send welcome email with all resources
- ✅ Post summary to Slack

**Target:** All tasks complete within 10 minutes ⏱️

---

### Check Onboarding Status

```bash
python execution/onboarding_automation.py --status "Acme Corporation"
```

Output:
```
============================================================
ONBOARDING STATUS: Acme Corporation
============================================================
Started: 2025-12-25T10:30:00
Phase: INTRA-ONBOARDING
Tasks completed: 7
Resources:
  Dashboard: https://docs.google.com/spreadsheets/d/...
  Slack: #client-acme-corporation
  ICP Doc: https://docs.google.com/document/d/...
============================================================
```

---

### Create Onboarding Tracker Sheet

```bash
python execution/onboarding_tracker.py --create "Acme Corporation"
```

This creates a comprehensive tracker with:
- **Progress Checklist:** All tasks from INTRA-ONBOARDING through Month 1
- **KPI Dashboard:** Real-time metrics vs. targets

---

### Update Task Progress

```bash
python execution/onboarding_tracker.py \
  --update "SPREADSHEET_ID" \
  --task "Industry landscape analysis" \
  --status "completed" \
  --assigned "VA Team" \
  --notes "Completed research, ICP ready for review"
```

Status options:
- `pending` → ⏳ Pending
- `in_progress` → 🔄 In Progress
- `completed` → ✅ Completed
- `blocked` → ❌ Blocked
- `failed` → ⚠️ Failed

---

### Update KPI Metrics

```bash
python execution/onboarding_tracker.py \
  --update-kpi "SPREADSHEET_ID" \
  --kpi "Connection Requests Sent" \
  --value "250"
```

This automatically:
- Updates current value
- Calculates progress percentage
- Updates status icon (⏳ → 🔄 → ✅)

---

## Workflow Phases

### Phase 1: INTRA-ONBOARDING (Day 0 - Within 10 minutes)

**Automated by:** `onboarding_automation.py --new-client`

**Tasks:**
1. Send contract confirmation email
2. Create ClickUp client folder
3. Create Slack channel
4. Schedule onboarding call (30 minutes)
5. Send welcome email with next steps
6. Send onboarding questionnaire
7. Create client dashboard (view-only ClickUp)

**Quality Threshold:** All 7 tasks completed within 10 minutes, zero manual intervention

---

### Phase 2: Week 1 - Days 1-2 (Research)

**Owner:** VA Team
**Reviewer:** Saad (Day 2 EOD)

**Tasks:**
1. Industry landscape analysis
2. Competitor connection research
3. Build ICP document
4. Map connector ecosystem
5. Tag Saad for "power" review

**Deliverables:**
- ICP document (Google Doc)
- Competitor analysis sheet (Google Sheets)
- Ecosystem map (Excalidraw/Miro)

---

### Phase 3: Week 1 - Days 3-4 (Strategy & Launch)

**Owner:** Team
**Reviewer:** Saad (Day 4 for "Flow" review)

**Tasks:**
1. Create 3 connector strategies
2. Write value propositions for each type
3. Write 3-5 connection request templates
4. Build value-first content pieces
5. Build prospect list (300+ connectors)
6. Create follow-up sequences
7. Build sales system (Make.com/N8N)
8. Enrich with in-house tools
9. Set up AI personalization prompts
10. Tag Saad for "Flow" review
11. Set up tracking in ClickUp "Lead Management"
12. Build reporting dashboard

**Quality Threshold:**
- Templates pass grammar/spelling check (Grammarly)
- Prospect list >90% valid email/LinkedIn profiles
- Automation sends test sequence successfully

---

### Phase 4: Week 2 - Monitor & Optimize

**Daily Tasks:**
- Monitor acceptance rates and responses
- Quality check messaging and targeting
- Refine based on feedback
- Optimize high-performing messages
- Build larger prospect lists (1,000+)
- Route qualified connections to client
- Handle objections/issues

**Weekly Tasks:**
- Generate performance report
- Client check-in meeting
- Strategy adjustments
- Scale successful campaigns

---

### Phase 5: Month 1 Review (Days 27-30)

**Tasks:**
1. Generate comprehensive Month 1 report
2. Present results and learnings
3. Plan Month 2 strategy
4. Set up ongoing weekly check-ins

**Success Metrics (Month 1 KPIs):**
- ✅ 1000+ connection requests sent
- ✅ 60%+ connection acceptance rate
- ✅ 50+ qualified connections made
- ✅ 10+ warm introductions facilitated
- ✅ 1+ actual business opportunity created

**Quality Control:**
- Message quality score: >4.0/5.0
- Client satisfaction: >4.5/5.0
- Zero spam reports or complaints
- Response time to client: <4 hours

---

## File Structure

```
workspace/
├── directives/
│   └── onboarding_workflow.md      # Complete SOP (WHAT to do)
├── execution/
│   ├── onboarding_automation.py    # Main orchestration (HOW to do it)
│   └── onboarding_tracker.py       # Progress tracking
├── .tmp/
│   └── onboarding/
│       └── [client_name]/
│           ├── onboarding_data.json    # Client data
│           ├── prospect_lists/         # Lead lists
│           ├── message_templates/      # Campaign copy
│           └── daily_performance/      # Metrics
└── .env                            # API credentials
```

---

## Common Issues & Solutions

### Issue: "SLACK_BOT_TOKEN not configured"
**Solution:** Add Slack Bot Token to `.env` file (see Setup section)

### Issue: "Google credentials not found"
**Solution:** Ensure `credentials.json` exists in workspace root

### Issue: "ClickUp folder creation: Not implemented yet"
**Solution:** This is currently a manual step. The script logs a reminder.

### Issue: Low connection acceptance rate (<50%)
**Solution:**
1. Pause campaign immediately
2. Review message templates for quality
3. Adjust targeting criteria
4. Test with 50 connections before resuming

### Issue: Client doesn't respond to questionnaire
**Solution:**
1. Auto-reminder email after 24 hours
2. Escalate to Saad after 48 hours

---

## Integration Checklist

Before first use, verify:

- [ ] Slack bot installed and token configured
- [ ] ClickUp API key added to `.env`
- [ ] Google OAuth credentials in place
- [ ] Email SMTP credentials configured
- [ ] Test Slack channel creation works
- [ ] Test Google Sheets creation works
- [ ] Test email sending works

---

## Agent Orchestration

When you (the agent) receive a request like:

> "Onboard new client: Acme Corporation"

You should:

1. **Read** [directives/onboarding_workflow.md](directives/onboarding_workflow.md)
2. **Collect** required inputs (client_name, email, industry, goals)
3. **Execute** `onboarding_automation.py --new-client`
4. **Monitor** progress and report completion
5. **Alert** on any failures or blockers
6. **Update** directive with any learnings

---

## Quick Commands Reference

```bash
# New client
python execution/onboarding_automation.py --new-client "Company" --email "client@email.com"

# Check status
python execution/onboarding_automation.py --status "Company"

# Create tracker
python execution/onboarding_tracker.py --create "Company"

# Update task
python execution/onboarding_tracker.py --update SHEET_ID --task "Task name" --status completed

# Update KPI
python execution/onboarding_tracker.py --update-kpi SHEET_ID --kpi "Requests Sent" --value "500"
```

---

## Next Steps

1. **Test** with a sample client (use fake data)
2. **Verify** all integrations work (Slack, ClickUp, Google, Email)
3. **Customize** email templates and messaging
4. **Document** any learnings or edge cases
5. **Self-anneal** the system based on real usage

---

**Last Updated:** 2025-12-25
**Version:** 1.0
**Directive:** [directives/onboarding_workflow.md](directives/onboarding_workflow.md)
