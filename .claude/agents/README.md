# Sub-Agent Directory

This directory contains specialized sub-agent definitions for the Anti-Gravity DO Framework.

## Purpose

Sub-agents are **context-isolated specialist workers** that handle specific research or analysis tasks, keeping the main orchestrator's context window clean.

---

## Available Agents

### 1. First Agent (`first_agent.json`)

**Purpose:** Research API documentation and extract endpoint specifications

**Layer:** Pre-Execution Research (Layer 0)

---

### 2. Code Reviewer (`code_reviewer.json`)

**Purpose:** Ruthlessly review Python scripts against directives for alignment, security, and efficiency

**Layer:** Post-Execution Quality Gate

**When to Use:**
- After completing complex multi-file implementations
- Before production deployments or git commits
- After fixing critical bugs (validate fix quality)
- When user explicitly requests code review/audit
- After modifying security-sensitive code (API calls, auth)
- As final step in self-annealing loop

**When NOT to Use:**
- During active development (wait until complete)
- For trivial changes (typos, comment updates)
- When code hasn't been executed/tested yet
- For research tasks (no code to review)

**Input:**
- Directive path (e.g., `directives/scrape_leads.md`)
- Script path (e.g., `execution/scrape_apify_leads.py`)
- Focus areas (security, efficiency, alignment, quality)

**Output:**
- Review report: `.tmp/reviews/review_[script]_[date].md`
- Executive scores (Alignment, Efficiency, Security, Reliability)
- Prioritized issues (P0 critical, E1 efficiency, A1 alignment, Q1 quality)
- Security risk matrix with CVSS scores
- Production readiness assessment

**Permissions (Read-Only Auditor):**
- ✅ Read: `directives/*.md`, `execution/*.py`, `.tmp/reviews/`, `CLAUDE.md`
- ✅ Write: `.tmp/reviews/` ONLY
- ✅ Tools: Read, Glob, Write (reviews), Task
- ❌ No access to: `.env`, `credentials.json`, `execution/` (write), Bash, network

**Token Budget:** 80,000 tokens (large scripts + directives)

**Max Execution Time:** 90 seconds

**Success Metrics (2025-12-25):**
- Reviews completed: 1
- Critical issues found: 4 (API key exposure, no timeouts, async crash, validation gap)
- Issues fixed: 4 (100% resolution rate)
- Production readiness improvement: 60% → 85% (+25%)
- Zero-day vulnerabilities prevented: 2

---

### 3. Documentation Agent (`documentation_agent.json`)

**Purpose:** Maintain directives as source of truth by capturing learnings from execution layer changes

**Layer:** Knowledge Preservation (Post-Execution)

**When to Use:**
- After successful workflow completion (Main Agent calls as final step)
- After fixing an error that required code changes (self-annealing loop)
- After modifying execution script with performance improvements
- After discovering new edge cases or API behavior changes
- When Main Agent says "Update the directive with this learning"

