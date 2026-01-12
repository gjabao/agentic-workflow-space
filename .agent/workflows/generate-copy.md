---
description: Generate custom cold email copy (SSM + Connector Angle) for client
---

# Generate Custom Cold Email Copy - Fast Workflow

This workflow generates SSM opener + Connector Angle cold email copy for any client URL in under 2 minutes.

## Prerequisites
- Azure OpenAI credentials in `.env` file
- Google OAuth credentials (optional, for auto-upload to Google Docs)

## Quick Start (Fastest Method)

### Step 1: Run the generator script
```bash
python3 execution/generate_custom_copy.py --client_url <CLIENT_URL> --num_variants 3 --competitors <COMPETITOR_URLS>
```

**Example:**
```bash
python3 execution/generate_custom_copy.py \
  --client_url https://veretin.com/ \
  --num_variants 3 \
  --competitors https://plexusrs.com,https://cryptorecruit.com,https://thecryptorecruiters.io
```

// turbo
### Step 2: Upload to Google Docs (plaintext)
```bash
python3 execution/upload_to_gdoc.py custom_copy_*.md
```

## Manual Fast Method (No Script)

If you want me to generate copy manually (faster for one-off requests):

1. **Provide client URL** - I'll analyze the website
2. **I'll research 3-5 competitors** - Using web search
3. **I'll generate 3 email variants** - SSM opener + Connector Angle framework
4. **I'll save to markdown** - In workspace root
5. **I'll upload to Google Docs** - Plaintext format

**Time:** ~2-3 minutes total

## Output Files
- `custom_copy_<client_name>.md` - Markdown file with all copy
- `.tmp/custom_copy/custom_copy_<timestamp>.json` - JSON backup
- Google Doc URL - Shareable link (if uploaded)

## Framework Applied
- ✅ SSM opener (6 variants available)
- ✅ Connector Angle positioning
- ✅ Spartan/Laconic tone rules
- ✅ <100 words per email
- ✅ No punctuation at end
- ✅ Simple language only (no jargon)
- ✅ Follow-ups (Day 3, Day 7)

## Speed Optimizations
1. **Parallel research** - Analyze client + competitors simultaneously
2. **Limited competitors** - 3-5 max (vs 10) for faster analysis
3. **Direct markdown output** - Skip complex Google Docs formatting
4. **Cached credentials** - Reuse Google OAuth token
5. **Minimal logging** - Less verbose output
