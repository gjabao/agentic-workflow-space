# DOE Architecture Workspace

> **Directive-Orchestration-Execution Framework**
> Making unreliable LLM outputs work reliably in production.

## 🎯 What is This?

A 3-layer architecture for building reliable AI-powered automation:

- **Layer 1: Directives** (`directives/*.md`) - WHAT to do (SOPs in markdown)
- **Layer 2: Orchestration** (AI Agent) - WHO decides (intelligent routing)
- **Layer 3: Execution** (`execution/*.py`) - HOW it's done (deterministic scripts)

## 📁 Directory Structure

```
workspace/
├── directives/           # SOPs (version controlled)
│   └── scrape_leads.md  # Example directive
├── execution/            # Python tools (version controlled)
│   └── scrape_apify_leads.py # Lead scraping script
├── .tmp/                 # Temporary files (NOT in git, regenerable)
│   ├── dossiers/
│   ├── scraped_data/
│   └── temp_exports/
├── .env                  # Secrets (NOT in git)
├── .gitignore
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy .env and add your API keys
# Edit .env and add:
# - APIFY_API_KEY
# - SSMASTERS_API_KEY
# - AZURE_OPENAI_API_KEY
```

### 3. Add Google Credentials (Required for Sheets Export)

To enable automatic Google Sheets export:

1.  **Create a Project** in [Google Cloud Console](https://console.cloud.google.com).
2.  **Enable APIs**: Search for and enable "Google Sheets API" and "Google Drive API".
3.  **Configure OAuth Consent Screen**:
    *   User Type: External
    *   App Name: "Lead Scraper"
    *   Add your email as a "Test User"
4.  **Create Credentials**:
    *   Go to Credentials > Create Credentials > OAuth client ID
    *   Application type: Desktop app
    *   Name: "Desktop Client"
5.  **Download JSON**:
    *   Download the JSON file
    *   Rename it to `credentials.json`
    *   Place it in the root directory: `Anti-Gravity Workspace/credentials.json`
6.  **First Run**: The script will open a browser window to authenticate. A `token.json` file will be created automatically.

### 4. Start Using

The AI agent will:
1. Read directives to understand what to do
2. Call appropriate execution scripts
3. Monitor progress and handle errors
4. Learn from failures (self-anneal)
5. Deliver results (typically as Google Sheets links)

## 📋 How It Works

### Example: Scraping Leads

**User says:** "Scrape 100 dentists in New York"

**Agent does:**
```
1. Reads directives/scrape_leads.md ✓
2. Finds execution/scrape_apify_leads.py ✓
3. Validates inputs (industry, location, quantity) ✓
4. Runs test scrape (25 leads) → 88% valid → PASS ✓
5. Runs full scrape (100 leads) with progress updates ✓
6. Validates output (92/100 valid emails) ✓
7. Exports to Google Sheets ✓
8. Returns: "✓ Complete! [Sheet link]"
```

**Total time:** ~3 minutes
**User active time:** 10 seconds

## 🔧 Self-Annealing

When errors occur, the system:
1. **Detects** - Reads error messages carefully
2. **Analyzes** - Identifies root cause (code bug, API limit, etc.)
3. **Fixes** - Updates scripts with error handling, retries, validation
4. **Documents** - Updates directives with learnings
5. **Tests** - Verifies the fix works
6. **Result** - System is now stronger (won't fail the same way again)

## 📊 Quality Standards

- ✅ **Code**: Docstrings, error handling, type hints, logging
- ✅ **Output**: Data validation, deduplication, consistent formatting
- ✅ **Process**: Test before full run, progress updates, graceful error recovery

## 🎓 Key Principles

1. **Directives are sacred** - They preserve institutional knowledge
2. **Test small first** - 10-25 samples before full runs
3. **Cloud deliverables** - Results go to Google Sheets/Drive (shareable links)
4. **Local is temporary** - `.tmp/` files can be deleted anytime
5. **Ask, don't guess** - Clarify when uncertain

## 📖 Documentation

See `Gemini.md` for complete agent instructions and architecture details.

## 🤝 Contributing

When adding new capabilities:
1. Create directive in `directives/[name].md`
2. Create execution script in `execution/[name].py`
3. Test thoroughly with small samples
4. Document learnings and edge cases
5. Update this README if needed

---

**Remember:** This system learns from failures. Each error makes it stronger. 🚀
