# Image & Content SEO Guidelines — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Define standards for all visual and written content across the site. Ensure consistency, compliance, and SEO optimization for every piece of content published on Beauty Connect Shop.

## Image Guidelines

### Alt Text
- Length: 50-125 characters
- Format: descriptive, include product name + key ingredient or use case
- Example: "KRX PDRN Ampoule Serum 35ml — professional-grade skin rejuvenation treatment"
- Never: "image1.jpg", "product photo", or empty alt text

### Format & Size
- Preferred format: WebP (Shopify CDN converts automatically from PNG/JPG)
- Product images: < 150KB after compression
- Hero/banner images: < 300KB after compression
- Dimensions: consistent aspect ratio per page type (product: 1:1, banner: 16:9)

### File Naming
- Use descriptive, hyphenated filenames
- Good: `korean-cica-cream-50ml.webp`, `pdrn-ampoule-serum-professional.webp`
- Bad: `IMG_4532.jpg`, `Screenshot 2026-03-23.png`, `product-1.webp`

### Technical Requirements
- All `<img>` tags must have explicit `width` and `height` attributes (prevents CLS)
- Use `loading="lazy"` for below-the-fold images
- First visible image (LCP candidate): do NOT lazy load

## Content Guidelines

### Product Descriptions
- Minimum: 200 words
- Structure: Benefits > Ingredients > How to Use > Who It's For
- Include 2-3 target keywords naturally
- Link to related products (internal linking)

### Collection Descriptions
- Minimum: 150 words
- Structure: buying guide angle + mini FAQ (2-3 questions)
- Include collection-level keywords (e.g., "Korean moisturizers for estheticians")

### Blog Posts
- Minimum: 1,000 words
- H2/H3 heading hierarchy (never skip levels)
- Include at least 1 featured snippet-optimized section (definition, numbered list, or table)
- Internal links: >= 3 links to products or collections per post
- External links: >= 1 authoritative source per post

### FAQ Answers
- Length: 40-80 words per answer
- Tone: concise, factual, helpful
- Must use FAQ schema markup (JSON-LD)

## Health Canada Compliance Rules

### ALLOWED Claims (Non-therapeutic)
- "improves the look of", "helps improve the appearance of"
- "supports skin's natural renewal", "formulated to help with"
- "moisturizes", "hydrates", "soothes dry skin"
- "reduces the look of fine lines", "firms the look of skin"
- "cleanser for acne-prone skin", "covers blemishes"
- "professional-grade", "dermatologist tested"

### FORBIDDEN Claims (Therapeutic — requires DIN/NPN)
- "heals", "repairs skin", "repairs damaged skin"
- "treats [any condition]" (acne, rosacea, eczema, etc.)
- "anti-inflammatory", "antibacterial", "antiseptic"
- "medical grade", "prescription strength", "clinical strength"
- "prevents acne/breakouts", "cures", "prevents disease"
- "removes scars", "reduces redness due to rosacea"
- "stimulates hair growth", "prevents hair loss"
- Any SPF/UV/sunscreen claims without proper DIN

### Compliance Process
- When in doubt: run `check_health_canada_compliance()` from `execution/seo_shared.py`
- All AI-generated content must pass compliance check before publishing
- Flag borderline claims for manual review
- Reference: ASC "Guidelines for Non-therapeutic Advertising and Labelling Claims" (Oct 2016)

## Edge Cases & Constraints
- Images uploaded by suppliers: re-name and optimize before publishing
- User-generated content (reviews): not subject to same SEO requirements but must comply with Health Canada
- Bilingual content: English primary, French translations follow same guidelines
- Seasonal content: update hero images and featured collections quarterly

## Quality Thresholds
- All images: alt text 50-125 chars, < 150KB (products), explicit dimensions
- Product descriptions: >= 200 words, structured format, 0 Health Canada violations
- Collection descriptions: >= 150 words with buying guide angle
- Blog posts: >= 1,000 words, proper heading hierarchy, >= 3 internal links
- Health Canada compliance: 0 violations across all content

## Changelog
- v1.0 (2026-03-23): Initial version — image standards, content standards, Health Canada compliance rules
