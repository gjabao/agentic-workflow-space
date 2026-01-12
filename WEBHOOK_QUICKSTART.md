# Webhook Quick Start - TL;DR Version

## 🎯 What You Have

Two ways to trigger Apify lead scraping via webhook:

| Method | URL | Setup Time | Best For |
|--------|-----|------------|----------|
| **Local** | `http://localhost:5000` | 30 seconds | Testing |
| **Modal** | `https://xxx.modal.run` | 5 minutes | Production |

---

## ⚡ Super Quick Start

### Option 1: Local (30 seconds)

```bash
# Start server
python3 execution/webhook_server.py

# Test (in another terminal)
curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{"industry": "Marketing Agency", "fetch_count": 5}'
```

**Done!** ✅

---

### Option 2: Modal (One Command)

```bash
# Automated setup (does everything)
./setup_modal_webhook.sh
```

**What it does:**
1. ✅ Installs Modal CLI
2. ✅ Authenticates you (opens browser)
3. ✅ Uploads your API keys from `.env`
4. ✅ Deploys webhook to Modal
5. ✅ Gives you public HTTPS URL

**Output:**
```
🎉 SETUP COMPLETE!

Your webhook is live at:
https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/webhook/scrape-apify-leads
```

**Done!** ✅

---

## 📡 How to Use

### Basic Example

```bash
curl -X POST YOUR_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 30
  }'
```

### Full Example (All Options)

```bash
curl -X POST YOUR_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 30,
    "location": "united states",
    "company_keywords": ["digital marketing", "PPC"],
    "job_title": ["CEO", "Founder"],
    "skip_test": true,
    "valid_only": true
  }'
```

### Response

```json
{
  "status": "accepted",
  "job_id": "ca-abc123",
  "message": "Lead scraping workflow triggered"
}
```

---

## 🔗 Integration Examples

### Make.com / Integromat

1. HTTP module → POST request
2. URL: Your webhook URL
3. Body: Map trigger fields to JSON

### Zapier

1. Webhooks by Zapier → POST
2. URL: Your webhook URL
3. Payload: JSON with industry, fetch_count, etc.

### Python

```python
import requests

response = requests.post(
    "YOUR_WEBHOOK_URL",
    json={
        "industry": "Marketing Agency",
        "fetch_count": 30,
        "skip_test": True,
        "valid_only": True
    }
)

print(response.json())
```

### Google Sheets (Apps Script)

```javascript
function scrapeLeads() {
  var url = "YOUR_WEBHOOK_URL";
  var payload = {
    "industry": "Marketing Agency",
    "fetch_count": 30
  };

  UrlFetchApp.fetch(url, {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  });
}
```

---

## 📊 Monitoring

### Local Flask

```bash
# Check terminal where server is running
# Logs show up in real-time
```

### Modal

```bash
# View logs
modal app logs anti-gravity-webhook

# Download results
modal volume ls anti-gravity-data /data/scraped_data
```

---

## 🆘 Troubleshooting

### Local: "Connection refused"

→ Server not running. Start it:
```bash
python3 execution/webhook_server.py
```

### Modal: "APIFY_API_KEY not found"

→ Add secrets:
```bash
modal secret create anti-gravity-secrets APIFY_API_KEY=your_key
```

### Both: "Invalid industry"

→ Check spelling and format:
```json
{"industry": "Marketing Agency"}  ✅
{"industry": "marketing agency"}  ❌ (case matters)
```

---

## 📚 Full Documentation

- **Step-by-step guide**: [MODAL_WEBHOOK_HOWTO.md](MODAL_WEBHOOK_HOWTO.md)
- **Local vs Modal comparison**: [WEBHOOK_COMPARISON.md](WEBHOOK_COMPARISON.md)
- **Modal deep dive**: [modal_workflows/WEBHOOK_MODAL_QUICKSTART.md](modal_workflows/WEBHOOK_MODAL_QUICKSTART.md)
- **Local webhook guide**: [WEBHOOK_APIFY_QUICKSTART.md](WEBHOOK_APIFY_QUICKSTART.md)

---

## 🎯 Common Use Cases

### 1. Daily Automated Scraping

**Cron (Linux/Mac):**
```bash
# Edit crontab
crontab -e

# Add: Run daily at 9 AM
0 9 * * * curl -X POST YOUR_WEBHOOK_URL -H "Content-Type: application/json" -d '{"industry":"Marketing Agency","fetch_count":30}'
```

**Make.com:**
- Trigger: Schedule (daily 9 AM)
- Action: HTTP POST to webhook

---

### 2. Trigger from Airtable

1. Create button field in Airtable
2. Add automation: "When button clicked"
3. Action: Send webhook
4. URL: Your webhook URL
5. Body: Map Airtable fields

---

### 3. Scrape Multiple Industries

```bash
# Scrape 3 industries in parallel
for industry in "Marketing Agency" "IT Recruitment" "Real Estate"; do
  curl -X POST YOUR_WEBHOOK_URL \
    -H "Content-Type: application/json" \
    -d "{\"industry\":\"$industry\",\"fetch_count\":30}" &
done
wait
```

---

## 🔥 Pro Tips

1. **Use `skip_test: true`** for faster scraping (skips 25-lead validation)
2. **Use `valid_only: true`** to get only verified emails
3. **Location must be lowercase**: `"united states"` not `"United States"`
4. **Company industry must be lowercase**: `["marketing & advertising"]`
5. **Modal free tier = 30 credits/month** (~30 hours compute) - enough for most use cases

---

## ✅ That's It!

**You have:**
- ✅ Local webhook for testing
- ✅ Modal webhook for production
- ✅ Integration examples for Make/Zapier/Python
- ✅ Complete documentation

**Choose your path:**
- 🏃 **Quick test?** Use local webhook
- 🚀 **Production?** Deploy to Modal
- 🤖 **Integration?** Use Modal webhook URL

**One command to rule them all:**
```bash
./setup_modal_webhook.sh
```

Happy scraping! 🎉
