---
name: model-chat
description: >
  Spawn N Claude agents in a shared debate format where agents read and respond to each other's
  outputs across rounds. Unlike stochastic consensus (isolated agents), model-chat agents directly
  agree, disagree, build on, and challenge what others said — producing progressively refined,
  more nuanced outputs. Triggers on "model-chat", "debate", "agents discuss", "have agents argue",
  "stress-test this idea", "challenge this strategy", "which of these actually works",
  "agents debate", "debate: which is better", "second opinion from multiple angles".
  Do NOT trigger for simple brainstorming (use stochastic consensus), factual research
  (use fan-out/fan-in), or single-answer questions.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Agent
---

# Model-Chat: Multi-Agent Debate Skill

Spawn N agents in a structured debate where each agent sees ALL previous responses before
writing their next one. Weak ideas get challenged and dropped, strong ideas get reinforced,
and novel combinations emerge from disagreement.

**Key difference from stochastic consensus:** Agents here READ each other and RESPOND directly.
This is a conversation, not a poll.

## Execution

### 1. Parse the Request

Extract from the user's message:
- **Topic or question** being debated
- **Number of agents** — default 5, max 10
- **Number of rounds** — default 3
- **Agent personas** — if not specified, auto-generate (see step 2)
- **Output format** — if the user wants something specific beyond the default

If the topic is vague, ask the user to sharpen it. Debates on fuzzy prompts waste tokens.

### 2. Auto-Generate Personas (if not provided)

If the user doesn't specify personas, generate ones relevant to the topic domain.

**Rules:**
- Always include at least one **Contrarian** agent whose explicit job is to challenge every other agent's points
- Generate personas with distinct expertise, biases, and perspectives
- Each persona should have a clear reason to disagree with at least one other persona

**Use the persona library** at [references/persona-library.md](references/persona-library.md) for
ready-made sets. The user can reference these by name:
- "BCS persona set" → Beauty Connect Shop industry experts
- "Cold email persona set" → Email outreach specialists
- "Klaviyo persona set" → Email marketing experts
- "Business strategy persona set" → Strategic advisors
- "Automation persona set" → Tech/automation experts

**For topics outside these domains**, generate personas following this pattern:
- Domain expert with 10+ years experience
- Practitioner who does this daily
- Skeptic / end-user who has to live with the decision
- Data/analytics person who wants evidence
- Contrarian who challenges assumptions

### 3. Run the Debate Loop

Use the Agent tool to spawn agents. Each agent runs as a subagent with its persona as context.

#### Round 1: Independent Responses
Spawn all agents in parallel. Each responds to the original question without seeing others.

For each agent, use this system prompt structure:
```
You are [PERSONA NAME AND DESCRIPTION] participating in a structured debate.

Your job:
- Give your honest, expert opinion based on your persona
- This is Round 1: respond directly to the question
- Be direct. No fluff. Max 150 words.
- Take a clear position — do not hedge or try to cover all sides
```

#### Round 2+: Debate Responses
For each subsequent round, spawn all agents in parallel BUT include the full history
of all previous rounds in each agent's prompt.

System prompt for Round 2+:
```
You are [PERSONA NAME AND DESCRIPTION] participating in a structured debate.

Your job:
- You MUST reference at least one other participant BY NAME
- You MUST either agree with their reasoning OR explain specifically why you disagree
- You MUST add at least one new point not yet raised in the debate
- Be direct. No fluff. Max 150 words.
- You are allowed to completely change your position if someone made a compelling argument
```

The user message should contain:
```
DEBATE TOPIC: [topic]

PREVIOUS RESPONSES:
Round [N] — [Persona Name]:
[Their response]

[...all previous responses...]

Now give your Round [current] response:
```

#### Parallel Execution Within Rounds
- Within each round: spawn ALL agents in parallel (single message, multiple Agent tool calls)
- Between rounds: wait for all agents to complete before starting next round
- This is critical — agents in Round 2 MUST see ALL Round 1 responses

### 4. Synthesis

After the final round, produce a synthesis using your own (Opus-level) reasoning.
Analyze the full debate transcript and produce:

1. **CONSENSUS** — Points where 3+ agents agreed across rounds. These are strong findings.
2. **CONTESTED** — Points that remained unresolved or where agents stayed divided. Flag as "needs more data" or "genuine tradeoff."
3. **SURPRISE INSIGHT** — Any point that emerged ONLY from the debate interaction (wasn't in any Round 1 response). These are the unique value of debate over polling.
4. **FINAL RECOMMENDATION** — One clear recommendation with confidence level (High / Medium / Low).
5. **TOP 3 ACTIONABLE TAKEAWAYS** — In plain language, what should someone DO based on this debate?

### 5. Output Format

Structure the output exactly like this:

```
# Model-Chat Debate

**Topic:** [the question]
**Agents:** [list of personas]
**Rounds:** [number]

---

## Round 1

**[Persona Name]:**
[response]

**[Persona Name]:**
[response]

[...all agents...]

---

## Round 2

**[Persona Name]:**
[response — must reference other agents]

[...all agents...]

---

[...additional rounds...]

---

## Synthesis

### Consensus (3+ agents agreed)
- [point 1]
- [point 2]

### Contested (remained unresolved)
- [point 1]
- [point 2]

### Surprise Insight
- [insight that emerged from debate interaction]

### Final Recommendation
[One clear recommendation] — Confidence: [High/Medium/Low]

### Top 3 Actionable Takeaways
1. [action 1]
2. [action 2]
3. [action 3]
```

Save the full transcript to `active/research/YYYY-MM-DD-model-chat-[topic-slug].md`.

## Standalone Script

For running debates outside Claude Code, use the Python script at
[scripts/model_chat.py](scripts/model_chat.py).

```bash
cd .claude/skills/model-chat/scripts/
python model_chat.py \
  --topic "Should we add subscription boxes?" \
  --agents 5 \
  --rounds 3 \
  --personas "Senior Esthetician,Medical Spa Director,Skeptical Clinic Owner,Korean Skincare Formulator,Beauty Industry Contrarian" \
  --output-file active/research/debate-output.md
```

Requires `ANTHROPIC_API_KEY` in environment or `.env`.

## Configuration Defaults

| Parameter | Default | Max | Override |
|-----------|---------|-----|----------|
| Agents    | 5       | 10  | "use 7 agents" |
| Rounds    | 3       | 5   | "run 4 rounds" |
| Words/response | 150 | 300 | "longer responses" |
| Synthesis model | Opus | — | — |
| Debate model | Sonnet | — | — |
