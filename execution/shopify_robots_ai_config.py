#!/usr/bin/env python3
"""
Shopify Robots.txt & AI Crawler Configuration — Beauty Connect Shop
DOE Architecture: Execution layer

Analyzes current robots.txt, identifies AI crawler rules, and generates
a robots.txt.liquid template with recommended allow/block rules.

Usage:
    python execution/shopify_robots_ai_config.py [--dry_run] [--allow-training]
"""

import argparse
import re
import sys
import textwrap
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

from seo_shared import ShopifyClient, logger, BASE_DIR

# ─── Constants ────────────────────────────────────────────────────────────────

STORE_URL = "https://beautyconnectshop.com"
ROBOTS_URL = f"{STORE_URL}/robots.txt"
REQUESTS_TIMEOUT = 15

# AI Search bots — power AI search results, ALLOW by default
AI_SEARCH_BOTS = {
    "OAI-SearchBot": "ChatGPT search results",
    "PerplexityBot": "Perplexity AI search",
    "GoogleBot": "Google Search (default allowed)",
    "Bingbot": "Bing Search (default allowed)",
}

# AI Training bots — only train models, no search benefit, BLOCK by default
AI_TRAINING_BOTS = {
    "GPTBot": "OpenAI model training",
    "Google-Extended": "Gemini model training",
    "CCBot": "Common Crawl dataset",
    "anthropic-ai": "Claude model training",
    "ClaudeBot": "Anthropic web crawler",
}

# All AI-related user agents to check
ALL_AI_BOTS = {**AI_SEARCH_BOTS, **AI_TRAINING_BOTS}


# ─── Fetch & Parse ───────────────────────────────────────────────────────────

def fetch_robots_txt() -> str:
    """Fetch robots.txt from the live store."""
    logger.info(f"📡 Fetching robots.txt from {ROBOTS_URL}")
    try:
        resp = requests.get(ROBOTS_URL, timeout=REQUESTS_TIMEOUT)
        resp.raise_for_status()
        logger.info(f"✓ Fetched robots.txt ({len(resp.text)} bytes)")
        return resp.text
    except requests.RequestException as e:
        logger.error(f"❌ Failed to fetch robots.txt: {e}")
        return ""


def parse_robots_txt(content: str) -> dict:
    """
    Parse robots.txt into structured data.
    Returns dict with keys: sitemaps, user_agents (dict of agent -> list of rules).
    """
    result = {
        "sitemaps": [],
        "user_agents": {},
        "raw": content,
    }

    current_agent = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Sitemap directives
        sitemap_match = re.match(r"^Sitemap:\s*(.+)$", line, re.IGNORECASE)
        if sitemap_match:
            result["sitemaps"].append(sitemap_match.group(1).strip())
            continue

        # User-agent directives
        ua_match = re.match(r"^User-agent:\s*(.+)$", line, re.IGNORECASE)
        if ua_match:
            current_agent = ua_match.group(1).strip()
            if current_agent not in result["user_agents"]:
                result["user_agents"][current_agent] = []
            continue

        # Allow / Disallow rules
        rule_match = re.match(r"^(Allow|Disallow):\s*(.*)$", line, re.IGNORECASE)
        if rule_match and current_agent:
            action = rule_match.group(1).capitalize()
            path = rule_match.group(2).strip()
            result["user_agents"][current_agent].append({"action": action, "path": path})

    return result


# ─── Analysis ─────────────────────────────────────────────────────────────────

def analyze_ai_bot_status(parsed: dict) -> dict:
    """Check which AI bots have explicit rules in current robots.txt."""
    status = {}
    agents = parsed["user_agents"]

    for bot, description in ALL_AI_BOTS.items():
        bot_lower = bot.lower()
        found = False
        for agent_name, rules in agents.items():
            if agent_name.lower() == bot_lower:
                found = True
                disallowed = any(r["action"] == "Disallow" and r["path"] for r in rules)
                allowed = any(r["action"] == "Allow" for r in rules)
                if disallowed:
                    status[bot] = {"status": "BLOCKED", "rules": rules, "description": description}
                elif allowed:
                    status[bot] = {"status": "ALLOWED", "rules": rules, "description": description}
                else:
                    status[bot] = {"status": "PARTIAL", "rules": rules, "description": description}
                break
        if not found:
            # Check wildcard rules
            wildcard_rules = agents.get("*", [])
            wildcard_blocked = any(r["action"] == "Disallow" and r["path"] == "/" for r in wildcard_rules)
            if wildcard_blocked:
                status[bot] = {"status": "BLOCKED (via *)", "rules": [], "description": description}
            else:
                status[bot] = {"status": "NO RULE (default allowed)", "rules": [], "description": description}

    return status


