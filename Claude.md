# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Mirrored across claude.md, agents.md, gemini.md for cross-platform compatibility

---

## Who I Am

- **Name:** Bao
- **Business:** Smart Marketing Flow — B2B lead generation and automation agency based in Vietnam
- **Core services:** cold email infrastructure, Klaviyo email marketing, signal-based outreach (Connector System), AI automation workflows
- **Active clients:**
  - SOFI (Source of Fabric International, LA) — cold email via Instantly
  - Beauty Connect Shop (Canadian B2B Korean dermaceutical) — Klaviyo
- **Tech stack:** N8N, Make.com, Instantly, Klaviyo, Apollo, Claude Code, Python, MCP integrations
- **My constraint right now:** English speaking confidence on sales calls
- **My goal:** scale Smart Marketing Flow to $5K+/month, then agency-level revenue

---

## Development Commands

### Setup
```bash
pip install -r requirements.txt     # 43 packages: dotenv, requests, apify-client, openai, google-apis, pandas, chromadb, anthropic, tenacity, etc.
cp .env.example .env                # Then fill in API keys
```

### Running Execution Scripts
All scripts live in `execution/` and follow the same pattern:
```bash
cd execution/
python scrape_apify_leads.py --help           # Most scripts use argparse — check --help first
python scrape_indeed_jobs.py --query "nurse" --location "US" --max-results 25
python shopify_seo_optimizer.py --audit        # SEO scripts support subcommands
python seo_keyword_tracker.py --domain beautyconnectshop.com
```

Scripts load `.env` via `load_dotenv()` and log to `.tmp/execution.log` + stdout.

### Running Tests
```bash
cd execution/
python ../tests/test_anymailfinder.py         # Unit: email finder API
python ../tests/test_connector_os.py          # Unit: connector system
python ../tests/test_full_workflow.py          # Integration: end-to-end
bash ../tests/test_webhook_apify.sh           # Bash: webhook integration
```

### Ops Scripts
```bash
bash scripts/backup_workspace.sh              # Backup to GitHub + local archive
bash scripts/push_to_github.sh                # Push to remote
bash scripts/setup_github_auth.sh             # Configure GitHub auth (no embedded PATs)
```

---

## Project Overview

**Lead generation & outreach automation platform** built on the DOE (Directive-Orchestration-Execution) architecture. Automates lead scraping, enrichment, email campaigns, SEO optimization, LinkedIn automation, and content generation for B2B sales workflows.

---

## The DOE Architecture

Three-layer separation that makes unreliable LLM outputs work reliably in production:

```
┌──────────────────────────────────────────────────────────┐
│  DIRECTIVES/ (36 SOPs)                                   │
│  WHAT to do — Markdown SOPs with goals, inputs, tools,   │
│  expected outputs, edge cases, quality thresholds         │
└──────────────────┬───────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────┐
│  ORCHESTRATION (Claude Agent — THIS IS YOU)               │
│  Read directives → Plan → Route to scripts → Monitor →   │
│  Self-anneal on failure → Update directives with learnings│
└──────────────────┬───────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────┐
│  EXECUTION/ (83 Python Scripts)                           │
│  HOW it's done — Deterministic, API calls, data I/O      │
│  Shared: seo_shared.py, utils_notifications.py           │
│  Config: .env file (credentials, rate limits)             │
└──────────────────────────────────────────────────────────┘
```

**Key principle:** You don't execute raw logic — you route intelligently to deterministic scripts.

### Execution Script Patterns
- Entry: `#!/usr/bin/env python3` with docstrings
- Config: `load_dotenv()` + `os.getenv()`
- Logging: dual handler (`.tmp/execution.log` + stdout)
- Args: most use `argparse` with `--help`
- Rate limiting: thread-safe `Lock()` + exponential backoff via `tenacity`
- Notifications: `from utils_notifications import notify_success, notify_error`
- BASE_DIR: always `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` — never hardcode

