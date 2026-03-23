# Blog Publisher — Directive v2.0
> Google Doc → AI Metadata + Multi-Image Pipeline → Shopify Draft

## Goal
Given a Google Doc ID, automatically read the blog content, generate SEO metadata using Claude, create 4-5 images from 3 sources (AI-generated, stock photos, product photos with AI backgrounds), and publish as a DRAFT article on Shopify.

## Image Pipeline (3 Sources)

| Source | Method | Count | Placement |
|--------|--------|-------|-----------|
| AI-generated | gpt-image-1 `generate` | 1 | Featured image (article attachment) |
| Stock photos | Pexels API → gpt-image-1 `edit` | 1-2 | After H2 headings (in body HTML) |
| Product photos | Shopify products → gpt-image-1 `edit` background | 1-2 | After H2 headings (in body HTML) |

**Product image rule:** Keep product label/packaging EXACTLY as-is. Only redesign the background.

## Inputs

- `--doc_id` (required): Google Doc ID from the doc URL
- `SHOPIFY_STORE_URL`, `SHOPIFY_ADMIN_API_TOKEN` in `.env`
- `ANTHROPIC_API_KEY` in `.env` (Claude metadata)
- `OPENAI_API_KEY` in `.env` (gpt-image-1 generation + editing)
- `PEXELS_API_KEY` in `.env` (stock photos — optional, skipped if missing)
- `credentials.json` + `token.json` in project root (Google OAuth2)

## Tools

- `execution/publish_blog_to_shopify.py`

## Outputs

- Shopify blog article (status: **DRAFT**)
  - SEO title + meta description (via metafields)
  - Blog body as HTML with embedded `<figure><img>` blocks after H2 headings
  - Featured image (AI-generated, 1536x1024)
  - 3-4 in-body images (stock + product, uploaded via Shopify Files API)
  - Tags from AI-generated keywords

## Process

### Step 1: Read Google Doc
- Google Docs API v1 → clean HTML (headings, bold, links preserved)

### Step 2: Generate SEO Metadata (Claude)
- Returns: title, meta_description, slug, tags, image_prompt, image_search_keywords

### Step 3: Image Pipeline

**3a. AI Featured Image**
- gpt-image-1 `generate`, 1536x1024 landscape
- Attached as base64 in article payload

**3b. Stock Photos (Pexels)**
- Search Pexels API with `image_search_keywords` (ingredient/lifestyle)
- Download → redesign with gpt-image-1 `edit` (brand aesthetic)
- Upload to Shopify Files API → get CDN URL
- Attribution included as `<figcaption>`

**3c. Product Photos (Shopify)**
- Fetch all products via GraphQL
- Fuzzy match product names in blog text (fuzzywuzzy, threshold 75+)
- Download product image → redesign background with gpt-image-1 `edit`
  - Prompt preserves product packaging, only changes background
- Upload to Shopify Files API → get CDN URL

### Step 4: Inject Images into HTML
- Insert `<figure>` blocks after first `<p>` following each `<h2>`
- Stock photos include attribution caption
- Extra images appended before end of content

### Step 5: Create Shopify Draft
- REST POST `/blogs/{id}/articles.json` with `published: false`
- SEO fields via metafields (global namespace)
- Featured image via base64 attachment

## CLI Usage

```bash
# Full pipeline — all 3 image sources
python execution/publish_blog_to_shopify.py --doc_id DOC_ID

# Preview without posting
python execution/publish_blog_to_shopify.py --doc_id DOC_ID --dry_run

# Skip stock photos (AI + product only)
python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_stock

# Skip product images (AI + stock only)
python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_products

# Text only — no images at all
python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_images

# Specific blog + custom author
python execution/publish_blog_to_shopify.py --doc_id DOC_ID --blog_name "Tips" --author "Jane"
```

## Graceful Degradation

| Failure | Behavior |
|---------|----------|
| No OPENAI_API_KEY | Skip all AI images, text-only draft |
| No PEXELS_API_KEY | Skip stock photos, continue with AI + product |
| gpt-image-1 edit fails | Use original image without redesign |
| No product matches | Skip product images |
| Shopify Files upload fails | Skip that image, continue with others |
| Zero images succeed | Publish text-only (still works) |

## Cost per Blog Post

- Claude metadata: ~$0.01
- 1x gpt-image-1 generate: ~$0.04
- 2-3x gpt-image-1 edit: ~$0.08-0.12
- Pexels + Shopify APIs: free
- **Total: ~$0.13-0.17**

## Edge Cases

- Empty doc → error with clear message
- No H2 headings → images appended at end
- Blog not found → uses first Shopify blog
- Google token expired → auto-refresh
- Product images: **requires human review** before publishing (AI may slightly alter product)

## First-Time Setup

1. `credentials.json` in project root (Google Cloud Console → OAuth2)
2. Add to `.env`: `OPENAI_API_KEY`, `PEXELS_API_KEY`
3. Run once — browser opens for Google OAuth approval
4. `token.json` saved automatically

## Changelog

- v2.0 (2026-03-13): Multi-image pipeline — 3 sources, Shopify Files API, H2 placement, product matching
- v1.0 (2026-03-13): Initial — single featured image, Google Doc → Shopify draft
