# Technical SEO Fixes — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Fix technical SEO issues found in Phase 1 audit: missing structured data, suboptimal robots.txt configuration, and unoptimized image alt text across the entire Shopify store.

## Tools
- `execution/shopify_schema_injector.py` — JSON-LD schema markup (Product, Organization, BreadcrumbList)
- `execution/shopify_robots_ai_config.py` — Robots.txt + AI crawler configuration
- `execution/shopify_image_optimizer.py` — Image alt text optimization

## Prerequisites
- Shopify Admin API credentials in `.env`
- Azure OpenAI credentials in `.env` (for alt text generation)
- Phase 1 audit results (baseline Lighthouse scores)

## Process

### Step 1: Schema Markup Injection
1. Run `python execution/shopify_schema_injector.py --dry_run` to preview JSON-LD output
2. Review generated schemas: Product (all products), Organization (homepage), BreadcrumbList (collections)
3. Validate with Google Rich Results Test (https://search.google.com/test/rich-results)
4. Push live: `python execution/shopify_schema_injector.py --push_live`

### Step 2: Robots.txt & AI Crawler Config
1. Run `python execution/shopify_robots_ai_config.py --dry_run` to generate template
2. Review the robots.txt template — ensure AI bots (OAI-SearchBot, PerplexityBot, ClaudeBot) are allowed
3. Manually add to Shopify theme (Settings > Custom Data > robots.txt.liquid)
4. Verify at `https://beautyconnectshop.com/robots.txt`

### Step 3: Image Alt Text Optimization
1. Run `python execution/shopify_image_optimizer.py --dry_run --limit 10` to test quality
2. Review generated alt text for accuracy and keyword inclusion
3. Full run: `python execution/shopify_image_optimizer.py --dry_run`
4. Approve in Google Sheet, then: `python execution/shopify_image_optimizer.py --push_live`

### Step 4: Verification
1. Re-run Lighthouse audit on 5 representative pages
2. Compare Core Web Vitals before/after
3. Submit updated sitemap to Google Search Console

## Edge Cases & Constraints
- Products with no images: skip image optimization, flag for manual review
- Shopify Liquid injection: schema must go in `theme.liquid` head section — backup theme first
- Robots.txt on Shopify: cannot use standard file upload; must use `robots.txt.liquid` template
- Rate limits: 40 req/min Shopify API — use 0.1s delay between calls

## Quality Thresholds
- All products have valid Product schema (test with Google Rich Results)
- Organization schema present on homepage
- BreadcrumbList schema on all collection pages
- All images have alt text between 50-125 characters
- Robots.txt allows AI search bots (OAI-SearchBot, PerplexityBot, ClaudeBot)
- Lighthouse Performance score >= 80, SEO score >= 90

## Changelog
- v1.0 (2026-03-23): Initial version — schema injection, robots config, image optimization
