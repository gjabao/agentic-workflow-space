# SEO Master Workflow — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Comprehensive SEO optimization for beautyconnectshop.com covering technical, on-page, content, off-page, AI visibility, and monitoring — executed through the DOE architecture.

## Prerequisites
- Shopify Admin API: SHOPIFY_STORE_URL + SHOPIFY_ADMIN_API_TOKEN in .env
- Google Search Console: token_gsc.pickle authenticated for beautyconnectshop.com
- Google Sheets: credentials.json + token.json (OAuth)
- Azure OpenAI: AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY (for AI content generation)

## Workflow Phases

### Phase 1: Audit & Baseline (READ-ONLY)
**Always run first. No changes to Shopify.**

| Step | Tool | Command | Output |
|------|------|---------|--------|
| 1.1 GSC Baseline | execution/google_search_console.py | `--action query --site https://beautyconnectshop.com/ --dimensions query page --limit 5000` | Top queries + pages |
| 1.2 Product SEO Scores | execution/shopify_seo_optimizer.py | `--dry_run` | Product scores 0-100 |
| 1.3 Technical Audit | execution/seo_technical_audit.py | default | CWV, schema, robots, sitemap |
| 1.4 Content Audit | execution/seo_content_audit.py | default | Content inventory + gaps |

**Approval checkpoint:** Present all 4 reports. User decides priorities.

### Phase 2: Technical SEO Fixes
**Each step: dry_run → user review → push_live**

| Step | Tool | What |
|------|------|------|
| 2.1 Schema Markup | execution/shopify_schema_injector.py | Product, Organization, BreadcrumbList, FAQ JSON-LD |
| 2.2 Robots.txt | execution/shopify_robots_ai_config.py | AI crawler access config |
| 2.3 Image Optimization | execution/shopify_image_optimizer.py | Alt text generation, size audit |

### Phase 3: On-Page Optimization
**Each step: dry_run → user review → push_live**

| Step | Tool | What |
|------|------|------|
| 3.1 Product Pages | execution/shopify_seo_optimizer.py | Meta titles, descriptions, body HTML |
| 3.2 Collection Pages | execution/shopify_collection_optimizer.py | Collection meta + descriptions |
| 3.3 Internal Links | execution/seo_internal_linker.py | Link opportunities (report only) |

### Phase 4: Content Strategy
| Step | Tool | What |
|------|------|------|
| 4.1 Content Plan | execution/seo_content_planner.py | 3-month calendar with topic clusters |
| 4.2 Blog Publishing | execution/publish_blog_to_shopify.py | Publish from Google Docs |
| 4.3 FAQ Generation | execution/shopify_faq_creator.py | FAQ Q&A + schema per product |

### Phase 5: Off-Page & AI Visibility
| Step | Tool | What |
|------|------|------|
| 5.1 IndexNow | execution/bing_indexnow.py | Submit URLs to Bing |
| 5.2 AI Visibility | execution/seo_ai_visibility_checker.py | Track brand mentions in AI search |

### Phase 6: Monitoring (Recurring)
| Step | Tool | Frequency |
|------|------|-----------|
| 6.1 Weekly Report | execution/seo_weekly_report.py | Weekly |
| 6.2 Keyword Tracking | execution/seo_keyword_tracker.py | Weekly |
| 6.3 Full Re-audit | Phase 1 tools | Quarterly |

## Critical Rules

1. **NEVER push changes without user approval** — all scripts support --dry_run
2. **Health Canada compliance is mandatory** — every customer-facing text must pass check_health_canada_compliance()
3. **Test small first** — use --limit 5 before running on all products
4. **Export to Google Sheets** — all reports go to Sheets for easy review
5. **Self-anneal** — if a script errors, fix and update the directive

## Quality Thresholds
- Product SEO score target: ≥85/100
- Meta title length: 50-60 characters
- Meta description length: 140-155 characters
- Product description: ≥200 words
- Collection description: ≥150 words
- Blog post: ≥1,000 words
- Core Web Vitals: LCP <2.5s, INP <200ms, CLS <0.1

## File Map
| File | Phase | Type |
|------|-------|------|
| execution/seo_shared.py | All | Shared utilities |
| execution/seo_technical_audit.py | 1 | Audit |
| execution/seo_content_audit.py | 1 | Audit |
| execution/shopify_schema_injector.py | 2 | Technical |
| execution/shopify_robots_ai_config.py | 2 | Technical |
| execution/shopify_image_optimizer.py | 2 | Technical |
| execution/shopify_seo_optimizer.py | 3 | On-page (existing) |
| execution/shopify_collection_optimizer.py | 3 | On-page |
| execution/seo_internal_linker.py | 3 | On-page |
| execution/seo_content_planner.py | 4 | Content |
| execution/publish_blog_to_shopify.py | 4 | Content (existing) |
| execution/shopify_faq_creator.py | 4 | Content |
| execution/bing_indexnow.py | 5 | Off-page |
| execution/seo_ai_visibility_checker.py | 5 | Off-page |
| execution/seo_weekly_report.py | 6 | Monitoring |
| execution/seo_keyword_tracker.py | 6 | Monitoring |

## Changelog
- v1.0 (2026-03-23): Initial workflow with 6 phases, 16 tools
