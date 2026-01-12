# 🎯 How to Trigger Modal Workflows

Complete guide on triggering your Modal workflows on-demand.

---

## 🚀 Method 1: Command Line (Easiest)

### Basic Usage

```bash
export PATH="/Users/nguyengiabao/Library/Python/3.9/bin:$PATH"
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# Run any workflow
python3 -m modal run modal_workflows/your_workflow.py
```

### Examples

```bash
# Daily campaign report
python3 -m modal run modal_workflows/email_campaign_report.py

# Scrape leads with parameters
python3 -m modal run modal_workflows/scrape_on_demand.py \
    --query "dentists in New York" \
    --limit 100

# Generate copy
python3 -m modal run modal_workflows/generate_copy_on_demand.py \
    --company-name "ABC Dental" \
    --industry "dental" \
    --location "New York"
```

---

## 🎮 Method 2: Interactive Menu (Super Easy!)

I created an interactive script for you:

```bash
./trigger_workflow.sh
```

**What it does:**
- Shows menu of available workflows
- Prompts for parameters
- Runs the workflow
- Shows results

**Menu:**
```
🚀 Modal Workflow Trigger
=========================

Select workflow to run:
1. Daily Campaign Report
2. Scrape Leads (custom query)
3. Generate Email Copy
4. View Logs
5. Exit

Enter choice [1-5]:
```

---

## 🌐 Method 3: API Endpoint (Call from Anywhere)

### Step 1: Deploy API

```bash
python3 -m modal deploy modal_workflows/api_endpoint_example.py
```

**Output:**
```
✓ App deployed!

View at: https://modal.com/apps/anti-gravity-api
API URL: https://giabaongb0305--anti-gravity-api-fastapi-app.modal.run
```

### Step 2: Get Your API URL

Go to https://modal.com/apps and find your API URL.

It looks like: `https://giabaongb0305--anti-gravity-api-fastapi-app.modal.run`

### Step 3: Call the API

**From command line (curl):**

```bash
# Scrape leads
curl -X POST https://your-app.modal.run/scrape \
    -H 'Content-Type: application/json' \
    -d '{"query": "dentists in New York", "limit": 100}'

# Generate copy
curl -X POST https://your-app.modal.run/generate-copy \
    -H 'Content-Type: application/json' \
    -d '{"company_name": "ABC Dental", "industry": "dental"}'

# Simple GET request
curl "https://your-app.modal.run/scrape-simple?query=dentists&limit=100"
```

**From Python:**

```python
import requests

url = "https://your-app.modal.run/scrape"
data = {
    "query": "dentists in New York",
    "limit": 100
}

response = requests.post(url, json=data)
print(response.json())
```

**From browser:**
```
https://your-app.modal.run/scrape-simple?query=dentists&limit=100
```

**From Zapier/Make/n8n:**
- Webhook trigger → HTTP request → Your Modal API URL

---

## 📱 Method 4: Python Script

Create a Python script to trigger workflows:

```python
#!/usr/bin/env python3
import requests

def trigger_scrape(query: str, limit: int = 100):
    """Trigger lead scraping"""
    url = "https://your-app.modal.run/scrape"
    data = {"query": query, "limit": limit}

    response = requests.post(url, json=data)
    return response.json()

# Use it
result = trigger_scrape("dentists in New York", 100)
print(result)
```

See [modal_workflows/python_trigger_example.py](modal_workflows/python_trigger_example.py) for more examples.

---

## ⏰ Method 5: Scheduled (Cron)

Workflows run automatically on schedule:

```python
# Already deployed: runs daily at 7 AM Hanoi time
@app.function(schedule=modal.Cron("0 0 * * *"))
def daily_campaign_report():
    # Runs automatically
    pass
```

**View schedule:**
```bash
python3 -m modal app list
```

**Change schedule:** Edit the workflow file and redeploy:
```bash
python3 -m modal deploy modal_workflows/email_campaign_report.py
```

---

## 🔗 Method 6: Webhooks (Real-time Triggers)

Deploy a webhook endpoint that responds to external events:

```python
# Deploy webhook server
python3 -m modal deploy modal_workflows/webhook_server.py
```

**Use cases:**
- Instantly sends a reply → Your webhook processes it
- New lead added to CRM → Webhook generates copy
- Campaign reaches 100 sends → Webhook checks performance

**Get webhook URL from Modal dashboard.**

---

## 🔄 Method 7: From Another Modal Function

Call one Modal function from another:

```python
@app.function()
def scrape_leads(query: str):
    # Scrape logic
    return leads

@app.function()
def scrape_and_enrich(query: str):
    # Call another Modal function
    leads = scrape_leads.remote(query)

    # Enrich the leads
    enriched = enrich_leads.remote(leads)

    return enriched
```

---

## 📊 Comparison: Which Method to Use?

| Method | Best For | Difficulty | Speed |
|--------|----------|-----------|-------|
| **Command Line** | Quick tests, manual runs | Easy | Instant |
| **Interactive Menu** | Non-technical users | Very Easy | Instant |
| **API Endpoint** | Integrations, automations | Medium | Instant |
| **Python Script** | Batch processing | Easy | Instant |
| **Scheduled (Cron)** | Recurring tasks | Easy | Scheduled |
| **Webhooks** | Real-time triggers | Medium | Real-time |
| **From Modal** | Complex workflows | Medium | Instant |

