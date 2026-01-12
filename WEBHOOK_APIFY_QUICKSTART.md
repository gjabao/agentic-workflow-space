# Apify Leads Scraping Webhook - Quick Start Guide

## Overview

Trigger Apify lead scraping workflows via HTTP webhook. Perfect for integrating with external tools, schedulers, or automation platforms like Make.com, Zapier, or n8n.

---

## 1. Start the Webhook Server

### Option A: Development Mode (Local Testing)
```bash
python3 execution/webhook_server.py
```
Server will run on: `http://localhost:5000`

### Option B: Production Mode (Public Server)
```bash
# Install gunicorn first
pip install gunicorn

# Run with 4 worker processes
gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
```

---

## 2. Webhook Endpoint

**URL:** `POST /webhook/scrape-apify-leads`

**Authentication:** Optional `X-Webhook-Secret` header

**Content-Type:** `application/json`

---

## 3. Request Payload

### Required Fields
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `industry` | string | Target industry | `"Marketing Agency"` |

### Optional Fields
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `fetch_count` | integer | Number of leads (default: 30) | `50` |
| `location` | string | Target location (lowercase) | `"united states"` |
| `city` | string | Target city | `"New York"` |
| `job_title` | array | Job titles to filter | `["CEO", "Founder"]` |
| `company_size` | array | Company size ranges | `["51-100", "101-200"]` |
| `company_keywords` | array | Keywords for filtering | `["PPC", "digital marketing"]` |
| `company_industry` | array | Apify industry filters | `["marketing & advertising"]` |
| `skip_test` | boolean | Skip 25-lead validation | `true` |
| `valid_only` | boolean | Export only valid emails | `true` |
| `sender_context` | string | Context for SSM icebreakers | `"We help agencies scale PPC"` |

---

## 4. Example Requests

### Minimal Request (Industry Only)
```bash
curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "Marketing Agency"
  }'
```

### Full Request (All Options)
```bash
curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-secret-key" \
  -d '{
    "industry": "Marketing Agency",
    "fetch_count": 30,
    "location": "united states",
    "company_keywords": ["digital marketing", "PPC agency", "performance marketing"],
    "job_title": ["CEO", "Founder", "CMO"],
    "company_industry": ["marketing & advertising"],
    "skip_test": true,
    "valid_only": true,
    "sender_context": "We help marketing agencies scale their PPC campaigns with AI"
  }'
```

### Using the Test Script
```bash
chmod +x test_webhook_apify.sh
./test_webhook_apify.sh
```

---

## 5. Response Format

### Success Response (202 Accepted)
```json
{
  "status": "success",
  "message": "Lead scraping workflow triggered",
  "industry": "Marketing Agency",
  "fetch_count": 30,
  "request_file": ".tmp/webhooks/scrape_request_20251225_143022.json",
  "process_id": 12345
}
```

### Error Responses

**401 Unauthorized** (Invalid webhook secret)
```json
{
  "error": "Unauthorized"
}
```

**400 Bad Request** (Missing required field)
```json
{
  "error": "Missing required field: industry"
}
```

**500 Internal Server Error** (Execution failed)
```json
{
  "error": "Error message here"
}
```

---

## 6. Integration Examples

### Make.com (Integromat)
1. Add HTTP module → Make a POST request
2. URL: `http://your-server:5000/webhook/scrape-apify-leads`
3. Headers: `Content-Type: application/json`
4. Body: JSON payload (see examples above)

### Zapier
1. Add Webhooks by Zapier → POST
2. URL: `http://your-server:5000/webhook/scrape-apify-leads`
3. Payload Type: JSON
4. Data: Map your trigger data to the payload fields

### n8n
1. Add HTTP Request node
2. Method: POST
3. URL: `http://your-server:5000/webhook/scrape-apify-leads`
4. Body Content Type: JSON
5. Specify JSON: Paste payload structure

### Cron Job (Scheduled Scraping)
```bash
# Add to crontab -e
# Scrape 30 marketing agency leads every Monday at 9am
0 9 * * 1 curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{"industry":"Marketing Agency","fetch_count":30,"skip_test":true,"valid_only":true}'
```

---

## 7. Monitoring & Debugging

### Check Webhook Logs
Webhook requests are saved to: `.tmp/webhooks/scrape_request_*.json`

### View Workflow Output
Check execution logs: `.tmp/execution.log`

### Health Check
```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-25T14:30:22.123456"
}
```

---

## 8. Security Best Practices

### Set Webhook Secret
```bash
export INSTANTLY_WEBHOOK_SECRET="your-super-secret-key"
```

Then include in requests:
```bash
-H "X-Webhook-Secret: your-super-secret-key"
```

### Production Deployment
1. Use HTTPS (not HTTP)
2. Use a reverse proxy (nginx, Caddy)
3. Enable rate limiting
4. Use environment variables for secrets
5. Monitor webhook logs for suspicious activity

---

## 9. Troubleshooting

### Webhook Returns 500 Error
- Check server logs for error details
- Verify API keys are set in `.env`
- Ensure `scrape_apify_leads.py` is executable

### Workflow Not Running
- Check server logs for subprocess errors
- Verify Python path is correct (`python3` vs `python`)
- Ensure all dependencies are installed

### Invalid Company Size Error
Use valid Apify size ranges:
```
"1-10", "11-20", "21-50", "51-100", "101-200", "201-500",
"501-1000", "1001-2000", "2001-5000", "5001-10000",
"10001-20000", "20001-50000", "50000+"
```

---

## 10. Advanced Usage

### Trigger Multiple Workflows in Parallel
Send multiple webhook requests to different endpoints:
```bash
# Scrape marketing agencies
curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{"industry":"Marketing Agency","fetch_count":30}'

# Scrape IT recruitment firms
curl -X POST http://localhost:5000/webhook/scrape-apify-leads \
  -H "Content-Type: application/json" \
  -d '{"industry":"IT Recruitment","fetch_count":30}'
```

### Chain Workflows (Scrape → Email Campaign)
1. Trigger scrape webhook
2. Use webhook response `request_file` to track progress
3. Monitor for Google Sheet URL in execution logs
4. Trigger email campaign webhook with leads from sheet

---

**Questions?** Check the main directive: [directives/scrape_leads.md](directives/scrape_leads.md)