#!/usr/bin/env python3
"""
SEO Weekly Report Generator — Beauty Connect Shop
DOE Architecture: Execution layer

Pulls Google Search Console data for two consecutive weeks,
calculates week-over-week comparisons, identifies top movers,
and exports to Google Sheets + local JSON.

Usage:
    python execution/seo_weekly_report.py [--site URL] [--days 7]
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import GSCClient, GoogleSheetsExporter, export_to_csv, BASE_DIR, logger

load_dotenv()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def pct_change(current: float, previous: float) -> float:
    """Calculate percentage change. Returns 0 if previous is 0."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100


def fmt_pct(value: float) -> str:
    """Format percentage change with +/- prefix."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def fmt_delta(current: float, previous: float, is_pct: bool = False) -> str:
    """Format absolute delta with +/- prefix."""
    delta = current - previous
    sign = "+" if delta >= 0 else ""
    if is_pct:
        return f"{sign}{delta:.2f}%"
    return f"{sign}{delta:.1f}"


# ─── Data Fetching ───────────────────────────────────────────────────────────

def fetch_period_data(gsc: GSCClient, site: str, start: str, end: str,
                      dimensions: list, row_limit: int = 5000) -> list:
    """Fetch GSC data for a given period and dimensions."""
    logger.info(f"📡 Fetching GSC data: {start} → {end} | dims={dimensions}")
    rows = gsc.query(
        site_url=site,
        start_date=start,
        end_date=end,
        dimensions=dimensions,
        row_limit=row_limit
    )
    logger.info(f"   ✓ Got {len(rows)} rows")
    return rows


def rows_to_dict(rows: list, key_index: int = 0) -> dict:
    """Convert GSC rows to dict keyed by dimension value."""
    result = {}
    for row in rows:
        key = row['keys'][key_index]
        result[key] = {
            'clicks': row['clicks'],
            'impressions': row['impressions'],
            'ctr': row['ctr'],
            'position': row['position'],
        }
    return result


# ─── Aggregate Metrics ───────────────────────────────────────────────────────

def aggregate_totals(rows: list) -> dict:
    """Sum clicks/impressions and average CTR/position across all rows."""
    if not rows:
        return {'clicks': 0, 'impressions': 0, 'ctr': 0.0, 'position': 0.0}

    total_clicks = sum(r['clicks'] for r in rows)
    total_impressions = sum(r['impressions'] for r in rows)
    avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    # Weighted average position by impressions
    weighted_pos = sum(r['position'] * r['impressions'] for r in rows)
    avg_pos = weighted_pos / total_impressions if total_impressions > 0 else 0.0

    return {
        'clicks': total_clicks,
        'impressions': total_impressions,
        'ctr': avg_ctr,
        'position': avg_pos,
    }


# ─── Movers Calculation ─────────────────────────────────────────────────────

def calculate_movers(current_dict: dict, previous_dict: dict, top_n: int = 10):
    """
    Calculate gainers/losers between two period dicts.
    Returns (gainers, losers, new_entries).
    """
    all_keys = set(current_dict.keys()) | set(previous_dict.keys())
    deltas = []

    for key in all_keys:
        curr = current_dict.get(key, {'clicks': 0, 'impressions': 0, 'ctr': 0, 'position': 0})
        prev = previous_dict.get(key, {'clicks': 0, 'impressions': 0, 'ctr': 0, 'position': 0})
        delta_clicks = curr['clicks'] - prev['clicks']
        deltas.append({
            'key': key,
            'current_clicks': curr['clicks'],
            'previous_clicks': prev['clicks'],
            'delta_clicks': delta_clicks,
            'current_position': curr['position'],
            'previous_position': prev['position'],
            'current_impressions': curr['impressions'],
            'current_ctr': curr['ctr'],
        })

    # Sort by delta clicks
    sorted_deltas = sorted(deltas, key=lambda x: x['delta_clicks'], reverse=True)
    gainers = [d for d in sorted_deltas if d['delta_clicks'] > 0][:top_n]
    losers = [d for d in sorted_deltas if d['delta_clicks'] < 0][-top_n:]
    losers.reverse()  # Most negative first (sorted asc by delta)
    losers = sorted([d for d in sorted_deltas if d['delta_clicks'] < 0],
                    key=lambda x: x['delta_clicks'])[:top_n]

    # New entries: in current but not in previous
    new_entries = [d for d in sorted_deltas
                   if d['key'] in current_dict and d['key'] not in previous_dict]
    new_entries = sorted(new_entries, key=lambda x: x['current_clicks'], reverse=True)[:top_n]

    return gainers, losers, new_entries


# ─── Page 1 Changes ─────────────────────────────────────────────────────────

def calculate_page1_changes(current_dict: dict, previous_dict: dict):
    """
    Find queries that moved to/from page 1 (position <= 10).
    Returns (entered_page1, dropped_from_page1).
    """
    entered = []
    dropped = []

    all_keys = set(current_dict.keys()) | set(previous_dict.keys())

    for key in all_keys:
        curr = current_dict.get(key)
        prev = previous_dict.get(key)

        if curr and prev:
            curr_pos = curr['position']
            prev_pos = prev['position']

            # Moved to page 1
            if curr_pos <= 10 and prev_pos > 10:
                entered.append({
                    'query': key,
                    'current_position': round(curr_pos, 1),
                    'previous_position': round(prev_pos, 1),
                    'clicks': curr['clicks'],
                })

            # Dropped from page 1
            elif curr_pos > 10 and prev_pos <= 10:
                dropped.append({
                    'query': key,
                    'current_position': round(curr_pos, 1),
                    'previous_position': round(prev_pos, 1),
                    'clicks': curr['clicks'],
                })

    entered.sort(key=lambda x: x['current_position'])
    dropped.sort(key=lambda x: x['current_position'])

    return entered, dropped


# ─── Console Report ──────────────────────────────────────────────────────────

def print_report(totals_curr, totals_prev, dates, gainers_q, losers_q,
                 entered_p1, dropped_p1, new_queries):
    """Print formatted console report."""
    clicks_pct = pct_change(totals_curr['clicks'], totals_prev['clicks'])
    imp_pct = pct_change(totals_curr['impressions'], totals_prev['impressions'])
    ctr_delta = (totals_curr['ctr'] - totals_prev['ctr']) * 100  # as percentage points
    pos_delta = totals_curr['position'] - totals_prev['position']

    print()
    print("📊 WEEKLY SEO REPORT — Beauty Connect Shop")
    print("═" * 50)
    print(f"Period: {dates['curr_start']} → {dates['curr_end']} vs {dates['prev_start']} → {dates['prev_end']}")
    print()
    print("TRAFFIC")
    print(f"  Clicks:       {totals_curr['clicks']:,} ({fmt_pct(clicks_pct)} vs prev)")
    print(f"  Impressions:  {totals_curr['impressions']:,} ({fmt_pct(imp_pct)} vs prev)")
    print(f"  CTR:          {totals_curr['ctr']:.2%} ({fmt_delta(totals_curr['ctr']*100, totals_prev['ctr']*100, is_pct=True)} vs prev)")
    print(f"  Avg Position: {totals_curr['position']:.1f} ({fmt_delta(totals_curr['position'], totals_prev['position'])} vs prev)")
    print()

    if gainers_q:
        print("🔼 TOP GAINING QUERIES")
        for i, g in enumerate(gainers_q[:10], 1):
            print(f"  {i}. \"{g['key']}\" — +{g['delta_clicks']} clicks, position {g['current_position']:.1f}")
        print()

    if losers_q:
        print("🔽 TOP LOSING QUERIES")
        for i, l in enumerate(losers_q[:10], 1):
            print(f"  {i}. \"{l['key']}\" — {l['delta_clicks']} clicks, position {l['current_position']:.1f}")
        print()

    if new_queries:
        print("🆕 NEW QUERIES THIS WEEK")
        for i, n in enumerate(new_queries[:10], 1):
            print(f"  {i}. \"{n['key']}\" — {n['current_clicks']} clicks, position {n['current_position']:.1f}")
        print()

    if entered_p1:
        print("🎯 NEW PAGE 1 RANKINGS")
        for e in entered_p1:
            print(f"  • \"{e['query']}\" — position {e['current_position']} (was {e['previous_position']})")
        print()

    if dropped_p1:
        print("⚠ DROPPED FROM PAGE 1")
        for d in dropped_p1:
            print(f"  • \"{d['query']}\" — position {d['current_position']} (was {d['previous_position']})")
        print()


# ─── Export to Google Sheets ─────────────────────────────────────────────────

def export_to_sheets(totals_curr, totals_prev, dates,
                     gainers_q, losers_q, gainers_p, losers_p,
                     entered_p1, dropped_p1, new_queries, report_date):
    """Export report to Google Sheets with multiple tabs."""
    try:
        sheets = GoogleSheetsExporter()
    except Exception as e:
        logger.warning(f"⚠ Google Sheets unavailable: {e}")
        logger.info("Falling back to CSV export...")
        return export_csv_fallback(totals_curr, totals_prev, dates,
                                   gainers_q, losers_q, gainers_p, losers_p,
                                   entered_p1, dropped_p1, report_date)

    title = f"SEO Weekly Report — {report_date}"

    # Tab 1: Summary
    clicks_pct = pct_change(totals_curr['clicks'], totals_prev['clicks'])
    imp_pct = pct_change(totals_curr['impressions'], totals_prev['impressions'])

    summary_headers = ["Metric", "Current Week", "Previous Week", "Change", "Change %"]
    summary_rows = [
        ["Clicks", totals_curr['clicks'], totals_prev['clicks'],
         totals_curr['clicks'] - totals_prev['clicks'], f"{clicks_pct:.1f}%"],
        ["Impressions", totals_curr['impressions'], totals_prev['impressions'],
         totals_curr['impressions'] - totals_prev['impressions'], f"{imp_pct:.1f}%"],
        ["CTR", f"{totals_curr['ctr']:.2%}", f"{totals_prev['ctr']:.2%}",
         f"{(totals_curr['ctr'] - totals_prev['ctr'])*100:.2f}pp", ""],
        ["Avg Position", f"{totals_curr['position']:.1f}", f"{totals_prev['position']:.1f}",
         f"{totals_curr['position'] - totals_prev['position']:.1f}", ""],
        [],
        ["Report Period", f"{dates['curr_start']} → {dates['curr_end']}"],
        ["Comparison Period", f"{dates['prev_start']} → {dates['prev_end']}"],
    ]

    # Create sheet with Summary tab (uses Sheet1 which we rename conceptually)
    sheet_url = sheets.create_sheet(title, summary_headers, summary_rows)
    spreadsheet_id = sheet_url.split('/d/')[1].split('/')[0]

    # Tab 2: Gaining Queries
    gq_headers = ["Query", "Current Clicks", "Previous Clicks", "Delta", "Position"]
    gq_rows = [[g['key'], g['current_clicks'], g['previous_clicks'],
                 g['delta_clicks'], round(g['current_position'], 1)]
                for g in gainers_q]
    sheets.add_sheet_tab(spreadsheet_id, "Gaining Queries", gq_headers, gq_rows)

    # Tab 3: Losing Queries
    lq_headers = ["Query", "Current Clicks", "Previous Clicks", "Delta", "Position"]
    lq_rows = [[l['key'], l['current_clicks'], l['previous_clicks'],
                 l['delta_clicks'], round(l['current_position'], 1)]
                for l in losers_q]
    sheets.add_sheet_tab(spreadsheet_id, "Losing Queries", lq_headers, lq_rows)

    # Tab 4: Gaining Pages
    gp_headers = ["Page", "Current Clicks", "Previous Clicks", "Delta", "Position"]
    gp_rows = [[g['key'], g['current_clicks'], g['previous_clicks'],
                 g['delta_clicks'], round(g['current_position'], 1)]
                for g in gainers_p]
    sheets.add_sheet_tab(spreadsheet_id, "Gaining Pages", gp_headers, gp_rows)

    # Tab 5: Page 1 Changes
    p1_headers = ["Direction", "Query", "Current Position", "Previous Position", "Clicks"]
    p1_rows = []
    for e in entered_p1:
        p1_rows.append(["🔼 Entered", e['query'], e['current_position'],
                         e['previous_position'], e['clicks']])
    for d in dropped_p1:
        p1_rows.append(["🔽 Dropped", d['query'], d['current_position'],
                         d['previous_position'], d['clicks']])
    sheets.add_sheet_tab(spreadsheet_id, "Page 1 Changes", p1_headers, p1_rows)

    logger.info(f"✅ Google Sheet: {sheet_url}")
    return sheet_url


def export_csv_fallback(totals_curr, totals_prev, dates,
                        gainers_q, losers_q, gainers_p, losers_p,
                        entered_p1, dropped_p1, report_date):
    """CSV fallback when Google Sheets is unavailable."""
    paths = []

    # Gaining queries
    gq_headers = ["Query", "Current Clicks", "Previous Clicks", "Delta", "Position"]
    gq_rows = [[g['key'], g['current_clicks'], g['previous_clicks'],
                 g['delta_clicks'], round(g['current_position'], 1)]
                for g in gainers_q]
    paths.append(export_to_csv(f"seo_gaining_queries_{report_date}", gq_headers, gq_rows))

    # Losing queries
    lq_headers = ["Query", "Current Clicks", "Previous Clicks", "Delta", "Position"]
    lq_rows = [[l['key'], l['current_clicks'], l['previous_clicks'],
                 l['delta_clicks'], round(l['current_position'], 1)]
                for l in losers_q]
    paths.append(export_to_csv(f"seo_losing_queries_{report_date}", lq_headers, lq_rows))

    logger.info(f"✅ CSV files saved: {paths}")
    return paths


# ─── JSON Archive ────────────────────────────────────────────────────────────

def save_json_archive(totals_curr, totals_prev, dates,
                      gainers_q, losers_q, gainers_p, losers_p,
                      entered_p1, dropped_p1, new_queries, report_date):
    """Save report data as JSON for historical tracking."""
    archive_dir = os.path.join(BASE_DIR, '.tmp', 'weekly_reports')
    os.makedirs(archive_dir, exist_ok=True)

    report = {
        'generated_at': datetime.now().isoformat(),
        'dates': dates,
        'summary': {
            'current': totals_curr,
            'previous': totals_prev,
            'changes': {
                'clicks_pct': round(pct_change(totals_curr['clicks'], totals_prev['clicks']), 2),
                'impressions_pct': round(pct_change(totals_curr['impressions'], totals_prev['impressions']), 2),
                'ctr_delta_pp': round((totals_curr['ctr'] - totals_prev['ctr']) * 100, 3),
                'position_delta': round(totals_curr['position'] - totals_prev['position'], 2),
            }
        },
        'gaining_queries': gainers_q[:10],
        'losing_queries': losers_q[:10],
        'gaining_pages': gainers_p[:10],
        'losing_pages': losers_p[:10],
        'new_queries': new_queries[:10],
        'entered_page_1': entered_p1,
        'dropped_from_page_1': dropped_p1,
    }

    filepath = os.path.join(archive_dir, f"seo_weekly_{report_date}.json")
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"💾 JSON archive: {filepath}")
    return filepath


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='📊 Weekly SEO Report Generator — Beauty Connect Shop'
    )
    parser.add_argument('--site', default='https://beautyconnectshop.com/',
                        help='GSC site URL (default: https://beautyconnectshop.com/)')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days per period (default: 7)')
    args = parser.parse_args()

    site = args.site
    days = args.days
    data_delay = 3  # GSC data freshness offset

    # Calculate date ranges
    today = datetime.now()
    curr_end = (today - timedelta(days=data_delay)).strftime('%Y-%m-%d')
    curr_start = (today - timedelta(days=data_delay + days)).strftime('%Y-%m-%d')
    prev_end = (today - timedelta(days=data_delay + days + 1)).strftime('%Y-%m-%d')
    prev_start = (today - timedelta(days=data_delay + days * 2 + 1)).strftime('%Y-%m-%d')
    report_date = today.strftime('%Y-%m-%d')

    dates = {
        'curr_start': curr_start,
        'curr_end': curr_end,
        'prev_start': prev_start,
        'prev_end': prev_end,
    }

    logger.info(f"📊 Generating Weekly SEO Report for {site}")
    logger.info(f"   Current:  {curr_start} → {curr_end}")
    logger.info(f"   Previous: {prev_start} → {prev_end}")

    # Initialize GSC client
    gsc = GSCClient()

    # ── Fetch query-level data ──
    curr_query_rows = fetch_period_data(gsc, site, curr_start, curr_end, ['query'])
    prev_query_rows = fetch_period_data(gsc, site, prev_start, prev_end, ['query'])

    curr_query_dict = rows_to_dict(curr_query_rows, key_index=0)
    prev_query_dict = rows_to_dict(prev_query_rows, key_index=0)

    # ── Fetch page-level data ──
    curr_page_rows = fetch_period_data(gsc, site, curr_start, curr_end, ['page'])
    prev_page_rows = fetch_period_data(gsc, site, prev_start, prev_end, ['page'])

    curr_page_dict = rows_to_dict(curr_page_rows, key_index=0)
    prev_page_dict = rows_to_dict(prev_page_rows, key_index=0)

    # ── Aggregate totals ──
    totals_curr = aggregate_totals(curr_query_rows)
    totals_prev = aggregate_totals(prev_query_rows)

    # ── Calculate movers ──
    gainers_q, losers_q, new_queries = calculate_movers(curr_query_dict, prev_query_dict)
    gainers_p, losers_p, _ = calculate_movers(curr_page_dict, prev_page_dict)

    # ── Page 1 changes ──
    entered_p1, dropped_p1 = calculate_page1_changes(curr_query_dict, prev_query_dict)

    # ── Print console report ──
    print_report(totals_curr, totals_prev, dates,
                 gainers_q, losers_q, entered_p1, dropped_p1, new_queries)

    # ── Save JSON archive ──
    json_path = save_json_archive(
        totals_curr, totals_prev, dates,
        gainers_q, losers_q, gainers_p, losers_p,
        entered_p1, dropped_p1, new_queries, report_date
    )

    # ── Export to Google Sheets ──
    sheet_result = export_to_sheets(
        totals_curr, totals_prev, dates,
        gainers_q, losers_q, gainers_p, losers_p,
        entered_p1, dropped_p1, new_queries, report_date
    )

    print()
    print("═" * 50)
    print(f"✅ Weekly SEO Report complete!")
    print(f"   📄 JSON: {json_path}")
    if isinstance(sheet_result, str) and sheet_result.startswith('http'):
        print(f"   📊 Sheet: {sheet_result}")
    else:
        print(f"   📊 CSV fallback: {sheet_result}")
    print("═" * 50)


if __name__ == '__main__':
    main()
