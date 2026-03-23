# Shopify SEO Optimizer — Directive v1.0

## Goal
Automatically fetch all products from the Beauty Connect Shop Shopify store, score their SEO health, generate AI-optimized SEO content (meta title, meta description, product description) that is Health Canada compliant, and export a before/after audit report to Google Sheets for review before pushing live.

## Inputs
- Shopify store URL + Admin API access token (in .env)
- Azure OpenAI credentials (in .env)
- `directives/brand/brand_voice.md` — tone, compliance rules, product context
- CLI flags: `--limit`, `--dry_run`, `--push_live`

## Tools
- `execution/shopify_seo_optimizer.py`

## Outputs
1. **Google Sheets "SEO Audit Report"** — before/after comparison for all products
   - Columns: Product title | Current SEO title | Optimized SEO title | Current meta desc | Optimized meta desc | Current alt text | Optimized alt text | SEO score before | SEO score after | Status (review/approved/pushed)
2. **Live Shopify updates** (only after `--push_live` flag, or row status = "approved" in sheet)

## Process

### Step 1: Fetch Products
- Shopify GraphQL Admin API: fetch all products with pagination
- Extract per product: id, title, handle, descriptionHtml, SEO fields (title_tag, description_tag), first image (id, altText, src)
- API version: 2024-10

### Step 2: Score SEO Health (0-100)
Scoring rubric per product:
- Meta title present: +20pts
- Meta title 30-60 chars: +10pts (too short <30 or too long >60: 0pts)
- Meta title contains primary keyword: +10pts
- Meta description present: +20pts
- Meta description 120-160 chars: +10pts
- Product description >200 words: +10pts
- Image alt text present: +10pts
- Image alt text contains product name + keyword: +10pts

Products scoring <70 are flagged for optimization.

### Step 3: Generate Optimized SEO Content
For each flagged product, call Azure OpenAI (GPT-4o) with:
- System: Health Canada compliance rules, brand voice from `brand_voice.md`
- User: product name, current description, product category, target keywords

**Outputs per product:**
- Optimized meta title (50-60 chars, primary keyword first)
- Optimized meta description (140-155 chars, includes benefit + CTA)
- Optimized first 150 words of product description (keyword-rich, brand voice)
- Optimized image alt text (descriptive, includes product + use case)

**3-Pass SEO Strategy:**
1. Technical pass: fix length issues, add missing fields
2. Keyword pass: inject K-beauty terms (skin barrier, glass skin, PDRN, snail mucin, peptides, hanbang, slow aging, Korean skincare Canada)
3. Conversion pass: rewrite for purchase intent (not just "KRX serum" but "KRX HA Vitamin C Serum for Brightening Skin — Professional Grade")

### Step 4: Health Canada Compliance Check (ASC Guidelines)
Reference: ASC "Guidelines for Non-therapeutic Advertising and Labelling Claims" (Oct 2016)
Principle: Cosmetics may only use Column I (non-therapeutic) claims. Column II (therapeutic/health) claims require DIN or NPN pre-market authorization from Health Canada.

Before saving any output, validate against **all** Column II forbidden therapeutic patterns:

**Skin Care / Makeup:**
- "heals" (unqualified), "repairs skin/damaged skin", "repairs skin's moisture barrier"
- "treats [condition]" (acne, rosacea, eczema, burns, infections, cellulite)
- "cures", "prevents disease/infection/acne/breakouts"
- "calms/soothes abrasions/bites/cuts/irritated/inflamed skin/rashes/sunburns"
- "numbs", any reference to pain or irritation
- "removes/reduces scars", "reduces redness due to rosacea", any rosacea reference
- "eliminates age spots", "prevents new spots", "skin de-pigmentation", "prevents photoaging"
- "provides effect of medical/surgical procedure"
- "reduces/controls swelling/edema", "weight/fat loss", "removes/treats cellulite", "lipodraining"
- "action at cellular level", "reference to action on tissue/body/cells"
- "cleans wounds", "anti-blemish", "clears skin (acne)", "heals/prevents/treats acne"
- SPF/UV/UVA/UVB claims, "sunburn protectant", "sunscreen", "protects sun damaged skin"
- "kills pathogens/germs/bacteria" (except odour-causing), "antibacterial", "antiseptic", "disinfectant", "sanitizer", "fungicide"
- "prescription strength", "Rx", "Pr", "clinical/therapeutic strength/effect/action"
- "active/medicinal/therapeutic ingredient", "promotes health", "biological action/effect"
- "free radical scavenging", dose units (IU)

