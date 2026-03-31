# Off-Page & AI Visibility — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Build external authority and ensure visibility in AI search engines (ChatGPT, Perplexity, Gemini). Establish entity presence across structured data platforms and traditional off-page channels.

## Tools
- `execution/bing_indexnow.py` — Instant Bing/Yandex indexing via IndexNow protocol
- `execution/seo_ai_visibility_checker.py` — Track AI engine citations and visibility

## Prerequisites
- Bing Webmaster Tools account (verify site ownership)
- Google Business Profile access
- IndexNow API key generated and hosted at `/indexnow-key.txt`

## Process

### Step 1: Search Engine Registration
1. **Bing Webmaster Tools:** Go to bing.com/webmasters, add site, verify via DNS/meta tag
2. Submit XML sitemap: `https://beautyconnectshop.com/sitemap.xml`
3. Enable IndexNow: `python execution/bing_indexnow.py --submit_all`

### Step 2: AI Crawler Access
1. Verify robots.txt allows these bots (should be done in technical fixes phase):
   - `OAI-SearchBot` (ChatGPT search)
   - `PerplexityBot` (Perplexity AI)
   - `ClaudeBot` (Claude/Anthropic)
   - `Applebot-Extended` (Apple Intelligence)
2. Add `llms.txt` to site root with structured site summary

### Step 3: Entity SEO (Manual)
1. **Wikidata:** Create entry for Beauty Connect Shop (Canadian beauty distributor)
2. **Crunchbase:** Create company profile with founding date, description, industry
3. **LinkedIn:** Complete company page — logo, banner, about, specialties, website
4. **Google Business Profile:** Set up as Service Area Business
   - Category: "Wholesale beauty supply"
   - Post weekly updates (products, tips, offers)
   - Respond to all reviews within 24 hours

### Step 4: Digital PR (Manual)
1. Build media list: The Kit, Canadian Esthetician Magazine, Beauty Independent
2. Pitch angles: "Korean beauty wholesale enters Canadian market", ingredient spotlights
3. Target: 2-3 media mentions per quarter
4. Track all backlinks in Google Search Console

### Step 5: AI Visibility Baseline & Tracking
1. Run: `python execution/seo_ai_visibility_checker.py --baseline`
2. Test queries: "Korean skincare wholesale Canada", "professional beauty products distributor"
3. Record which AI engines cite Beauty Connect Shop
4. Re-run monthly to track progress

## Edge Cases & Constraints
- IndexNow: only works for Bing/Yandex — Google uses its own crawl schedule
- GBP: Service Area Business has limited features vs storefront — no street address shown
- Wikidata: requires notability evidence (media mentions, official registrations)
- AI visibility: no direct way to influence AI citations — focus on being the best source
- Digital PR: expect 2-4 week lead time for media coverage

## Quality Thresholds
- All URLs submitted to Bing within 24 hours of publication (via IndexNow)
- GBP: >= 1 post per week, all reviews responded to within 24 hours
- Entity profiles: complete on Wikidata, Crunchbase, LinkedIn within 30 days
- AI visibility: track baseline and monthly changes for 5 target queries
- Backlinks: >= 5 referring domains from DR 30+ sites within 6 months

## Changelog
- v1.0 (2026-03-23): Initial version — Bing setup, AI crawler access, entity SEO, digital PR
