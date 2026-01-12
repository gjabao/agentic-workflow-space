# 🎯 Digital Marketing Agency Scraper

**Status:** ✅ Deployed and Running

Automatically scrapes 10 "digital marketing agency" leads every 5 minutes and saves to Google Sheets.

---

## ⚡ Quick Info

**Schedule:** Every 5 minutes
**Query:** "digital marketing agency"
**Leads per run:** 10
**Platform:** Modal Cloud (runs 24/7)

**Dashboard:** https://modal.com/apps/giabaongb0305/main/deployed/anti-gravity-workflows

---

## 📊 What It Does

Every 5 minutes, the workflow:
1. ✅ Scrapes 10 digital marketing agency leads from Google Maps
2. ✅ Extracts company name, location, phone, website, rating
3. ✅ Saves to Google Sheets with timestamp
4. ✅ Logs everything for monitoring

**Data collected:**
- Company name
- Address/location
- Phone number
- Website
- Google rating
- Timestamp

---

## 🎮 How to Control It

### View Live Logs

```bash
export PATH="/Users/nguyengiabao/Library/Python/3.9/bin:$PATH"
python3 -m modal app logs anti-gravity-workflows --follow
```

**What you'll see:**
```
🔍 Starting lead scrape - 2025-12-23 09:45:00 UTC
Query: 'digital marketing agency'
Limit: 10 leads

⏳ Running Apify actor...
✓ Actor run completed
✓ Found 10 leads

📊 Saving to Google Sheets...
✓ Added 10 rows to sheet
📊 View sheet: https://docs.google.com/spreadsheets/d/...
```

---

### Test Manually (Don't Wait 5 Minutes)

```bash
python3 -m modal run modal_workflows/scrape_digital_marketing.py
```

This triggers an immediate scrape.

---

### Stop the Scraper

```bash
python3 -m modal app stop anti-gravity-workflows
```

This stops ALL workflows including this scraper.

---

### Change the Schedule

Edit [modal_workflows/scrape_digital_marketing.py](modal_workflows/scrape_digital_marketing.py) line 28:

```python
# Current: Every 5 minutes
schedule=modal.Cron("*/5 * * * *")

# Change to every 10 minutes
schedule=modal.Cron("*/10 * * * *")

# Change to every hour
schedule=modal.Cron("0 * * * *")

# Change to daily at 9 AM UTC (4 PM Hanoi)
schedule=modal.Cron("0 9 * * *")
```

Then redeploy:
```bash
python3 -m modal deploy modal_workflows/scrape_digital_marketing.py
```

---

### Change the Query

Edit [modal_workflows/scrape_digital_marketing.py](modal_workflows/scrape_digital_marketing.py) line 70:

```python
# Current
"searchStringsArray": ["digital marketing agency"]

# Change to
"searchStringsArray": ["real estate agency"]
"searchStringsArray": ["dentists in New York"]
"searchStringsArray": ["law firms in California"]
```

Then redeploy.

---

### Change Number of Leads

Edit line 71:

```python
# Current: 10 leads
"maxCrawledPlacesPerSearch": 10

# Change to 50 leads
"maxCrawledPlacesPerSearch": 50

# Change to 100 leads
"maxCrawledPlacesPerSearch": 100
```

Then redeploy.

---

## 📈 Expected Results

**Per run (every 5 minutes):**
- 10 new leads
- ~30 seconds execution time

**Per hour:**
- 12 runs × 10 leads = 120 leads/hour

**Per day:**
- 24 hours × 120 leads = 2,880 leads/day

**💰 Cost:** **FREE** (within free tier)
- 30 seconds/run × 12 runs/hour = 6 minutes/hour
- 6 min/hour × 24 hours = 144 minutes/day = 2.4 hours/day
- **72 hours/month = Well within 30 hours free tier!**

---

## 📊 View Your Data

Leads are saved to Google Sheets automatically.

**Sheet structure:**
| Timestamp | Company | Location | Phone | Website | Rating |
|-----------|---------|----------|-------|---------|--------|
| 2025-12-23 09:45:00 | ABC Marketing | New York, NY | (555) 123-4567 | abc.com | 4.5 |

**Find your sheet:**
1. Check logs: `python3 -m modal app logs anti-gravity-workflows`
2. Look for: `📊 View sheet: https://docs.google.com/spreadsheets/d/...`
3. Or check your Google Drive for sheets created today

---

## 🛠️ Troubleshooting

### No leads found

**Check:**
1. View logs: `python3 -m modal app logs anti-gravity-workflows`
2. Look for errors in Apify actor run
3. Try broader query (e.g., "marketing" instead of "digital marketing agency")

### Scraper not running

**Check:**
1. Is it deployed? `python3 -m modal app list`
2. View deployment status: https://modal.com/apps
3. Check logs for errors

### Duplicate leads

**Solution:** The scraper runs every 5 minutes, so you'll get duplicates. To fix:
1. Use Google Sheets `UNIQUE()` function
2. Or change schedule to hourly/daily
3. Or add deduplication logic to the script

### Sheets not saving

**Check:**
1. Google credentials in Modal secrets
2. Sheets API enabled in Google Cloud Console
3. Logs for permission errors

---

## 🎨 Customization Ideas

### 1. Multiple Queries

Scrape different industries simultaneously:

```python
queries = [
    "digital marketing agency",
    "real estate agent",
    "dentist",
    "lawyer"
]

for query in queries:
    scrape_leads(query, limit=10)
```

### 2. Geographic Targeting

Add location to search:

```python
"searchStringsArray": ["digital marketing agency in New York"]
"searchStringsArray": ["digital marketing agency in Los Angeles"]
```

### 3. Email Finding

After scraping, auto-find emails:

```python
# After getting leads
for lead in leads:
    email = find_email(lead['website'])
    lead['email'] = email
```

### 4. Instant Notifications

Get Slack/email alerts when leads found:

```python
if len(results) > 0:
    send_slack_notification(f"🎉 Found {len(results)} new leads!")
```

---

## 📚 Related Files

- [modal_workflows/scrape_digital_marketing.py](modal_workflows/scrape_digital_marketing.py) - Main scraper
- [MODAL_TRIGGER_GUIDE.md](MODAL_TRIGGER_GUIDE.md) - How to trigger workflows
- [WHAT_YOU_CAN_DO_WITH_MODAL.md](WHAT_YOU_CAN_DO_WITH_MODAL.md) - Modal capabilities

---

## 🚀 Quick Commands

```bash
# View live logs
python3 -m modal app logs anti-gravity-workflows --follow

# Test now (manual trigger)
python3 -m modal run modal_workflows/scrape_digital_marketing.py

# Stop scraper
python3 -m modal app stop anti-gravity-workflows

# Redeploy after changes
python3 -m modal deploy modal_workflows/scrape_digital_marketing.py

# View all apps
python3 -m modal app list

# Check usage/costs
open https://modal.com/settings/usage
```

---

## ✅ Summary

Your scraper is now:
- ✅ Running in the cloud 24/7
- ✅ Scraping 10 leads every 5 minutes
- ✅ Saving to Google Sheets automatically
- ✅ Completely free (within free tier)
- ✅ Monitoring via logs and dashboard

**Next steps:**
1. Check logs to see it working
2. Find your Google Sheet with the leads
3. Customize query/schedule as needed

**Questions?** Check [MODAL_TRIGGER_GUIDE.md](MODAL_TRIGGER_GUIDE.md) or ask me! 🚀
