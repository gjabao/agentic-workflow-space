# How to Use Modal Webhook - Complete Walkthrough

## 📋 Prerequisites

- Python 3.11+ installed
- Terminal/command line access
- Modal account (free - create at https://modal.com)
- Apify API key (from https://console.apify.com)

---

## 🎯 Part 1: One-Time Setup (5 minutes)

### Step 1: Install Modal CLI

```bash
pip install modal
```

**Expected output:**
```
Successfully installed modal-0.x.x
```

---

### Step 2: Authenticate with Modal

```bash
modal token new
```

**What happens:**
- Browser opens automatically
- Login/create account at modal.com
- Click "Create Token"
- Terminal shows: ✓ Token created

**First time?** Create free account at modal.com (no credit card needed!)

---

### Step 3: Add Your API Keys to Modal

**Option A: Interactive (Easiest)**

```bash
# Check your current API keys
cat .env | grep APIFY_API_KEY

# Copy the value, then create Modal secret:
modal secret create anti-gravity-secrets
```

When prompted, enter:
- `APIFY_API_KEY`: `apify_api_xxxxx` (paste your key)
- `SSMASTERS_API_KEY`: `sk_xxxxx` (optional - press Enter to skip)
- `AZURE_OPENAI_ENDPOINT`: `https://xxx.openai.azure.com/` (optional)
- `AZURE_OPENAI_API_KEY`: `xxxxx` (optional)

**Option B: One Command**

```bash
# Get your keys from .env file
source .env

# Create secret with all keys
modal secret create anti-gravity-secrets \
  APIFY_API_KEY=$APIFY_API_KEY \
  SSMASTERS_API_KEY=$SSMASTERS_API_KEY \
  AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
  AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY
```

**Verify:**
```bash
modal secret list
```

You should see: `anti-gravity-secrets`

---

### Step 4: Deploy Your Webhook

```bash
modal deploy modal_workflows/webhook_scrape_apify.py
```

**Expected output:**
```
✓ Initialized. View run at https://modal.com/...
✓ Created objects.
├── 🔨 Created volume anti-gravity-data
└── 🔨 Created web function fastapi_app

View Deployment: https://modal.com/apps/your-workspace/anti-gravity-webhook
```

**🎉 Your webhook is now LIVE!**

---

### Step 5: Get Your Webhook URL

```bash
modal app list
```

**Look for:**
```
anti-gravity-webhook    https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run
```

**Copy this URL!** This is your webhook endpoint.

**Full URL format:**
```
https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/webhook/scrape-apify-leads
```

---

## 🚀 Part 2: Using Your Webhook

### Method 1: Test with curl (Quick Test)

```bash
# Replace YOUR_URL with your actual Modal URL
curl -X POST https://YOUR_URL.modal.run/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 5
  }'
```

**Expected response:**
```json
{
  "status": "accepted",
  "message": "Lead scraping workflow triggered",
  "job_id": "ca-abc123",
  "industry": "Marketing Agency",
  "fetch_count": 5
}
```

**✅ Success!** Your webhook is working!

---

### Method 2: Full Example (Production)

```bash
curl -X POST https://YOUR_URL.modal.run/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 30,
    "location": "united states",
    "company_keywords": ["digital marketing", "PPC agency"],
    "job_title": ["CEO", "Founder"],
    "company_industry": ["marketing & advertising"],
    "skip_test": true,
    "valid_only": true
  }'
```

---

### Method 3: Using the Test Script

```bash
# First, set your webhook URL as environment variable
export MODAL_WEBHOOK_URL="https://YOUR_URL.modal.run"

# Run test
./modal_workflows/test_modal_webhook.sh
```

---

### Method 4: From Python

```python
import requests

webhook_url = "https://YOUR_URL.modal.run/webhook/scrape-apify-leads"

payload = {
    "industry": "Marketing Agency",
    "fetch_count": 30,
    "skip_test": True,
    "valid_only": True
}

response = requests.post(webhook_url, json=payload)
print(response.json())
```

---

### Method 5: From Make.com / Integromat

1. Add **HTTP** module
2. Method: `POST`
3. URL: `https://YOUR_URL.modal.run/webhook/scrape-apify-leads`
4. Headers:
   ```
   Content-Type: application/json
   ```
5. Body (JSON):
   ```json
   {
     "industry": "{{trigger.industry}}",
     "fetch_count": 30,
     "skip_test": true,
     "valid_only": true
   }
   ```

---

### Method 6: From Zapier

1. Add **Webhooks by Zapier** action
2. Choose **POST**
3. URL: `https://YOUR_URL.modal.run/webhook/scrape-apify-leads`
4. Payload Type: `JSON`
5. Data:
   - `industry`: Map from trigger
   - `fetch_count`: `30`
   - `skip_test`: `true`
   - `valid_only`: `true`

---

## 📊 Part 3: Monitoring Your Jobs

### View Real-Time Logs

```bash
modal app logs anti-gravity-webhook
```

**You'll see:**
```
📨 Webhook Request Received (ASYNC)
🎯 Industry: Marketing Agency
📊 Fetch Count: 30
🌍 Location: united states
...
✅ Scraped 30 leads
✅ Scraping completed successfully!
```

---

### Check Job Status

Visit Modal dashboard:
```
https://modal.com/apps/your-workspace/anti-gravity-webhook
```

You can see:
- All function calls
- Execution time
- Success/failure status
- Detailed logs

---

### Download Results

```bash
# List all scraped data files
modal volume ls anti-gravity-data /data/scraped_data

# Download specific file
modal volume get anti-gravity-data \
  /data/scraped_data/apify_leads_Marketing_Agency_20251225_143022.json \
  ./results.json

# View results
cat results.json | jq '.'
```

---

## 🔧 Part 4: Common Use Cases

### Use Case 1: Scrape on Schedule (Daily)

**Option A: Using cron**

```bash
# Add to crontab
crontab -e

# Add this line (runs daily at 9 AM):
0 9 * * * curl -X POST https://YOUR_URL.modal.run/webhook/scrape-apify-leads -H "Content-Type: application/json" -d '{"industry":"Marketing Agency","fetch_count":30,"skip_test":true}'
```

**Option B: Using Make.com Schedule Trigger**
1. Trigger: Schedule (Daily at 9 AM)
2. Action: HTTP POST to your webhook

---

### Use Case 2: Scrape from Google Sheets

**Google Apps Script:**

```javascript
function scrapeLeadsFromSheet() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var industry = sheet.getRange("A2").getValue(); // Industry in cell A2
  var count = sheet.getRange("B2").getValue();    // Count in cell B2

  var url = "https://YOUR_URL.modal.run/webhook/scrape-apify-leads";

  var payload = {
    "industry": industry,
    "fetch_count": count,
    "skip_test": true,
    "valid_only": true
  };

  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  };

  var response = UrlFetchApp.fetch(url, options);
  Logger.log(response.getContentText());

  // Show success message
  Browser.msgBox("Scraping started! Check Modal logs for progress.");
}
```

**Add menu to trigger:**
```javascript
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Lead Scraper')
      .addItem('Scrape Leads', 'scrapeLeadsFromSheet')
      .addToUi();
}
```

---

### Use Case 3: Trigger from Airtable

1. Create Automation in Airtable
2. Trigger: "When record created" or "Button clicked"
3. Action: **Send webhook**
   - Method: POST
   - URL: Your Modal webhook URL
   - Body: Map Airtable fields to JSON

---

### Use Case 4: Multiple Industries in Parallel

```python
import requests
import concurrent.futures

webhook_url = "https://YOUR_URL.modal.run/webhook/scrape-apify-leads"

industries = [
    "Marketing Agency",
    "IT Recruitment",
    "Real Estate",
    "Healthcare"
]

def scrape_industry(industry):
    response = requests.post(webhook_url, json={
        "industry": industry,
        "fetch_count": 30,
        "skip_test": True,
        "valid_only": True
    })
    return response.json()

# Run all 4 in parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    results = list(executor.map(scrape_industry, industries))

for result in results:
    print(f"Job ID: {result['job_id']}, Industry: {result['industry']}")
```

---

## 🐛 Troubleshooting

### Problem: "APIFY_API_KEY not found"

**Solution:**
```bash
# Check if secret exists
modal secret list

# Create if missing
modal secret create anti-gravity-secrets APIFY_API_KEY=your_key_here
```

---

### Problem: "401 Unauthorized"

**Cause:** Webhook secret mismatch

**Solution:**
```bash
# If you set WEBHOOK_SECRET in Modal secrets, include it in requests:
curl -X POST https://YOUR_URL.modal.run/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your_secret_here" \
  -d '{...}'
```

---

### Problem: "Deployment failed"

**Solution:**
```bash
# 1. Check authentication
modal token current

# 2. Re-authenticate if needed
modal token new

# 3. Redeploy
modal deploy modal_workflows/webhook_scrape_apify.py
```

---

### Problem: Job runs but no results

**Solution:**
```bash
# Check logs for errors
modal app logs anti-gravity-webhook

# Common issues:
# - Invalid industry name
# - API rate limits
# - Invalid location format (must be lowercase)
```

---

## 📚 Quick Reference

### All Available Parameters

```json
{
  "industry": "Marketing Agency",           // REQUIRED
  "fetch_count": 30,                       // Default: 30
  "location": "united states",             // Optional (lowercase!)
  "city": "New York",                      // Optional
  "job_title": ["CEO", "Founder"],         // Optional
  "company_size": ["51-100", "101-200"],   // Optional
  "company_keywords": ["PPC", "SEO"],      // Optional
  "company_industry": ["marketing"],       // Optional (lowercase!)
  "skip_test": true,                       // Default: false
  "valid_only": true,                      // Default: false
  "sender_context": "We help agencies..."  // Optional
}
```

---

### Common Commands

```bash
# Deploy webhook
modal deploy modal_workflows/webhook_scrape_apify.py

# View logs
modal app logs anti-gravity-webhook

# List apps
modal app list

# View secrets
modal secret list

# Download results
modal volume ls anti-gravity-data /data/scraped_data
```

---

## 🎉 You're All Set!

**Your workflow:**

1. **Trigger** → Send POST request to webhook
2. **Process** → Modal scrapes leads (30-120 seconds)
3. **Results** → Check logs or download from volume

**Next steps:**
- Integrate with Make.com/Zapier
- Set up scheduled scraping
- Build custom workflows

**Need help?** Check the full guide at [WEBHOOK_MODAL_QUICKSTART.md](modal_workflows/WEBHOOK_MODAL_QUICKSTART.md)
