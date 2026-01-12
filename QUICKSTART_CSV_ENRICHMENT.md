# CSV Enrichment - Quick Start Guide

## 🚀 One-Command Enrichment

```bash
python3 execution/enrich_client_prospects.py \
  --csv "YOUR_FILE.csv" \
  --sheet-id "YOUR_GOOGLE_SHEET_ID" \
  --tab-name "TAB_NAME" \
  --location "City, Country"
```

---

## ✅ What You Need

### 1. CSV File
Must have `Business Name` column. All other columns optional.

### 2. Google Sheet ID
Get from sheet URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

### 3. API Keys in .env
```bash
APIFY_API_KEY=apify_api_xxxxx              # Required
ANYMAILFINDER_API_KEY=xxxxx                # Optional
RAPIDAPI_KEYS=key1,key2                    # Optional
```

---

## 📊 Example

### Input CSV:
```csv
Business Name,City,Status,Notes
"Lethbridge plastic surgery","Lethbridge","","dr. Secretan - left info"
"Bliss beauty bar","Lethbridge","Interested","Stevie interested***"
```

### Run Command:
```bash
python3 execution/enrich_client_prospects.py \
  --csv "Client_Prospects_Lethbridge.csv" \
  --sheet-id "1raXQLnGSw8z2ejNwRbud52YL1KiBW18eChzPh5vIe2s" \
  --tab-name "Lethbridge" \
  --location "Lethbridge, Canada" \
  --test-limit 3
```

### Output Google Sheet:
```csv
Business Name,Phone,Website,Email,City,Type,Status,Notes
"Lethbridge plastic surgery","+1-403-XXX","https://...","info@...","Lethbridge","Plastic Surgery","","dr. Secretan - left info"
"Bliss beauty bar","+1-403-XXX","https://...","stevie@...","Lethbridge","Beauty Salon","Interested","Stevie interested***"
```

**✅ Status & Notes PRESERVED!**

---

## ⚡ Quick Tips

### Test First
```bash
--test-limit 3  # Test with 3 rows only
```

### Fix OAuth Issues
```bash
rm -f token.json  # Delete and re-authenticate
```

### Check Logs
```bash
tail -f .tmp/enrich_client_prospects.log
```

---

## 💰 Cost

| Businesses | Old Cost | Batch Cost | Savings |
|------------|----------|------------|---------|
| 3 | $0.0135 | $0.0045 | 66% |
| 16 | $0.072 | $0.0045 | 94% |
| 100 | $0.45 | $0.0045 | **99%** |

**ONE Apify call for ALL businesses = 99% cost savings!**

---

## 🎯 What Gets Enriched

- ✅ Phone (~95%)
- ✅ Website (~95%)
- ✅ Full Address (~95%)
- ✅ Type/Category (~95%)
- ✅ Email (50-70%)
- ✅ Primary Contact (18-25%)
- ✅ Job Title (18-25%)
- ✅ Contact LinkedIn (18-25%)
- ✅ Company Social (70-75%)
- ✅ **ALL original data preserved (100%)**

---

## 🔍 Troubleshooting

**OAuth Error?**
```bash
rm -f token.json && python3 execution/enrich_client_prospects.py ...
```

**CSV Not Found?**
```bash
ls -la *.csv  # Check file exists
```

**Low Contact Rate?**
Normal for small businesses (18-25% expected)

---

## 📖 Full Documentation

See: `directives/enrich_csv_to_sheets.md`

---

**Ready to enrich? Just run the command!** 🚀
