# Instantly Analytics Report Workflow

## Goal
Automatically fetch campaign performance data from Instantly.ai, analyze metrics, and send beautiful HTML email reports to stakeholders.

---

## What This Does
Pulls analytics from Instantly API → Analyzes campaign health → Generates HTML report → Sends via Gmail → Saves local copy

---

## Inputs

### Required
- **INSTANTLY_API_KEY** (in .env): Your Instantly.ai API key
- **REPORT_EMAIL** (in .env): Email address to send report to (defaults to GMAIL_USER)

### Optional Filters
- By default: Reports ALL active campaigns (status = 1 or 2)
- Manual run: Can be triggered on-demand via command line
- Scheduled: Can be automated via cron (see setup_cron.sh)

---

## Execution Tool

**Script:** `execution/email_campaign_report.py`

**Usage:**
```bash
# Run once (manual)
python3 execution/email_campaign_report.py

# Schedule daily (7 AM)
# Already configured in setup_cron.sh:
# 0 0 * * * /path/to/email_campaign_report.py
```

---

## How It Works

### Step 1: Fetch Campaign Data
```
GET https://api.instantly.ai/api/v2/campaigns/analytics
Authorization: Bearer {INSTANTLY_API_KEY}
```

Returns all campaigns with metrics:
- `leads_count` - Total leads in campaign
- `emails_sent_count` - Emails sent
- `reply_count_unique` - Unique replies (includes auto-replies)
- `reply_count_automatic_unique` - Auto-replies only
- `bounced_count` - Bounced emails
- `total_opportunities` - Marked opportunities

### Step 2: Filter Active Campaigns
For each campaign, fetches campaign details to check status:
```
GET https://api.instantly.ai/api/v2/campaigns/{campaign_id}
```

**Status codes:**
- 1 = Active (include)
- 2 = Paused (include for monitoring)
- Other = Exclude

### Step 3: Calculate Metrics
For each active campaign:

```python
real_replies = replies_unique - replies_auto  # Filter out bot replies
real_reply_rate = (real_replies / leads_count) * 100
bounce_rate = (bounced / emails_sent) * 100
opp_rate = (opportunities / leads_count) * 100
```

### Step 4: Health Classification

| Health | Criteria |
|--------|----------|
| 🚨 **Critical** | Bounce rate > 5% |
| ⚠️ **Warning** | Reply rate < 1% AND emails sent > 100 |
| 🎉 **Excellent** | Reply rate ≥ 3% |
| ✅ **Healthy** | Normal performance |

### Step 5: Generate HTML Email

**Template includes:**
- **Summary Cards**: Count of Critical, Warning, Excellent, Healthy campaigns
- **Data Table**: All campaigns with metrics, sorted by health (critical first)
- **Color Coding**:
  - Green: Reply rate ≥ 2%, Bounce rate < 2%
  - Orange: Reply rate ≥ 1%, Bounce rate < 5%
  - Red: Reply rate < 1%, Bounce rate ≥ 5%
- **Responsive Design**: Mobile-friendly, renders correctly in Gmail

### Step 6: Send Email via Gmail API

**Authentication:** OAuth2 (credentials.json + token.json)

**Subject Line:**
- 🚨 Instantly Report: {N} Critical Issue(s) - {Date}  (if critical issues)
- 🎉 Instantly Report: {N} Winner(s) - {Date}  (if excellent campaigns)
- 📊 Instantly Daily Report - {Date}  (default)

**Delivery:** HTML email to REPORT_EMAIL

### Step 7: Save Local Copy
```
.tmp/email_reports/report_{timestamp}.html
```

---

## Expected Outputs

### Email Report
- **To:** Email specified in REPORT_EMAIL env var
- **Format:** HTML with embedded CSS (no external dependencies)
- **Size:** ~15-30KB depending on number of campaigns

### Local Archive
- **Path:** `.tmp/email_reports/report_YYYYMMDD_HHMMSS.html`
- **Retention:** Keep for debugging/reference (cleaned up by workspace cleanup scripts after 14 days)

---

## Quality Thresholds

### Campaign Inclusion
- ✅ Include: Status 1 or 2 (Active/Paused)
- ✅ Include: Has sent emails (emails_sent > 0)
- ❌ Exclude: No leads (leads_count = 0)
- ❌ Exclude: No activity (emails_sent = 0)

