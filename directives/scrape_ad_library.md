# Directive: Ad Library Scraper + AI Image Spinner

**Version:** 1.0
**Created:** 2026-02-23
**Script:** `execution/scrape_ad_library.py`

---

## Goal

Scrape competitor ads from Facebook's Ad Library, analyze each ad image with AI vision, and automatically generate remixed variants using Flux Kontext Pro. All assets organized in Google Drive with a tracking Google Sheet.

---

## Required Inputs

| Input | Required | Example |
|-------|----------|---------|
| `--keyword` | Yes | `"agency"`, `"ai automation"`, `"dental marketing"` |
| `--style` | Yes | `"Bright blue ultra-maximalist style. Replace text with AI automation messaging."` |
| `--max_ads` | No (default: 20) | `50` |
| `--variants` | No (default: 3) | `5` |
| `--folder_name` | No (default: "Ad Library Spins") | `"PPC Thievery"` |
| `--test` | No | Flag — limits to 2 ads |
| `--folder_id` | No | Reuse existing Drive folder |
| `--sheet_id` | No | Reuse existing Google Sheet |

---

## Tools & APIs

| API | Purpose | Env Var |
|-----|---------|---------|
| Apify (`curious_coder~facebook-ads-library-scraper`) | Scrape Facebook Ad Library | `APIFY_API_KEY` |
| Azure OpenAI GPT-4o (vision) | Analyze/describe ad images | `AZURE_OPENAI_*` |
| Azure OpenAI GPT-4o (text) | Generate spin variant prompts | `AZURE_OPENAI_*` |
| fal.ai Flux Kontext Pro | Generate remixed ad images | `FAL_KEY` |
| Google Drive API v3 | Folder creation, file upload, sharing | `credentials.json` |
| Google Sheets API v4 | Tracking spreadsheet | `credentials.json` |

---

## Expected Output

### Google Drive Structure
```
{folder_name}/
├── {ad_archive_id_1}/
│   ├── 1 Source Assets/
│   │   └── {ad_archive_id_1}.png        ← original ad image
│   └── 2 Spun Assets/
│       ├── {ad_archive_id_1}_v1.png      ← variant 1
│       ├── {ad_archive_id_1}_v2.png      ← variant 2
│       └── {ad_archive_id_1}_v3.png      ← variant 3
├── {ad_archive_id_2}/
│   ├── ...
```

### Google Sheet (12 columns)
`Timestamp | Ad Archive ID | Page ID | Original Image URL | Page Name | Ad Body | Date Scraped | Spun Prompt | Asset Folder | Source Folder | Spun Folder | Direct Spun Image Link`

One row per variant (3 rows per ad by default).

---

## Workflow

```
1. Authenticate Google (OAuth2)
2. Create Drive folder + Sheet (if not reusing)
3. Scrape ads via Apify
4. Filter → static image ads only
5. Apply test limit (--test → 2 ads)
6. Deduplicate against existing sheet rows
7. For each ad:
   a. Download original image
   b. Create Drive folders (parent + source + spun)
   c. Upload original to "1 Source Assets"
   d. Describe image (Azure GPT-4o vision)
   e. Generate N variant prompts (Azure GPT-4o text)
   f. For each variant:
      - Generate spun image (Flux Kontext Pro via fal.ai)
      - Upload to "2 Spun Assets"
      - Log row to Google Sheet
8. Print summary
```

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| No static image ads found | Abort with message |
| Image download 404 | Skip ad, log warning |
| Azure GPT-4o rate limited (429) | Exponential backoff, 3 retries |
| fal.ai queue timeout (>5 min) | Skip variant, log warning |
| fal.ai NSFW rejection | Skip variant, log warning |
| Drive upload fails | Retry once, skip ad on second failure |
| Sheet append fails | CSV backup to `.tmp/` |
| Duplicate ad_archive_id | Skip (deduplication check) |

---

## Quality Thresholds

- Image ads after filter: expect 50-70% of scraped ads
- Variant generation success: 90%+
- fal.ai image generation success: 85%+

---

## Cost Estimate

| API | Per Unit | 20 ads (~13 with images, 39 variants) |
|-----|----------|---------------------------------------|
| Apify | ~$0.50/run | $0.50 |
| Azure GPT-4o Vision | ~$0.05/call | $0.65 |
| Azure GPT-4o Text | ~$0.01/call | $0.13 |
| Flux Kontext Pro | $0.04/image | $1.56 |
| **Total** | | **~$2.84** |

---

## Usage Examples

```bash
# Test run (2 ads, verify everything works)
python3 execution/scrape_ad_library.py \
  --keyword "agency" \
  --style "Bright blue ultra-maximalist style. Replace text with AI automation messaging." \
  --test

# Full run
python3 execution/scrape_ad_library.py \
  --keyword "dental marketing" \
  --max_ads 30 \
  --style "Clean minimalist white background. Add company logo bottom-right." \
  --folder_name "Dental PPC Spins"

# Reuse existing folder/sheet (subsequent runs)
python3 execution/scrape_ad_library.py \
  --keyword "agency" \
  --style "Dark mode theme with neon accents" \
  --folder_id 1aBcDeFgHiJkLmNoPqRsT \
  --sheet_id 1uVwXyZ123456789
```

---

## First-Time Setup

1. Ensure `.env` has: `APIFY_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `FAL_KEY`
2. Ensure `credentials.json` exists in workspace root (Google OAuth)
3. Run with `--test` first to verify all APIs work
4. Save the printed `folder_id` and `sheet_id` for subsequent runs

---

## Changelog

- **v1.0 (2026-02-23):** Initial version. Flux Kontext Pro via fal.ai, Azure OpenAI for vision/text, deduplication built-in.
