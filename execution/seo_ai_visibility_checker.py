#!/usr/bin/env python3
"""
Beauty Connect Shop — AI Visibility Checker
DOE Architecture Execution Script v1.0

Checks brand presence across AI search engines and traditional search.
Since direct API access to ChatGPT/Perplexity/Gemini search is limited,
this script:
1. Checks Google Search results via Google Custom Search API or SerpAPI
2. Generates a manual tracking template for AI platforms
3. Tracks visibility over time with trend analysis

Usage:
    python execution/seo_ai_visibility_checker.py
    python execution/seo_ai_visibility_checker.py --queries "korean skincare wholesale" "k-beauty canada"
    python execution/seo_ai_visibility_checker.py --output csv
"""

import os
import sys
import csv
import json
import logging
import argparse
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

# Import shared utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import GoogleSheetsExporter, export_to_csv, BASE_DIR, logger

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)

log = logging.getLogger('seo_ai_visibility')
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/seo_ai_visibility.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

# ─── Constants ────────────────────────────────────────────────────────────────
BRAND_DOMAIN = "beautyconnectshop.com"
BRAND_NAME = "Beauty Connect Shop"
VISIBILITY_LOG_PATH = os.path.join(BASE_DIR, '.tmp', 'ai_visibility_log.csv')

DEFAULT_QUERIES = [
    "korean skincare wholesale canada",
    "K-beauty distributor canada",
    "professional korean skincare products",
    "korean dermaceutical distributor",
    "beauty connect shop",
    "korean peels for estheticians",
    "PDRN skincare products wholesale",
    "korean skincare for clinics canada",
]

AI_PLATFORMS = [
    "Google",
    "ChatGPT",
    "Perplexity",
    "Gemini",
    "Copilot",
    "Claude",
]

REQUESTS_TIMEOUT = 30


# ─── Google Custom Search ─────────────────────────────────────────────────────

