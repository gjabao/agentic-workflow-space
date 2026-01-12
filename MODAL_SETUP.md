# 🚀 Modal Cloud Cron Setup Guide

## What is Modal?

Modal is a serverless Python platform that runs your code in the cloud. Perfect for:
- ✅ Cron jobs that run 24/7 (even when your laptop is off)
- ✅ Auto-scaling (handles any load)
- ✅ Free tier: 30 hours/month of compute
- ✅ Built-in scheduling, secrets management, logging

---

## 📋 Prerequisites

- [ ] Python 3.8+ installed
- [ ] Modal account (free tier available)
- [ ] Your API keys ready (Instantly, Apollo, OpenAI, etc.)

---

## 🎯 Setup in 4 Steps

### Step 1: Install Modal (1 minute)

```bash
pip install modal
```

### Step 2: Authenticate Modal (1 minute)

```bash
modal token new
```

This will:
1. Open browser for login
2. Create account (if needed) - use giabaongb0305@gmail.com
3. Save credentials locally

### Step 3: Add Secrets to Modal (2 minutes)

```bash
# Set all your API keys in Modal
modal secret create anti-gravity-secrets \
  INSTANTLY_API_KEY="your_instantly_key" \
  APOLLO_API_KEY="your_apollo_key" \
  OPENAI_API_KEY="your_openai_key" \
  GMAIL_APP_PASSWORD="your_gmail_app_password" \
  GMAIL_ADDRESS="giabaongb0305@gmail.com"
```

**Or** go to https://modal.com/secrets and add them via web UI.

### Step 4: Deploy Your First Cron Job (1 minute)

```bash
modal deploy modal_workflows/email_campaign_report.py
```

Done! Your workflow is now running in the cloud.

---

## 📂 File Structure

```
workspace/
├── modal_workflows/          # Modal cron jobs (NEW)
│   ├── email_campaign_report.py   # Daily email report
│   ├── monitor_campaigns.py       # Hourly monitoring
│   ├── scrape_and_enrich.py      # Weekly lead scraping
│   └── shared/                    # Shared utilities
│       ├── __init__.py
│       ├── google_auth.py         # Google Sheets/Drive
│       └── notifications.py       # Email/Slack alerts
├── execution/                # Original scripts (unchanged)
├── directives/              # SOPs (unchanged)
└── .env                     # Local only (NOT used in Modal)
```

---

## 🔧 How Modal Works

### Standard Python Script (Local)
```python
# execution/email_campaign_report.py
import os
api_key = os.getenv("INSTANTLY_API_KEY")
# Runs on your laptop
```

### Modal Script (Cloud)
```python
# modal_workflows/email_campaign_report.py
import modal

app = modal.App("anti-gravity")

@app.function(
    schedule=modal.Cron("0 7 * * *"),  # 7 AM daily
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600  # 10 minutes max
)
def send_daily_report():
    import os
    api_key = os.environ["INSTANTLY_API_KEY"]  # From Modal secrets
    # Your logic here
    print("✅ Report sent!")

# Runs in Modal's cloud
```

**Key differences:**
1. `modal.App()` - Creates Modal application
2. `@app.function()` - Decorator with schedule + secrets
3. `modal deploy` - Deploys to cloud
4. No need for crontab or keeping computer on

---

## 📅 Cron Schedule Examples

```python
# Every day at 7 AM UTC (2 PM Hanoi)
schedule=modal.Cron("0 7 * * *")

# Every hour from 9 AM to 5 PM UTC (4 PM - 12 AM Hanoi)
schedule=modal.Cron("0 9-17 * * *")

# Every Monday at 9 AM UTC (4 PM Hanoi)
schedule=modal.Cron("0 9 * * 1")

# Every 4 hours
schedule=modal.Cron("0 */4 * * *")

# Multiple times per day (9 AM, 1 PM, 5 PM UTC)
schedule=modal.Cron("0 9,13,17 * * *")
```

**Timezone:** Modal uses UTC. Hanoi is UTC+7.
- 0 AM UTC = 7 AM Hanoi
- 7 AM UTC = 2 PM Hanoi

---

## 🎨 Real Examples

### Example 1: Daily Campaign Report

File: `modal_workflows/email_campaign_report.py`

