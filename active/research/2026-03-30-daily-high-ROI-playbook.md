# Daily High-ROI Playbook

> 90 minutes/day. 3 blocks. Every task maps to revenue.

---

## Block 1: Revenue Protection (20 min) — Keep existing clients happy

These tasks protect the money already coming in. A churned client costs 5x more to replace.

### SOFI (Cold Email)
**Daily (5 min):**
- Check Instantly campaign analytics — look for reply rate drops or bounce spikes
- Command: `"check SOFI Instantly analytics"` or use Instantly MCP directly
- If reply rate < 1%: flag sequence for rewrite
- If bounce > 3%: pause campaign, clean list

**Weekly (15 min, Monday):**
- Pull weekly report, compare to last week
- Propose 1 subject line A/B test
- Refresh lead list if running low (< 100 remaining)

### Beauty Connect Shop (Klaviyo)
**Daily (5 min):**
- Check Klaviyo flow performance — open rate, CTR, revenue attributed
- Command: `"check Beauty Connect Klaviyo metrics"`
- Their problem is weak CTR — look for which emails get opens but no clicks

**Weekly (15 min, Wednesday):**
- Propose 1 CTA or layout change based on data
- Check if any new products launched that need email support

### Why this is high-ROI:
- Retaining a $1,500/month client = $18K/year
- 10 minutes of monitoring prevents surprise churn
- Data-backed recommendations make you look proactive, not reactive

---

## Block 2: Revenue Growth (40 min) — Close the recruitment agency + find next client

This is where your income scales. Every day, move the pipeline forward.

### Connector System — Close the Recruitment Agency (Priority #1)
**Daily (20 min):**

| Day | Task | Tool |
|-----|------|------|
| Mon | Run hiring signal scrapers for their vertical | `scrape_linkedin_jobs.py` + `scrape_indeed_jobs.py` |
| Tue | Score results + generate weekly brief | `score_hiring_signals.py --auto-detect` |
| Wed | Send brief to recruitment agency contact (email) | Manual email with Google Sheet link |
| Thu | Check if they opened/used the brief — follow up if silent | Email follow-up |
| Fri | Run employee departure tracker for fresh signals | `track_employee_departures.py` |

**The play:** Send them 2-3 FREE weekly briefs. After week 3, the conversation is: "Want this every week? $1,500/month." The data sells itself.

### New Client Acquisition (20 min)
**Daily:**
1. **Scrape 10 potential clients** — staffing firms, B2B agencies, or SaaS companies hiring SDRs
   ```
   python3 execution/scrape_linkedin_jobs.py --query "SDR" --location "United States" --limit 10 --min-age 14
   ```
2. **Send 5 cold emails** to potential agency clients via Instantly
   - Use Connector Angle: "I track hiring signals across 4 job boards. Here's what I found for your vertical this week."
   - Attach a mini sample (5 scored leads) as proof
3. **Check replies** from yesterday's batch — respond within 2 hours

**Weekly target:** 25 cold emails sent → 2-3 replies → 1 meeting (async/Loom) → close 1 client/month

### Why this is high-ROI:
- 1 new client at $1,500/month = $18K/year
- The recruitment agency is ALREADY interested — this is the lowest-hanging fruit
- Free briefs cost you $5-15 in API calls but demonstrate $1,500/month value

---

## Block 3: Asset Building (30 min) — Things that compound over time

These don't pay today but make everything easier next month.

### LinkedIn Authority (15 min)
**Daily:**
- Post 1 short LinkedIn post sharing a hiring insight from your data
- Example: "Tracked 200 companies this week. 47 have had roles open 30+ days with no internal recruiter. That's $2.3M in unfilled salary sitting on the table."
- Use LinkedIn parasite posting skill or write manually
- **Don't sell.** Just share data. Let people come to you.

**Why:** After 30 days of daily posts, inbound leads start. After 90 days, you're the "hiring signals guy." This reduces your dependence on cold outreach.

### Skill Improvement (15 min)
**Pick ONE each day:**

| Day | Focus | Action |
|-----|-------|--------|
| Mon | Cold email craft | Rewrite 1 email sequence using a different framework. Test it. |
| Tue | Scoring model | Review which leads converted last week. Adjust weights in `score_hiring_signals.py`. |
| Wed | New vertical research | Research 1 new industry your pipeline could serve (healthcare staffing? IT? finance?) |
| Thu | Automation | Automate 1 manual step (e.g., wire N8N to auto-send Monday brief) |
| Fri | Self-annealing | Review Lab Notes. What failed this week? Update directives. |

### Why this is high-ROI:
- LinkedIn posts compound — each one builds on the last
- Improving the scoring model makes every future brief more valuable
- Automating one step per week means in 3 months the system runs itself

---

## Daily Schedule Template

```
8:00 - 8:20   Block 1: Check SOFI + BCS metrics (revenue protection)
8:20 - 9:00   Block 2: Run scrapers + send outreach + reply to leads (revenue growth)
9:00 - 9:30   Block 3: LinkedIn post + 1 improvement task (asset building)
```

Total: 90 minutes. Then focus on delivery work for the rest of the day.

---

## Weekly Milestones (Track These)

| Metric | Target | Why |
|--------|--------|-----|
| Cold emails sent to potential clients | 25/week | Pipeline for new business |
| Replies received | 2-3/week | Conversion funnel |
| Hiring briefs delivered (free or paid) | 1/week | Proves your value |
| LinkedIn posts published | 5/week | Inbound pipeline |
| Client health checks done | 2/week (1 per client) | Retention |
| Scoring model improvements | 1/week | Product gets better |

---

## The Math: Why This Works

**Current state:** ~$2-3K/month (2 clients)

**After 30 days of this playbook:**
- SOFI retained: $1,500/month (protected)
- BCS retained: $1,000/month (protected)
- Recruitment agency signed: $1,500/month (new)
- **Total: $4,000/month**

**After 60 days:**
- 1 more client from cold outreach: +$1,500/month
- Recruitment agency upsell (more verticals): +$500/month
- **Total: $6,000/month → goal hit**

**After 90 days:**
- LinkedIn inbound starts producing leads
- 1-2 more clients close
- System is 80% automated
- **Total: $8,000-10,000/month**

---

## One Rule: Don't Skip Block 2

Block 1 protects revenue. Block 3 builds long-term assets. But Block 2 is where NEW money comes from. If you only have 20 minutes in a day, spend it all on Block 2.

The recruitment agency is your #1 priority. Send them a brief THIS WEEK.