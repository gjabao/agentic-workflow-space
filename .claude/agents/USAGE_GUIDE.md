# Documentation Agent - Usage Guide

## Quick Start

The Documentation Agent is your **institutional knowledge guardian**. It automatically updates directives when you fix errors or improve performance.

---

## How Main Agent Should Use It

### Trigger Pattern (Final Step in Every Workflow)

After any significant workflow completion, Main Agent should:

```python
# 1. User requests task
# 2. Main Agent reads directive
# 3. Main Agent executes workflow
# 4. Workflow completes successfully OR error is fixed
# 5. Main Agent identifies if there's a learning to capture

# If there IS a learning:
Task(
    subagent_type='general-purpose',
    description="Update directive with learning",
    prompt=f"""
    You are Documentation Agent. Update directives/{directive_name}.md with this learning.

    {DOCUMENTATION_AGENT_SYSTEM_PROMPT}

    Context:
    {{
      "directive": "{directive_name}.md",
      "trigger": "{trigger_type}",
      "context": {{
        "error_message": "{error_msg}",  # if error fix
        "solution_applied": "{solution}",
        "script_modified": "{script_path}",
        "performance_before": "{before_metric}",
        "performance_after": "{after_metric}",
        "impact": "{impact_description}"
      }},
      "learning_title": "{short_title}"
    }}

    Task: Append this learning to the "Learnings & Optimizations" section.
    Preserve all existing directive structure.
    """,
    model='haiku'  # Fast for simple edits
)
```

---

## Example Scenarios

### Scenario 1: Error Fixed During Workflow

**Situation:** User asks to scrape 100 leads. Azure OpenAI throws content filter error. You fix it by sanitizing input. Workflow completes successfully.

**Main Agent Action:**

```python
# After workflow completes successfully with fix:
Task(
    subagent_type='general-purpose',
    description="Document error fix",
    prompt="""
    You are Documentation Agent. Update directives/scrape_leads.md.

    {DOCUMENTATION_AGENT_SYSTEM_PROMPT}

    Context:
    {
      "directive": "scrape_leads.md",
      "trigger": "error_fixed",
      "context": {
        "error_message": "Azure OpenAI 400: Content filter triggered - jailbreak attempt detected",
        "solution_applied": "Added sanitize_input() function in generate_icebreaker() to remove special characters before API call",
        "script_modified": "execution/scrape_apify_leads.py",
        "impact": "0% lead loss (was 6% before)"
      },
      "learning_title": "Content Filter Protection"
    }

    Task: Append this learning to "Learnings & Optimizations" section.
    """,
    model='haiku'
)
```

**Documentation Agent Output:**

Appends to [directives/scrape_leads.md](directives/scrape_leads.md):

```markdown
### 2025-12-25: Version 2.5 - Content Filter Protection
- **Problem:** Azure OpenAI returned 400 errors when company descriptions contained special characters (6% of leads lost)
- **Solution:** Added `sanitize_input()` function in `execution/scrape_apify_leads.py:145` to strip special chars before API call
- **Impact:** 0% lead loss (was 6% before)
- **Result:** Robust handling of any company description text
```

---

### Scenario 2: Performance Optimization

**Situation:** You modify `scrape_apify_leads.py` to use adaptive polling instead of fixed intervals. Performance improves 30-40%.

**Main Agent Action:**

```python
Task(
    subagent_type='general-purpose',
    description="Document performance optimization",
    prompt="""
    You are Documentation Agent. Update directives/scrape_leads.md.

    {DOCUMENTATION_AGENT_SYSTEM_PROMPT}

    Context:
    {
      "directive": "scrape_leads.md",
      "trigger": "script_modified",
      "context": {
        "solution_applied": "Changed email verification polling from fixed 5s intervals to adaptive 2s→3s intervals",
        "script_modified": "execution/scrape_apify_leads.py",
        "performance_before": "155s for 100 leads",
        "performance_after": "90-120s for 100 leads",
        "impact": "30-40% faster verification phase"
      },
      "learning_title": "Adaptive Polling for Email Verification"
    }

    Task: Append learning + update Performance Targets table.
    """,
    model='haiku'
)
```

**Documentation Agent Output:**

1. Appends to "Learnings & Optimizations"
2. Updates "Performance Targets" table
3. Updates "API Integration Details" if relevant

---

### Scenario 3: New Edge Case Discovered