**Hair / Nail:**
- "anti-dandruff", "controls/eliminates/prevents dandruff"
- "stimulates hair/eyelash growth", "prevents hair loss/thinning", "treats alopecia"
- "inhibits/stops hair growth", "effect on living tissue/hair follicles"
- "promotes nail growth (physiological)", "antifungal"

**Oral Care:**
- "anti-cavity", "anti-gingivitis", "anti-sensitivity", "anti-plaque", "anti-tartar"
- "fluoride effect", "strengthens enamel/teeth/gums", "desensitizes teeth/gums"
- "kills germs/pathogens", "antiseptic", "antiviral"
- "removes permanent stains", "effect below gum line"

**Antiperspirants:**
- "hyperhidrosis", "excessive/problem perspiration"
- "hormonal/endocrine perspiration references"
- "clinical strength/protection" (unqualified)

**Intimate Products:**
- "spermicidal", "increases libido", "prolongs/produces erection/orgasm"
- "stimulates genital tissue", "vaginal tightening", "delays orgasm"
- "enhances sperm motility", "pH-balanced to prevent infection"

**Other Claims:**
- "active/effective/medicinal/therapeutic ingredient"
- "free radical scavenging", dose units (IU)
- "promotes health", "biological/therapeutic action/effect"
- "disease prevention/control/healing", "disease-causing organisms"

**Allowed non-therapeutic alternatives:**
- moisturizes, hydrates, soothes dry skin, improves the appearance/look of
- reduces the look of, firms/tones/conditions the look of skin
- cleanser for acne-prone skin, covers blemishes, professional-grade
- dermatologist tested, healthy (from appearance perspective)

If forbidden pattern detected → regenerate with explicit avoidance instruction

### Step 5: Export to Google Sheets
- Create new spreadsheet: "BeautyConnect SEO Audit — [date]"
- Export all products (flagged + passed) with before/after comparison
- Share link returned to user

### Step 6: Push Live (manual trigger)
- Only runs with `--push_live` flag
- Updates Shopify via `productUpdate` GraphQL mutation:
  - `seo.title` and `seo.description` fields
  - Image alt text via `productImageUpdate` mutation
- Logs each update with success/error

## CLI Usage
```bash
# Dry run — analyze only, export to Google Sheets, NO Shopify changes
python execution/shopify_seo_optimizer.py --dry_run

# Analyze first 10 products only (test)
python execution/shopify_seo_optimizer.py --limit 10 --dry_run

# Analyze all + push live updates
python execution/shopify_seo_optimizer.py --push_live

# Re-run only for products below a score threshold
python execution/shopify_seo_optimizer.py --min_score 70 --dry_run
```

## Edge Cases & Constraints
- Products with no description: generate from product title + category only (flag as "needs review")
- Products with multiple images: only update first/featured image alt text
- API rate limits: Shopify allows 40 requests/minute (standard plan). Use 0.1s delay between GraphQL calls. Cost API: uses "points" system — each call = 1 point, bulk operations cheaper.
- Shopify GraphQL max depth: 3 levels of nesting
- Error on push: log error, continue to next product (never abort full run on single failure)
- Products with existing SEO scores ≥85: skip optimization unless `--force_all` flag

## Quality Thresholds
- Target SEO score: ≥85 for all products
- Meta title: 50-60 characters
- Meta description: 140-155 characters
- Min product description: 150 words
- Health Canada compliance: 0 violations allowed

## Changelog
- v1.1 (2026-03-16): Expanded Health Canada compliance to full ASC Guidelines — all Column II categories (Skin Care, Hair/Nail, Oral, Antiperspirants, Intimate, Other Claims). Regex patterns expanded from 17 to 100+. AI prompt now includes complete allowed/forbidden claim lists per category.
- v1.0 (2026-03-06): Initial version — fetch, score, optimize, export, push
