# SEO Monitoring & Reporting — Beauty Connect Shop
> Version: 1.0 | Created: 2026-03-23

## Goal
Continuous monitoring of SEO performance with automated weekly reports, keyword tracking, and AI visibility checks. Detect regressions early and maintain upward organic growth trajectory.

## Tools
- `execution/seo_weekly_report.py` — Weekly GSC comparison report (clicks, impressions, CTR, position)
- `execution/seo_keyword_tracker.py` — Keyword position tracking across target queries
- `execution/seo_ai_visibility_checker.py` — Monthly AI engine citation check

## Prerequisites
- Google Search Console API access (`token_gsc.pickle` or OAuth flow)
- Target keyword list defined (minimum 20 keywords)
- Baseline metrics recorded (from Phase 1 audit)

## Schedule

### Weekly (Every Monday)
1. Run: `python execution/seo_weekly_report.py`
   - Compares last 7 days vs previous 7 days
   - Outputs: clicks, impressions, CTR, average position (week-over-week delta)
2. Run: `python execution/seo_keyword_tracker.py`
   - Tracks position for all target keywords
   - Flags any keyword that dropped > 5 positions
3. Export combined report to Google Sheet

### Monthly (First Monday of Month)
1. Run: `python execution/seo_ai_visibility_checker.py --monthly`
   - Tests 10 target queries across ChatGPT, Perplexity, Gemini
   - Records citation rate and ranking
2. Append results to monthly tracking sheet

### Quarterly (First Week of Quarter)
1. Full re-audit using Phase 1 tools (Lighthouse, schema validation, content audit)
2. Compare against previous quarter baselines
3. Update strategy based on findings

## Alert Thresholds
- **Position drop > 5** on any tracked keyword: investigate immediately (algorithm update? competitor? content issue?)
- **CTR drop > 20%** week-over-week: check for SERP feature changes (featured snippets, AI overviews)
- **Core Web Vitals failure**: fix within 48 hours (LCP > 2.5s, CLS > 0.1, INP > 200ms)
- **Organic clicks drop > 15%** week-over-week: escalate to full investigation
- **New 404 errors**: fix or redirect within 24 hours

## KPIs
- **Organic clicks** — weekly trend (target: 10% month-over-month growth)
- **Keywords on page 1** — count (target: +5 new keywords per month)
- **Average position** — trend for top 20 keywords (target: steady improvement)
- **AI citation rate** — monthly (target: cited in >= 2 AI engines for brand queries)
- **Core Web Vitals** — all passing (green) in GSC

## Edge Cases & Constraints
- GSC data has 2-3 day delay — weekly reports cover data up to 3 days ago
- Keyword tracking may show daily fluctuations — focus on 7-day rolling average
- AI visibility results vary by session — run 3 checks per query and average
- Seasonal trends: compare year-over-year when available, not just week-over-week
- API quota: GSC allows 200 queries per minute — batch requests accordingly

## Quality Thresholds
- Weekly reports delivered every Monday by 10 AM
- All tracked keywords have position data (no gaps)
- Alert response time: < 48 hours for critical issues
- Monthly AI visibility check completed by 5th of each month
- Quarterly re-audit completed within first 2 weeks of quarter

## Changelog
- v1.0 (2026-03-23): Initial version — weekly GSC reports, keyword tracking, AI visibility monitoring
