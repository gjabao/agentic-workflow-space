# Modal Cloud Workflows

Run your Anti-Gravity workflows in the cloud using Modal - serverless Python platform.

## Quick Start (5 minutes)

### 1. Install Modal
```bash
pip install modal
```

### 2. Authenticate
```bash
modal token new
```
This opens your browser to create/login to Modal account (free tier available).

### 3. Set Up Secrets
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
bash modal_workflows/setup_modal_secrets.sh
```

This reads your `.env` file and uploads secrets to Modal cloud.

### 4. Deploy Your First Workflow
```bash
modal deploy modal_workflows/email_campaign_report.py
```

**Done!** Your workflow now runs daily at 7 AM Hanoi time (midnight UTC) in the cloud.

---

## Available Workflows

### 📧 Daily Campaign Report
**File:** `email_campaign_report.py`
**Schedule:** Every day at 7 AM Hanoi time
**What it does:**
- Fetches all active Instantly campaigns
- Analyzes performance metrics
- Sends beautiful HTML email report via Gmail
- Highlights critical issues, warnings, and winners

**Deploy:**
```bash
modal deploy modal_workflows/email_campaign_report.py
```

**Test manually:**
```bash
modal run modal_workflows/email_campaign_report.py
```

---

## Viewing Logs

### Real-time logs (live tail)
```bash
modal app logs anti-gravity-workflows --follow
```

### Recent logs
```bash
modal app logs anti-gravity-workflows
```

### Specific function logs
```bash
modal app logs anti-gravity-workflows::daily_campaign_report
```

### Web dashboard
Go to https://modal.com/apps to see:
- Execution history
- Logs for each run
- Resource usage
- Costs

---

## Managing Secrets

### View secrets
https://modal.com/secrets

### Update a secret
Go to web UI or delete and recreate:
```bash
modal secret delete anti-gravity-secrets
bash modal_workflows/setup_modal_secrets.sh
```

### Required secrets
- `INSTANTLY_API_KEY` - Your Instantly API key
- `APOLLO_API_KEY` - Your Apollo.io API key
- `OPENAI_API_KEY` - OpenAI API key for AI features
- `REPORT_EMAIL` - Email to send reports to
- `GMAIL_CREDENTIALS_JSON` - OAuth credentials (from credentials.json)
- `GMAIL_TOKEN_JSON` - OAuth token (from token.json)

---

## Deployment Commands

### Deploy (creates/updates cron job)
```bash
modal deploy modal_workflows/email_campaign_report.py
```

### Run manually (test without waiting for cron)
```bash
modal run modal_workflows/email_campaign_report.py
```

### View deployed apps
```bash
modal app list
```

### Stop/delete a deployed app
```bash
modal app stop anti-gravity-workflows
```

---

## Customizing Schedule

Edit the cron schedule in the workflow file:

```python
@app.function(
    schedule=modal.Cron("0 0 * * *"),  # Cron expression
    ...
)
```

**Cron examples:**
- `"0 0 * * *"` - Daily at midnight UTC (7 AM Hanoi)
- `"0 */2 * * *"` - Every 2 hours
- `"0 9 * * 1"` - Every Monday at 9 AM UTC (4 PM Hanoi)
- `"0 9,13,17 * * *"` - 9 AM, 1 PM, 5 PM UTC

**Remember:** Modal uses UTC timezone. Hanoi is UTC+7.

---

## Cost & Limits

**Free tier (generous for most workflows):**
- ✅ 30 compute hours/month
- ✅ 10 GB storage
- ✅ Unlimited deployments

**Example usage:**
- Daily 5-min report = 2.5 hours/month = **FREE**
- Hourly 2-min check = 96 hours/month = ~$25/month

Most Anti-Gravity workflows fit in free tier!

---

## Troubleshooting

### "Secret not found"
**Fix:** Run setup script
```bash
bash modal_workflows/setup_modal_secrets.sh
```

### "GMAIL_TOKEN_JSON not found"
**Fix:** Generate token.json locally first
```bash
python execution/email_campaign_report.py
# This will open browser for Gmail OAuth
# Then token.json will be created
# Re-run: bash modal_workflows/setup_modal_secrets.sh
```

### "Import error" or missing package
**Fix:** Add to image dependencies in workflow file
```python
image = (
    modal.Image.debian_slim()
    .pip_install("requests", "pandas", "your-package")
)
```

### Workflow not running on schedule
**Check:**
1. Is it deployed? `modal app list`
2. View logs: `modal app logs anti-gravity-workflows`
3. Check schedule in code (remember UTC timezone!)

### Timeout error
**Fix:** Increase timeout in function decorator
```python
@app.function(
    timeout=1800,  # 30 minutes (in seconds)
    ...
)
```

---

## Migration from Local Cron

### Current setup (local cron)
- ✅ Works when computer is on
- ❌ Stops when computer sleeps/off
- ❌ Manual setup on each machine
- ❌ Limited to single machine

### With Modal (cloud)
- ✅ Runs 24/7 regardless of computer state
- ✅ Auto-scales for any workload
- ✅ Accessible from anywhere
- ✅ Built-in logging and monitoring
- ✅ No server management

### Migration steps:
1. Test Modal workflow alongside local cron for 1 week
2. Verify results match expectations
3. Disable local cron: `crontab -r`
4. Keep Modal workflow running

---

## Adding New Workflows

### 1. Create new workflow file
```python
# modal_workflows/my_workflow.py
import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    schedule=modal.Cron("0 * * * *"),  # Every hour
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600
)
def my_workflow():
    print("Running my workflow!")
    # Your code here

@app.local_entrypoint()
def main():
    my_workflow.remote()
```

### 2. Deploy
```bash
modal deploy modal_workflows/my_workflow.py
```

### 3. Test
```bash
modal run modal_workflows/my_workflow.py
```

---

## Support

**Modal Documentation:**
- https://modal.com/docs
- https://modal.com/docs/guide/cron
- https://modal.com/docs/guide/secrets

**Questions?**
Check `MODAL_SETUP.md` for comprehensive guide.

**Dashboard:**
https://modal.com/apps

---

## File Structure

```
modal_workflows/
├── README.md                      # This file
├── setup_modal_secrets.sh         # One-time setup script
├── email_campaign_report.py       # Daily email reports
└── shared/                        # Shared utilities (future)
    ├── __init__.py
    ├── google_auth.py            # Google API helpers
    └── notifications.py          # Email/Slack alerts
```

---

Ready to deploy? 🚀

```bash
modal deploy modal_workflows/email_campaign_report.py
```
