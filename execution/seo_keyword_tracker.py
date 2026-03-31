#!/usr/bin/env python3
"""
SEO Keyword Position Tracker — Beauty Connect Shop
DOE Architecture: Execution layer

Tracks keyword positions in Google Search Console over time,
calculates changes, flags significant movements, and maintains
a 4-week historical trend per keyword.

Usage:
    python execution/seo_keyword_tracker.py
    python execution/seo_keyword_tracker.py --keywords "korean skincare" "K-beauty"
    python execution/seo_keyword_tracker.py --keywords-file keywords.txt
    python execution/seo_keyword_tracker.py --output csv
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add parent dir so imports work when run from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_shared import GSCClient, GoogleSheetsExporter, export_to_csv, K_BEAUTY_KEYWORDS, BASE_DIR, logger

# ─── Constants ────────────────────────────────────────────────────────────────

SITE_URL = os.getenv('GSC_SITE_URL', 'https://beautyconnectshop.com')
HISTORY_FILE = os.path.join(BASE_DIR, '.tmp', 'keyword_tracking_history.json')

BUSINESS_CRITICAL_KEYWORDS = [
    "korean skincare wholesale canada",
    "korean skincare distributor canada",
    "K-beauty professional products",
    "korean dermaceutical products",
    "korean peels for estheticians",
    "PDRN skincare products",
    "beauty connect shop",
    "professional korean skincare canada",
    "wholesale beauty products canada",
    "korean spa products wholesale",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_history() -> dict:
    """Load keyword tracking history from JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load history file: {e}")
    return {}


