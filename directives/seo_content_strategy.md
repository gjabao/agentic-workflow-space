# Content Strategy — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Build topical authority through strategic content creation. Establish Beauty Connect Shop as a trusted resource for Korean skincare, professional treatments, and B2B beauty distribution in Canada.

## Tools
- `execution/seo_content_planner.py` — AI-powered content calendar generation
- `execution/publish_blog_to_shopify.py` — Blog publishing to Shopify (existing)
- `execution/shopify_faq_creator.py` — FAQ schema generation for product pages

## Prerequisites
- Shopify Admin API credentials in `.env`
- Azure OpenAI credentials in `.env`
- Google Sheets API credentials (for content calendar)
- Keyword research data (from Phase 1 audit or GSC)

## Process

### Step 1: Content Calendar Generation
1. Run: `python execution/seo_content_planner.py --months 3`
2. Review 3-month content calendar in Google Sheet
3. Prioritize topics by opportunity score (search volume x inverse competition)
4. Approve or adjust calendar with user

### Step 2: Content Creation
1. Write content in Google Docs (one doc per article)
2. Follow content mix: 70% evergreen, 20% trending, 10% promotional
3. All content must pass Health Canada compliance check before publishing
4. Target word count: >= 1,000 words per blog post

### Step 3: Publishing
1. Publish via: `python execution/publish_blog_to_shopify.py --draft`
2. Always publish as DRAFT first — user reviews before going live
3. Add internal links to relevant products/collections
4. Include featured snippet-optimized sections (definition boxes, numbered lists)

### Step 4: FAQ Generation
1. Run: `python execution/shopify_faq_creator.py --top_products 20`
2. Review generated FAQs for accuracy and compliance
3. Push approved FAQs to product pages with FAQ schema markup

## Content Mix
- **70% Evergreen:** Ingredient guides, how-to routines, product comparisons
- **20% Trending:** Seasonal skincare, K-beauty trends, new ingredient spotlights
- **10% Promotional:** New product launches, B2B offers, brand stories

## Cadence
- Minimum: 2 blog posts per week
- FAQs: update monthly with new questions from GSC queries

## Pillar Topics
1. **Korean Skincare Ingredients** — PDRN, snail mucin, peptides, centella, hanbang
2. **Professional Treatments** — Esthetician protocols, clinic-grade products, treatment guides
3. **B2B Distribution Canada** — Wholesale beauty supply, salon/spa partnerships, regulatory compliance

## Edge Cases & Constraints
- Duplicate content: never repurpose product descriptions as blog content
- Health Canada: blog content has same compliance requirements as product pages
- Seasonal timing: publish seasonal content 4-6 weeks before peak season
- Thin content: never publish posts under 800 words (target 1,000+)

## Quality Thresholds
- Blog posts: >= 1,000 words, H2/H3 hierarchy, >= 1 featured snippet section
- FAQ answers: 40-80 words each, concise and factual
- Content calendar: minimum 24 topics per quarter
- Health Canada compliance: 0 violations
- Internal links: each post links to >= 3 products or collections

## Changelog
- v1.0 (2026-03-23): Initial version — content planner, blog publishing, FAQ creation