```python
import modal
import os
import requests
from datetime import datetime

app = modal.App("anti-gravity")

@app.function(
    schedule=modal.Cron("0 0 * * *"),  # Midnight UTC = 7 AM Hanoi
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600
)
def daily_campaign_report():
    """Fetch Instantly campaigns and email performance report"""

    api_key = os.environ["INSTANTLY_API_KEY"]
    gmail_pwd = os.environ["GMAIL_APP_PASSWORD"]
    gmail_addr = os.environ["GMAIL_ADDRESS"]

    print("🔍 Fetching campaigns from Instantly...")

    # Fetch campaigns
    response = requests.get(
        "https://api.instantly.ai/api/v1/campaign/list",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    campaigns = response.json()

    # Generate report
    report_html = generate_report_html(campaigns)

    # Send email
    send_email(
        to=gmail_addr,
        subject=f"📊 Campaign Report - {datetime.now().strftime('%Y-%m-%d')}",
        html=report_html,
        gmail_user=gmail_addr,
        gmail_pwd=gmail_pwd
    )

    print("✅ Report sent successfully!")

def generate_report_html(campaigns):
    """Generate HTML report from campaigns data"""
    # Your report generation logic
    return "<h1>Campaign Report</h1>..."

def send_email(to, subject, html, gmail_user, gmail_pwd):
    """Send email via Gmail SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_pwd)
        server.send_message(msg)
```

**Deploy:**
```bash
modal deploy modal_workflows/email_campaign_report.py
```

---

### Example 2: Hourly Campaign Monitoring

File: `modal_workflows/monitor_campaigns.py`

```python
import modal

app = modal.App("anti-gravity")

@app.function(
    schedule=modal.Cron("0 * * * *"),  # Every hour
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=300
)
def hourly_monitor():
    """Check campaigns for issues and send alerts"""

    import os
    import requests

    api_key = os.environ["INSTANTLY_API_KEY"]

    print("🔍 Checking campaign health...")

    response = requests.get(
        "https://api.instantly.ai/api/v1/campaign/list",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    campaigns = response.json()

    alerts = []

    for campaign in campaigns:
        # Check bounce rate
        if campaign.get('bounce_rate', 0) > 5:
            alerts.append(f"🚨 {campaign['name']}: Bounce rate {campaign['bounce_rate']}%")

        # Check reply rate
        if campaign.get('reply_rate', 0) > 3:
            alerts.append(f"🎉 {campaign['name']}: Winner! Reply rate {campaign['reply_rate']}%")

    if alerts:
        # Send Slack/email notification
        send_alert("\n".join(alerts))

    print(f"✅ Checked {len(campaigns)} campaigns")

def send_alert(message):
    """Send alert via Slack or email"""
    # Your notification logic
    print(message)
```

---

### Example 3: Weekly Lead Scraping + Enrichment

File: `modal_workflows/scrape_and_enrich.py`

```python
import modal

app = modal.App("anti-gravity")

# Mount local files (optional - for reading directives)
volume = modal.Volume.from_name("anti-gravity-data", create_if_missing=True)

@app.function(
    schedule=modal.Cron("0 9 * * 1"),  # Every Monday 9 AM UTC (4 PM Hanoi)
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    volumes={"/data": volume},
    timeout=1800,  # 30 minutes
    cpu=2.0  # More compute for scraping
)
def weekly_scrape():
    """Scrape leads from Apollo and enrich with emails"""

    import os
    import sys

    # Import your existing scripts
    sys.path.append("/data")

    print("🔍 Starting weekly lead scraping...")

    # Option 1: Call API directly
    scrape_apollo_leads(
        api_key=os.environ["APOLLO_API_KEY"],
        query="dentists in New York",
        limit=500
    )

    # Option 2: Use subprocess to run existing script
    import subprocess
    result = subprocess.run(
        ["python", "execution/scrape_apify_leads.py", "--limit", "500"],
        capture_output=True,
        text=True
    )

    print("✅ Scraping complete!")
    print(result.stdout)

def scrape_apollo_leads(api_key, query, limit):
    """Your scraping logic"""
    pass
```

---

## 🎛️ Advanced Features

### 1. Run on Demand (Not Just Cron)

```python
@app.function(secrets=[modal.Secret.from_name("anti-gravity-secrets")])
def scrape_on_demand(query: str, limit: int = 100):
    """Run this anytime via CLI or API"""
    print(f"Scraping {limit} leads for: {query}")
    # Your logic

# Call from terminal
# modal run modal_workflows/scrape.py::scrape_on_demand --query "dentists" --limit 50
```

### 2. Persistent Storage (Save Files)

```python
volume = modal.Volume.from_name("anti-gravity-data", create_if_missing=True)

@app.function(
    volumes={"/data": volume},
    schedule=modal.Cron("0 0 * * *")
)
def save_results():
    # Save to /data/results.csv
    with open("/data/results.csv", "w") as f:
        f.write("name,email\n")

    volume.commit()  # Persist changes
    print("✅ Saved to persistent storage")
```

