# 🚀 Modal Cloud Setup - 5 Minutes

Get your workflows running in the cloud (24/7, even when your laptop is off).

---

## ✅ What You'll Get

After setup:
- ☁️ **Workflows run in cloud** - No need to keep laptop on
- 📧 **Daily email reports** at 7 AM Hanoi time
- 🔄 **Auto-scaling** - Handles any workload
- 📊 **Built-in monitoring** - View logs anytime
- 💰 **Free tier** - 30 hours/month (enough for most workflows)

---

## 📋 Prerequisites

- [x] Python 3.8+ installed
- [x] `.env` file with your API keys
- [x] `credentials.json` (Google OAuth)
- [x] `token.json` (generated from running local workflow once)

---

## 🎯 Setup in 4 Steps

### Step 1: Install Modal (30 seconds)

```bash
pip install modal
```

### Step 2: Authenticate (1 minute)

```bash
modal token new
```

This will:
1. Open browser for login
2. Create/login to Modal account (use giabaongb0305@gmail.com)
3. Save credentials locally

**Note:** Use the free tier to start. No credit card required.

---

### Step 3: Upload Your Secrets (2 minutes)

First, make sure you have `token.json` (Gmail OAuth token). If not, generate it:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
python execution/email_campaign_report.py
```

This will open browser for Gmail authentication and create `token.json`.

Now upload all secrets to Modal:

```bash
bash modal_workflows/setup_modal_secrets.sh
```

**What this does:**
- Reads `.env` file
- Reads `credentials.json` and `token.json`
- Uploads everything to Modal's secure secrets storage

**Expected output:**
```
✓ All required secrets found in .env
✓ Found credentials.json
✓ Found token.json

🚀 Creating Modal secret: anti-gravity-secrets

✅ Setup complete!
```

---

### Step 4: Deploy Your First Workflow (1 minute)

Deploy the daily campaign report:

```bash
modal deploy modal_workflows/email_campaign_report.py
```

**Expected output:**
```
✓ Created objects.
├── 🔨 Created mount /Users/.../Anti-Gravity Workspace/modal_workflows
├── 🔨 Created function daily_campaign_report.
└── 🔨 Deployed app anti-gravity-workflows.

✅ App deployed! 🎉

View at: https://modal.com/apps/anti-gravity-workflows
```

**Done!** Your workflow is now running in the cloud.

---

## 🧪 Test It Right Now

Don't want to wait until tomorrow? Test it immediately:

```bash
modal run modal_workflows/email_campaign_report.py
```

**What happens:**
1. Runs workflow in Modal cloud
2. Fetches your Instantly campaigns
3. Sends email report to your inbox
4. Shows logs in terminal

**Expected output:**
```
🔍 Starting daily campaign report - 2025-12-23 05:15:32 UTC
✓ Found 1 active campaigns
🔐 Building Gmail API service...
📨 Sending email to giabaongb0305@gmail.com...
✅ Email sent! Message ID: 18d2f8a...
✅ Daily report sent successfully!
```

**Check your email inbox!** You should receive a beautiful HTML report.

---

## 📊 Monitoring Your Workflows

### View Logs (Real-time)
```bash
modal app logs anti-gravity-workflows --follow
```

### View Recent Logs
```bash
modal app logs anti-gravity-workflows
```

### Web Dashboard
Go to: https://modal.com/apps

You'll see:
- ✅ All deployed workflows
- ✅ Execution history (when they ran)
- ✅ Logs for each run
- ✅ Resource usage
- ✅ Costs (if any)

---

## 📅 Workflow Schedule

Your workflow runs:
- **Schedule:** Every day at midnight UTC
- **Hanoi time:** 7:00 AM (UTC+7)
- **Auto-runs:** No manual trigger needed

**Want to change schedule?**

Edit [modal_workflows/email_campaign_report.py](modal_workflows/email_campaign_report.py#L28):

```python
schedule=modal.Cron("0 0 * * *"),  # Current: Midnight UTC (7 AM Hanoi)
```

**Examples:**
```python
# Every 2 hours
schedule=modal.Cron("0 */2 * * *")

# Every Monday at 9 AM UTC (4 PM Hanoi)
schedule=modal.Cron("0 9 * * 1")

# Twice daily: 9 AM and 5 PM UTC
schedule=modal.Cron("0 9,17 * * *")
```

After editing, redeploy:
```bash
modal deploy modal_workflows/email_campaign_report.py
```

---

## 🔧 Managing Secrets

### View Secrets
Go to: https://modal.com/secrets

You'll see `anti-gravity-secrets` with all your API keys.

### Update a Secret

**Option 1:** Web UI (easiest)
1. Go to https://modal.com/secrets
2. Click on `anti-gravity-secrets`
3. Edit any key/value
4. Save

**Option 2:** Re-run setup script
```bash
# Update .env file first
vim .env

