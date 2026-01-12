# 🚀 What You Can Do With Modal

Modal is your serverless Python platform in the cloud. Here's everything you can do with it for your Anti-Gravity workflows.

---

## ✅ What You Have Now

**Modal Setup Complete:**
- ✅ Account authenticated: `giabaongb0305` workspace
- ✅ Secrets uploaded: All your API keys are in Modal cloud
- ✅ First workflow deployed: Daily campaign report
- ✅ Dashboard: https://modal.com/apps

---

## 🎯 Core Capabilities

### 1. **Scheduled Cron Jobs** (What You're Using Now)

Run Python scripts on a schedule, 24/7, even when your laptop is off.

**Examples:**
```python
# Daily at 7 AM Hanoi time (midnight UTC)
@app.function(schedule=modal.Cron("0 0 * * *"))

# Every 2 hours
@app.function(schedule=modal.Cron("0 */2 * * *"))

# Every Monday at 9 AM UTC (4 PM Hanoi)
@app.function(schedule=modal.Cron("0 9 * * 1"))

# Twice daily: 9 AM and 5 PM UTC
@app.function(schedule=modal.Cron("0 9,17 * * *"))
```

**Your Use Cases:**
- ✅ Daily campaign performance reports
- ✅ Hourly campaign health monitoring
- ✅ Weekly lead scraping from Apollo/Apify
- ✅ Daily email verification
- ✅ Automated copy generation for new leads

---

### 2. **On-Demand Execution**

Run any script instantly from your terminal, no waiting for cron.

**Command:**
```bash
export PATH="/Users/nguyengiabao/Library/Python/3.9/bin:$PATH"
python3 -m modal run modal_workflows/your_workflow.py
```

**Your Use Cases:**
- Test workflows before deploying
- Generate reports on demand
- Scrape leads right now (not waiting for weekly cron)
- Generate custom copy for urgent campaigns
- Verify emails in bulk when needed

---

### 3. **Parallel Processing** (HUGE Performance Boost)

Process 1000+ items in parallel instead of one-by-one.

**Example:**
```python
# OLD: Sequential (takes 1000 seconds for 1000 leads)
for lead in leads:
    enrich_lead(lead)  # 1 second each

# NEW: Parallel (takes 10 seconds for 1000 leads!)
@app.function()
def enrich_lead(lead):
    # Enrich single lead
    return enriched_data

@app.function()
def enrich_all_leads():
    leads = get_1000_leads()
    # Process 100 at a time in parallel
    results = list(enrich_lead.map(leads))
```

**Your Use Cases:**
- ✅ Enrich 1000 leads in minutes (not hours)
- ✅ Verify 500 emails in parallel
- ✅ Generate copy for 100 companies simultaneously
- ✅ Scrape multiple sources at once

**Speed Comparison:**
- Sequential: 1000 leads × 2 seconds = 33 minutes
- Parallel (Modal): 1000 leads / 100 workers = 20 seconds ⚡

---

### 4. **Serverless Functions** (API Endpoints)

Turn any Python function into a web API.

**Example:**
```python
@app.function()
@modal.web_endpoint()
def scrape_company(company_name: str):
    leads = scrape_apollo(company_name)
    return {"leads": leads, "count": len(leads)}
```

**Access via:**
```bash
curl https://your-app.modal.run/scrape_company?company_name=dentists
```

**Your Use Cases:**
- ✅ Webhook endpoint for Instantly (when someone replies)
- ✅ API for your frontend to trigger workflows
- ✅ Zapier integration endpoint
- ✅ Custom dashboard API

---

### 5. **Persistent Storage**

Save files in the cloud, accessible across all runs.

**Example:**
```python
volume = modal.Volume.from_name("anti-gravity-data", create_if_missing=True)

@app.function(volumes={"/data": volume})
def save_leads():
    # Save to persistent storage
    with open("/data/leads_2025.csv", "w") as f:
        f.write("name,email,company\n")

    volume.commit()  # Persist changes
```

**Your Use Cases:**
- ✅ Store scraped leads history
- ✅ Cache enriched company data (avoid re-scraping)
- ✅ Store campaign performance over time
- ✅ Build lead database incrementally

