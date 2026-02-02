# Track Employee Departures → Find Decision Makers

## Goal

Track people who recently changed jobs on LinkedIn → Extract their PREVIOUS company → Find decision makers at that company to outreach.

**Why this works:**
- Job boards = 100+ agencies contact same companies (crowded)
- Employee departures = You're the ONLY one who knows (competitive advantage)
- Conversion rate 3-5x higher than cold outreach

## Input

**Google Sheet with LinkedIn profile URLs:**

| Column | Example | Required |
|--------|---------|----------|
| linkedin_url | https://linkedin.com/in/mitchellsgreen | Yes |
| notes | (optional context) | No |

**CLI:**

```bash
python execution/track_employee_departures.py \
  --sheet-url "https://docs.google.com/spreadsheets/d/..." \
  --limit 25
```

**API Keys Required (.env):**

- `APIFY_API_KEY` - harvestapi/linkedin-profile-scraper
- `ANYMAILFINDER_API_KEY` - Company email finder
- `RAPIDAPI_KEY` - Google Search for LinkedIn
- `RAPIDAPI_KEY_2` - (Optional) second key for throughput

## Tool

`execution/track_employee_departures.py`

## Expected Output

**Google Sheet (11 columns):**

| Column | Example | Source |
|--------|---------|--------|
| person_who_left | Mitch Green | LinkedIn Profile |
| person_linkedin | linkedin.com/in/mitchellsgreen | LinkedIn Profile |
| role_they_left | Board Director | experience[].position |
| previous_company | F12.net | experience[].companyName |
| left_date | 2025 | experience[].endDate.year |
| dm_first_name | Alex | Email extraction |
| dm_last_name | Webb | Email extraction |
| dm_job_title | CEO | LinkedIn search |
| dm_email | alex@f12.net | AnyMailFinder |
| dm_linkedin_url | linkedin.com/in/... | RapidAPI |
| company_website | f12.net | Google Search |

**Quality Metrics:**

- Coverage: 80%+ profiles have recent departures
- Website found: 70%+ companies
- Decision-makers: 150%+ (1.5+ per company average)
- Email quality: 85%+ valid format
- Processing: ~30-60 seconds per profile

## Workflow

```
1. READ Google Sheet
   └─ Extract LinkedIn profile URLs

2. SCRAPE LinkedIn profiles (Apify: harvestapi/linkedin-profile-scraper)
   └─ Get full experience history for each person

3. EXTRACT Previous Company
   ├─ Filter: Jobs with endDate.year (not "Present")
   ├─ Filter: Jobs ended within 6 MONTHS (recent signal only)
   ├─ Sort: By end_year descending
   └─ Select: Most recent departure

4. FOR EACH PREVIOUS COMPANY (parallel, 10 workers):
   ├─ Find website via 3-attempt Google Search
   ├─ Find ALL emails at domain (AnyMailFinder, up to 20/company)
   └─ FOR EACH EMAIL (parallel, 5 workers):
       ├─ Extract name from email (firstname.lastname@)
       ├─ Search LinkedIn by name + company
       ├─ Validate decision-maker title
       └─ Deduplicate by full name

5. OUTPUT to Google Sheet
   └─ One row per decision-maker found
```

## Previous Company Extraction Logic

```python
def extract_previous_company(profile: Dict) -> Dict:
    """
    Extract company they JUST LEFT from experience history.

    Filter criteria:
    - Job has endDate.year (not "Present")
    - Job ended within 6 months (recent signal)
    - Take most recent departure
    """
    experiences = profile.get('experience', [])

    recent_departures = []
    for exp in experiences:
        end_date = exp.get('endDate', {})

        # Skip current jobs
        if end_date.get('text') == 'Present' or not end_date:
            continue

        end_year = end_date.get('year')
        if end_year:
            recent_departures.append({
                'company_name': exp.get('companyName', ''),
                'position': exp.get('position', ''),
                'location': exp.get('location', ''),
                'end_year': end_year
            })

    # Filter: Only jobs ended in last 6 months
    current_year = datetime.now().year
    cutoff_year = current_year - 1 if datetime.now().month <= 6 else current_year

    recent_departures = [
        d for d in recent_departures
        if d['end_year'] >= cutoff_year
    ]

    if not recent_departures:
        return None

    # Return most recent
    recent_departures.sort(key=lambda x: x['end_year'], reverse=True)
    return recent_departures[0]
```

## Decision-Maker Keywords

**Included:**

- founder, co-founder, ceo, chief executive, chief
- owner, president, managing partner, managing director
- vice president, vp, cfo, cto, coo, cmo
- executive, c-suite, c-level, principal, partner

**Excluded:**

- assistant, associate, junior, intern, coordinator
- analyst, specialist, representative, agent, clerk

## Edge Cases & Constraints

**Profile has no experience:** Skip (no data to extract)

**Only current jobs (all "Present"):** Skip (no departure detected)

**All departures older than 6 months:** Skip (signal too stale)

**No website found:** Try Google Search with 3 attempts, then skip

**No emails found:** Skip company (cannot find contacts)

**No decision-makers:** Include company row with empty DM fields (for manual research)

**Multiple recent departures:** Take the most recent one (highest end_year)

## Quality Thresholds

**Test with 5 profiles first:**

- 80%+ profiles have extractable previous company
- 70%+ companies have findable website
- 150%+ decision-makers found (avg 1.5 per company)
- 85%+ emails in valid format

**Fail → Adjust:**

- Low previous companies (<80%) → Check if profiles actually changed jobs recently
- Low websites (<70%) → Normal for small/local businesses
- Low DMs (<150%) → Check industry (B2C has lower rates)

## Self-Annealing Notes

**v1.0 (2026-02-01) - Initial Implementation:**

- Based on Crunchbase scraper v4.0 email-first workflow
- Reuses AnyMailFinder, RapidAPIGoogleSearch classes
- 6-month filter for recent departures only
- Parallel processing: 10 company workers, 5 email workers

**Cost Estimate (per 100 profiles):**

- Apify LinkedIn scraper: ~$2-3
- AnyMailFinder: ~$0.50
- RapidAPI: Free (5000 req/month)
- **Total:** ~$3 per 100 profiles

## Outreach Template

```
Subject: Saw {person_who_left} left {role_they_left} position

Hi {dm_first_name},

Noticed on LinkedIn that {person_who_left} recently moved on
from the {role_they_left} position at {previous_company}.

Transitions like this can be tricky - especially keeping
[projects/clients/operations] running smoothly while you search.

I specialize in helping companies like yours with {your_service}
during these transitions. Happy to share how {similar_company}
handled this exact situation.

Worth a quick chat?

{your_name}
```