**Situation:** User runs workflow, discovers Apify requires lowercase location input. You fix it by adding auto-normalization.

**Main Agent Action:**

```python
Task(
    subagent_type='general-purpose',
    description="Document edge case fix",
    prompt="""
    You are Documentation Agent. Update directives/scrape_leads.md.

    {DOCUMENTATION_AGENT_SYSTEM_PROMPT}

    Context:
    {
      "directive": "scrape_leads.md",
      "trigger": "error_fixed",
      "context": {
        "error_message": "Apify 400: Invalid location parameter 'United States'",
        "solution_applied": "Added auto-normalization: location.lower() before API call",
        "script_modified": "execution/scrape_apify_leads.py",
        "impact": "100% success rate for location inputs"
      },
      "learning_title": "Location Input Auto-Normalization"
    }

    Task: Append learning + add to Edge Cases section.
    """,
    model='haiku'
)
```

**Documentation Agent Output:**

1. Appends to "Learnings & Optimizations"
2. Adds entry to "Edge Cases & Constraints"

---

## When NOT to Call Documentation Agent

### Don't Call If:

1. **No behavioral change:**
   - Renamed variables
   - Added comments
   - Formatted code
   - Refactored without performance/accuracy impact

2. **Unconfirmed fix:**
   - Error might recur
   - Need to validate fix works long-term

3. **User-specific execution:**
   - Ran workflow with default parameters
   - Got expected results
   - No new learnings

4. **Research-only tasks:**
   - User asked "how does this work?"
   - You explained code
   - No execution occurred

---

## Quality Standards

### Good Learning Entry ✅

```markdown
### 2025-12-25: Version 2.3 - Speed Optimization
- **Problem:** Fixed 5s polling intervals caused slow verification for jobs that complete quickly
- **Solution:** Implemented adaptive polling in `execution/scrape_apify_leads.py:validate_emails()` - starts at 2s, scales to 3s
- **Impact:** 30-40% faster verification phase (155s → 90-120s for 100 leads)
- **Result:** Optimized polling strategy checks more frequently early when jobs complete fast
```

**Why it's good:**
- ✅ Specific problem stated
- ✅ Exact solution with file/function reference
- ✅ Measurable impact with numbers
- ✅ Clear result/outcome

### Bad Learning Entry ❌

```markdown
### 2025-12-25: Made it faster
- Changed some code to be faster
```

**Why it's bad:**
- ❌ Vague problem
- ❌ No solution details
- ❌ No measurable impact
- ❌ Can't reproduce fix

---

## Agent Permissions (Read-Only Verification)

Documentation Agent has **surgical write access**:

### ✅ Allowed:
- Read: `directives/*.md`, `execution/*.py`, `.tmp/`, `CLAUDE.md`
- Edit: `directives/*.md` ONLY
- Tools: Read, Edit, Glob

### ❌ Forbidden:
- Write to: `.env`, `credentials.json`, `execution/*.py`, `CLAUDE.md`
- Tools: Bash, WebFetch, WebSearch, Task, Skill
- Network access: All forbidden

**Why:** Documentation Agent should ONLY update directives based on evidence from Main Agent. It cannot execute code, fetch data, or modify production scripts.

---

## Testing Documentation Agent

### Manual Test

1. **Create test learning context:**
   ```json
   {
     "directive": "scrape_leads.md",
     "trigger": "error_fixed",
     "context": {
       "error_message": "Test error: Rate limit exceeded",
       "solution_applied": "Added exponential backoff with 3 retries",
       "script_modified": "execution/test_script.py",
       "impact": "0% failures (was 12%)"
     },
     "learning_title": "Test Learning Entry"
   }
   ```

2. **Invoke Documentation Agent:**
   ```python
   Task(
       subagent_type='general-purpose',
       description="Test directive update",
       prompt=f"""
       You are Documentation Agent.
       {DOCUMENTATION_AGENT_SYSTEM_PROMPT}
       Context: {test_context}
       Task: Append learning to directive.
       """,
       model='haiku'
   )
   ```

3. **Verify output:**
   - Read updated directive
   - Check "Learnings & Optimizations" section
   - Verify DOE structure preserved
   - Confirm version incremented

---

## Integration with Self-Annealing Loop