---

### 6. **GPU Support** (AI/ML Workloads)

Run AI models on powerful GPUs, pay only for seconds used.

**Example:**
```python
@app.function(gpu="T4")  # Or A100, A10G, etc.
def generate_copy_with_ai(company_info):
    # Load model
    model = load_llm_model()
    # Generate copy
    return model.generate(company_info)
```

**Your Use Cases:**
- ✅ Fine-tuned copy generation model
- ✅ Custom email personalization AI
- ✅ Lead scoring with ML
- ✅ Image generation for campaigns

**Cost:** ~$0.50/hour for T4 GPU (only when running!)

---

### 7. **Secrets Management**

Store API keys securely, never hardcode them.

**What you have:**
```
INSTANTLY_API_KEY
APIFY_API_KEY
AZURE_OPENAI_API_KEY
REPORT_EMAIL
GMAIL_CREDENTIALS_JSON
GMAIL_TOKEN_JSON
```

**Add more:**
```bash
python3 -m modal secret create anti-gravity-secrets \
  SLACK_WEBHOOK_URL="https://hooks.slack.com/..." \
  TELEGRAM_BOT_TOKEN="..." \
  CUSTOM_API_KEY="..."
```

**View/Edit:** https://modal.com/secrets

---

### 8. **Custom Docker Images**

Install any software, not just Python packages.

**Example:**
```python
image = (
    modal.Image.debian_slim()
    .apt_install("chromium", "ffmpeg")  # Install system packages
    .pip_install("selenium", "opencv-python")
    .run_commands("wget https://example.com/tool.sh && bash tool.sh")
)

@app.function(image=image)
def scrape_with_browser():
    # Use Chromium for scraping
    pass
```

**Your Use Cases:**
- ✅ Browser automation (Selenium/Playwright)
- ✅ PDF generation
- ✅ Image processing
- ✅ Video creation for ads

---

### 9. **Streaming Logs**

Monitor your workflows in real-time.

**Commands:**
```bash
# Live tail logs
python3 -m modal app logs anti-gravity-workflows --follow

# Recent logs
python3 -m modal app logs anti-gravity-workflows

# Specific function
python3 -m modal app logs anti-gravity-workflows::daily_campaign_report
```

**Dashboard:** https://modal.com/apps (visual logs)

---

### 10. **Cost Tracking**

Pay only for what you use, track every cent.

**Free Tier:**
- ✅ 30 compute hours/month
- ✅ 10 GB storage
- ✅ Unlimited deployments

**Paid Tier (if needed):**
- CPU: $0.0001/second (~$0.36/hour)
- GPU T4: $0.50/hour
- Storage: $0.10/GB-month

**View usage:** https://modal.com/settings/usage

**Your workflows cost:**
- Daily 5-min report: 2.5 hrs/month = **FREE**
- Hourly 2-min check: 96 hrs/month = ~$25/month
- Weekly 30-min scrape: 2 hrs/month = **FREE**

---

## 🎨 Practical Examples for You

### Example 1: Hourly Campaign Monitor

**File:** `modal_workflows/monitor_campaigns.py`

```python
import modal

app = modal.App("anti-gravity-workflows")

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

    # Fetch campaigns
    response = requests.get(
        "https://api.instantly.ai/api/v2/campaigns/analytics",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    campaigns = response.json()

    alerts = []
    for campaign in campaigns:
        bounce_rate = campaign.get('bounced_count', 0) / max(campaign.get('emails_sent_count', 1), 1) * 100

        if bounce_rate > 5:
            alerts.append(f"🚨 {campaign['campaign_name']}: Bounce rate {bounce_rate:.1f}%")

    if alerts:
        print("\n".join(alerts))
        # Send to Slack/Telegram

    print(f"✅ Checked {len(campaigns)} campaigns")
```

**Deploy:**
```bash
python3 -m modal deploy modal_workflows/monitor_campaigns.py
```

---

### Example 2: Weekly Lead Scraper

**File:** `modal_workflows/weekly_scraper.py`