# Re-upload to Modal
modal secret delete anti-gravity-secrets
bash modal_workflows/setup_modal_secrets.sh
```

---

## 💰 Costs & Free Tier

**Free Tier (generous):**
- ✅ 30 compute hours/month
- ✅ 10 GB storage
- ✅ Unlimited deployments

**Example usage:**
- Daily 5-min report = 2.5 hours/month = **FREE**
- Hourly 2-min check = 96 hours/month = ~$25/month

**Current workflow:** Runs ~5 minutes/day = **2.5 hours/month = FREE** ✅

View your usage: https://modal.com/settings/usage

---

## 🛠️ Troubleshooting

### Issue: "Secret not found"

**Fix:** Create secrets first
```bash
bash modal_workflows/setup_modal_secrets.sh
```

### Issue: "GMAIL_TOKEN_JSON not found"

**Fix:** Generate `token.json` locally first
```bash
python execution/email_campaign_report.py
# Opens browser for Gmail OAuth
# Creates token.json
# Then re-run: bash modal_workflows/setup_modal_secrets.sh
```

### Issue: Email not sending

**Check logs:**
```bash
modal app logs anti-gravity-workflows
```

**Common causes:**
1. Gmail OAuth token expired → Re-generate `token.json` and re-upload
2. Wrong secret values → Check https://modal.com/secrets
3. Gmail API not enabled → Enable at https://console.cloud.google.com/

### Issue: Workflow not running on schedule

**Check:**
1. Is it deployed? `modal app list`
2. View logs: `modal app logs anti-gravity-workflows`
3. Wait for next scheduled time (midnight UTC = 7 AM Hanoi)

**Force run now:**
```bash
modal run modal_workflows/email_campaign_report.py
```

---

## 🔄 Comparison: Local Cron vs Modal

| Feature | Local Cron | Modal Cloud |
|---------|-----------|-------------|
| **Runs when laptop off** | ❌ No | ✅ Yes |
| **Setup time** | 10 min | 5 min |
| **Monitoring** | Manual (check logs) | Web dashboard |
| **Scaling** | Limited to 1 machine | Auto-scales |
| **Costs** | $0 | $0 (free tier) |
| **Maintenance** | Manual updates | Auto-updates |

**Recommendation:** Use Modal for production. Keep local cron for testing.

---

## 📚 Next Steps

### 1. Add More Workflows

Create new workflows based on your existing scripts:

**Hourly Campaign Monitor:**
```bash
# Convert execution/monitor_campaigns.py to Modal
# I can help you with this - just ask!
```

**Weekly Lead Scraper:**
```bash
# Convert execution/scrape_apify_leads.py to Modal
# Runs every Monday at 9 AM
```

### 2. Add Slack Notifications

Want Slack alerts instead of email?

1. Add to Modal secrets:
```bash
modal secret create anti-gravity-secrets \
  SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

2. Use shared notification helper:
```python
from modal_workflows.shared.notifications import send_slack_notification

send_slack_notification("🎉 Campaign winner detected!")
```

### 3. Migrate All Workflows

Once you're comfortable, migrate all your local cron jobs to Modal:
- Daily reports
- Hourly monitoring
- Weekly scraping
- Email campaigns

---

## ✅ Quick Commands Reference

```bash
# Deploy workflow
modal deploy modal_workflows/email_campaign_report.py

# Run workflow now (test)
modal run modal_workflows/email_campaign_report.py

# View logs (live)
modal app logs anti-gravity-workflows --follow

# View logs (recent)
modal app logs anti-gravity-workflows

# List deployed apps
modal app list

# Stop/delete app
modal app stop anti-gravity-workflows

# Manage secrets
modal secret list
modal secret delete anti-gravity-secrets

# View usage & costs
open https://modal.com/settings/usage
```

---

## 📖 Documentation

- **Modal Docs:** https://modal.com/docs
- **Cron Guide:** https://modal.com/docs/guide/cron
- **Secrets Guide:** https://modal.com/docs/guide/secrets
- **Full Modal Setup:** [MODAL_SETUP.md](MODAL_SETUP.md)
- **Workflows README:** [modal_workflows/README.md](modal_workflows/README.md)

---

## 🎉 You're Done!

Your workflow is now running in the cloud 24/7.

**What you have:**
- ☁️ Daily campaign reports at 7 AM Hanoi time
- 📧 Beautiful HTML emails to your inbox
- 📊 Live monitoring dashboard
- 💰 Free (within free tier limits)

**Next actions:**
1. Check your email tomorrow at 7 AM for the first report
2. Monitor at: https://modal.com/apps
3. Ask me to convert more workflows to Modal

**Questions? Just ask!** 🚀