### Metrics Benchmarks
| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Reply Rate | ≥ 2% | 1-2% | < 1% |
| Bounce Rate | < 2% | 2-5% | > 5% |
| Opportunity Rate | ≥ 1% | 0.5-1% | < 0.5% |

---

## Edge Cases

### No Active Campaigns
- Behavior: Script exits with message "No active campaigns found"
- Email: Not sent
- Exit code: 0 (success)

### API Rate Limiting
- Instantly API: 30 requests/min
- Script behavior: Fetches campaigns sequentially (not parallel)
- Current load: ~15-20 API calls for 13 campaigns (well under limit)

### Gmail OAuth Token Expired
- Script checks token validity
- Auto-refreshes if refresh_token available
- Re-authenticates via browser if refresh fails
- Token saved to token.json for next run

### Missing Credentials
- credentials.json missing: Error + exit
- INSTANTLY_API_KEY missing: Error + exit
- REPORT_EMAIL missing: Defaults to GMAIL_USER from .env

---

## Schedule Options

### Manual (Current Default)
```bash
python3 execution/email_campaign_report.py
```
**Use case:** On-demand reports, testing

### Daily (Recommended)
```bash
# In setup_cron.sh (already configured)
0 0 * * * /path/to/email_campaign_report.py  # 7 AM Hanoi time
```
**Use case:** Daily morning briefing

### Hourly Monitoring
```bash
# For active campaign monitoring (see monitor_campaigns.py)
0 9-19 * * * /path/to/monitor_campaigns.py  # Business hours only
```
**Use case:** Real-time alerts for critical issues

### Webhook-Triggered (Advanced)
```python
# Via webhook_server.py
POST /webhook/instantly/campaign-completed
→ Triggers single campaign analysis
```
**Use case:** Instant reports when campaign finishes

---

## Comparison: email_campaign_report.py vs monitor_campaigns.py

| Feature | email_campaign_report.py | monitor_campaigns.py |
|---------|--------------------------|----------------------|
| **Purpose** | Comprehensive daily report | Real-time monitoring |
| **Frequency** | Daily (manual or cron) | Hourly during business hours |
| **Output** | HTML email | Console alerts + JSON logs |
| **Alerts** | Summary of all campaigns | Only critical issues |
| **Use case** | Daily briefing | Active monitoring |
| **Email** | Always sends | Only on critical issues |

**Recommendation:** Use **both**
- `email_campaign_report.py` for daily overview
- `monitor_campaigns.py` for real-time alerts

---

## Customization

### Filter Specific Campaigns
```python
# In email_campaign_report.py, modify get_active_campaigns_analytics():
campaigns = [c for c in campaigns if 'keyword' in c.get('campaign_name', '').lower()]
```

### Change Email Recipient
```bash
# In .env
REPORT_EMAIL=team@company.com
```

### Adjust Health Thresholds
```python
# In analyze_campaign():
if bounce_rate > 5:  # Change to 3 for stricter
    health = '🚨 Critical'
elif real_reply_rate < 1:  # Change to 2 for higher standard
    health = '⚠️ Warning'
```

### Add More Metrics
Available from Instantly API but not shown:
- `opened_count` - Email opens
- `clicked_count` - Link clicks
- `unsubscribed_count` - Unsubscribes

---

## Troubleshooting

### Email Not Sent
1. Check Gmail OAuth: `ls -lh token.json credentials.json`
2. Test authentication: Script will open browser if token invalid
3. Check scopes: Must include `gmail.compose`

### Missing Campaigns in Report
1. Check campaign status in Instantly (must be Active or Paused)
2. Check if campaign has sent emails (filters out zero-activity)
3. Check API response: Saved to `.tmp/email_reports/` for debugging

### HTML Not Rendering in Email
- Gmail web/mobile: Should work (tested)
- Outlook: May strip some CSS, but readable
- Apple Mail: Full support
- **Tip:** Always test in target email client first

---

## Future Enhancements (Not Implemented)

### Interactive Charts
- Add Chart.js for reply rate trends
- Show 7-day performance graph
- Campaign comparison bar chart

### PDF Export
- Generate PDF version of report
- Attach to email or upload to Google Drive