### Shared Utilities
- **`seo_shared.py`** — Shopify GraphQL client, Google Sheets export, GSC integration (used by all SEO/Shopify scripts)
- **`utils_notifications.py`** — Success/error notification helpers (used by 14+ scripts)

---

## Tools & Services Connected

| Service | Purpose | Auth |
|---------|---------|------|
| Apify | Web scraping orchestration | APIFY_API_KEY |
| Apollo | Lead enrichment, email verification | APOLLO_API_KEY |
| Instantly.ai | Email campaigns | INSTANTLY_API_KEY |
| Google Sheets | Data export/import | credentials.json |
| Google Search Console | SEO monitoring | token_gsc.pickle |
| Shopify (BCS) | Store SEO optimization | SHOPIFY_ADMIN_API_TOKEN |
| LinkedIn | Parasite posting, pain signals | LINKEDIN_ACCESS_TOKEN |
| ClickUp | Project management | CLICKUP_API_KEY |
| Klaviyo | Email marketing | KLAVIYO_API_KEY |
| Modal.com | Serverless deployment | Modal CLI |
| OpenAI / Azure OpenAI | Content generation | OPENAI_API_KEY |
| Anthropic Claude | Blog writing | ANTHROPIC_API_KEY |
| Bing IndexNow | Search indexing | via API |

---

## Autonomy Boundaries

**Claude CAN autonomously:**
- Read directives and execute scripts
- Write to `active/` directory (leads, research, drafts, exports, tmp)
- Update directives with learnings
- Fix script bugs and self-anneal
- Run test batches (10-25 items) before scaling

**Claude must ASK before:**
- Spending paid API credits (Apollo, Apify actors)
- Sending emails via Instantly
- Posting to LinkedIn
- Pushing to git remote
- Modifying `.env` or credentials
- Creating new execution scripts (check existing first)
- Running scrapes > 25 items

---

## Preferences

- Always return absolute file paths so I can click them
- When generating files, always save to `active/` unless I specify otherwise
- When making widespread edits to a file, read the whole file first, rewrite in one shot — do NOT edit line by line
- Always check `active/` before creating a new file to avoid duplicates
- Show progress updates for long-running tasks (every 10%)
- Test with 10-25 items before scaling to full runs
- Use batch API endpoints over single requests when available
- When I ask for research, default to fan-out with 3-5 sub-agents unless I say otherwise
- When I ask to brainstorm, use stochastic consensus with at least 4 agents with different personas
- When you finish a task, ask: "Could I have done this faster or with fewer tokens?" If yes, append the insight to Lab Notes
- Never fetch well-known websites (Google, Facebook, LinkedIn homepage) to check general facts
- Always save generated content to `active/` with a descriptive filename including the date: `YYYY-MM-DD-description.md`
- When I say "quick" or "fast", skip explanations and give me the output directly
- When I say "think through this", give me full reasoning before output

---

## Operating Rules

1. **Check Tools First** — Before creating any new script: check `execution/` for existing tools, read relevant directive, only create new if none exist.
2. **Preserve Directives** — Directives are sacred. Update/improve them as you learn. Never overwrite without asking.
3. **Test Small Before Scaling** — Test with 10-25 first → validate quality (80%+ threshold) → proceed with full run.
4. **Communicate Progress** — Show what you're doing with status updates and completion summaries.
5. **Ask, Don't Guess** — Missing API key? → Ask. Ambiguous requirement? → Clarify. Multiple approaches? → Present options. Uncertain about cost? → Get approval.

---

## Self-Annealing Protocol

When errors occur:
1. **DETECT** — Read error message & stack trace
2. **ANALYZE** — Is it: code bug? unclear directive? API limit? missing credential?
3. **FIX** — Update script, add retry logic, add validation. If fix requires paid tokens → ask first
4. **DOCUMENT** — Update directive with learnings
5. **TEST** — Verify fix works
6. **RESULT** — System is now stronger

---

## File Output Rules