```python
import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    schedule=modal.Cron("0 9 * * 1"),  # Monday 9 AM UTC (4 PM Hanoi)
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=1800,  # 30 minutes
    cpu=2.0  # More power for scraping
)
def weekly_scrape():
    """Scrape 500 leads weekly and upload to Google Sheets"""
    import os
    import requests

    apify_key = os.environ["APIFY_API_KEY"]

    print("🔍 Starting weekly lead scrape...")

    # Run Apify actor
    response = requests.post(
        "https://api.apify.com/v2/acts/YOUR_ACTOR/runs",
        json={
            "query": "dentists in New York",
            "maxResults": 500
        },
        params={"token": apify_key}
    )

    run_id = response.json()["data"]["id"]

    # Wait for results...
    # Upload to Google Sheets...

    print("✅ Scraped 500 leads and uploaded to Sheets")
```

---

### Example 3: Parallel Email Verification

**File:** `modal_workflows/verify_emails.py`

```python
import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")]
)
def verify_single_email(email: str):
    """Verify a single email"""
    import os
    import requests

    api_key = os.environ["ANYMAILFINDER_API_KEY"]

    response = requests.get(
        f"https://api.anymailfinder.com/verify?email={email}",
        headers={"Authorization": f"Bearer {api_key}"}
    )

    return {
        "email": email,
        "valid": response.json().get("valid", False)
    }

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")]
)
def verify_all_emails(emails: list):
    """Verify 1000 emails in parallel"""
    print(f"🔍 Verifying {len(emails)} emails in parallel...")

    # Run 100 verifications at a time
    results = list(verify_single_email.map(emails))

    valid_count = sum(1 for r in results if r["valid"])
    print(f"✅ {valid_count}/{len(emails)} valid emails")

    return results

@app.local_entrypoint()
def main():
    emails = ["test1@example.com", "test2@example.com"]  # Load from CSV
    results = verify_all_emails.remote(emails)
    print(results)
```

**Run:**
```bash
python3 -m modal run modal_workflows/verify_emails.py
```

---

### Example 4: Webhook Endpoint

**File:** `modal_workflows/webhook_server.py`

```python
import modal
from fastapi import FastAPI

app = modal.App("anti-gravity-workflows")
web_app = FastAPI()

@web_app.post("/instantly-reply")
async def handle_reply(data: dict):
    """Handle reply from Instantly webhook"""
    print(f"📧 New reply from: {data.get('email')}")

    # Categorize reply
    # Update Google Sheets
    # Send Slack notification

    return {"status": "processed"}

@app.function()
@modal.asgi_app()
def fastapi_app():
    return web_app
```

**Deploy:**
```bash
python3 -m modal deploy modal_workflows/webhook_server.py
```

**Webhook URL:** `https://your-app.modal.run/instantly-reply`

---

## 📊 Comparison: Local vs Modal

| Feature | Local Cron | Modal Cloud |
|---------|-----------|-------------|
| **Runs when laptop off** | ❌ No | ✅ Yes |
| **Parallel processing** | ❌ Limited | ✅ Unlimited |
| **GPU access** | ❌ No | ✅ Yes |
| **Monitoring dashboard** | ❌ Manual | ✅ Built-in |
| **Scalability** | ❌ 1 machine | ✅ Auto-scales |
| **Cost** | $0 | $0 (free tier) |
| **Setup time** | 10 min | 5 min |
| **API endpoints** | ❌ Requires server | ✅ Built-in |
| **Secrets management** | ❌ .env file | ✅ Encrypted |

---

## 🚀 Next Steps for You

### 1. **Fix Gmail Scope** (5 minutes)

Current token has Sheets/Drive scope, but you need Gmail scope.

Run this to generate a new token with Gmail permission:
```bash
python3 modal_workflows/regenerate_gmail_token.py
bash .tmp/update_secrets.sh
```

Then test:
```bash
python3 -m modal run modal_workflows/email_campaign_report.py
```

---

### 2. **Add More Workflows** (I can help!)

Pick any of these to convert to Modal:

