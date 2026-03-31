---
name: pipeline
description: >
  Run a sequential chain of specialist agents where each agent completes one job then passes
  its output to the next agent. Each agent is spawned fresh with zero memory of previous agents —
  it only receives the OUTPUT of the previous step, not the full history. This prevents context
  pollution and conflict of interest between roles. Triggers on "pipeline", "handoff",
  "sequential agents", "chain agents", "build then review", "write then QA", "create then check",
  "run a pipeline on", "fresh eyes review", "stage 1 build stage 2 check", "create then audit",
  "proofread", "QA", "fact-check", "stress-test", "audit" something just produced.
  Do NOT trigger for tasks one agent can do in one pass, parallel research (use fan-out/fan-in),
  or brainstorming (use stochastic consensus).
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Agent
---

# Pipeline: Sequential Agent Handoff

Spawn specialist agents in a strict sequence. Each agent completes one job, then its raw output
(and ONLY its raw output) is handed to the next agent. No shared history. No reasoning leakage.
Each agent gets a clean context window with a single role.

**Why this works:** A builder who also reviews their own work is biased toward their own choices.
A QA agent who sees the builder's reasoning will unconsciously rubber-stamp it. Context isolation
forces each stage to evaluate the work on its own merits.

**This is DIFFERENT from:**
- Fan-out/fan-in (parallel agents) — use stochastic consensus instead
- Model-chat (agents debate each other) — use model-chat instead
- Single-agent tasks — just do them directly

## Execution

### 1. Parse the Request

Extract from the user's message:
- **Subject/deliverable** being processed (email HTML, code, copy, workflow, etc.)
- **Number of pipeline stages** — default: 2 (Builder + QA)
- **Stage names and roles** — if not provided, auto-generate based on the task
- **Input material** — existing content to pass through the pipeline, if any
- **Output format** for the final stage

### 2. Auto-Generate Pipeline Stages (if not specified)

**Default 2-stage pipeline:**
- Stage 1: Builder — creates or drafts the deliverable
- Stage 2: QA — reviews with zero knowledge of how it was built

**Common 3-stage pipelines to suggest when relevant:**
- Write -> Edit -> Fact-check (content/copy)
- Build -> QA -> Security audit (code/automation)
- Draft -> Compliance check -> Final polish (BCS emails / Health Canada rules)
- Research -> Synthesize -> Validate (reports)

**Rules for EVERY stage:**
- Each agent receives ONLY the output of the previous stage
- Each agent does NOT receive conversation history or previous agents' reasoning
- Each agent's prompt describes ONLY their role — not what came before

### 3. Context Isolation (CRITICAL)

This is the most important rule of a pipeline. When passing work from Stage N to Stage N+1:

**DO NOT INCLUDE:**
- Why the previous agent made its choices
- The reasoning or chain-of-thought from previous stages
- Any meta-commentary about what previous agents were trying to do
- The user's original prompt (unless it's the input material itself)

**ONLY INCLUDE:**
- The raw output from the previous stage
- The current stage's role instructions

This prevents the QA agent from being biased toward the builder's intent.

### 4. Stage Execution

For each stage, use the Agent tool to spawn a fresh subagent:

a) Announce: `--- Stage [N]: [Role Name] ---`
b) Show the brief role description being given to that stage's agent
c) Spawn the agent with this prompt structure:

```
[ROLE SYSTEM PROMPT — describes ONLY this agent's job, nothing about previous stages]

Here is the [deliverable/content/code] to work with:

---
[RAW OUTPUT FROM PREVIOUS STAGE — no commentary, no reasoning, just the artifact]
---

[SPECIFIC INSTRUCTIONS for this stage's task]
```

d) Show output clearly labeled
e) Announce: `--- Handoff to Stage [N+1] ---`
f) Pass ONLY the output (strip any reasoning preamble) to the next stage

**Model selection per stage:**
- Builder/Writer/Drafter/Polish/Editor stages: use `model: "sonnet"` (fast, creative)
- QA/Review/Audit/Compliance stages: use `model: "opus"` (thorough, catches more issues)

### 5. Final Output

After all stages complete:

```
--- Pipeline Complete ---

## Pipeline Summary
- Stage 1 ([Role]): [one-line summary of what was produced/done]
- Stage 2 ([Role]): [one-line summary of findings/changes]
- Stage 3 ([Role]): [one-line summary of final result]

## Critical Issues Found
[If QA/review stages found critical issues, list them here so the user can
decide whether to accept or request revision]

## Final Output
[The complete, ready-to-use deliverable from the last stage]
```

Save the full pipeline transcript to `active/drafts/YYYY-MM-DD-pipeline-[topic-slug].md`.

## Pipeline Templates

Ready-to-use templates for common tasks are in [references/pipeline-templates.md](references/pipeline-templates.md).

Reference a template by name:
- "BCS Klaviyo email pipeline" -> 3-stage email build + QA + polish
- "Cold email pipeline" -> 3-stage write + spam check + rewrite
- "SEO blog pipeline" -> 3-stage write + compliance review + edit
- "Automation QA pipeline" -> 2-stage build + security audit
- "Write + review pipeline" -> 2-stage generic build + fresh review

## Standalone Script

For running pipelines outside Claude Code via the Anthropic API:

```bash
cd .claude/skills/pipeline/scripts/
python pipeline_runner.py \
  --config pipeline_config.json \
  --output-file active/drafts/pipeline-output.md
```

See [scripts/pipeline_runner.py](scripts/pipeline_runner.py) for details.

## Configuration Defaults

| Parameter | Default | Override |
|-----------|---------|---------|
| Stages | 2 (Builder + QA) | "3 stages", "add a polish stage" |
| Builder model | Sonnet | "use opus for building" |
| QA model | Opus | — |
| Output location | active/drafts/ | "save to active/exports/" |

## Edge Cases

- **User provides existing content**: Skip the Builder stage, start with QA. The existing content IS Stage 1's output.
- **QA finds zero issues**: Report "QA passed with no issues" — skip the polish stage if one exists.
- **QA finds critical issues that need user decision**: Flag them BEFORE applying the polish stage. Ask whether to proceed or revise.
- **Single stage requested**: Just run it directly — no pipeline needed. Tell the user.
- **More than 5 stages**: Warn that more stages = more token cost and latency. Suggest consolidating.
