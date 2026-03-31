#!/usr/bin/env python3
"""
Model-Chat: Multi-Agent Debate Engine

Spawns N Claude agents in a shared debate format. Agents read each other's responses
and can directly agree, disagree, build on, or challenge what others said.

Usage:
    python model_chat.py \
        --topic "Should we add subscription boxes?" \
        --agents 5 \
        --rounds 3 \
        --personas "Esthetician,Clinic Owner,Formulator,Educator,Contrarian" \
        --output-file debate_output.md
"""

import anthropic
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

client = anthropic.Anthropic()

DEBATE_MODEL = "claude-sonnet-4-5"
SYNTHESIS_MODEL = "claude-opus-4-6"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2


def run_agent(persona, topic, history, round_num):
    """Run a single agent for one round with retry logic."""

    system_prompt = f"""You are {persona} participating in a structured debate.

Your job:
- Give your honest, expert opinion based on your persona
- {"This is Round 1: respond directly to the question" if round_num == 1 else "You MUST (1) reference at least one other participant by name, (2) either agree with their reasoning or explain specifically why you disagree, (3) add at least one new point not yet raised"}
- Be direct. No fluff. Max 150 words per response.
- Take a clear position — do not hedge or try to cover all sides.
- You are allowed to completely change your position if someone made a compelling argument."""

    messages = []

    if history:
        history_text = "\n\n".join([
            f"Round {r['round']} — {r['persona']}:\n{r['response']}"
            for r in history
        ])
        messages.append({
            "role": "user",
            "content": f"DEBATE TOPIC: {topic}\n\nPREVIOUS RESPONSES:\n{history_text}\n\nNow give your Round {round_num} response (150 words max):"
        })
    else:
        messages.append({
            "role": "user",
            "content": f"DEBATE TOPIC: {topic}\n\nGive your Round 1 response (150 words max):"
        })

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=DEBATE_MODEL,
                max_tokens=300,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"    Rate limited for {persona}, retrying in {delay}s...")
            time.sleep(delay)
        except anthropic.APIError as e:
            if attempt == MAX_RETRIES - 1:
                return f"[Agent error after {MAX_RETRIES} retries: {type(e).__name__}]"
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"    API error for {persona}, retrying in {delay}s...")
            time.sleep(delay)

    return "[Agent failed to respond]"


def run_synthesis(topic, full_history):
    """Final Opus synthesis of the entire debate."""
    history_text = "\n\n".join([
        f"Round {r['round']} — {r['persona']}:\n{r['response']}"
        for r in full_history
    ])

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=SYNTHESIS_MODEL,
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": f"""You observed this multi-round debate on: {topic}

FULL DEBATE TRANSCRIPT:
{history_text}

Synthesize the debate into exactly this structure:

### Consensus (3+ agents agreed)
- List each point where multiple agents converged

### Contested (remained unresolved)
- List each point where agents stayed divided

### Surprise Insight
- List any point that emerged ONLY from the debate interaction (wasn't in Round 1)

### Final Recommendation
One clear recommendation with confidence level (High/Medium/Low)

### Top 3 Actionable Takeaways
1. [specific action]
2. [specific action]
3. [specific action]"""
                }]
            )
            return response.content[0].text
        except (anthropic.RateLimitError, anthropic.APIError):
            if attempt == MAX_RETRIES - 1:
                return "[Synthesis failed — see debate transcript above for raw responses]"
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))

    return "[Synthesis failed]"


def run_debate(topic, personas, num_rounds, output_file):
    """Run the full multi-round debate."""
    full_history = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    transcript_parts = [
        f"# Model-Chat Debate\n",
        f"**Topic:** {topic}\n",
        f"**Agents:** {', '.join(personas)}\n",
        f"**Rounds:** {num_rounds}\n",
        f"**Date:** {timestamp}\n",
        f"\n---\n"
    ]

    print(f"\nModel-Chat Debate")
    print(f"Topic: {topic}")
    print(f"Agents: {', '.join(personas)}")
    print(f"Rounds: {num_rounds}")
    print(f"{'=' * 60}")

    for round_num in range(1, num_rounds + 1):
        print(f"\n--- Round {round_num} / {num_rounds} ---")
        transcript_parts.append(f"\n## Round {round_num}\n")
        round_responses = []

        with ThreadPoolExecutor(max_workers=len(personas)) as executor:
            futures = {
                executor.submit(run_agent, persona, topic, full_history, round_num): persona
                for persona in personas
            }
            for future in as_completed(futures):
                persona = futures[future]
                try:
                    response = future.result()
                except Exception as e:
                    response = f"[Error: {type(e).__name__}]"

                print(f"  {persona} responded")
                round_responses.append({
                    "round": round_num,
                    "persona": persona,
                    "response": response
                })
                transcript_parts.append(f"**{persona}:**\n{response}\n")

        full_history.extend(round_responses)

        if round_num < num_rounds:
            time.sleep(1)

    # Synthesis
    print(f"\n--- Synthesis (Opus) ---")
    synthesis = run_synthesis(topic, full_history)
    transcript_parts.append(f"\n---\n\n## Synthesis\n\n{synthesis}")

    full_transcript = "\n".join(transcript_parts)

    # Save output
    if output_file:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        with open(output_file, "w") as f:
            f.write(full_transcript)
        print(f"\nTranscript saved to {output_file}")

    print(f"\n{'=' * 60}")
    print("\nSYNTHESIS:")
    print(synthesis)

    return full_transcript


def main():
    parser = argparse.ArgumentParser(
        description="Model-Chat: Multi-Agent Debate Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python model_chat.py --topic "Should we pivot to B2C?" --agents 5 --rounds 3
  python model_chat.py --topic "Best email subject line approach" --personas "Copywriter,Data Analyst,Contrarian"
  python model_chat.py --topic "Add subscription boxes?" --rounds 4 --output-file debate.md
        """
    )
    parser.add_argument("--topic", required=True, help="The debate topic or question")
    parser.add_argument("--agents", type=int, default=5, help="Number of agents (default: 5, max: 10)")
    parser.add_argument("--rounds", type=int, default=3, help="Number of debate rounds (default: 3, max: 5)")
    parser.add_argument("--personas", default="", help="Comma-separated list of persona names")
    parser.add_argument("--output-file", default="", help="Path to save the full debate transcript")
    args = parser.parse_args()

    # Validate
    args.agents = min(args.agents, 10)
    args.rounds = min(args.rounds, 5)

    # Parse personas
    if args.personas:
        personas = [p.strip() for p in args.personas.split(",") if p.strip()]
    else:
        print("No personas provided. Using default set.")
        personas = [
            "Domain Expert (10+ years experience)",
            "Hands-on Practitioner",
            "Skeptical End User",
            "Data Analyst",
            "Contrarian"
        ]
        personas = personas[:args.agents]

    run_debate(args.topic, personas, args.rounds, args.output_file)


if __name__ == "__main__":
    main()
