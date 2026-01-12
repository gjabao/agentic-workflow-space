# Documentation Agent - Quick Start Guide

## TL;DR

**Documentation Agent** updates your directives automatically after successful workflows, capturing learnings from errors fixed and optimizations made.

**When to use:** Call as FINAL STEP after workflows where you fixed an error or improved performance.

---

## 30-Second Setup

### 1. Agent is Ready

The agent is already configured in [documentation_agent.json](.claude/agents/documentation_agent.json).

### 2. How to Trigger (Main Orchestrator)

After any successful workflow with a learning:

```python
Task(
    subagent_type='general-purpose',
    description="Update directive with learning",
    prompt=f"""
    You are Documentation Agent.

    {READ_FILE('.claude/agents/documentation_agent.json')['system_prompt']}

    Update directives/{directive_name}.md with this learning:

    {{
      "directive": "{directive_name}.md",
      "trigger": "error_fixed",  # or "script_modified" or "successful_workflow"
      "context": {{
        "error_message": "{the_error}",
        "solution_applied": "{what_you_changed}",
        "script_modified": "{script_path}",
        "impact": "{measurable_improvement}"
      }},
      "learning_title": "{short_title}"
    }}
    """,
    model='haiku'  # Fast for simple edits
)
```

### 3. Verify Update

Check [directives/{directive_name}.md](directives/) - new entry in "Learnings & Optimizations" section.

---

## Real Example

### User Request
"Scrape 100 leads"

### What Happens

1. **Workflow executes**
2. **Error occurs:** Azure OpenAI content filter triggered
3. **You fix it:** Add input sanitization
4. **Workflow completes successfully**
5. **Call Documentation Agent:**

```python
Task(
    subagent_type='general-purpose',
    description="Document content filter fix",
    prompt="""
    You are Documentation Agent. Update directives/scrape_leads.md.

    Context:
    {
      "directive": "scrape_leads.md",
      "trigger": "error_fixed",
      "context": {
        "error_message": "Azure OpenAI 400: Content filter triggered",
        "solution_applied": "Added sanitize_input() in generate_icebreaker()",
        "script_modified": "execution/scrape_apify_leads.py",
        "impact": "0% lead loss (was 6%)"
      },
      "learning_title": "Content Filter Protection"
    }
    """,
    model='haiku'
)
```

6. **Result:** Directive updated with learning. Same error won't happen again.

---

## What Gets Updated

### Automatically Updated Sections

✓ **Learnings & Optimizations** (always)
✓ **Performance Targets** (if metrics improved)
✓ **Edge Cases** (if new edge case discovered)
✓ **Error Recovery** (if new error type handled)
✓ **Best Practices** (if new recommendation)

### Never Modified Sections

✗ Goal/Objective
✗ Required Inputs
✗ Execution Tools
✗ Expected Outputs
✗ Process Flow

---

## Learning Entry Format

Good entry (evidence-based, specific):

```markdown
### 2025-12-25: Version 2.3 - Adaptive Polling
- **Problem:** Fixed 5s polling caused slow verification
- **Solution:** Implemented adaptive polling in execution/scrape_apify_leads.py:validate_emails()
- **Impact:** 30-40% faster (155s → 90-120s for 100 leads)
- **Result:** Checks more frequently early when jobs complete fast
```

Bad entry (vague, no evidence):

```markdown
### 2025-12-25: Made it faster
- Changed code to be faster
```

---

## When to Call Documentation Agent

### ✅ DO Call:

- Fixed an error during workflow (self-annealing)
- Improved performance measurably (>20%)
- Discovered new edge case or API behavior
- Modified execution script with significant change

### ❌ DON'T Call:

- Routine execution (no new learnings)
- Minor refactor (no behavioral change)
- Unconfirmed fix (error might recur)
- During active workflow (wait for completion)

---

## Folder Structure

```
.claude/agents/
├── documentation_agent.json    ← Agent definition
├── README.md                   ← Overview of all agents
├── USAGE_GUIDE.md             ← Detailed usage examples
├── ARCHITECTURE.md            ← System architecture
└── QUICK_START.md             ← This file

directives/                     ← Updated by Documentation Agent
├── scrape_leads.md
├── generate_custom_copy.md
└── ...
```

---

## Permissions

**Documentation Agent can:**
- ✅ Read: directives/*.md, execution/*.py, .tmp/
- ✅ Edit: directives/*.md ONLY

**Documentation Agent cannot:**
- ❌ Modify execution scripts
- ❌ Access secrets (.env, credentials.json)
- ❌ Use Bash, WebFetch, WebSearch
- ❌ Execute code

**Why:** Surgical write access prevents accidental damage.

---

## Verification

After calling Documentation Agent, verify:

1. **Learning entry added** to "Learnings & Optimizations"
2. **Version incremented** (e.g., 2.2 → 2.3)
3. **DOE structure preserved** (all sections intact)
4. **Related sections updated** (if applicable)

```bash
# Quick check:
git diff directives/scrape_leads.md
```

---

## Troubleshooting

### Issue: No update visible

**Check:**
- Did agent receive correct directive name?
- Was learning context provided with all fields?
- Check agent execution logs for errors

**Fix:**
- Verify directive filename matches exactly
- Provide complete learning context (error, solution, impact)

### Issue: Wrong section updated

**Check:**
- Review agent system prompt
- Verify learning entry format

**Fix:**
- Update agent definition with clearer section identification rules

### Issue: DOE structure damaged

**Check:**
- Review agent Edit tool calls
- Check if multiple edits conflicted

**Fix:**
- Restore from git
- Update agent with stricter preservation rules

---

## Integration with Workflows

### Pattern 1: Error Fix

```python
# Workflow
result = execute_workflow()

# Error occurs
if error:
    fix_error()
    result = execute_workflow()  # Success

    # CALL DOCUMENTATION AGENT
    document_learning(
        directive="scrape_leads.md",
        trigger="error_fixed",
        error=error_message,
        solution=fix_applied
    )
```

### Pattern 2: Performance Optimization

```python
# Measure before
start = time.time()
result = execute_workflow()
before_time = time.time() - start

# Apply optimization
optimize_script()

# Measure after
start = time.time()
result = execute_workflow()
after_time = time.time() - start

# CALL DOCUMENTATION AGENT
document_learning(
    directive="scrape_leads.md",
    trigger="script_modified",
    performance_before=f"{before_time}s",
    performance_after=f"{after_time}s",
    impact=f"{(before_time-after_time)/before_time*100:.0f}% faster"
)
```

---

## Self-Annealing Loop

```
Error → Analyze → Fix → Test → Document → Stronger System
                                    ↑
                        Documentation Agent
```

Every error fixed makes the system smarter. Directives evolve based on real-world execution.

---

## Next Steps

1. **Read:** [ARCHITECTURE.md](ARCHITECTURE.md) - Understand 4-layer system
2. **Read:** [USAGE_GUIDE.md](USAGE_GUIDE.md) - See detailed examples
3. **Test:** Run a workflow, fix an error, call Documentation Agent
4. **Verify:** Check directive was updated correctly
5. **Iterate:** Build institutional knowledge over time

---

## Support

**Questions?**
- Check [USAGE_GUIDE.md](USAGE_GUIDE.md) for examples
- Review [documentation_agent.json](documentation_agent.json) for system prompt
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for context

**Found a bug?**
- Update agent definition with fix
- Document in agent meta.changelog

---

**Remember:** Documentation Agent is your knowledge guardian. Call it after every meaningful learning. Your directives will become smarter over time.

🚀 **Ready to use!**