def print_analysis(parsed: dict, bot_status: dict):
    """Print current robots.txt analysis."""
    print("\n" + "=" * 60)
    print("📋 CURRENT ROBOTS.TXT ANALYSIS")
    print("=" * 60)

    # Sitemaps
    if parsed["sitemaps"]:
        print(f"\n🗺  Sitemaps: {len(parsed['sitemaps'])} found")
        for sm in parsed["sitemaps"]:
            print(f"   ✓ {sm}")
    else:
        print("\n🗺  Sitemaps: ⚠ NONE FOUND")

    # Standard rules summary
    agents = parsed["user_agents"]
    print(f"\n📜 User-Agent Sections: {len(agents)}")
    for agent, rules in agents.items():
        allow_count = sum(1 for r in rules if r["action"] == "Allow")
        disallow_count = sum(1 for r in rules if r["action"] == "Disallow")
        print(f"   • {agent}: {allow_count} allow, {disallow_count} disallow")

    # AI Search bots
    print(f"\n🔍 AI SEARCH BOTS (should be ALLOWED):")
    for bot in AI_SEARCH_BOTS:
        info = bot_status.get(bot, {})
        st = info.get("status", "UNKNOWN")
        desc = info.get("description", "")
        icon = "✅" if "ALLOWED" in st or "NO RULE" in st else "⚠️"
        print(f"   {icon} {bot}: {st}  — {desc}")

    # AI Training bots
    print(f"\n🤖 AI TRAINING BOTS (should be BLOCKED):")
    for bot in AI_TRAINING_BOTS:
        info = bot_status.get(bot, {})
        st = info.get("status", "UNKNOWN")
        desc = info.get("description", "")
        icon = "✅" if "BLOCKED" in st else "⚠️"
        print(f"   {icon} {bot}: {st}  — {desc}")


# ─── Template Generation ─────────────────────────────────────────────────────

