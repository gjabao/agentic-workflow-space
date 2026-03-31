# Security Audit Report — Agentic Workflow Space

**Date:** 2026-03-30
**Auditor:** Claude (Automated Security Audit)
**Codebase:** Lead generation & outreach automation platform (DOE Architecture)
**Framework:** Python scripts + Flask webhook server + Modal serverless
**Architecture:** No database — CSV/Google Sheets data layer, .env for secrets, Flask webhook server as primary attack surface

---

## 1. Security Posture Rating

### :orange_circle: NEEDS WORK — Significant gaps that would be exploitable

This codebase is a collection of Python automation scripts with a Flask webhook server as the only network-exposed component. The **critical issues** are: (1) Flask debug mode enabled on `0.0.0.0` which enables remote code execution via Werkzeug debugger, (2) webhook authentication that silently degrades to "allow all" when the secret is unset, (3) `eval` in a shell script that processes secret values, and (4) `.env.clickup` was committed to git history (low-risk contents, but sets a bad precedent). The main `.env` file with 19+ API keys is correctly `.gitignore`d and was never committed. The codebase has no SQL database, no user-facing frontend, and no file upload handling — which eliminates entire classes of vulnerabilities. The primary attack surface is the webhook server.

---

## 2. Critical and High Findings

### FINDING #1

