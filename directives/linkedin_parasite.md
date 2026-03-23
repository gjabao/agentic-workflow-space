# LinkedIn Parasite System — Directive v1.0

## Goal
Autonomously find viral B2B/Sales LinkedIn creators, scrape their best posts, use AI to generate unique content in your personal tone, and post to LinkedIn daily.

## Architecture
4 independent modules connected via a shared Google Sheet ("LinkedIn Parasite System"):

| Module | Script | Schedule | Purpose |
|--------|--------|----------|---------|
| 1. Init | `linkedin_parasite_init.py` | Manual / as needed | Find viral creators via keyword search |
| 2. Scrape | `linkedin_parasite_scrape.py` | Weekly (Monday 9AM) | Pull recent posts from tracked creators |
| 3. Generate | `linkedin_parasite_generate.py` | Daily (10AM) | AI: image analysis → outline → final post |
| 4. Post | `linkedin_parasite_post.py` | Daily (2PM) | Publish 1 draft to LinkedIn |

## Prerequisites
- Apify API key (`.env: APIFY_API_KEY`)
- Azure OpenAI (`.env: AZURE_OPENAI_*`)
- Google Sheets OAuth (`credentials.json` + `token.json`)
- LinkedIn Developer App (`.env: LINKEDIN_*`)
- Tone of voice examples in `directives/linkedin_parasite_tone.md`

## Google Sheets Schema

### Tab: Creators
| Column | Type | Notes |
|--------|------|-------|
| linkedin_url | string | Primary key — creator's profile URL |
| name | string | Display name |
| headline | string | LinkedIn headline |
| sample_post_likes | int | Likes on qualifying post |
| added_date | date | When added to database |

### Tab: Source Posts
| Column | Type | Notes |
|--------|------|-------|
| post_id | string | Unique post ID |
| post_url | string | Full LinkedIn post URL |
| content | string | Post text content |
| creator_url | string | FK → Creators.linkedin_url |
| posted_at | date | Original post date |
| image_url_1 | string | First image URL (optional) |
| image_url_2 | string | Second image (optional) |
| image_url_3 | string | Third image (optional) |
| scraped_at | date | Scrape timestamp |
| processed | string | "yes" / "no" |

### Tab: Destination Posts
| Column | Type | Notes |
|--------|------|-------|
| dest_id | string | UUID |
| source_post_id | string | FK → Source Posts.post_id |
| source_post_url | string | For reference |
| generated_content | string | AI-generated LinkedIn post |
| status | string | "draft" / "published" / "skipped" |
| generated_at | date | Generation timestamp |
| published_at | date | LinkedIn post timestamp |

## Module 1: Init — Find Viral Creators

**Apify Actor:** `buIWk2uOUzTmcLsuB` (LinkedIn keyword search)

**Inputs:**
- `--keyword "B2B sales"` (search term)
- `--min-likes 100` (engagement filter)
- `--max-results 200` (Apify limit)

**Workflow:**
1. Call Apify keyword search actor
2. Filter by engagement ≥ min_likes
3. Extract unique creator profiles
4. Deduplicate against existing Creators tab
5. Append new creators

**Quality check:** Should find ≥5 creators per keyword with ≥100 likes

## Module 2: Scrape — Collect Source Posts

**Apify Actor:** `A3cAPGpwBEG8RJwse` (LinkedIn profile post bulk scraper)

**Inputs:**
- `--posted-limit week` (time filter)
- `--max-posts 10` (per creator)

**Workflow:**
1. Read all creator URLs from Creators tab
2. Call Apify bulk profile scraper
3. Deduplicate against existing Source Posts (by post_url)
4. Append with `processed = "no"`

**Quality check:** Should return ≥5 posts per active creator

## Module 3: Generate — AI Content Engine

**AI Models:** Azure OpenAI (GPT-4o vision, GPT-4.1 text)

**Per source post (batch size = 1):**
1. **Image Analysis** (if image exists): GPT-4o vision → text description
2. **Outline Generation**: GPT-4.1 (content + image desc + model knowledge → unique outline)
3. **Final Post**: GPT-4.1 (outline + tone examples → polished LinkedIn post)

**Quality checks:**
- Content differs meaningfully from source (not copy-paste)
- Matches user's tone of voice
- Under 1300 characters
- No rhetorical questions, minimal emojis

**Rate limiting:** 3s delay between posts, 3 retries with exponential backoff

## Module 4: Post — LinkedIn Auto-Poster

**API:** LinkedIn Community Management API (`POST /rest/posts`)

**Workflow:**
1. Read first row where `status = "draft"`
2. Post to LinkedIn (visibility: PUBLIC)
3. Update status → "published", set published_at

**Safety:** Posts only 1 per execution. Run daily via cron.

## Setup Checklist
1. Create LinkedIn Developer App → get Client ID + Secret → `.env`
2. Run `python3 execution/linkedin_auth.py` (one-time OAuth)
3. Paste 2-5 example posts into `directives/linkedin_parasite_tone.md`
4. Run Module 1: `python3 execution/linkedin_parasite_init.py --keyword "B2B sales"`
5. Run Module 2 → 3 → 4 sequentially to test
6. Set up cron for automation

## Cron Schedule
```bash
# Weekly: Scrape posts (Monday 9AM)
0 9 * * 1 python3 execution/linkedin_parasite_scrape.py >> .tmp/parasite_scrape.log 2>&1

# Daily: Generate content (10AM)
0 10 * * * python3 execution/linkedin_parasite_generate.py --max-posts 3 >> .tmp/parasite_generate.log 2>&1

# Daily: Post to LinkedIn (2PM)
0 14 * * * python3 execution/linkedin_parasite_post.py >> .tmp/parasite_post.log 2>&1
```

## Cost Estimate (per 100 posts)
| API | Cost |
|-----|------|
| Apify (search + scrape) | ~$1.50 |
| Azure OpenAI (vision + text) | ~$1.30 |
| **Total** | **~$2.80** |

## Self-Annealing Notes
- v1.0: Initial implementation (2026-02-25)