def search_google_cse(query: str, api_key: str, cx: str, num_results: int = 20) -> List[Dict]:
    """
    Search Google via Custom Search Engine API.
    Returns list of {position, title, link, snippet}.
    Max 10 per request, so we do 2 requests for top 20.
    """
    results = []
    for start in [1, 11]:
        if len(results) >= num_results:
            break
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "start": start,
                    "num": 10,
                },
                timeout=REQUESTS_TIMEOUT,
            )
            if resp.status_code == 429:
                log.warning(f"⚠️ Google CSE rate limited on query: {query}")
                break
            resp.raise_for_status()
            data = resp.json()

            for i, item in enumerate(data.get("items", [])):
                results.append({
                    "position": start + i,
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            time.sleep(0.5)  # Be nice to the API
        except requests.RequestException as e:
            log.error(f"❌ Google CSE error for '{query}': {e}")
            break

    return results


def search_serpapi(query: str, api_key: str, num_results: int = 20) -> List[Dict]:
    """
    Search Google via SerpAPI.
    Returns list of {position, title, link, snippet}.
    """
    results = []
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "api_key": api_key,
                "q": query,
                "num": num_results,
                "engine": "google",
                "gl": "ca",
                "hl": "en",
            },
            timeout=REQUESTS_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("organic_results", []):
            results.append({
                "position": item.get("position", 0),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        time.sleep(0.5)
    except requests.RequestException as e:
        log.error(f"❌ SerpAPI error for '{query}': {e}")

    return results


# ─── Brand Detection ─────────────────────────────────────────────────────────

def check_brand_in_results(results: List[Dict]) -> Dict:
    """
    Check if brand domain appears in search results.
    Returns {mentioned: bool, position: int|None, title: str, snippet: str, competitors: list}.
    """
    mentioned = False
    position = None
    title = ""
    snippet = ""
    competitors = []

    for r in results:
        link = r.get("link", "").lower()
        if BRAND_DOMAIN in link:
            mentioned = True
            position = r["position"]
            title = r["title"]
            snippet = r["snippet"]
            break

    # Collect competitor mentions (skincare/beauty domains in top 10)
    competitor_keywords = ["skincare", "beauty", "kbeauty", "k-beauty", "korean", "wholesale", "distributor"]
    for r in results[:10]:
        link = r.get("link", "").lower()
        if BRAND_DOMAIN not in link:
            for kw in competitor_keywords:
                if kw in link or kw in r.get("title", "").lower():
                    competitors.append(f"#{r['position']}: {r.get('title', '')[:60]}")
                    break

    return {
        "mentioned": mentioned,
        "position": position,
        "title": title,
        "snippet": snippet,
        "competitors": competitors,
    }


# ─── Search Execution ────────────────────────────────────────────────────────

def run_search_checks(queries: List[str]) -> List[Dict]:
    """
    Run Google search checks for all queries.
    Tries Google CSE first, then SerpAPI, returns results.
    """
    google_cse_key = os.getenv("GOOGLE_CSE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    google_cse_cx = os.getenv("GOOGLE_CSE_CX") or os.getenv("GOOGLE_CSE_ID")
    serpapi_key = os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")

    search_fn = None
    search_name = None

    if google_cse_key and google_cse_cx:
        search_fn = lambda q: search_google_cse(q, google_cse_key, google_cse_cx)
        search_name = "Google CSE"
    elif serpapi_key:
        search_fn = lambda q: search_serpapi(q, serpapi_key)
        search_name = "SerpAPI"
    else:
        log.warning("⚠️ No search API keys found (GOOGLE_CSE_API_KEY + GOOGLE_CSE_CX, or SERPAPI_KEY)")
        log.info("📋 Will generate manual tracking template only")
        return []

    log.info(f"🔍 Using {search_name} to check {len(queries)} queries...")
    results = []
    for i, query in enumerate(queries):
        log.info(f"⏳ [{i+1}/{len(queries)}] Searching: {query}")
        search_results = search_fn(query)
        brand_check = check_brand_in_results(search_results)

        results.append({
            "query": query,
            "platform": "Google",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "mentioned": "Yes" if brand_check["mentioned"] else "No",
            "position": brand_check["position"] or "Not in top 20",
            "title": brand_check["title"],
            "snippet": brand_check["snippet"],
            "competitors": "; ".join(brand_check["competitors"][:5]),
        })

        if brand_check["mentioned"]:
            log.info(f"  ✅ Found at position #{brand_check['position']}")
        else:
            log.info(f"  ❌ Not found in top 20")

    return results


# ─── Manual Tracking Template ────────────────────────────────────────────────

def generate_tracking_template(queries: List[str]) -> Tuple[List[str], List[List]]:
    """
    Generate a pre-filled manual tracking template for AI platforms.
    Returns (headers, rows).
    """
    headers = [
        "Query",
        "Platform",
        "Date Checked",
        "Brand Mentioned (Y/N)",
        "Position / Citation",
        "Competitor Mentions",
        "Notes",
    ]
    rows = []
    today = datetime.now().strftime("%Y-%m-%d")

    for query in queries:
        for platform in AI_PLATFORMS:
            rows.append([
                query,
                platform,
                today if platform == "Google" else "",  # Pre-fill date for Google (auto-checked)
                "",
                "",
                "",
                f"Try: '{query}' in {platform}" if platform != "Google" else "Auto-checked via API",
            ])

    return headers, rows


# ─── Trend Tracking ──────────────────────────────────────────────────────────

def append_to_log(results: List[Dict]):
    """Append search results to the running visibility log."""
    if not results:
        return

    os.makedirs(os.path.dirname(VISIBILITY_LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(VISIBILITY_LOG_PATH)
    fieldnames = ["date", "query", "platform", "mentioned", "position", "title", "snippet", "competitors"]

    with open(VISIBILITY_LOG_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    log.info(f"📝 Appended {len(results)} entries to {VISIBILITY_LOG_PATH}")


def load_historical_data() -> Tuple[List[str], List[List]]:
    """
    Load historical visibility data from log file.
    Returns (headers, rows).
    """
    headers = ["Date", "Query", "Platform", "Mentioned", "Position", "Title", "Competitors"]
    rows = []

    if not os.path.exists(VISIBILITY_LOG_PATH):
        log.info("📊 No historical data found — this is the first check")
        return headers, []

    with open(VISIBILITY_LOG_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append([
                row.get("date", ""),
                row.get("query", ""),
                row.get("platform", ""),
                row.get("mentioned", ""),
                row.get("position", ""),
                row.get("title", ""),
                row.get("competitors", ""),
            ])

    log.info(f"📊 Loaded {len(rows)} historical entries")
    return headers, rows


def compare_with_previous(current_results: List[Dict]) -> List[str]:
    """
    Compare current results with the most recent previous check.
    Returns list of trend observations.
    """
    trends = []
    if not os.path.exists(VISIBILITY_LOG_PATH) or not current_results:
        return trends

    # Load previous results grouped by query
    previous = {}
    with open(VISIBILITY_LOG_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = row.get("query", "")
            # Keep the latest entry per query (before this run)
            previous[query] = row

    for result in current_results:
        query = result["query"]
        if query in previous:
            prev = previous[query]
            prev_mentioned = prev.get("mentioned", "No") == "Yes"
            curr_mentioned = result["mentioned"] == "Yes"

            if not prev_mentioned and curr_mentioned:
                trends.append(f"🆕 '{query}' — NEW appearance at position #{result['position']}")
            elif prev_mentioned and not curr_mentioned:
                trends.append(f"📉 '{query}' — DROPPED out of top 20 (was #{prev.get('position', '?')})")
            elif prev_mentioned and curr_mentioned:
                prev_pos = prev.get("position", "")
                curr_pos = result["position"]
                try:
                    prev_pos_int = int(prev_pos)
                    curr_pos_int = int(curr_pos)
                    if curr_pos_int < prev_pos_int:
                        trends.append(f"📈 '{query}' — IMPROVED #{prev_pos_int} → #{curr_pos_int}")
                    elif curr_pos_int > prev_pos_int:
                        trends.append(f"📉 '{query}' — DECLINED #{prev_pos_int} → #{curr_pos_int}")
                    else:
                        trends.append(f"➡️ '{query}' — STABLE at #{curr_pos_int}")
                except (ValueError, TypeError):
                    pass

    return trends


# ─── Output ──────────────────────────────────────────────────────────────────

def export_results(results: List[Dict], queries: List[str], output_mode: str):
    """Export results to Google Sheets or CSV."""
    today = datetime.now().strftime("%Y-%m-%d")

    # ── Tab 1: Search Results ──
    results_headers = ["Query", "Platform", "Date", "Mentioned", "Position", "Title", "Snippet", "Competitors"]
    results_rows = []
    for r in results:
        results_rows.append([
            r["query"], r["platform"], r["date"], r["mentioned"],
            str(r["position"]), r["title"], r["snippet"], r["competitors"],
        ])

    # ── Tab 2: Tracking Template ──
    template_headers, template_rows = generate_tracking_template(queries)

    # Merge auto-checked Google results into template
    google_lookup = {r["query"]: r for r in results if r["platform"] == "Google"}
    for row in template_rows:
        query, platform = row[0], row[1]
        if platform == "Google" and query in google_lookup:
            g = google_lookup[query]
            row[2] = g["date"]
            row[3] = g["mentioned"]
            row[4] = str(g["position"])
            row[5] = g["competitors"]

    # ── Tab 3: Trends ──
    trends_headers, trends_rows = load_historical_data()

    # ── Summary stats ──
    total_queries = len(queries)
    found_count = sum(1 for r in results if r["mentioned"] == "Yes")
    if results:
        log.info(f"\n{'='*60}")
        log.info(f"📊 AI VISIBILITY SUMMARY — {today}")
        log.info(f"{'='*60}")
        log.info(f"  Queries checked: {total_queries}")
        log.info(f"  Brand found:     {found_count}/{len(results)} ({found_count/len(results)*100:.0f}%)")
        log.info(f"  Not found:       {len(results) - found_count}/{len(results)}")

        # Show trends
        trend_notes = compare_with_previous(results)
        if trend_notes:
            log.info(f"\n📈 TRENDS vs previous check:")
            for t in trend_notes:
                log.info(f"  {t}")
        log.info(f"{'='*60}\n")
    else:
        log.info(f"\n📋 No API keys configured — manual template generated for {total_queries} queries × {len(AI_PLATFORMS)} platforms")

    # ── Export ──
    if output_mode == "sheets":
        try:
            sheets = GoogleSheetsExporter()
            sheet_title = f"AI Visibility Check — {today}"

            # Create with results tab (or template if no results)
            if results_rows:
                sheet_url = sheets.create_sheet(sheet_title, results_headers, results_rows)
            else:
                sheet_url = sheets.create_sheet(sheet_title, template_headers, template_rows)

            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]

            # Add tracking template tab
            if results_rows:
                sheets.add_sheet_tab(spreadsheet_id, "Tracking Template", template_headers, template_rows)

            # Add trends tab if we have historical data
            if trends_rows:
                sheets.add_sheet_tab(spreadsheet_id, "Trends", trends_headers, trends_rows)

            log.info(f"✅ Google Sheet: {sheet_url}")
            return sheet_url
        except Exception as e:
            log.warning(f"⚠️ Google Sheets failed ({e}), falling back to CSV")
            output_mode = "csv"

    if output_mode == "csv":
        paths = []
        if results_rows:
            p = export_to_csv(f"ai_visibility_results", results_headers, results_rows)
            paths.append(p)
            log.info(f"✅ Results CSV: {p}")

        p = export_to_csv(f"ai_visibility_template", template_headers, template_rows)
        paths.append(p)
        log.info(f"✅ Template CSV: {p}")

        if trends_rows:
            p = export_to_csv(f"ai_visibility_trends", trends_headers, trends_rows)
            paths.append(p)
            log.info(f"✅ Trends CSV: {p}")

        return paths


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🔍 AI Visibility Checker — Beauty Connect Shop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/seo_ai_visibility_checker.py
  python execution/seo_ai_visibility_checker.py --queries "korean skincare" "k-beauty wholesale"
  python execution/seo_ai_visibility_checker.py --output csv

Environment variables:
  GOOGLE_CSE_API_KEY / GOOGLE_API_KEY  — Google Custom Search API key
  GOOGLE_CSE_CX / GOOGLE_CSE_ID       — Google Custom Search Engine ID
  SERPAPI_KEY / SERPAPI_API_KEY         — SerpAPI key (fallback)
        """,
    )
    parser.add_argument(
        "--queries", nargs="+", default=None,
        help="Custom queries to check (default: built-in list of 8 queries)",
    )
    parser.add_argument(
        "--output", choices=["sheets", "csv"], default="sheets",
        help="Output format (default: sheets)",
    )
    args = parser.parse_args()

    queries = args.queries if args.queries else DEFAULT_QUERIES

    log.info(f"🚀 AI Visibility Checker — {BRAND_NAME}")
    log.info(f"🌐 Domain: {BRAND_DOMAIN}")
    log.info(f"📋 Queries: {len(queries)}")
    log.info(f"📤 Output: {args.output}\n")

    # Step 1: Run Google search checks
    results = run_search_checks(queries)

    # Step 2: Append to running log
    if results:
        append_to_log(results)

    # Step 3: Export results
    export_results(results, queries, args.output)

    log.info("✅ AI Visibility Check complete!")


if __name__ == "__main__":
    main()
