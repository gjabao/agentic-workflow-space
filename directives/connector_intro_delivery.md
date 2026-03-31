# Connector Intro Delivery — Directive

> **Purpose:** How to package and deliver hiring signal leads to recruitment agency clients.
> **Model:** Bao finds companies that need to hire → introduces them to recruitment agency → earns retainer/referral per placement.

---

## The Deliverable: Weekly Hiring Intelligence Brief

### What the recruitment agency receives every week:

**1. Google Sheet (live, updated weekly)**
- 15-50 scored companies per week
- Sorted by hiring urgency score (highest first)
- Color-coded: RED = HOT (70+), ORANGE = WARM (50-69), YELLOW = WATCH (40-49)
- Each row = one company with decision-maker contact + suggested outreach angle
- Columns: Score, Heat, Company, Website, Size, Open Roles, Stale Jobs, Key Departure, DM Name, DM Title, DM Email, DM LinkedIn, Suggested Angle

**2. Email summary (Monday morning, their timezone)**
```
Subject: Weekly Hiring Brief — [X] HOT targets this week

Hi [Agency Contact],

This week's brief is ready: [Google Sheet link]

Quick highlights:
- [X] HOT companies (urgent hiring need, no internal recruiter)
- [X] WARM companies (active hiring, worth monitoring)
- Top target: [Company Name] — [reason: e.g., "VP Engineering left 2 weeks ago, 5 roles open 30+ days, no TA team"]

Let me know if you want me to dig deeper on any of these.

— Bao
```

**3. Monthly performance report (1st of each month)**
- Total leads delivered
- How many the agency contacted
- How many converted to meetings/placements
- ROI calculation: "X leads → Y placements → $Z in fees vs $1,500 service cost"

---

## Delivery Schedule

| Day | Action | Tool |
|-----|--------|------|
| Friday | Run all scrapers (LinkedIn, Indeed, Glassdoor, departures) | Execution scripts |
| Saturday | Score & deduplicate → generate brief | `execution/score_hiring_signals.py` |
| Monday 7 AM | Email summary sent to agency contact | Automated (N8N or manual) |
| Monthly 1st | Performance report | Manual or automated |

---

## How to Run the Full Pipeline

### Quick version (auto-detect latest files):
```bash
python3 execution/score_hiring_signals.py \
  --auto-detect \
  --min-score 40 \
  --sheet-name "Weekly Hiring Brief - $(date +%b\ %d)"
```

### Full version (specify all files):
```bash
# Step 1: Run scrapers (in parallel if possible)
python3 execution/scrape_linkedin_jobs.py --query "Software Engineer" --location "United States" --limit 50 --min-age 14
python3 execution/scrape_indeed_jobs.py --query "Software Engineer" --location "United States" --limit 50 --min-age 14
python3 execution/scrape_glassdoor_jobs.py --position "Software Engineer" --location "United States" --limit 50

# Step 2: Score everything
python3 execution/score_hiring_signals.py \
  --auto-detect \
  --min-score 40 \
  --sheet-name "Weekly Brief - Client Name"
```

---

## Intro Angle Framework

When the recruitment agency reaches out to companies from the brief, they should NOT say "we got your info from a lead list." Instead:

### For Departure Signals:
> "I noticed [Person] recently moved on from [Role] at your company. Backfilling senior roles can be challenging — we specialize in [industry] placements and typically fill roles like this in 2-3 weeks. Worth a quick chat?"

### For Stale Job Postings (30+ days):
> "I saw you've had [Role] open for a while. That role can be tough to fill through job boards alone — we have a curated network of [industry] candidates and usually present 3 qualified people within 5 business days. Would that be helpful?"

### For Multiple Open Roles (3+):
> "I noticed [Company] is scaling — [X] roles open right now. When you're hiring that aggressively, having a recruiting partner handle the pipeline lets your team focus on interviews, not sourcing. We do this for companies like [similar reference]. Open to exploring?"

### For Poor Glassdoor Rating:
> "Attracting talent when reviews are mixed takes a different sourcing strategy. We've helped companies in [industry] fill hard-to-fill roles by tapping into networks that don't rely on employer brand alone. Interested in hearing how?"

---

## Pricing Model for Recruitment Agency Client

| Tier | Monthly Fee | What They Get |
|------|------------|---------------|
| **Starter** | $1,000/mo | Weekly brief (1 vertical, 1 location), 15-30 leads/week |
| **Growth** | $2,000/mo | Weekly brief (2 verticals or 3 locations), 30-60 leads/week, monthly performance report |
| **Premium** | $3,500/mo | Daily signals, unlimited verticals, exclusive territory (no other agency gets same leads), priority support |

**Upsell path:** Starter → Growth → Premium as they see placements from the leads.

**ROI pitch:** One placement = $15,000-30,000 fee. Your service = $1,000-3,500/month. Even ONE placement per quarter pays for the entire year.

---

## Client Onboarding (Async — No Call Required)

### Step 1: Send intake form (email)
```
Hi [Name],

To set up your weekly hiring intelligence brief, I need a few details:

1. What verticals do you recruit for? (e.g., IT, healthcare, finance, engineering)
2. What geographies? (e.g., US nationwide, specific states, UK)
3. What company size is your sweet spot? (e.g., 20-200 employees)
4. What roles do your candidates typically fill? (e.g., VP Engineering, CFO, Registered Nurse)
5. Any industries or companies to EXCLUDE?
6. Preferred email for the weekly brief?

Once I have this, I'll have your first brief ready within 3-5 business days.

— Bao
```

### Step 2: Configure scrapers
- Set `--query` parameters based on their verticals
- Set `--location` based on their geographies
- Set `--max-size` based on their sweet spot
- Add exclusion list to scoring script (if needed)

### Step 3: Run test batch (25 leads per source)
- Validate quality: ≥50% with DM email, ≥15 scoring above threshold
- If pass → deliver first brief
- If fail → adjust parameters and re-run

### Step 4: Deliver first brief + collect feedback
- "Which leads were most useful? Any that were off-target?"
- Feed back into scoring weights (self-annealing)

---

## Quality Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Leads per week | ≥15 above threshold | Count from scoring output |
| DM email rate | ≥50% | Has email / total scored |
| Client feedback score | ≥7/10 | Monthly survey (1 question) |
| Placement conversion | ≥1 per quarter | Client reports back |
| Churn rate | <10%/quarter | Client retention |

---

## Self-Annealing Checkpoints

After every 4 weekly briefs (1 month):
1. Ask client: "Which 3 leads were best? Which 3 were worst?"
2. Analyze what signals the best leads had in common
3. Adjust scoring weights in `score_hiring_signals.py`
4. Update this directive with learnings
5. Document in Lab Notes

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-30 | Initial directive created |
