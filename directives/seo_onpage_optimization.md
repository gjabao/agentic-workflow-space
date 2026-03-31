# On-Page SEO Optimization — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Optimize all product and collection pages for search engines. Improve meta titles, meta descriptions, product descriptions, and internal linking structure to maximize organic visibility.

## Tools
- `execution/shopify_seo_optimizer.py` — Product SEO optimization (existing)
- `execution/shopify_collection_optimizer.py` — Collection page SEO
- `execution/seo_internal_linker.py` — Internal link analysis and recommendations

## Prerequisites
- Shopify Admin API credentials in `.env`
- Azure OpenAI credentials in `.env`
- Brand voice guidelines: `directives/brand/brand_voice.md`
- Technical SEO fixes completed (see `directives/seo_technical_fixes.md`)

## Process

### Step 1: Product Page Optimization
1. Test run: `python execution/shopify_seo_optimizer.py --dry_run --limit 5`
2. Review output quality in Google Sheet — check keyword usage, compliance, character counts
3. If quality passes (score >= 85 average): full run `python execution/shopify_seo_optimizer.py --dry_run`
4. Review full Google Sheet export
5. Approve rows, then: `python execution/shopify_seo_optimizer.py --push_live`

### Step 2: Collection Page Optimization
1. Test run: `python execution/shopify_collection_optimizer.py --dry_run --limit 3`
2. Review collection descriptions — must include buying guide angle + mini FAQ
3. Full run: `python execution/shopify_collection_optimizer.py --dry_run`
4. Approve in Sheet, then push live

### Step 3: Internal Linking Analysis
1. Run: `python execution/seo_internal_linker.py --analyze`
2. Review top 20 link suggestions (orphan pages, high-value targets)
3. Implement top suggestions manually in product/collection descriptions
4. Re-run analysis to confirm improvement

## Edge Cases & Constraints
- Products with no description: generate from title + category, flag as "needs review"
- Collections with <5 products: lower priority, optimize last
- Duplicate content risk: ensure each product/collection has unique meta description
- Health Canada compliance: all generated content must pass compliance check (see `directives/shopify_seo_optimizer.md` Step 4)
- Shopify character limits: meta title max 70 chars, meta description max 320 chars (target shorter)

## Quality Thresholds
- Product SEO scores >= 85 (all products)
- Meta titles: 50-60 characters, primary keyword first
- Meta descriptions: 140-155 characters, includes benefit + CTA
- Product descriptions: >= 200 words, structured format
- Collection descriptions: >= 150 words with buying guide + mini FAQ
- Internal links: every product links to >= 2 related products
- Health Canada compliance: 0 violations

## Changelog
- v1.0 (2026-03-23): Initial version — product optimization, collection optimization, internal linking
