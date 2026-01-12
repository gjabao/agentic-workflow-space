# Enrich Leads from Google Sheets

## Goal
Enrich a Google Sheet containing company names (and optionally websites) with:
1.  **Decision Maker Info** (Name, Title, LinkedIn) via RapidAPI Google Search.
2.  **Email Address** via Anymailfinder.
3.  **Personalized Message** via Azure OpenAI (using SSM SOP prompts).

## Required Inputs
- **Google Sheet ID**: ID of the sheet to read/write.
- **API Keys** (in `.env`):
    - `RAPIDAPI_KEY` (for Google Search)
    - `ANYMAILFINDER_API_KEY` (for Emails)
    - `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` (for Personalization)
    - `token.json` / `credentials.json` (for Google Sheets API)

## Process
1.  **Read Sheet**: Load rows from the specified Google Sheet.
2.  **Identify Columns**: Find "Company Name" and "Website" (if available).
3.  **Iterate & Enrich**:
    - **Find DM**: Search `site:linkedin.com/in/ ... "{Company}"` for CEO/Founder.
    - **Find Email**: Use Anymailfinder with (First Name, Last Name, Domain).
    - **Generate Message**:
        - Rotate between 5 opener families (Company, Market, Daily, Deal-Flow, Ultra-Operator).
        - Use Azure OpenAI to fill the specific template holes.
        - STRICT adherence to prompt rules (no fluff, spartan tone).
4.  **Update Sheet**: Write back results to:
    - `First Name`, `Last Name`, `Job Title`
    - `Email`
    - `Personalization` (The generated message)

## Outputs
- Updated Google Sheet with enriched columns.

## Quality Thresholds
- **Decision Maker**: Must be relevant (CEO, Founder, Owner, Managing Partner).
- **Email**: Only "personal" or high-confidence verified emails.
- **Message**:
    - **NO** corporate jargon (optimize, leverage, synergy).
    - **NO** punctuation at end of sentences/CTAs.
    - **MUST** follow the specific format of the selected opener.