---

## 🎯 Practical Examples

### Example 1: Daily Manual Report

**When:** Every morning, before your meeting

**How:** Interactive menu
```bash
./trigger_workflow.sh
# Select: 1. Daily Campaign Report
```

---

### Example 2: Urgent Lead Scraping

**When:** Client needs 500 dentist leads NOW

**How:** Command line with parameters
```bash
python3 -m modal run modal_workflows/scrape_on_demand.py \
    --query "dentists in New York" \
    --limit 500
```

---

### Example 3: Bulk Copy Generation

**When:** Generate copy for 100 companies

**How:** Python script
```python
companies = [
    ("ABC Dental", "dental", "New York"),
    ("XYZ Realty", "real estate", "California"),
    # ... 98 more
]

for name, industry, location in companies:
    result = trigger_copy_generation(name, industry, location)
    save_to_file(result)
```

---

### Example 4: Zapier Integration

**When:** New lead added to Google Sheets → Generate copy automatically

**How:** Zapier webhook → Modal API
1. Deploy API endpoint
2. Create Zapier workflow:
   - Trigger: New row in Google Sheets
   - Action: Webhook POST to Modal API
   - Pass company name, industry from sheet

---

### Example 5: Slack Command

**When:** Type `/scrape dentists 100` in Slack → Get results

**How:** Slack bot → Modal API
1. Deploy Modal API
2. Create Slack app with slash command
3. Slash command calls Modal API
4. Returns results to Slack

---

## 🛠️ Advanced: Trigger with Data

### Pass Complex Data

```python
# Workflow that accepts JSON
@app.function()
def process_leads(leads: list[dict]):
    for lead in leads:
        # Process each lead
        pass

@app.local_entrypoint()
def main():
    # Load leads from file
    import json
    with open('leads.json') as f:
        leads = json.load(f)

    # Process them
    process_leads.remote(leads)
```

**Run:**
```bash
python3 -m modal run modal_workflows/process_leads.py
```

---

### Upload Files to Modal

```python
# Workflow that processes a CSV
@app.function()
def process_csv(csv_content: str):
    import csv
    import io

    reader = csv.DictReader(io.StringIO(csv_content))
    for row in reader:
        # Process each row
        pass

@app.local_entrypoint()
def main():
    with open('leads.csv') as f:
        content = f.read()

    process_csv.remote(content)
```

---

## 📝 Quick Reference

### Essential Commands

```bash
# Set PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="/Users/nguyengiabao/Library/Python/3.9/bin:$PATH"

# Run workflow
python3 -m modal run modal_workflows/your_workflow.py

# Deploy workflow (creates cron)
python3 -m modal deploy modal_workflows/your_workflow.py

# View logs (live)
python3 -m modal app logs anti-gravity-workflows --follow

# View logs (recent)
python3 -m modal app logs anti-gravity-workflows

# List apps
python3 -m modal app list

# Stop app
python3 -m modal app stop anti-gravity-workflows
```

---

## 🎨 Create Custom Trigger

Want to create your own trigger method? Here's a template:

```python
"""
Custom Workflow Template
"""

import modal

app = modal.App("anti-gravity-workflows")

@app.function(
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600
)
def your_custom_function(param1: str, param2: int = 100):
    """
    Your custom logic here

    Args:
        param1: Description
        param2: Description (default: 100)
    """
    import os

    print(f"Running with: {param1}, {param2}")

    # Your code here
    api_key = os.environ["YOUR_API_KEY"]

    # Do something
    result = {"status": "success"}

    return result


@app.local_entrypoint()
def main(param1: str, param2: int = 100):
    """
    CLI entry point

    Usage:
        python3 -m modal run your_workflow.py \
            --param1 "value" \
            --param2 200
    """
    result = your_custom_function.remote(param1, param2)
    print(f"Result: {result}")
```

**Save as:** `modal_workflows/your_workflow.py`

**Run:**
```bash
python3 -m modal run modal_workflows/your_workflow.py \
    --param1 "test" \
    --param2 200
```

---

## 🚀 Next Steps

1. **Try the interactive menu:**
   ```bash
   ./trigger_workflow.sh
   ```

2. **Deploy an API endpoint:**
   ```bash
   python3 -m modal deploy modal_workflows/api_endpoint_example.py
   ```

3. **Create your own workflow** using the template above

4. **Integrate with Zapier/Make** for full automation

---

## 📚 Related Docs

- [WHAT_YOU_CAN_DO_WITH_MODAL.md](WHAT_YOU_CAN_DO_WITH_MODAL.md) - Full capabilities
- [MODAL_QUICKSTART.md](MODAL_QUICKSTART.md) - Setup guide
- [MODAL_SETUP.md](MODAL_SETUP.md) - Deep dive

**Need help?** Just ask! I can create any custom trigger you need. 🚀