def generate_liquid_template(parsed: dict, allow_training: bool = False) -> str:
    """
    Generate robots.txt.liquid Shopify theme template.

    Shopify's robots.txt.liquid uses Liquid to output the robots.txt content.
    We preserve Shopify's default rules and append AI crawler directives.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build AI search bot rules (always allowed)
    search_rules = []
    for bot, desc in AI_SEARCH_BOTS.items():
        if bot in ("GoogleBot", "Bingbot"):
            continue  # Already handled by Shopify defaults
        search_rules.append(f"# {desc}")
        search_rules.append(f"User-agent: {bot}")
        search_rules.append("Allow: /")
        search_rules.append("")

    # Build AI training bot rules
    training_rules = []
    for bot, desc in AI_TRAINING_BOTS.items():
        training_rules.append(f"# {desc}")
        training_rules.append(f"User-agent: {bot}")
        if allow_training:
            training_rules.append("Allow: /")
        else:
            training_rules.append("Disallow: /")
        training_rules.append("")

    training_action = "ALLOWED (user override)" if allow_training else "BLOCKED"

    template = textwrap.dedent(f"""\
        {{% comment %}}
          robots.txt.liquid — Beauty Connect Shop
          Generated: {timestamp}

          AI Search bots: ALLOWED (power search results)
          AI Training bots: {training_action}

          To apply: Shopify Admin > Online Store > Themes > Edit Code
          Create/edit templates/robots.txt.liquid and paste this content.
        {{% endcomment %}}

        {{% comment %}} ── Shopify default rules (do not remove) ── {{% endcomment %}}
        {{{{ content_for_header }}}}

        {{% comment %}} ── AI Search Bots (ALLOW — these power AI search results) ── {{% endcomment %}}
    """)

    for line in search_rules:
        template += line + "\n"

    template += textwrap.dedent(f"""\
        {{% comment %}} ── AI Training Bots ({training_action}) ── {{% endcomment %}}
    """)

    for line in training_rules:
        template += line + "\n"

    template += textwrap.dedent("""\
        # Sitemap (Shopify auto-generates this, but explicit is better)
        Sitemap: https://beautyconnectshop.com/sitemap.xml
    """)

    return template


def print_recommendations(parsed: dict, bot_status: dict, allow_training: bool = False):
    """Print recommended changes."""
    print("\n" + "=" * 60)
    print("🔧 RECOMMENDED CHANGES")
    print("=" * 60)

    changes = []

    # Check AI search bots
    for bot in AI_SEARCH_BOTS:
        if bot in ("GoogleBot", "Bingbot"):
            continue
        info = bot_status.get(bot, {})
        st = info.get("status", "")
        if "BLOCKED" in st:
            changes.append(f"  ✏️  UNBLOCK {bot} — currently blocked, should be allowed for AI search")
        elif "NO RULE" in st:
            changes.append(f"  ➕ ADD explicit Allow for {bot} — ensures AI search visibility")

    # Check AI training bots
    for bot in AI_TRAINING_BOTS:
        info = bot_status.get(bot, {})
        st = info.get("status", "")
        if allow_training:
            if "BLOCKED" in st:
                changes.append(f"  ✏️  UNBLOCK {bot} — user chose to allow training bots")
        else:
            if "BLOCKED" not in st:
                changes.append(f"  ➕ ADD Disallow for {bot} — block training crawler, no search benefit")

    if not changes:
        print("\n  ✅ No changes needed — current config matches recommendations!")
    else:
        print(f"\n  {len(changes)} change(s) recommended:\n")
        for c in changes:
            print(c)


def print_template(template: str):
    """Print the generated Liquid template."""
    print("\n" + "=" * 60)
    print("📝 ROBOTS.TXT.LIQUID TEMPLATE")
    print("=" * 60)
    print()
    print(template)
    print("=" * 60)
    print("⚠  TO APPLY:")
    print("   1. Go to Shopify Admin → Online Store → Themes → Edit Code")
    print("   2. Under Templates, create or edit 'robots.txt.liquid'")
    print("   3. Paste the template above (replace existing content if any)")
    print("   4. Save — changes take effect immediately")
    print()
    print("   ℹ  Note: Shopify standard plans customize robots.txt via this")
    print("      Liquid template. Direct file editing is not supported.")
    print("=" * 60)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🤖 Robots.txt & AI Crawler Config — Beauty Connect Shop"
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        default=True,
        help="Show analysis and proposed changes only (default)"
    )
    parser.add_argument(
        "--push_live",
        action="store_true",
        help="NOT SUPPORTED on Shopify standard plan — outputs template instead"
    )
    parser.add_argument(
        "--allow-training",
        action="store_true",
        help="Also allow AI training bots (GPTBot, Google-Extended, etc.)"
    )
    args = parser.parse_args()

    print("🤖 Shopify Robots.txt & AI Crawler Configuration")
    print(f"   Store: {STORE_URL}")
    print(f"   Date:  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if args.push_live:
        print("\n⚠  --push_live is NOT SUPPORTED for Shopify standard plans.")
        print("   Shopify controls the base robots.txt. Use the robots.txt.liquid")
        print("   template output below to customize via theme editor.\n")

    # Step 1: Fetch current robots.txt
    content = fetch_robots_txt()
    if not content:
        logger.warning("⚠ Could not fetch robots.txt — generating template from defaults")
        content = ""

    # Step 2: Parse and analyze
    parsed = parse_robots_txt(content)
    bot_status = analyze_ai_bot_status(parsed)

    # Step 3: Display analysis
    print_analysis(parsed, bot_status)

    # Step 4: Show recommendations
    print_recommendations(parsed, bot_status, allow_training=args.allow_training)

    # Step 5: Generate and display template
    template = generate_liquid_template(parsed, allow_training=args.allow_training)
    print_template(template)

    # Step 6: Save template to .tmp for reference
    import os
    os.makedirs(".tmp", exist_ok=True)
    out_path = os.path.join(
        ".tmp",
        f"robots_txt_liquid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.liquid"
    )
    with open(out_path, "w") as f:
        f.write(template)
    logger.info(f"✓ Template saved to {out_path}")

    print(f"\n✅ Done! Template also saved to: {out_path}")


if __name__ == "__main__":
    main()
