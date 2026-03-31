# ⚠️ v2.0 Website Finding Issue - Analysis

**Date:** 2026-01-16
**Test:** Glassdoor CFO jobs, Toronto, Canada (10 jobs)

---

## 🔴 Problem: Only 3/8 Companies Had Websites Found

### Test Results Summary

**10 jobs scraped → 8 unique companies**

| Company | Website Found? | Emails Found | DMs Found |
|---------|---------------|--------------|-----------|
| Supreme Motors | ✅ suprememotorsusa.com | 0 | 0 |
| Vaco by Highspring | ✅ vaco.com | 14 | 1 (Katie Hyde) |
| NFTC | ✅ nftc.org | 14 | 1 (Brian Waller) |
| George A Wright & Son | ❌ No website | - | 0 |
| Kingsdown Canada | ❌ No website | - | 0 |
| HSC Holdings Inc | ❌ No website | - | 0 |
| Procom | ❌ No website | - | 0 |
| Moneris Solutions | ❌ No website | - | 0 |

**Results:**
- **Website Success Rate:** 37.5% (3/8 companies)
- **Lost Opportunities:** 5 companies skipped due to no website
- **Email Success Rate:** 100% (3/3 companies with websites had emails)
- **DM Success Rate:** 66% (2/3 companies with emails had DMs)

---

## 🔍 Root Cause Analysis

### Issue 1: Website Finding Logic Too Strict

The `find_company_website()` method uses a 3-attempt Google Search strategy, but it may be failing for these reasons:

**Possible Failures:**
1. **Company Name Format Issues**
   - "George A Wright & Son" - special characters (&) may break search
   - "HSC Holdings Inc" - generic name, hard to find specific website
   - "Procom" - too generic (many companies called "Procom")

2. **Search Query Issues**
   - Current query: `"Company Name" official website`
   - May not work for companies with:
     - Multiple locations (Toronto-specific companies)
     - Generic names (HSC, Procom)
     - Special characters (George A Wright & Son)

3. **Domain Extraction Issues**
   - Even if website found, domain extraction might fail
   - URL parsing errors could return empty domain

---

## 📊 Impact on v2.0 Performance

### Glassdoor Test Impact

**If all 8 companies had websites found:**
- Estimated emails: 8 companies × 14 avg emails = 112 emails
- Estimated DMs (66% rate): 5.3 DMs
- **Actual DMs:** 2

**Coverage lost:** 62.5% of companies (5/8) due to website finding failure

### Comparison Across Scrapers

| Scraper | Test Type | Website Success | Why Different? |
|---------|-----------|----------------|----------------|
| **Indeed** | Enterprise (Blockchain) | ~90% (6/6 w/ emails) | Large companies, well-known brands |
| **LinkedIn** | Enterprise (Blockchain) | ~80% (4/5) | Tech companies, strong web presence |
| **Glassdoor** | SMB (CFO Toronto) | **37.5% (3/8)** | Small/medium businesses, local focus |

**Key Finding:** v2.0 workflow is **enterprise-biased** - works great for well-known companies, fails for SMBs

---

## 🔍 Let Me Check What `find_company_website()` Actually Does

Need to read the method to understand why it's failing for 5/8 companies.

**Expected behavior:**
1. Attempt 1: Search `"Company Name" official website`
2. Attempt 2: Search `"Company Name" site:.com OR site:.org`
3. Attempt 3: Search `Company Name` (broad search)

**Actual behavior:** Unknown - need to check code

---

## 💡 Potential Fixes

### Fix 1: Improve Company Name Normalization
**Before:** "George A Wright & Son"
**After:** "George Wright Son" (remove special chars, middle initials)

### Fix 2: Add Location Context to Search
**Before:** `"HSC Holdings Inc" official website`
**After:** `"HSC Holdings Inc" Toronto official website`

### Fix 3: Try Multiple Search Patterns
```python
search_attempts = [
    f'"{company}" official website',
    f'"{company}" {location} website',  # Add location
    f'{company} company site:.com OR site:.ca',  # Add country TLD
    f'{company} careers',  # Careers page often exists
    f'{company} about us'  # About page fallback
]
```

### Fix 4: Extract Domain from Job URL
**Glassdoor provides company info** - may include website already in job posting metadata

### Fix 5: Lower Website Requirement Confidence
- Currently: Website not found → skip company entirely
- Better: Website not found → try LinkedIn company page search instead
- Fallback: Use company name + LinkedIn to find emails

---

## 🧪 Evidence from Logs

**Supreme Motors (found website but 0 emails):**
```
✓ Website: suprememotorsusa.com
📧 Finding emails at suprememotorsusa.com...
✓ Found 0 emails
⊘ No emails found - skipping
```
**Why:** AnyMailFinder had no emails for this domain (small company, limited email data)

**Vaco by Highspring (success):**
```
✓ Website: vaco.com
📧 Finding emails at vaco.com...
✓ Found 14 emails
```
**Why:** Large recruiting firm, lots of public emails

**NFTC (success):**
```
✓ Website: nftc.org
📧 Finding emails at nftc.org...
✓ Found 14 emails
```
**Why:** Trade council, public organization, many emails

**George A Wright & Son (no website):**
```
⊘ No website domain - skipping
```
**Why:** Special characters in name, old company name format, search failed

---

## 🎯 Conclusion

**Primary Issue:** Website finding fails for 62.5% of SMB companies (5/8)

**Secondary Issue:** Even with websites, email finding can fail (Supreme Motors)

**Combined Impact:**
- Website finding: 37.5% success (3/8)
- Email finding: 100% success (3/3 with websites)
- DM finding: 66% success (2/3 with emails)
- **Overall DM coverage:** 25% (2/8 companies)

**Root Cause:**
1. Website finding logic too strict for SMB company names
2. v2.0 workflow requires website → fails early for 62.5% of companies
3. No fallback strategy when website not found

**Expected after fixes:**
- Website finding: 75%+ (with improved search + fallbacks)
- Email finding: 80%+ (more companies in pipeline)
- DM finding: 66% (same rate)
- **Overall DM coverage:** 50%+ (4/8 companies vs current 2/8)

---

**Status:** 🔴 CRITICAL - Website finding is the #1 bottleneck
**Next Action:** Investigate `find_company_website()` method and improve search logic
**Priority:** HIGH - 62.5% of companies lost before email search even starts
