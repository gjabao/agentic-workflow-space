# Modal Webhook for Apify Lead Scraping - Quick Start

## Overview

Deploy a serverless webhook on Modal to trigger Apify lead scraping from anywhere. Get a public HTTPS URL with automatic scaling, no server maintenance required.

---

## 1. Prerequisites

### Install Modal CLI
```bash
pip install modal
```

### Authenticate with Modal
```bash
modal token new
```

### Set Up Modal Secrets
```bash
# Run the secrets setup script
chmod +x modal_workflows/setup_modal_secrets.sh
./modal_workflows/setup_modal_secrets.sh
```

Or manually create secret `anti-gravity-secrets` with:
- `APIFY_API_KEY`
- `SSMASTERS_API_KEY` (optional)
- `AZURE_OPENAI_ENDPOINT` (optional)
- `AZURE_OPENAI_API_KEY` (optional)
- `WEBHOOK_SECRET` (optional - for webhook auth)

---

## 2. Deploy Webhook to Modal

### Deploy the webhook
```bash
modal deploy modal_workflows/webhook_scrape_apify.py
```

**Output:**
```
✓ Created objects.
├── 🔨 Created mount /Users/.../Anti-Gravity Workspace/modal_workflows
├── 🔨 Created volume anti-gravity-data
└── 🔨 Created web function fastapi_app => https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run

✓ App deployed! 🎉

View at: https://modal.com/apps/your-workspace/anti-gravity-webhook
```

**Your webhook URL:** The HTTPS URL shown in the output (save this!)

---

## 3. Usage

### Test with curl (Async - Recommended)
```bash
# Returns immediately, job runs in background
curl -X POST https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-secret" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 30,
    "location": "united states",
    "company_keywords": ["digital marketing", "PPC"],
    "skip_test": true,
    "valid_only": true
  }'
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "message": "Lead scraping workflow triggered",
  "job_id": "ca-abc123",
  "industry": "Marketing Agency",
  "fetch_count": 30,
  "note": "Job is running in background. Check Modal dashboard for results."
}
```

### Test with curl (Sync - Waits for results)
```bash
# Blocks until scraping completes
curl -X POST https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/webhook/scrape-apify-leads-sync \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 10
  }'
```

---

## 4. API Endpoints

### `GET /`
API documentation and examples

```bash
curl https://your-url.modal.run/
```

### `GET /health`
Health check

```bash
curl https://your-url.modal.run/health
```

### `POST /webhook/scrape-apify-leads`
Trigger scraping (async - returns immediately)

### `POST /webhook/scrape-apify-leads-sync`
Trigger scraping (sync - waits for completion)

### `GET /docs`
Interactive Swagger/OpenAPI docs

```
https://your-url.modal.run/docs
```

---

## 5. Request Payload

### Required Fields
```json
{
  "industry": "Marketing Agency"
}
```

### Full Example
```json
{
  "industry": "Marketing Agency",
  "fetch_count": 30,
  "location": "united states",
  "city": "New York",
  "job_title": ["CEO", "Founder", "CMO"],
  "company_size": ["51-100", "101-200"],
  "company_keywords": ["digital marketing", "PPC agency"],
  "company_industry": ["marketing & advertising"],
  "skip_test": true,
  "valid_only": true,
  "sender_context": "We help marketing agencies scale PPC"
}
```

---

## 6. Security

### Enable Webhook Secret Authentication
1. Add `WEBHOOK_SECRET` to your Modal secret:
   ```bash
   modal secret create anti-gravity-secrets \
     WEBHOOK_SECRET=your-super-secret-key \
     APIFY_API_KEY=apify_api_xxx...
   ```

2. Include header in requests:
   ```bash
   -H "X-Webhook-Secret: your-super-secret-key"
   ```

---

## 7. Monitoring & Debugging

### View Logs in Real-Time
```bash
modal app logs anti-gravity-webhook
```

### Check Running Jobs
Visit: https://modal.com/apps

### View Results
Results are saved to Modal Volume `anti-gravity-data`:
```bash
modal volume ls anti-gravity-data /data/scraped_data
```

Download results:
```bash
modal volume get anti-gravity-data /data/scraped_data/apify_leads_*.json ./
```

---

## 8. Integration Examples

### Make.com / Integromat
1. Add **HTTP** module → **Make a Request**
2. URL: `https://your-url.modal.run/webhook/scrape-apify-leads`
3. Method: POST
4. Headers:
   - `Content-Type`: `application/json`
   - `X-Webhook-Secret`: `{{your_secret}}`