### 3. Parallel Processing

```python
@app.function()
def process_lead(lead_id: int):
    """Process a single lead"""
    return {"id": lead_id, "enriched": True}

@app.function(schedule=modal.Cron("0 9 * * *"))
def process_all_leads():
    """Process 1000 leads in parallel"""
    lead_ids = range(1, 1001)

    # Run 1000 tasks in parallel!
    results = list(process_lead.map(lead_ids))

    print(f"✅ Processed {len(results)} leads")
```

### 4. Google Sheets Integration

```python
import modal

app = modal.App("anti-gravity")

@app.function(
    schedule=modal.Cron("0 0 * * *"),
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
)
def upload_to_sheets():
    """Upload results to Google Sheets"""

    # Read credentials from Modal secrets
    import os
    import json
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials

    # You'll need to add Google service account JSON to Modal secrets
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds = Credentials.from_service_account_info(json.loads(creds_json))

    service = build('sheets', 'v4', credentials=creds)

    # Write to sheet
    sheet_id = "your_sheet_id"
    range_name = "Sheet1!A1"
    values = [["Name", "Email"], ["John Doe", "john@example.com"]]

    body = {'values': values}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print("✅ Uploaded to Google Sheets")
```

---

## 📊 Monitoring & Logs

### View Logs
```bash
# View recent logs
modal app logs anti-gravity

# Live tail logs
modal app logs anti-gravity --follow

# View specific function
modal app logs anti-gravity::daily_campaign_report
```

### View Scheduled Jobs
```bash
# List all apps
modal app list

# View app details
modal app show anti-gravity
```

### Dashboard

Go to https://modal.com/apps to see:
- ✅ Execution history
- ✅ Logs for each run
- ✅ Resource usage
- ✅ Costs (if any)

---

## 💰 Pricing

**Free Tier:**
- 30 hours/month compute (generous for cron jobs)
- 10 GB storage
- Unlimited deployments

**Paid Tier (if needed):**
- $0.0001 per second of compute
- $0.10 per GB-month storage

**Example costs:**
- Daily 5-minute job = 2.5 hrs/month = **FREE**
- Hourly 2-minute job = 96 hrs/month = ~$25/month

Most workflows fit in free tier!

---

## 🔄 Migration Plan

### Current: Local Cron → Future: Modal Cloud

**Phase 1: Test with one workflow** (10 minutes)
1. Create `modal_workflows/email_campaign_report.py`
2. Deploy to Modal
3. Test for 1 week alongside local cron
4. Compare results

**Phase 2: Migrate all workflows** (30 minutes)
1. Convert `monitor_campaigns.py`
2. Convert `scrape_and_enrich.py`
3. Add any custom workflows
4. Disable local cron jobs

**Phase 3: Add advanced features** (optional)
1. Add Slack notifications
2. Add Google Sheets auto-upload
3. Add parallel processing for speed
4. Add webhooks for real-time triggers

---

## 🛠️ Troubleshooting

### Issue: "Secret not found"

**Fix:** Create secret first
```bash
modal secret create anti-gravity-secrets \
  INSTANTLY_API_KEY="your_key"
```

### Issue: "Import error"

**Fix:** Add dependencies to function
```python
@app.function(
    image=modal.Image.debian_slim().pip_install("requests", "pandas", "gspread")
)
def my_function():
    import requests
    # Your code
```

### Issue: "Timeout"

**Fix:** Increase timeout
```python
@app.function(timeout=1800)  # 30 minutes
def long_running_task():
    pass
```

### Issue: "Can't access Google Sheets"

**Fix:** Upload service account JSON to Modal secrets
```bash
# Create service account: https://console.cloud.google.com/iam-admin/serviceaccounts
# Download JSON key
# Add to Modal
modal secret create google-creds \
  GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
```

---

## 🚀 Next Steps

1. **Install Modal:** `pip install modal`
2. **Authenticate:** `modal token new`
3. **Tell me which workflow to convert first:**
   - Daily campaign report?
   - Hourly monitoring?
   - Weekly lead scraping?
   - Custom workflow?

I'll create the Modal script for you and deploy it together!

---

## 📚 Resources

- [Modal Docs](https://modal.com/docs)
- [Modal Cron Guide](https://modal.com/docs/guide/cron)
- [Modal Secrets](https://modal.com/docs/guide/secrets)
- [Modal Examples](https://github.com/modal-labs/modal-examples)

**Ready to deploy?** Tell me which workflow to start with! 🚀