**When NOT to Use:**
- During active workflow execution (wait until completion)
- For minor code refactors without behavior change
- When creating NEW directives (Main Agent handles initial creation)
- For research-only tasks (no execution occurred, nothing to document)
- When error is unresolved (don't document unconfirmed fixes)

**Input:**
- Directive filename (e.g., `scrape_leads.md`)
- Trigger type: `successful_workflow`, `error_fixed`, `script_modified`
- Context: error message, solution applied, performance metrics, script changes
- Learning title (short description)

**Output:**
- Updated directive file with new entry in "Learnings & Optimizations" section
- Preserved DOE structure and version history
- Updated related sections (Performance Targets, Edge Cases, etc.) if needed

**Permissions (Surgical Write Access):**
- ✅ Read: `directives/*.md`, `execution/*.py`, `.tmp/`, `CLAUDE.md`
- ✅ Edit: `directives/*.md` ONLY
- ✅ Tools: Read, Edit, Glob
- ❌ No access to: `.env`, `credentials.json`, `execution/` (write), Bash, WebFetch, Write

**Token Budget:** 20,000 tokens (directives can be lengthy)

**Max Execution Time:** 30 seconds

---

### First Agent (`first_agent.json`) - Full Details

**When to Use:**
- User asks: "Research [API Name] documentation"
- User asks: "What endpoints does [API] have?"
- User asks: "How do I authenticate with [API]?"
- Building new API integration from scratch
- Debugging API errors and need endpoint specs

**When NOT to Use:**
- User asks to CALL an API (use execution scripts instead)
- User asks to BUILD integration (orchestrator uses research as input)
- API already documented in `.tmp/api_research/`

**Input:**
- API name
- Documentation URL (optional)
- Focus area (e.g., "authentication", "lead search endpoints")

**Output:**
- `.tmp/api_research/[api_name]_[timestamp].json` - Structured endpoint catalog
- `.tmp/api_research/[api_name]_[timestamp].md` - Human-readable summary

**Permissions (Least Privilege):**
- ✅ Read: `.tmp/api_docs/`, `directives/*.md`
- ✅ Write: `.tmp/api_research/`
- ✅ Tools: WebFetch, WebSearch, Read, Write, Glob
- ❌ No access to: `.env`, `credentials.json`, `execution/`, Bash, Edit

**Token Budget:** 50,000 tokens (documentation can be lengthy)

**Max Execution Time:** 120 seconds

---

## Orchestration Workflow

### Main Agent Decision Tree

```
User Request
    ↓
Does it involve NEW API research?
    ├─ YES → Delegate to First Agent
    │   ├─ Agent researches API docs
    │   ├─ Outputs JSON catalog + Markdown summary
    │   └─ Main Agent uses results to build directive/script
    │
    └─ NO → Handle directly
        ├─ Is it execution? → Run existing script
        ├─ Is it a known API? → Read cached research from .tmp/api_research/
        └─ Is it general task? → Use directives + execution scripts
```

### Example Flow

**User:** "I want to integrate with the Apollo API for lead enrichment"

**Main Agent:**
1. Checks `.tmp/api_research/` for existing Apollo research
2. If not found: Delegates to First Agent
3. First Agent:
   - Fetches https://apolloio.github.io/apollo-api-docs/
   - Extracts endpoints, auth, rate limits
   - Outputs:
     - `.tmp/api_research/apollo_20251225.json`
     - `.tmp/api_research/apollo_20251225.md`
4. Main Agent:
   - Reads Markdown summary
   - Creates `directives/enrich_apollo.md`
   - Builds `execution/enrich_apollo.py` using endpoint specs
5. User gets working integration (no trial-and-error)

---

## Context Isolation Strategy

### Why Isolate Context?

**Problem:** API documentation is 10,000+ tokens. Reading it in main context wastes budget.

**Solution:** Delegate to First Agent with clean context window.

**Isolation Rules:**
1. **Main Agent sends:** API name + documentation URL only
2. **First Agent receives:** Clean context (no conversation history)
3. **First Agent returns:** File paths to research results
4. **Main Agent reads:** Summary files (not full docs)

**Token Savings:**
- Without isolation: 10,000 tokens (API docs) + 5,000 tokens (conversation) = 15,000 tokens
- With isolation: 200 tokens (file path) + 1,000 tokens (summary) = 1,200 tokens
- **Savings:** 92% context reduction

---

## Agent Invocation (For Main Agent)

### Method 1: Task Tool (Recommended)

```python
# In main orchestrator logic:
result = Task(
    subagent_type='general-purpose',
    description="Research Apollo API docs",
    prompt=f"""
    You are First Agent. Research the Apollo API and extract endpoint specifications.

    Documentation URL: https://apolloio.github.io/apollo-api-docs/

    {FIRST_AGENT_SYSTEM_PROMPT}

    Focus on:
    - Lead enrichment endpoints
    - Authentication mechanism
    - Rate limits

    Output:
    1. JSON catalog: .tmp/api_research/apollo_{timestamp}.json
    2. Markdown summary: .tmp/api_research/apollo_{timestamp}.md
    """,
    model='sonnet'  # or 'haiku' for speed
)

# Main agent then reads the output files
summary_path = result['output_files']['markdown']
summary = Read(summary_path)
# Use summary to build directive/script
```

### Method 2: Direct Invocation (Python)

```python
# In execution/invoke_first_agent.py:
import subprocess
import json

def research_api(api_name: str, docs_url: str) -> dict:
    """Invoke First Agent to research API."""

    # Load agent definition
    with open('.claude/agents/first_agent.json') as f:
        agent_config = json.load(f)

    # Build prompt
    prompt = agent_config['system_prompt']
    prompt += f"\n\nAPI Name: {api_name}\nDocs URL: {docs_url}"

    # Invoke via Task tool (in Claude Code context)
    # ... implementation depends on your environment

    return {
        'json_catalog': f'.tmp/api_research/{api_name}_{timestamp}.json',
        'markdown_summary': f'.tmp/api_research/{api_name}_{timestamp}.md'
    }
```

---

## Permission System

### Filesystem Access Control

**Read-Only Access:**
- `.tmp/api_docs/` - Cached documentation files
- `directives/*.md` - Reference existing SOPs for context

**Write Access:**
- `.tmp/api_research/` - Research output directory

**Forbidden Access:**
- `.env`, `credentials.json`, `token.json` - Secrets
- `execution/*.py` - Production code (no modifications)
- `.git/` - Version control

### Network Access Control

**Allowed:**
- WebFetch: `https://*.docs.*` (documentation sites)
- WebFetch: `https://*.api.*` (API reference pages)
- WebFetch: `https://developer.*` (developer portals)
- WebSearch: API documentation queries only

**Forbidden:**
- Direct API calls to production endpoints (research only, no execution)
- Bash: `curl`/`wget` commands (use WebFetch instead)
- External code execution

### Tool Access Control

**Allowed Tools:**
- WebFetch (fetch documentation pages)
- WebSearch (find API docs)
- Read (read directives for context)
- Write (save research results)
- Glob (pattern matching for docs)

**Forbidden Tools:**
- Bash (no system commands)
- Edit (no code modifications)
- NotebookEdit (no notebook edits)
- Task (no nested agent spawning)
- Skill (no skill invocations)

**Rationale:** First Agent is read-only researcher. It cannot modify production code or execute commands. This prevents accidental damage during research phase.

---

## Output Format Standards

### JSON Catalog Schema

```json
{
  "api_name": "Apollo",
  "base_url": "https://api.apollo.io/v1",
  "authentication": {
    "type": "API_KEY",
    "location": "header",
    "key_name": "X-Api-Key"
  },
  "rate_limits": {
    "requests_per_minute": 200,
    "requests_per_day": 10000,
    "burst_limit": null
  },
  "endpoints": [
    {
      "method": "POST",
      "path": "/people/match",
      "description": "Find person by email or LinkedIn URL",
      "parameters": {
        "required": ["email"],
        "optional": ["reveal_personal_emails"]
      },
      "response_format": "JSON",
      "example_response": {
        "person": {
          "id": "123",
          "email": "john@example.com",
          "title": "CEO"
        }
      }
    }
  ],
  "pagination": {
    "type": "offset",
    "parameters": ["page", "per_page"]
  },
  "error_codes": [
    {
      "code": 401,
      "meaning": "Invalid API key",
      "action": "Check X-Api-Key header"
    },
    {
      "code": 429,
      "meaning": "Rate limit exceeded",
      "action": "Wait 60s, implement exponential backoff"
    }
  ]
}
```

### Markdown Summary Template

```markdown
# API: Apollo

## Authentication
- Type: API_KEY
- Location: Header
- Key Name: `X-Api-Key`

## Rate Limits
- **RPM:** 200 requests/minute
- **Daily Quota:** 10,000 requests/day
- **Burst:** No burst limit

## Endpoints

### 1. Match Person
**Method:** `POST /people/match`
**Description:** Find person by email or LinkedIn URL
**Required Params:** `email`
**Optional Params:** `reveal_personal_emails`
**Response:** JSON object

**Example Request:**
```bash
curl -X POST 'https://api.apollo.io/v1/people/match' \
  -H 'X-Api-Key: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email": "john@example.com"}'
```

**Example Response:**
```json
{
  "person": {
    "id": "123",
    "email": "john@example.com",
    "title": "CEO"
  }
}
```

## Error Codes
- **401:** Invalid API key → Check X-Api-Key header
- **429:** Rate limit exceeded → Wait 60s, implement backoff

## Integration Notes
- Pagination: Offset-based (`page` and `per_page` params)
- Batch operations: Not available
- Webhooks: Not supported
```

---

## Self-Annealing for Agents

### Learning Loop

After each research session:
1. **Agent completes research** → Outputs saved to `.tmp/api_research/`
2. **Main Agent reviews output** → Checks completeness, accuracy
3. **If gaps found** → Update `first_agent.json` with new extraction patterns
4. **If common API pattern** → Document in agent definition for reuse
5. **If same API researched twice** → Use cached results, don't re-research

### Common Patterns Library

As First Agent researches more APIs, build a patterns library:

```json
{
  "common_patterns": {
    "rest_api_pagination": {
      "offset_based": {
        "params": ["page", "per_page", "offset", "limit"],
        "response_fields": ["total", "count", "next", "previous"]
      },
      "cursor_based": {
        "params": ["cursor", "next_cursor"],
        "response_fields": ["next_cursor", "has_more"]
      }
    },
    "authentication": {
      "api_key_header": "X-Api-Key, X-API-KEY, Api-Key, Authorization: ApiKey {key}",
      "bearer_token": "Authorization: Bearer {token}",
      "oauth2": "Authorization: Bearer {access_token}"
    },
    "rate_limiting": {
      "headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
      "retry_after": "Retry-After header (seconds or HTTP date)"
    }
  }
}
```

---

## Quality Checklist

Before completing research, First Agent MUST verify:

- [ ] All endpoints documented (GET, POST, PUT, DELETE, PATCH)
- [ ] Authentication mechanism identified and tested
- [ ] Rate limits specified (or marked as "Unknown")
- [ ] Required vs optional parameters distinguished
- [ ] Example requests/responses included
- [ ] Error codes mapped to human actions
- [ ] Pagination strategy documented
- [ ] Deprecated endpoints flagged
- [ ] Documentation version noted
- [ ] Ambiguities highlighted for manual review

---

## Integration with DO Architecture

```
DO Framework Layers:

┌─────────────────────────────────────────┐
│  Layer 1: Directives (WHAT to do)      │
│  - directives/*.md                      │
└─────────────────────────────────────────┘
                  ↑
                  │ (informed by research)
                  │
┌─────────────────────────────────────────┐
│  Layer 0: Pre-Execution Research        │  ← First Agent operates here
│  - .tmp/api_research/*.{json,md}        │
│  - API endpoint extraction              │
│  - Authentication discovery             │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Layer 2: Orchestration (WHO decides)   │
│  - Main Agent routes based on research  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Layer 3: Execution (HOW it's done)     │
│  - execution/*.py (uses API specs)      │
└─────────────────────────────────────────┘
```

**Value Proposition:**
- Without First Agent: Trial-and-error API integration (10+ failed attempts)
- With First Agent: Correct implementation first try (research → build → ship)

---

## Performance Metrics

### Target Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Research Duration | < 120s | TBD |
| Token Usage | < 50,000 | TBD |
| Endpoint Coverage | 100% | TBD |
| Authentication Accuracy | 100% | TBD |
| Rate Limit Discovery | 80%+ | TBD |

### Success Criteria

**Research session is successful if:**
1. All major endpoints documented
2. Authentication mechanism identified (with examples)
3. Rate limits specified (or marked as "Unknown - test carefully")
4. At least 3 example requests/responses included
5. Error codes mapped to actionable fixes
6. Output files created in `.tmp/api_research/`

---

## Troubleshooting

### Issue: Agent can't find documentation URL

**Solution:** Provide explicit URL or let agent search via WebSearch

### Issue: Documentation is behind login wall

**Solution:** Agent flags this, Main Agent prompts user for credentials or manual summary

### Issue: API is GraphQL, not REST

**Solution:** Agent adapts output format to document queries/mutations instead of endpoints

### Issue: Documentation is incomplete

**Solution:** Agent marks fields as "Unknown" and flags for manual testing

---

## Future Enhancements

### Planned Features

1. **GraphQL API support** - Document queries, mutations, subscriptions
2. **SDK detection** - If official Python SDK exists, document SDK usage instead of raw HTTP
3. **Postman collection export** - Generate importable Postman collections
4. **OpenAPI spec generation** - Output OpenAPI 3.0 spec files
5. **Automated testing** - Generate basic pytest tests for endpoint validation

### Agent Evolution

As more APIs are researched:
- Build common pattern library
- Improve extraction accuracy
- Reduce research time (current: 120s → target: 60s)
- Auto-detect API similarities (e.g., "This is similar to Stripe API")

---

## Contributing

To improve First Agent:

1. **After research session:** Review output quality
2. **If gaps found:** Update `first_agent.json` system prompt with new instructions
3. **If new pattern discovered:** Add to common patterns library
4. **If error occurred:** Document in self-annealing section

**Improvement Cycle:**
```
Research → Review → Update Agent Definition → Test → Deploy
```

This ensures First Agent gets better with each use (self-annealing principle).

---

**Last Updated:** 2025-12-25
**Maintainer:** Main Orchestrator Agent
**Review Schedule:** Quarterly or when API integrations fail