### Slack Integration
- Post summary to Slack channel
- Alert on critical campaigns

### Weekly Digest
- Aggregate last 7 days
- Trend analysis (improving/declining)
- Top performers ranking

---

## API Reference

### Instantly API Endpoints Used

**1. Get Campaign Analytics**
```
GET https://api.instantly.ai/api/v2/campaigns/analytics
Headers: Authorization: Bearer {api_key}
Response: Array of campaign objects with metrics
```

**2. Get Campaign Details**
```
GET https://api.instantly.ai/api/v2/campaigns/{campaign_id}
Headers: Authorization: Bearer {api_key}
Response: Single campaign object with status
```

**Documentation:** https://developer.instantly.ai/

---

## Example Output

### Email Subject
```
📊 Instantly Daily Report - Dec 23
```

### Email Body (Summary)
```
📊 Instantly Campaign Performance Report
December 23, 2024 at 12:03 PM

[Summary Cards]
🚨 Critical: 0
⚠️ Warnings: 2
🎉 Excellent: 3
✅ Healthy: 8

[Data Table]
Campaign | Status | Health | Leads | Sent | Reply % | Bounce % | Opps
---------|--------|--------|-------|------|---------|----------|-----
Execuxe-Search-Self-Employment | Active | 🎉 Excellent | 250 | 720 | 3.2% | 1.8% | 8
Marketing-Agency-Outreach | Active | ⚠️ Warning | 180 | 540 | 0.8% | 2.1% | 2
...
```

---

## Files

### Modified
- None (uses existing email_campaign_report.py)

### Created
- `directives/instantly_analytics_report.md` (this file)
- `.tmp/email_reports/report_*.html` (generated each run)

### Dependencies
- `execution/email_campaign_report.py` (480 lines)
- `credentials.json` (Google OAuth)
- `token.json` (Google OAuth token)
- `.env` (INSTANTLY_API_KEY, REPORT_EMAIL)

---

## Success Criteria

✅ **Workflow is successful when:**
1. Script fetches all active campaigns from Instantly
2. Calculates metrics correctly (reply rate, bounce rate, health)
3. Generates valid HTML email
4. Email delivered to REPORT_EMAIL inbox
5. HTML renders correctly in Gmail
6. Local copy saved to .tmp/email_reports/
7. No errors in execution

✅ **Email is actionable when:**
- Critical campaigns clearly highlighted at top
- Metrics color-coded (easy to scan)
- Health status visible at a glance
- Can be viewed on mobile devices

---

## Quick Start

### First Time Setup
```bash
# 1. Set up environment variables
echo "INSTANTLY_API_KEY=your_key_here" >> .env
echo "REPORT_EMAIL=giabaongb0305@gmail.com" >> .env

# 2. Set up Gmail OAuth (one-time)
# Download credentials.json from Google Cloud Console
# Place in workspace root

# 3. Run script (will trigger OAuth flow)
python3 execution/email_campaign_report.py
# Browser will open for Gmail authorization
# Token saved to token.json for future runs
```

### Daily Usage
```bash
# Manual run - All campaigns
python3 execution/email_campaign_report.py

# Or schedule via cron (see setup_cron.sh)
chmod +x setup_cron.sh
./setup_cron.sh
```

### Single Campaign Reports
```bash
# By campaign ID
python3 execution/single_campaign_report.py ef76771a-880c-426e-abc8-f6c30e70dde2

# By campaign name (partial match, case-insensitive)
python3 execution/single_campaign_report.py healthcare
python3 execution/single_campaign_report.py "IT Recruitment"

# If multiple matches found, use more specific name or exact ID
```

**Features:**
- ✅ Search by campaign ID (exact match)
- ✅ Search by campaign name (partial, case-insensitive)
- ✅ Auto-detects ambiguous matches and shows options
- ✅ Sends detailed HTML report via email
- ✅ Saves local copy to `.tmp/email_reports/`

---

## Related Workflows

- **monitor_campaigns.md** - Real-time campaign monitoring (complementary)
- **email_workflow.md** - Send/draft emails via Gmail API
- **connector_replies.md** - Auto-reply to lead responses

---

**Last Updated:** 2025-12-25
**Maintainer:** DO Framework
**Version:** 1.1