5. Body (JSON):
   ```json
   {
     "industry": "{{1.industry}}",
     "fetch_count": {{1.count}},
     "skip_test": true,
     "valid_only": true
   }
   ```

### Zapier
1. Add **Webhooks by Zapier** → **POST**
2. URL: Your Modal webhook URL
3. Payload Type: JSON
4. Data: Map trigger fields to payload

### n8n
1. Add **HTTP Request** node
2. Method: POST
3. URL: Your Modal webhook URL
4. Authentication: Header Auth
   - Name: `X-Webhook-Secret`
   - Value: Your secret
5. Body: JSON with lead scraping parameters

### Airtable Automation
1. Create **Webhook** action
2. Method: POST
3. URL: Your Modal webhook URL
4. Body: Map Airtable fields to JSON payload

### Google Apps Script (Sheets/Forms)
```javascript
function triggerLeadScraping(industry, count) {
  const url = 'https://your-url.modal.run/webhook/scrape-apify-leads';

  const payload = {
    industry: industry,
    fetch_count: count,
    skip_test: true,
    valid_only: true
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'X-Webhook-Secret': 'your-secret'
    },
    payload: JSON.stringify(payload)
  };

  const response = UrlFetchApp.fetch(url, options);
  Logger.log(response.getContentText());
}
```

---

## 9. Advanced Features

### Async vs Sync Endpoints

**Use `/webhook/scrape-apify-leads` (async)** when:
- Scraping 30+ leads
- Integrating with automation tools
- Don't need immediate results
- Want fast webhook responses

**Use `/webhook/scrape-apify-leads-sync` (sync)** when:
- Scraping < 10 leads
- Need results immediately
- Building synchronous workflows
- Can handle longer wait times

### Scheduled Scraping (Cron)

**Option 1: Modal Scheduled Functions**
Edit the webhook file to add:
```python
@app.function(
    schedule=modal.Period(days=1),  # Run daily
    secrets=[modal.Secret.from_name("anti-gravity-secrets")]
)
def scheduled_scrape():
    """Run daily lead scraping"""
    scrape_apify_leads_modal.remote(
        industry="Marketing Agency",
        fetch_count=50,
        skip_test=True,
        valid_only=True
    )
```

**Option 2: External Cron + Webhook**
```bash
# crontab -e
0 9 * * 1 curl -X POST https://your-url.modal.run/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{"industry":"Marketing Agency","fetch_count":30}'
```

---

## 10. Cost Optimization

### Modal Pricing
- **Free tier**: 30 free credits/month (~30 hours compute)
- **Paid**: $0.00040/sec for 2 vCPU, 2GB RAM
- **Average cost per scrape**: $0.02-0.10 (depending on lead count)

### Tips to Reduce Costs
1. Use `skip_test: true` to skip 25-lead validation
2. Use `valid_only: true` to reduce processing
3. Set appropriate timeouts
4. Use async endpoints (don't keep connections open)
5. Batch multiple requests instead of one-by-one

---

## 11. Troubleshooting

### "APIFY_API_KEY not found"
**Fix:** Add secret to Modal
```bash
modal secret create anti-gravity-secrets APIFY_API_KEY=apify_api_xxx
```

### Webhook returns 401 Unauthorized
**Fix:** Include correct webhook secret in header
```bash
-H "X-Webhook-Secret: your-secret"
```

### Job times out
**Fix:** Increase timeout in webhook file
```python
@app.function(
    timeout=7200,  # 2 hours instead of 1
    ...
)
```

### Can't access results
**Fix:** Check Modal volume
```bash
modal volume ls anti-gravity-data /data/scraped_data
```

---

## 12. Updating the Webhook

### Redeploy after code changes
```bash
modal deploy modal_workflows/webhook_scrape_apify.py
```

URL stays the same - updates are live immediately!

### View deployment history
Visit: https://modal.com/apps/your-workspace/anti-gravity-webhook

---

## 13. Local Testing (Before Deploy)

### Run locally with Modal
```bash
modal serve modal_workflows/webhook_scrape_apify.py
```

This starts a local dev server with hot reload:
- URL: `https://your-workspace--anti-gravity-webhook-fastapi-app-dev.modal.run`
- Auto-reloads on file changes
- Same environment as production

---

## Questions?

- **Modal Docs**: https://modal.com/docs
- **Webhook Logs**: `modal app logs anti-gravity-webhook`
- **Support**: Check Modal Slack or Discord

---

**You now have a production-ready, serverless webhook for lead scraping! 🚀**