# Test Client Enrichment Workflow

## ✅ READY TO TEST!

Tôi đã tạo xong toàn bộ workflow. Đây là cách test:

---

## Step 1: Upload CSV to Google Sheet

```bash
python execution/upload_csv_to_new_sheet.py \
  --csv "test_lethbridge_prospects.csv" \
  --title "Lethbridge Client Prospects - Test"
```

**Output sẽ cho bạn:**
- Sheet ID (VD: `1ABC...XYZ`)
- Sheet URL

---

## Step 2: Run Enrichment

```bash
# Test với 3 rows đầu tiên
python execution/enrich_client_prospects.py \
  --csv "test_lethbridge_prospects.csv" \
  --sheet-id "SHEET_ID_FROM_STEP_1" \
  --tab-name "Sheet1" \
  --location "Lethbridge, Canada" \
  --test-limit 3

# Full run (all rows)
python execution/enrich_client_prospects.py \
  --csv "test_lethbridge_prospects.csv" \
  --sheet-id "SHEET_ID_FROM_STEP_1" \
  --tab-name "Sheet1" \
  --location "Lethbridge, Canada"
```

---

## Expected Results

### Before Enrichment (CSV Input):
```csv
Business Name,Primary Contact,Phone,Email,City,Status,Notes
"Lethbridge plastic surgery","","","","Lethbridge","","dr. Secretan - left info"
"Bliss beauty bar","","","","Lethbridge","Interested","Stevie interested***"
```

### After Enrichment (Google Sheet):
```csv
Business Name,Primary Contact,Phone,Email,City,Job Title,Contact LinkedIn,Website,Full Address,Type,Company Social,Status,Notes
"Lethbridge plastic surgery","Dr. Secretan","+1 403-XXX-XXXX","info@example.com","Lethbridge","Plastic Surgeon","linkedin.com/in/...","https://...","830 4th Ave S","Plastic Surgery","instagram.com/...","","dr. Secretan - left info"
"Bliss beauty bar","Stevie","+1 403-XXX-XXXX","stevie@bliss.com","Lethbridge","Owner","linkedin.com/in/...","https://...","123 Main St","Beauty Salon","instagram.com/bliss","Interested","Stevie interested***"
```

**Key Points:**
- ✅ Status và Notes columns GIỮ NGUYÊN 100%
- ✅ Chỉ điền data vào fields TRỐNG
- ✅ Nếu không tìm được data → Để TRỐNG (không xoá row)

---

## What the Script Does

### 1. Batch Google Maps Lookup
```
Input: 5 business names from CSV
Apify Call: ONE batch call for all 5 businesses
Cost: $0.0045 (instead of $0.0225 for 5 individual calls)
```

### 2. Email Discovery
```
For each business with website:
  → AnyMailFinder: Get ALL emails
  → Prioritize: Personal emails > Generic emails
  → Pick best email
```

### 3. Contact Enrichment
```
For each email:
  → Extract name from email (if personal)
  → RapidAPI: Search LinkedIn
  → Extract: Full Name, Job Title, LinkedIn URL
```

### 4. Company Social
```
For each business:
  → RapidAPI: Search Instagram/Facebook
  → Return: Company social media URL
```

### 5. Update Google Sheet
```
Merge enriched data with original CSV
Preserve ALL existing columns (Status, Notes, etc.)
Update Google Sheet
```

---

## Logs

Check logs for details:
```bash
tail -f .tmp/enrich_client_prospects.log
```

---

## Architecture

### Files Created:
1. `directives/enrich_client_prospects.md` - ✅ Exists (v5.0)
2. `execution/enrich_client_prospects.py` - ✅ Created (v1.0)
3. `execution/upload_csv_to_new_sheet.py` - ✅ Created (helper)
4. `test_lethbridge_prospects.csv` - ✅ Created (test data)

### Logic Flow:
```
CSV File
  ↓
Upload to Google Sheet (Step 1)
  ↓
Batch Google Maps Lookup (ONE Apify call)
  ↓
Match each row with Google Maps result
  ↓
Enrich: Emails, Contacts, Social (parallel)
  ↓
Merge with original data (preserve 100%)
  ↓
Update Google Sheet (Step 2)
```

---

## Next Steps

Bạn muốn tôi:
1. ✅ Run test ngay với test_lethbridge_prospects.csv?
2. ⏸️ Wait cho bạn provide Sheet ID?
3. 🔧 Modify script (nếu cần thay đổi gì)?

**Let me know và tôi sẽ run test!** 🚀