**A. Hourly Campaign Monitor**
- Check bounce rates every hour
- Alert via Slack/email if issues
- Deploy: `python3 -m modal deploy modal_workflows/monitor_campaigns.py`

**B. Weekly Lead Scraper**
- Scrape 500 leads every Monday
- Enrich with emails
- Upload to Google Sheets
- Deploy: `python3 -m modal deploy modal_workflows/weekly_scraper.py`

**C. On-Demand Copy Generator**
- Generate personalized copy for any company
- Call from terminal or API
- Run: `python3 -m modal run modal_workflows/generate_copy.py --company "dentists"`

**D. Parallel Email Verifier**
- Verify 1000 emails in 2 minutes (not 30 minutes)
- Save results to Sheets
- Run: `python3 -m modal run modal_workflows/verify_emails.py`

**E. Webhook Server**
- Real-time reply handling from Instantly
- Auto-categorize replies
- Update CRM/Sheets automatically
- Deploy: `python3 -m modal deploy modal_workflows/webhook_server.py`

---

### 3. **Add Notifications** (Optional)

**Slack:**
```bash
python3 -m modal secret create anti-gravity-secrets \
  SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK"
```

**Telegram:**
```bash
python3 -m modal secret create anti-gravity-secrets \
  TELEGRAM_BOT_TOKEN="your_bot_token" \
  TELEGRAM_CHAT_ID="your_chat_id"
```

Then use:
```python
from modal_workflows.shared.notifications import send_slack_notification
send_slack_notification("🎉 Campaign winner detected!")
```

---

### 4. **Scale to Production**

Once comfortable:
- ✅ Migrate all local cron jobs to Modal
- ✅ Add parallel processing for speed
- ✅ Set up webhooks for real-time triggers
- ✅ Build API endpoints for frontend
- ✅ Add GPU for AI-powered copy generation

---

## 📚 Quick Commands Reference

```bash
# Deploy workflow (creates cron job)
python3 -m modal deploy modal_workflows/your_workflow.py

# Run workflow now (test)
python3 -m modal run modal_workflows/your_workflow.py

# View logs (live)
python3 -m modal app logs anti-gravity-workflows --follow

# View logs (recent)
python3 -m modal app logs anti-gravity-workflows

# List deployed apps
python3 -m modal app list

# Stop/delete app
python3 -m modal app stop anti-gravity-workflows

# Manage secrets
python3 -m modal secret list

# View usage & costs
open https://modal.com/settings/usage
```

---

## 💡 Best Practices

1. **Start small** - Deploy one workflow, test for a week
2. **Use parallel processing** - 10-100x speed boost for batch operations
3. **Monitor costs** - Check dashboard weekly
4. **Test locally first** - Use `modal run` before `modal deploy`
5. **Version control** - Keep workflows in git
6. **Use secrets** - Never hardcode API keys

---

## ❓ FAQ

**Q: Does Modal work when my laptop is off?**
A: Yes! Once deployed, it runs in Modal's cloud 24/7.

**Q: How much does it cost?**
A: Most workflows fit in free tier (30 hrs/month). Heavy usage ~$25-50/month.

**Q: Can I use my existing Python scripts?**
A: Yes! Just add `@app.function()` decorator and deploy.

**Q: How do I stop a workflow?**
A: `python3 -m modal app stop anti-gravity-workflows`

**Q: Can I schedule multiple workflows?**
A: Yes! Each workflow is a separate function with its own schedule.

---

## 🎉 What You Can Build

With Modal, you can automate your entire lead generation → campaign → follow-up pipeline:

**Monday 9 AM:** Scrape 500 new leads → Enrich with emails → Upload to Sheets

**Daily 7 AM:** Send campaign performance report → Highlight winners/losers

**Every hour:** Monitor campaigns → Alert if bounce rate > 5%

**On reply:** Webhook triggers → Categorize reply → Update CRM → Notify you

**On demand:** Generate personalized copy → Verify emails → Create campaign

All running 24/7, scaling automatically, costing $0-25/month.

---

**Ready to add your next workflow?** Tell me which one you want and I'll create it for you! 🚀
