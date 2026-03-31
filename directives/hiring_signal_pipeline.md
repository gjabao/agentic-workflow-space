# Hiring Signal Pipeline — Directive

> **Purpose:** Detect companies with active hiring needs, score them by urgency, find decision-makers, and package a weekly brief for recruitment agency clients.
>
> **Service model:** Connector System — find companies that need to hire → introduce them to recruitment agency partner → earn retainer/referral fee per placement.

---

## Overview

This pipeline combines 5 data sources into a single scored lead list:

| Source | Signal Type | Quality | Script |
|--------|------------|---------|--------|
| LinkedIn Jobs | Active job postings + age | High | `execution/scrape_linkedin_jobs.py` |
| Indeed Jobs | Volume hiring (10+ roles) | High | `execution/scrape_indeed_jobs.py` |
| Glassdoor | Hiring + poor employer rating = desperate | Medium-High | `execution/scrape_glassdoor_jobs.py` |
| Reed (UK) | UK market coverage | Medium | `execution/scrape_reed_jobs.py` |
| Employee Departures | Key person left = immediate backfill need | Highest (3-5x) | `execution/track_employee_departures.py` |

**Combined output:** Scored lead list with hiring urgency (1-100), decision-maker contacts, and suggested outreach angle — delivered as Google Sheet.

---

## Inputs

| Input | Required | Example |
|-------|----------|---------|
| Industry/vertical | Yes | "software engineering", "accounting", "nursing" |
| Location | Yes | "United States", "London", "California" |
| Company size range | Optional | 20-300 employees (default) |
| Job age minimum | Optional | 14 days (default) |
| Max results per source | Optional | 50 per source (default) |

---

## Execution Steps

### Step 1: Harvest (Parallel — run all sources simultaneously)

```bash
# LinkedIn — high-pain stale jobs
python3 execution/scrape_linkedin_jobs.py \
  --query "$INDUSTRY" --location "$LOCATION" \
  --limit 50 --min-age 14 --max-size 300

# Indeed — volume hiring
python3 execution/scrape_indeed_jobs.py \
  --query "$INDUSTRY" --location "$LOCATION" \
  --limit 50 --min-age 14 --max-size 300

# Glassdoor — desperation signal
python3 execution/scrape_glassdoor_jobs.py \
  --position "$INDUSTRY" --location "$LOCATION" \
  --limit 50

# Reed (UK only)
python3 execution/scrape_reed_jobs.py \
  --keyword "$INDUSTRY" --location "$LOCATION" \
  --limit 50

# Employee departures (if Google Sheet with LinkedIn URLs available)
python3 execution/track_employee_departures.py \
  --sheet-url "$DEPARTURE_SHEET_URL" --limit 25
```

**Output:** 4-5 CSV files in `.tmp/` with raw results.

### Step 2: Score & Deduplicate

```bash
python3 execution/score_hiring_signals.py \
  --input-dir .tmp/ \
  --output active/leads/hiring-signals/ \
  --min-score 40
```

**Scoring model (100-point scale):**

| Signal | Points | Logic |
|--------|--------|-------|
| Employee departure (someone left) | +35 | Highest quality — immediate backfill need |
| Job age 30+ days (stale posting) | +25 | They're struggling to fill |
| Job age 14-29 days | +15 | Active but not desperate yet |
| Multiple open roles (3+) | +20 | Scaling = budget confirmed |
| No internal recruiter/TA found | +15 | They need external help |
| Company size 20-150 | +10 | Sweet spot for agency recruiting |
| Company size 150-300 | +5 | Possible but more bureaucratic |
| Poor Glassdoor rating (<3.5) | +10 | Employer brand problem = harder to attract |
| Recent funding (Crunchbase, if available) | +10 | Budget confirmed |
| Decision-maker email found | +5 | Actionable lead |

**Score interpretation:**
- 70-100: HOT — contact immediately
- 50-69: WARM — include in weekly brief
- 40-49: WATCH — monitor for escalation
- <40: SKIP

**Deduplication:** Match on company domain. If same company appears in multiple sources, COMBINE signals (higher score).

### Step 3: Package Weekly Brief

The scoring script auto-generates:
1. **Google Sheet** with scored leads (sorted by urgency)
2. **Summary email** with top 10 hottest targets
3. **CSV backup** in `active/leads/hiring-signals/`

### Step 4: Deliver to Recruitment Agency Client

See `directives/connector_intro_delivery.md` for delivery SOP.

---

## Output Format (Google Sheet Columns)

| Column | Description |
|--------|------------|
| Hiring Score | 1-100 urgency score |
| Heat Level | HOT / WARM / WATCH |
| Company Name | — |
| Company Website | — |
| Company Size | Employee count |
| Industry | — |
| Signal Sources | "LinkedIn Jobs + Glassdoor + Departure" |
| Open Roles | Number of active job postings |
| Stale Jobs | Number of jobs 30+ days old |
| Key Departure | Name + role of person who left (if applicable) |
| DM Name | Decision-maker full name |
| DM Title | CEO, VP People, Head of HR, etc. |
| DM Email | Verified email |
| DM LinkedIn | Profile URL |
| Suggested Angle | AI-generated 2-line intro pitch |
| Date Added | When this lead was first detected |

---

## Quality Thresholds

- Email verification rate: ≥60%
- Decision-maker found rate: ≥50%
- Minimum 15 scored leads per weekly brief
- Score accuracy validated by client feedback monthly

---

## Cost Per Run (Estimated)

| Source | ~50 leads | Cost |
|--------|-----------|------|
| LinkedIn Jobs | 50 | $1-4 |
| Indeed Jobs | 50 | $1-4 |
| Glassdoor | 50 | $1-4 |
| Reed | 50 | $1-3 |
| Employee Departures | 25 | $1-2 |
| Scoring + Brief | — | $0 (local) |
| **Total per run** | **~200 raw → 50-80 scored** | **$4-17** |

Monthly cost for weekly runs: $16-68. Client pays $1,500+/month. Massive margin.

---

## Scheduling

- **Weekly:** Monday 6 AM (client's timezone) via N8N or Modal cron
- **On-demand:** Bao can trigger manually anytime

---

## Self-Annealing

After each client feedback cycle:
1. Update scoring weights based on which leads converted to placements
2. Add new signal patterns to this directive
3. Update score thresholds if needed
4. Document in Lab Notes

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-30 | Initial directive created |