| Type | Location | Example |
|------|----------|---------|
| Lead data (CSV) | `active/leads/` | `active/leads/misc/health_recruitment_US.csv` |
| Research/docs | `active/research/` | `active/research/INDEED_V3_SUMMARY.md` |
| Work in progress | `active/drafts/` | `active/drafts/blog_outline.md` |
| Final deliverables | `active/exports/` | `active/exports/client_report.pdf` |
| Temp/debug | `active/tmp/` | `active/tmp/debug_run.log` |
| Client-specific | `clients/<name>/` | `clients/beauty-connect/quiz-v4.jsx` |

---

## Client Context

### SOFI — Source of Fabric International
- **Industry:** fabric supply, LA apparel market
- **My service:** cold email outreach via Instantly MCP
- **ICP:** LA-based apparel brands, fashion startups, independent designers who need fabric suppliers
- **Pain signal:** posting on social about production issues, sourcing challenges, new collection launches
- **Campaign platform:** Instantly
- **Current status:** active outreach, ongoing sequence optimization
- **Do NOT email:** brands already in active conversation

### Beauty Connect Shop
- **Industry:** B2B Korean dermaceutical distribution, Canada
- **My service:** Klaviyo email marketing
- **Audience:** licensed estheticians, medical spas, aesthetic clinics
- **Brands:** KRX Aesthetics, ZENA, Corthe
- **Current issue:** strong open rates, weak click-through
- **Platform:** Klaviyo + Shopify
- **Tone:** professional, clinical, educational — not consumer beauty

### Connector System (my own service)
- **Model:** find companies with active hiring needs → introduce them to recruitment agency clients for retainer fee
- **Qualification criteria:** active need + no internal TA + decision maker confirmed
- **Outreach angle:** "I'm a connector, not a vendor"
- **Target:** recruitment agencies as clients, hiring companies as introductions

---

## Workflow Triggers

| When I say... | Claude does... |
|---------------|----------------|
| "research [company]" | Fan-out 4 agents, produce 1-page brief |
| "brainstorm [topic]" | Stochastic consensus, 5+ agents, return consensus + outliers |
| "write cold email for [X]" | Use cold-email skill if available, apply Saraev 4-step formula |
| "optimize [campaign]" | Read current version, propose 3 variants, score each, recommend winner |
| "prep for call with [name]" | Research company, find pain points, produce sales brief + 5 discovery questions |
| "clean up /active/" | Group loose files into subfolders, delete confirmed temp files, flag anything unclear |
| "security check" | Scan for hardcoded keys, check .gitignore, report findings |

---

## Lab Notes

> This section is updated automatically. When you make a mistake or find a faster way to do something, append a note here.

| Date | What Happened | Rule for Next Time |
|------|--------------|-------------------|
| 2026-03-30 | Workspace restructured. 130+ files moved from root to organized directories. | Always output to `active/` subdirectories, never to root. |
| 2026-03-30 | 3 Python files had hardcoded BASE_DIR paths that would break on move. | Always use `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` for BASE_DIR, never hardcode. |
| 2026-03-30 | GitHub PAT was embedded in git remote URL. | Never embed tokens in URLs. Use `gh auth` or credential helpers. |
| 2026-03-30 | Security audit: Flask debug=True on 0.0.0.0 = remote code execution. | Never use `debug=True` with `host='0.0.0.0'`. Use `127.0.0.1` for dev, gunicorn for prod. |
| 2026-03-30 | Security audit: Webhook auth defaulted to empty string = silently unauthenticated. | Webhook secrets must be REQUIRED (fail-fast if unset), never optional with empty-string default. |
| 2026-03-30 | Security audit: `eval $SECRET_CMD` in shell script = command injection risk. | Never use `eval` with dynamic strings. Use bash arrays: `cmd+=("arg")` then `"${cmd[@]}"`. |
| 2026-03-30 | Security audit: `str(e)` returned to HTTP clients leaks internals. | Always return generic "Internal server error" to clients. Log full exception server-side only. |