| Field | Value |
|-------|-------|
| **Severity** | **CRITICAL** |
| **Category** | Remote Code Execution via Debug Mode |
| **Location** | [webhook_server.py:225](execution/webhook_server.py#L225) |
| **CWE** | CWE-489 (Active Debug Code) |

**What's wrong:**
Flask is running with `debug=True` and bound to `0.0.0.0` (all interfaces). The Werkzeug debugger allows **arbitrary Python code execution** from any machine that can reach port 5000.

**Why it matters:**
Anyone on the same network (or the internet if port-forwarded) can trigger an error, access the Werkzeug interactive debugger console, and execute arbitrary code on your machine — full RCE with your user privileges. They can read `.env`, steal all API keys, execute system commands, etc.

**The vulnerable code:**
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

**The fix:**
```python
if __name__ == '__main__':
    # Development: bind to localhost only
    app.run(host='127.0.0.1', port=5000, debug=False)

    # Production: use gunicorn
    # gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
```

**Effort:** ~2 minutes

---

### FINDING #2

| Field | Value |
|-------|-------|
| **Severity** | **HIGH** |
| **Category** | Authentication Bypass — Optional Webhook Secret |
| **Location** | [webhook_server.py:16](execution/webhook_server.py#L16), [webhook_server.py:35](execution/webhook_server.py#L35), [webhook_server.py:134](execution/webhook_server.py#L134) |
| **CWE** | CWE-306 (Missing Authentication for Critical Function) |

**What's wrong:**
Webhook secret defaults to empty string. The auth check `if WEBHOOK_SECRET and ...` silently passes all requests when the env var is unset. Two endpoints (`/webhook/instantly/email-sent`, `/webhook/instantly/campaign-completed`) have **zero** authentication at all.

**Why it matters:**
An attacker who discovers the webhook URL can trigger Apify scraping (paid API — costs money), trigger email campaign analysis, and inject arbitrary data into your workflow pipeline. The webhook URL is hardcoded in `trigger_webhook.py:10`.

**The vulnerable code:**
```python
WEBHOOK_SECRET = os.getenv("INSTANTLY_WEBHOOK_SECRET", "")
# ...
if WEBHOOK_SECRET and webhook_secret != WEBHOOK_SECRET:
    return jsonify({"error": "Unauthorized"}), 401
```

**The fix:**
```python
WEBHOOK_SECRET = os.getenv("INSTANTLY_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("INSTANTLY_WEBHOOK_SECRET must be set")

# Apply to EVERY endpoint:
def verify_webhook():
    webhook_secret = request.headers.get('X-Webhook-Secret') or request.headers.get('X-Instantly-Secret')
    if webhook_secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    return None

# At top of each handler:
auth_error = verify_webhook()
if auth_error:
    return auth_error
```

**Effort:** ~15 minutes

---

### FINDING #3

| Field | Value |
|-------|-------|
| **Severity** | **HIGH** |
| **Category** | Command Injection via `eval` |
| **Location** | [setup_modal_webhook.sh:101](scripts/setup_modal_webhook.sh#L101) |
| **CWE** | CWE-78 (OS Command Injection) |

**What's wrong:**
Environment variable values are concatenated into a string and passed to `eval`. If any API key contains shell metacharacters (spaces, semicolons, backticks, `$(...)`, etc.), arbitrary commands execute.

**Why it matters:**
A malicious or malformed value in `.env` (e.g., `APIFY_API_KEY="x; rm -rf /"`) would execute as a shell command when this script runs.

**The vulnerable code:**
```bash
SECRET_CMD="modal secret create anti-gravity-secrets"
[ ! -z "$APIFY_API_KEY" ] && SECRET_CMD="$SECRET_CMD APIFY_API_KEY=$APIFY_API_KEY"
# ...
eval $SECRET_CMD
```

**The fix:**
```bash
# Use array instead of eval
SECRET_ARGS=()
[ -n "$APIFY_API_KEY" ] && SECRET_ARGS+=("APIFY_API_KEY=$APIFY_API_KEY")
[ -n "$SSMASTERS_API_KEY" ] && SECRET_ARGS+=("SSMASTERS_API_KEY=$SSMASTERS_API_KEY")
[ -n "$AZURE_OPENAI_ENDPOINT" ] && SECRET_ARGS+=("AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT")
[ -n "$AZURE_OPENAI_API_KEY" ] && SECRET_ARGS+=("AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY")
[ -n "$AZURE_OPENAI_DEPLOYMENT" ] && SECRET_ARGS+=("AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT")

modal secret create anti-gravity-secrets "${SECRET_ARGS[@]}"
```

**Effort:** ~5 minutes

---

### FINDING #4

| Field | Value |
|-------|-------|
| **Severity** | **HIGH** |
| **Category** | Error Message Information Disclosure |
| **Location** | [webhook_server.py:63](execution/webhook_server.py#L63), [webhook_server.py:85](execution/webhook_server.py#L85), [webhook_server.py:110](execution/webhook_server.py#L110), [webhook_server.py:214](execution/webhook_server.py#L214) |
| **CWE** | CWE-209 (Error Message Information Exposure) |

**What's wrong:**
Every exception handler returns `str(e)` directly to the HTTP client. Combined with debug=True, this exposes internal paths, stack traces, module names, and potentially environment variable names.

**Why it matters:**
Attackers use error messages to map internal structure, find file paths, identify installed packages, and craft targeted exploits.

**The vulnerable code:**
```python
except Exception as e:
    return jsonify({"error": str(e)}), 500
```

**The fix:**
```python
except Exception as e:
    import logging
    logging.exception("Webhook processing error")
    return jsonify({"error": "Internal server error"}), 500
```

**Effort:** ~5 minutes

---

### FINDING #5

| Field | Value |
|-------|-------|
| **Severity** | **HIGH** |
| **Category** | Argument Injection via Webhook Payload |
| **Location** | [webhook_server.py:159-201](execution/webhook_server.py#L159-L201) |
| **CWE** | CWE-88 (Improper Neutralization of Argument Delimiters) |

**What's wrong:**
User-controlled JSON values from webhook payloads are passed directly as subprocess arguments without validation. While `subprocess.Popen` with a list prevents shell injection, an attacker can inject flag-like arguments (e.g., `"--some-dangerous-flag"` as an industry name) that the downstream script's argparse might interpret.

**Why it matters:**
An attacker sending `{"industry": "--help"}` crashes the subprocess. Sending `{"sender_context": "--skip_test"}` or similar could manipulate the downstream script's behavior. The `fetch_count` field accepts any value from the request without bounds checking — an attacker could set it to 10000, triggering massive paid API usage.

**The vulnerable code:**
```python
industry = data.get('industry')
fetch_count = data.get('fetch_count', 30)
# No validation on type, length, or value
cmd = ['python3', 'execution/scrape_apify_leads.py', '--industry', industry, '--fetch_count', str(fetch_count)]
```

**The fix:**
```python
import re

# Validate industry
industry = data.get('industry', '')
if not isinstance(industry, str) or not re.match(r'^[a-zA-Z0-9\s&\-]{1,100}$', industry):
    return jsonify({"error": "Invalid industry format"}), 400

# Validate and cap fetch_count
try:
    fetch_count = int(data.get('fetch_count', 30))
    fetch_count = max(1, min(fetch_count, 50))  # Cap at 50
except (ValueError, TypeError):
    fetch_count = 30

# Validate all string parameters similarly before passing to subprocess
```

**Effort:** ~20 minutes

---

### FINDING #6

| Field | Value |
|-------|-------|
| **Severity** | **HIGH** |
| **Category** | Secret Exposure in Git History |
| **Location** | Git commit `fca8ce6` — `.env.clickup` |
| **CWE** | CWE-540 (Inclusion of Sensitive Information in Source Code) |

**What's wrong:**
`.env.clickup` was committed to git history in commit `fca8ce6`. While its current contents only contain a ClickUp list ID (low sensitivity), the `.gitignore` rule `.env.*` should have prevented this. The file being committed means either the `.gitignore` was added after, or `git add -f` was used.

**Why it matters:**
This sets a precedent for `.env.*` files being committed. The ClickUp workspace ID (`9018921308`) and space ID are exposed. More critically, this suggests the backup scripts may be force-adding files.

**The vulnerable code:**
```
# In git history:
CLICKUP_DEFAULT_LIST_ID=901807718471
```

**The fix:**
```bash
# Remove from git history (if repo is not shared widely):
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env.clickup' -- --all
# OR for newer git:
git filter-repo --path .env.clickup --invert-paths
```

**Effort:** ~10 minutes

---

## 3. Quick Wins (Under 10 Minutes Each)

| # | Fix | File | Time |
|---|-----|------|------|
| 1 | Change `debug=True` to `debug=False` and `0.0.0.0` to `127.0.0.1` | webhook_server.py:225 | 2 min |
| 2 | Replace `return jsonify({"error": str(e)})` with generic error in all 4 handlers | webhook_server.py | 5 min |
| 3 | Replace `eval $SECRET_CMD` with array-based command | setup_modal_webhook.sh:101 | 5 min |
| 4 | Add `fetch_count` bounds validation (cap at 50) | webhook_server.py:142 | 3 min |
| 5 | Add startup validation: `assert WEBHOOK_SECRET, "Set INSTANTLY_WEBHOOK_SECRET"` | webhook_server.py:16 | 2 min |
| 6 | Pin critical package versions in requirements.txt | requirements.txt | 5 min |

---

## 4. Prioritized Remediation Plan

| Priority | Finding | Severity | Effort |
|----------|---------|----------|--------|
| 1 | **#1** — Disable Flask debug mode | CRITICAL | 2 min |
| 2 | **#2** — Enforce webhook authentication on all endpoints | HIGH | 15 min |
| 3 | **#3** — Replace `eval` with array in shell script | HIGH | 5 min |
| 4 | **#4** — Sanitize error responses | HIGH | 5 min |
| 5 | **#5** — Add input validation + bounds checking for webhook params | HIGH | 20 min |
| 6 | **#6** — Remove `.env.clickup` from git history | HIGH | 10 min |
| 7 | **#7** — Add rate limiting to webhook server (Flask-Limiter) | MEDIUM | 30 min |
| 8 | **#8** — Add subprocess timeout to all Popen calls | MEDIUM | 10 min |
| 9 | **#9** — Move hardcoded webhook URL to env var | MEDIUM | 5 min |
| 10 | **#10** — Pin package versions in requirements.txt | LOW | 10 min |
| 11 | **#11** — Add Flask to requirements.txt | LOW | 2 min |

---

## 5. What's Already Done Right

| Area | Details |
|------|---------|
| **.gitignore is solid** | `.env`, `.env.*`, `credentials.json`, `token.json`, `*.pickle`, `*.key`, `*.pem` all covered. Main `.env` was never committed. |
| **No hardcoded secrets in source code** | All 83+ Python scripts use `os.getenv()` / `load_dotenv()` properly. Zero API keys found in `.py` files. |
| **Safe subprocess usage** | All `subprocess.Popen` calls use list-form (no `shell=True`). This prevents direct shell injection. |
| **.env.example uses placeholders** | Template file contains only `xxx` / `your_key_here` values — safe to commit. |
| **No SQL database** | Entire data layer is CSV + Google Sheets. Zero SQL injection surface. |
| **No user-facing frontend** | No XSS surface. No client-side JavaScript. No browser-based UI. |
| **No file upload handling** | All file operations are internal (CSV read/write). No user-uploaded file risk. |
| **Tenacity retry with backoff** | Rate limiting via `tenacity` library used across scraping scripts — prevents self-inflicted API abuse. |
| **Thread-safe locking** | Scripts use `Lock()` for thread-safe API rate limiting. |
| **Credential cleanup pattern** | Some scripts delete API key variables after use (`del api_key`). |

---

## 6. Checklist Summary

### Section 1: Environment Variables and Secret Management
| Item | Verdict | Notes |
|------|---------|-------|
| 1.1 | :white_check_mark: PASS | No hardcoded secrets in source code. All use `os.getenv()`. |
| 1.2 | :warning: PARTIAL | `.gitignore` covers `.env*` but `.env.clickup` was committed in `fca8ce6`. Main `.env` never committed. |
| 1.3 | :ballot_box_with_check: N/A | No frontend framework (no NEXT_PUBLIC_, VITE_, REACT_APP_ prefixes). |
| 1.4 | :x: FAIL | `webhook_server.py` prints lead emails and campaign IDs to stdout (Finding #4). |
| 1.5 | :ballot_box_with_check: N/A | No frontend build system. No source maps. |
| 1.6 | :x: FAIL | Webhook server starts with empty string default for secret — no fail-fast (Finding #2). |

### Section 2: Database Security
| Item | Verdict | Notes |
|------|---------|-------|
| 2.1–2.8 | :ballot_box_with_check: N/A | No SQL database. Data stored in CSV/Google Sheets. No RLS, no SQL queries. |

### Section 3: Authentication and Session Management
| Item | Verdict | Notes |
|------|---------|-------|
| 3.1 | :x: FAIL | No auth middleware. 2 of 4 webhook endpoints have zero authentication (Finding #2). |
| 3.2 | :x: FAIL | No default-deny. Endpoints are open by default (Finding #2). |
| 3.3 | :ballot_box_with_check: N/A | No Supabase. |
| 3.4 | :ballot_box_with_check: N/A | No OAuth callback handler for the webhook server. |
| 3.5 | :ballot_box_with_check: N/A | No sessions. Webhook server is stateless. |
| 3.6 | :x: FAIL | `/webhook/instantly/email-sent` and `/webhook/instantly/campaign-completed` skip auth entirely. |
| 3.7 | :white_check_mark: PASS | LinkedIn OAuth flow uses standard library patterns in `linkedin_auth.py`. |
| 3.8 | :ballot_box_with_check: N/A | No password reset flows. |

### Section 4: Server-Side Validation
| Item | Verdict | Notes |
|------|---------|-------|
| 4.1 | :x: FAIL | No schema validation on webhook payloads. Only checks if `industry` field exists (Finding #5). |
| 4.2 | :ballot_box_with_check: N/A | No user identity concept in this application. |
| 4.3 | :ballot_box_with_check: N/A | No HTML rendering. No frontend. |
| 4.4 | :white_check_mark: PASS | All state-changing webhook endpoints use POST. Health check is GET. |
| 4.5 | :x: FAIL | `str(e)` returned directly to client in all error handlers (Finding #4). |
| 4.6 | :warning: PARTIAL | 2 of 4 endpoints check `X-Webhook-Secret` / `X-Instantly-Secret`. 2 endpoints skip it entirely. |

### Section 5: Dependency and Package Security
| Item | Verdict | Notes |
|------|---------|-------|
| 5.1 | :warning: PARTIAL | Cannot run `pip audit` in this environment. Packages use `>=` constraints — latest versions pulled. |
| 5.2 | :white_check_mark: PASS | All packages are well-known (requests, pandas, anthropic, openai, flask, etc.). No hallucinated packages. |
| 5.3 | :x: FAIL | No lockfile (no `requirements.lock`, `Pipfile.lock`, or `poetry.lock`). |
| 5.4 | :warning: PARTIAL | Unpinned versions mean audit is not reproducible. |
| 5.5 | :warning: PARTIAL | Flask is used by webhook_server.py but not listed in requirements.txt. |

### Section 6: Rate Limiting
| Item | Verdict | Notes |
|------|---------|-------|
| 6.1 | :x: FAIL | Webhook endpoint triggers paid Apify API with no rate limiting. Attacker can run up costs. |
| 6.2 | :ballot_box_with_check: N/A | No login/signup/password endpoints. |
| 6.3 | :x: FAIL | No rate limiting exists on the webhook server at all. |

### Section 7: CORS Configuration
| Item | Verdict | Notes |
|------|---------|-------|
| 7.1 | :warning: PARTIAL | No CORS headers configured. Flask defaults to same-origin, which is safe. But if accessed cross-origin, no explicit policy exists. |
| 7.2 | :ballot_box_with_check: N/A | No CORS credentials mode configured. |

### Section 8: File Upload Security
| Item | Verdict | Notes |
|------|---------|-------|
| 8.1–8.3 | :ballot_box_with_check: N/A | No file upload handling in the codebase. |

### Compact Summary

```
1.1 ✅  1.2 ⚠️  1.3 ⬚  1.4 ❌  1.5 ⬚  1.6 ❌
2.1 ⬚  2.2 ⬚  2.3 ⬚  2.4 ⬚  2.5 ⬚  2.6 ⬚  2.7 ⬚  2.8 ⬚
3.1 ❌  3.2 ❌  3.3 ⬚  3.4 ⬚  3.5 ⬚  3.6 ❌  3.7 ✅  3.8 ⬚
4.1 ❌  4.2 ⬚  4.3 ⬚  4.4 ✅  4.5 ❌  4.6 ⚠️
5.1 ⚠️  5.2 ✅  5.3 ❌  5.4 ⚠️  5.5 ⚠️
6.1 ❌  6.2 ⬚  6.3 ❌
7.1 ⚠️  7.2 ⬚
8.1 ⬚  8.2 ⬚  8.3 ⬚
```

**Legend:** ✅ PASS | ❌ FAIL | ⚠️ PARTIAL | ⬚ N/A