def save_history(history: dict):
    """Save keyword tracking history, keeping last 4 weeks of data points."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    cutoff = (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d')
    for kw in history:
        history[kw] = [
            entry for entry in history[kw]
            if entry.get('date', '') >= cutoff
        ]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    logger.info(f"History saved to {HISTORY_FILE}")


def direction_arrow(change: float) -> str:
    """Return direction indicator based on position change."""
    if change > 0:
        return "+"
    elif change < 0:
        return "-"
    return "="


def query_gsc_for_keywords(gsc: GSCClient, keywords: list, start_date: str, end_date: str) -> dict:
    """
    Query GSC for each keyword individually.
    Returns dict: keyword -> {position, clicks, impressions, ctr}
    """
    results = {}
    total = len(keywords)

    for i, keyword in enumerate(keywords, 1):
        if i % max(1, total // 10) == 0 or i == 1 or i == total:
            logger.info(f"Querying GSC: {i}/{total} ({i * 100 // total}%)")

        try:
            rows = gsc.query(
                site_url=SITE_URL,
                start_date=start_date,
                end_date=end_date,
                dimensions=['query'],
                row_limit=1,
                dimension_filters=[{
                    'dimension': 'query',
                    'operator': 'equals',
                    'expression': keyword.lower()
                }]
            )

            if rows:
                row = rows[0]
                results[keyword] = {
                    'position': round(row.get('position', 0), 1),
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': round(row.get('ctr', 0) * 100, 2),
                }
            else:
                results[keyword] = {
                    'position': 0,
                    'clicks': 0,
                    'impressions': 0,
                    'ctr': 0,
                }
        except Exception as e:
            logger.error(f"GSC query failed for '{keyword}': {e}")
            results[keyword] = {
                'position': 0,
                'clicks': 0,
                'impressions': 0,
                'ctr': 0,
            }

    return results


# ─── Main Logic ───────────────────────────────────────────────────────────────

def track_keywords(keywords: list, output_mode: str = 'sheets') -> str:
    """
    Main tracking function.
    1. Query GSC for current (last 7d) and previous (7-14d ago) periods
    2. Calculate changes
    3. Update history
    4. Export results
    Returns: Google Sheet URL or CSV path
    """
    logger.info(f"Tracking {len(keywords)} keywords for {SITE_URL}")

    # ── Initialize GSC client ─────────────────────────────────────────────
    gsc = GSCClient()

    # ── Define date ranges ────────────────────────────────────────────────
    today = datetime.now()
    # Current period: last 7 days (with 3-day GSC lag)
    current_end = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    current_start = (today - timedelta(days=10)).strftime('%Y-%m-%d')
    # Previous period: 7-14 days ago
    previous_end = (today - timedelta(days=10)).strftime('%Y-%m-%d')
    previous_start = (today - timedelta(days=17)).strftime('%Y-%m-%d')

    logger.info(f"Current period:  {current_start} to {current_end}")
    logger.info(f"Previous period: {previous_start} to {previous_end}")

    # ── Query GSC ─────────────────────────────────────────────────────────
    logger.info("Querying current period...")
    current_data = query_gsc_for_keywords(gsc, keywords, current_start, current_end)

    logger.info("Querying previous period...")
    previous_data = query_gsc_for_keywords(gsc, keywords, previous_start, previous_end)

    # ── Load history & calculate changes ──────────────────────────────────
    history = load_history()
    today_str = today.strftime('%Y-%m-%d')

    improved = 0
    declined = 0
    stable = 0
    page_one = 0
    significant_changes = []
    rows = []

    for keyword in keywords:
        curr = current_data.get(keyword, {})
        prev = previous_data.get(keyword, {})

        curr_pos = curr.get('position', 0)
        prev_pos = prev.get('position', 0)

        # Position change: positive = improved (moved up), negative = dropped
        # Lower position number = better rank, so change = prev - curr
        if curr_pos > 0 and prev_pos > 0:
            change = round(prev_pos - curr_pos, 1)
        elif curr_pos > 0 and prev_pos == 0:
            change = 0  # New appearance, no comparison
        else:
            change = 0

        # Direction
        if change > 0.5:
            direction = "^"
            improved += 1
        elif change < -0.5:
            direction = "v"
            declined += 1
        else:
            direction = "="
            stable += 1

        # Page 1 check
        if 0 < curr_pos <= 10:
            page_one += 1

        # Best position from history (4 weeks)
        kw_history = history.get(keyword, [])
        historical_positions = [
            entry['position'] for entry in kw_history
            if entry.get('position', 0) > 0
        ]
        if curr_pos > 0:
            historical_positions.append(curr_pos)
        best_position = min(historical_positions) if historical_positions else 0

        # Alert for significant changes
        alert = ""
        if abs(change) > 3:
            alert = f"{'IMPROVED' if change > 0 else 'DROPPED'} {abs(change):.1f} positions"
            significant_changes.append({
                'keyword': keyword,
                'prev_pos': prev_pos,
                'curr_pos': curr_pos,
                'change': change,
                'direction': direction,
            })

        # Build row
        rows.append([
            keyword,
            curr_pos if curr_pos > 0 else "N/A",
            prev_pos if prev_pos > 0 else "N/A",
            f"{change:+.1f}" if (curr_pos > 0 and prev_pos > 0) else "N/A",
            direction,
            curr.get('clicks', 0),
            curr.get('impressions', 0),
            f"{curr.get('ctr', 0):.2f}%",
            best_position if best_position > 0 else "N/A",
            alert,
        ])

        # Update history
        if keyword not in history:
            history[keyword] = []
        history[keyword].append({
            'date': today_str,
            'position': curr_pos,
            'clicks': curr.get('clicks', 0),
            'impressions': curr.get('impressions', 0),
            'ctr': curr.get('ctr', 0),
        })

    # ── Save history ──────────────────────────────────────────────────────
    save_history(history)

    # ── Print summary ─────────────────────────────────────────────────────
    print()
    print("=" * 50)
    print(f"KEYWORD TRACKER -- Beauty Connect Shop")
    print("=" * 50)
    print(f"  Keywords tracked: {len(keywords)}")
    print(f"  Improved (^):     {improved}")
    print(f"  Declined (v):     {declined}")
    print(f"  Stable (=):       {stable}")
    print(f"  On page 1:        {page_one}")
    print()

    if significant_changes:
        print("SIGNIFICANT CHANGES (>3 positions):")
        for sc in significant_changes:
            arrow = "^" if sc['change'] > 0 else "v"
            sign = "+" if sc['change'] > 0 else ""
            print(f"  {arrow} \"{sc['keyword']}\" -- position {sc['prev_pos']} -> {sc['curr_pos']} ({sign}{sc['change']:.1f})")
        print()
    else:
        print("  No significant changes (>3 positions) this period.")
        print()

    # ── Export ─────────────────────────────────────────────────────────────
    headers = [
        'Keyword', 'Current Position', 'Previous Position', 'Change',
        'Direction', 'Clicks (7d)', 'Impressions (7d)', 'CTR',
        'Best Position (4 weeks)', 'Alert'
    ]

    date_str = today.strftime('%Y-%m-%d')

    if output_mode == 'sheets':
        try:
            exporter = GoogleSheetsExporter()
            sheet_url = exporter.create_sheet(
                title=f"Keyword Tracker -- {date_str}",
                headers=headers,
                rows=rows
            )
            logger.info(f"Google Sheet: {sheet_url}")
            print(f"Google Sheet: {sheet_url}")
            return sheet_url
        except Exception as e:
            logger.warning(f"Google Sheets export failed: {e} — falling back to CSV")
            output_mode = 'csv'

    if output_mode == 'csv':
        csv_path = export_to_csv(f"keyword_tracker_{date_str}", headers, rows)
        print(f"CSV saved: {csv_path}")
        return csv_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SEO Keyword Position Tracker — Beauty Connect Shop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/seo_keyword_tracker.py
  python execution/seo_keyword_tracker.py --keywords "korean skincare" "K-beauty"
  python execution/seo_keyword_tracker.py --keywords-file my_keywords.txt
  python execution/seo_keyword_tracker.py --output csv
        """
    )
    parser.add_argument(
        '--keywords', nargs='+',
        help='Keywords to track (space-separated, quote multi-word keywords)'
    )
    parser.add_argument(
        '--keywords-file',
        help='Path to a text file with one keyword per line'
    )
    parser.add_argument(
        '--output', choices=['sheets', 'csv'], default='sheets',
        help='Output format: Google Sheets (default) or CSV'
    )

    args = parser.parse_args()

    # ── Determine keyword list ────────────────────────────────────────────
    if args.keywords:
        keywords = args.keywords
        logger.info(f"Using {len(keywords)} keywords from CLI")
    elif args.keywords_file:
        filepath = args.keywords_file
        if not os.path.exists(filepath):
            logger.error(f"Keywords file not found: {filepath}")
            sys.exit(1)
        with open(filepath, 'r') as f:
            keywords = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(keywords)} keywords from {filepath}")
    else:
        # Default: K_BEAUTY_KEYWORDS + business-critical keywords (deduplicated)
        seen = set()
        keywords = []
        for kw in K_BEAUTY_KEYWORDS + BUSINESS_CRITICAL_KEYWORDS:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                keywords.append(kw)
        logger.info(f"Using default keyword list ({len(keywords)} keywords)")

    # ── Run tracker ───────────────────────────────────────────────────────
    result = track_keywords(keywords, output_mode=args.output)

    if result:
        logger.info(f"Tracking complete. Output: {result}")
    else:
        logger.error("Tracking failed — no output generated")
        sys.exit(1)


if __name__ == '__main__':
    main()