```
┌─────────────────────────────────────────┐
│ 1. DETECT: Error occurs during workflow │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. ANALYZE: Main Agent identifies cause │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. FIX: Main Agent modifies script      │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 4. TEST: Workflow completes successfully│
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 5. DOCUMENT: Call Documentation Agent   │  ← Documentation Agent operates here
│    - Captures error + fix in directive  │
│    - Updates Performance Targets        │
│    - Adds to Edge Cases if needed       │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 6. RESULT: System is STRONGER           │
│    - Same error won't occur again       │
│    - Future users benefit from learning │
│    - Directive is source of truth       │
└─────────────────────────────────────────┘
```

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Execution Time | < 30s | Simple append operation |
| Token Usage | < 20,000 | Directive can be lengthy |
| Accuracy | 100% | Must preserve structure |
| Updates per Session | 0-3 | Only when meaningful learnings occur |

---

## Troubleshooting

### Issue: Documentation Agent modified wrong section

**Cause:** Unclear directive structure
**Fix:** Update agent system prompt with section identification rules

### Issue: Learning entry is vague

**Cause:** Main Agent provided insufficient context
**Fix:** Main Agent should include specific metrics, file paths, error messages

### Issue: DOE structure was altered

**Cause:** Agent misunderstood preservation rules
**Fix:** Review system prompt, add explicit preservation checklist

### Issue: Same learning documented twice

**Cause:** Main Agent called Documentation Agent twice for same fix
**Fix:** Main Agent should check "Learnings & Optimizations" section before calling

---

## Best Practices for Main Agent

### ✅ DO:

1. **Call as final step** in workflow (after success confirmation)
2. **Provide specific context** (error messages, metrics, file paths)
3. **Include measurable impact** (percentages, time savings, accuracy improvements)
4. **Reference code locations** (file:line_number)
5. **Use semantic versioning** (patch for fixes, minor for features)

### ❌ DON'T:

1. **Call during active execution** (wait for completion)
2. **Document unconfirmed fixes** (validate fix works first)
3. **Provide vague context** ("made it better")
4. **Document routine executions** (no new learnings)
5. **Call for minor refactors** (no behavioral change)

---

## Example: Complete Workflow with Documentation Agent

**User Request:** "Scrape 100 leads"

**Main Agent Execution:**

```python
# 1. Read directive
directive = Read('directives/scrape_leads.md')

# 2. Execute workflow
result = Bash('python3 execution/scrape_apify_leads.py --fetch_count 100 --skip_test --valid_only')

# 3. Error occurs: Azure OpenAI content filter triggered
# Main Agent analyzes error, identifies solution

# 4. Fix applied: Add input sanitization
Edit(
    file_path='execution/scrape_apify_leads.py',
    old_string='icebreaker = openai_call(prompt)',
    new_string='icebreaker = openai_call(sanitize_input(prompt))'
)

# 5. Re-run workflow
result = Bash('python3 execution/scrape_apify_leads.py --fetch_count 100 --skip_test --valid_only')
# Success! 0% lead loss (was 6%)

# 6. CALL DOCUMENTATION AGENT (FINAL STEP)
Task(
    subagent_type='general-purpose',
    description="Document content filter fix",
    prompt=f"""
    You are Documentation Agent. Update directives/scrape_leads.md.

    {DOCUMENTATION_AGENT_SYSTEM_PROMPT}

    Context:
    {{
      "directive": "scrape_leads.md",
      "trigger": "error_fixed",
      "context": {{
        "error_message": "Azure OpenAI 400: Content filter triggered",
        "solution_applied": "Added sanitize_input() to remove special chars in generate_icebreaker()",
        "script_modified": "execution/scrape_apify_leads.py",
        "impact": "0% lead loss (was 6%)"
      }},
      "learning_title": "Content Filter Protection"
    }}
    """,
    model='haiku'
)

# 7. Report to user
print("✓ Workflow complete! Fixed content filter issue. Directive updated with learning.")
```

**Result:**
- User got 100 leads successfully
- Error was fixed permanently
- Directive now documents the fix
- Future executions won't fail the same way

---

## Summary

**Purpose:** Capture learnings from execution layer → Update directives → Build institutional knowledge

**When to use:** After successful workflow with new optimization, error fix, or edge case discovery

**How to use:** Call as final step with structured learning context

**Value:** System self-anneals—every error makes it smarter, preventing same mistake twice

**Key principle:** Directives = living documentation that evolves based on real-world execution

---

**Last Updated:** 2025-12-25
**Version:** 1.0.0
