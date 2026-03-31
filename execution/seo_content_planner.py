#!/usr/bin/env python3
"""
SEO Content Planner — Beauty Connect Shop
DOE Architecture: Execution layer

Plans and schedules blog content based on GSC data, existing content inventory,
and AI-powered topic clustering via Azure OpenAI.

Usage:
    python execution/seo_content_planner.py [--months 3] [--skip-gsc] [--skip-ai] [--output sheets|csv]

Requires:
    AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
    SHOPIFY_STORE_URL, SHOPIFY_ADMIN_API_TOKEN
    GSC_SITE_URL (e.g. sc-domain:beautyconnectshop.com)
    credentials.json + token_gsc.pickle (for GSC)
    credentials.json + token.json (for Google Sheets)
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# ─── Shared imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    GSCClient,
    export_to_csv,
    K_BEAUTY_KEYWORDS,
    strip_html,
    BASE_DIR,
    logger,
)

# ─── Constants ───────────────────────────────────────────────────────────────
GSC_SITE_URL = os.getenv('GSC_SITE_URL', 'sc-domain:beautyconnectshop.com')
QUESTION_MARKERS = ["how", "what", "why", "best", "vs"]
IMPRESSION_THRESHOLD = 100
POSITION_THRESHOLD = 10  # Not on page 1
ARTICLES_PER_WEEK = 2
PUBLISH_DAYS = [0, 3]  # Monday=0, Thursday=3

CONTENT_MIX = {
    "evergreen": 0.70,
    "trending": 0.20,
    "promotional": 0.10,
}


# ─── Data Gathering ─────────────────────────────────────────────────────────

def fetch_gsc_queries(days: int = 90, row_limit: int = 1000) -> List[Dict]:
    """Pull top GSC queries by impressions for the last N days."""
    logger.info(f"📊 Fetching GSC queries (last {days} days, top {row_limit})...")
    try:
        gsc = GSCClient()
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        rows = gsc.query(
            site_url=GSC_SITE_URL,
            start_date=start_date,
            end_date=end_date,
            dimensions=['query'],
            row_limit=row_limit,
        )
        queries = []
        for row in rows:
            queries.append({
                'query': row['keys'][0],
                'clicks': row.get('clicks', 0),
                'impressions': row.get('impressions', 0),
                'ctr': round(row.get('ctr', 0) * 100, 2),
                'position': round(row.get('position', 0), 1),
            })
        # Sort by impressions descending
        queries.sort(key=lambda x: x['impressions'], reverse=True)
        logger.info(f"✅ Retrieved {len(queries)} GSC queries")
        return queries
    except Exception as e:
        logger.error(f"❌ GSC fetch failed: {e}")
        return []


def fetch_gsc_trending(days: int = 90) -> List[Dict]:
    """Identify queries with increasing impressions over the period.

    Compares the first half vs second half of the date range.
    """
    logger.info("📈 Identifying trending queries...")
    try:
        gsc = GSCClient()
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        mid_date = (datetime.now() - timedelta(days=3 + days // 2)).strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        first_half = gsc.query(
            site_url=GSC_SITE_URL,
            start_date=start_date,
            end_date=mid_date,
            dimensions=['query'],
            row_limit=5000,
        )
        second_half = gsc.query(
            site_url=GSC_SITE_URL,
            start_date=mid_date,
            end_date=end_date,
            dimensions=['query'],
            row_limit=5000,
        )

        first_map = {r['keys'][0]: r.get('impressions', 0) for r in first_half}
        second_map = {r['keys'][0]: r.get('impressions', 0) for r in second_half}

        trending = []
        for query, imp2 in second_map.items():
            imp1 = first_map.get(query, 0)
            if imp2 > imp1 and imp2 >= 20:
                growth = ((imp2 - imp1) / max(imp1, 1)) * 100
                if growth >= 30:  # At least 30% growth
                    trending.append({
                        'query': query,
                        'impressions_first_half': imp1,
                        'impressions_second_half': imp2,
                        'growth_pct': round(growth, 1),
                    })
        trending.sort(key=lambda x: x['growth_pct'], reverse=True)
        logger.info(f"✅ Found {len(trending)} trending queries")
        return trending
    except Exception as e:
        logger.error(f"❌ Trending analysis failed: {e}")
        return []


def fetch_existing_articles() -> List[Dict]:
    """Fetch all blog articles from Shopify."""
    logger.info("📝 Fetching existing blog articles from Shopify...")
    try:
        shopify = ShopifyClient()
        articles = shopify.fetch_all_blog_articles()
        logger.info(f"✅ Found {len(articles)} existing blog articles")
        return articles
    except Exception as e:
        logger.error(f"❌ Shopify article fetch failed: {e}")
        return []


# ─── Opportunity Identification ──────────────────────────────────────────────

def identify_high_impression_gaps(queries: List[Dict]) -> List[Dict]:
    """Queries with >100 impressions but position >10 (not on page 1)."""
    gaps = [
        q for q in queries
        if q['impressions'] > IMPRESSION_THRESHOLD and q['position'] > POSITION_THRESHOLD
    ]
    gaps.sort(key=lambda x: x['impressions'], reverse=True)
    logger.info(f"🔍 High-impression gaps: {len(gaps)} queries")
    return gaps


def identify_question_queries(queries: List[Dict]) -> List[Dict]:
    """Queries containing question words — great for blog posts."""
    questions = []
    for q in queries:
        query_lower = q['query'].lower()
        if any(marker in query_lower.split() for marker in QUESTION_MARKERS):
            questions.append(q)
    questions.sort(key=lambda x: x['impressions'], reverse=True)
    logger.info(f"❓ Question queries: {len(questions)} found")
    return questions


def identify_uncovered_keywords(articles: List[Dict]) -> List[str]:
    """K_BEAUTY_KEYWORDS not matching any existing blog post title."""
    existing_titles_lower = set()
    for article in articles:
        title = (article.get('title') or '').lower()
        existing_titles_lower.add(title)
        # Also check SEO title
        seo_title = (article.get('seo', {}) or {}).get('title', '') or ''
        if seo_title:
            existing_titles_lower.add(seo_title.lower())

    # Combine all existing title text for substring matching
    all_titles_text = ' '.join(existing_titles_lower)

    uncovered = []
    for kw in K_BEAUTY_KEYWORDS:
        if kw.lower() not in all_titles_text:
            uncovered.append(kw)

    logger.info(f"🆕 Uncovered keywords: {len(uncovered)} of {len(K_BEAUTY_KEYWORDS)}")
    return uncovered


# ─── AI Topic Generation ────────────────────────────────────────────────────

def generate_topic_clusters(
    gaps: List[Dict],
    questions: List[Dict],
    uncovered: List[str],
    trending: List[Dict],
    existing_articles: List[Dict],
) -> List[Dict]:
    """Use Azure OpenAI to organize opportunities into pillar/cluster topics."""
    logger.info("🤖 Generating topic clusters with Azure OpenAI...")

    from openai import AzureOpenAI

    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    if not azure_key or not azure_endpoint:
        logger.error("❌ AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT not set in .env")
        return []

    client = AzureOpenAI(
        api_key=azure_key,
        api_version="2024-12-01-preview",
        azure_endpoint=azure_endpoint,
    )
    del azure_key  # Clear from memory

    # Prepare context for the prompt
    top_gaps = [f"- \"{g['query']}\" ({g['impressions']} imp, pos {g['position']})" for g in gaps[:20]]
    top_questions = [f"- \"{q['query']}\" ({q['impressions']} imp)" for q in questions[:15]]
    top_uncovered = [f"- {kw}" for kw in uncovered[:20]]
    top_trending = [f"- \"{t['query']}\" (+{t['growth_pct']}%)" for t in trending[:10]]
    existing_titles = [f"- {a.get('title', 'Untitled')}" for a in existing_articles[:30]]

    prompt = f"""You are an SEO content strategist for Beauty Connect Shop, a Canadian K-beauty e-commerce store
targeting professional estheticians and skincare enthusiasts.

Based on the following search data, create 3 pillar topic clusters with 8-12 cluster articles each.

## High-Impression Content Gaps (ranking outside page 1):
{chr(10).join(top_gaps) if top_gaps else "No data available"}

## Question Queries (blog-worthy):
{chr(10).join(top_questions) if top_questions else "No data available"}

## Uncovered K-Beauty Keywords (no existing content):
{chr(10).join(top_uncovered) if top_uncovered else "All keywords covered"}

## Trending Queries (growing impressions):
{chr(10).join(top_trending) if top_trending else "No trending data"}

## Existing Blog Articles (avoid duplicates):
{chr(10).join(existing_titles) if existing_titles else "No existing articles"}

For each article, provide:
1. title: SEO-optimized, 50-60 characters
2. target_keyword: primary keyword to rank for
3. content_type: pillar / cluster / FAQ / comparison
4. word_count: target word count (1500-3000 for pillar, 800-1500 for cluster, 600-1000 for FAQ)
5. priority: high / medium / low (based on search volume and competition)
6. internal_link_targets: which product collections or pages to link to

Return ONLY valid JSON in this exact format:
{{
  "pillars": [
    {{
      "pillar_topic": "Pillar Topic Name",
      "pillar_keyword": "main keyword",
      "articles": [
        {{
          "title": "Article Title Here",
          "target_keyword": "target keyword",
          "content_type": "pillar",
          "word_count": 2500,
          "priority": "high",
          "internal_link_targets": ["collections/serums", "products/snail-mucin"]
        }}
      ]
    }}
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {"role": "system", "content": "You are an SEO content strategist. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)
        pillars = data.get('pillars', [])
        total_articles = sum(len(p.get('articles', [])) for p in pillars)
        logger.info(f"✅ Generated {len(pillars)} pillars with {total_articles} total articles")
        return pillars
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse AI response as JSON: {e}")
        logger.debug(f"Raw response: {raw[:500]}")
        return []
    except Exception as e:
        logger.error(f"❌ Azure OpenAI call failed: {e}")
        return []


# ─── Content Calendar Builder ────────────────────────────────────────────────

def build_content_calendar(
    pillars: List[Dict],
    months: int = 3,
) -> List[Dict]:
    """Distribute articles across months with 2/week cadence on Mon & Thu."""
    logger.info(f"📅 Building {months}-month content calendar ({ARTICLES_PER_WEEK}/week)...")

    # Collect all articles from pillars and tag with pillar info
    all_articles = []
    for pillar in pillars:
        pillar_topic = pillar.get('pillar_topic', 'Unknown')
        for article in pillar.get('articles', []):
            article['pillar_topic'] = pillar_topic
            all_articles.append(article)

    if not all_articles:
        logger.warning("⚠ No articles to schedule")
        return []

    # Sort: high priority first, then pillar content first
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    type_order = {'pillar': 0, 'cluster': 1, 'comparison': 2, 'FAQ': 3, 'faq': 3}
    all_articles.sort(key=lambda a: (
        priority_order.get(a.get('priority', 'medium'), 1),
        type_order.get(a.get('content_type', 'cluster'), 1),
    ))

    # Assign content mix tags
    total = len(all_articles)
    n_evergreen = int(total * CONTENT_MIX['evergreen'])
    n_trending = int(total * CONTENT_MIX['trending'])
    # Remainder goes to promotional
    for i, article in enumerate(all_articles):
        if i < n_evergreen:
            article['content_category'] = 'evergreen'
        elif i < n_evergreen + n_trending:
            article['content_category'] = 'trending'
        else:
            article['content_category'] = 'promotional'

    # Generate publish dates (Mon=0, Thu=3) starting next Monday
    today = datetime.now()
    # Find next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    start_date = today + timedelta(days=days_until_monday)

    publish_dates = []
    current = start_date
    end_limit = start_date + timedelta(weeks=months * 4 + 2)
    while current <= end_limit and len(publish_dates) < len(all_articles):
        if current.weekday() in PUBLISH_DAYS:
            publish_dates.append(current)
        current += timedelta(days=1)

    # Build calendar entries
    calendar = []
    for i, article in enumerate(all_articles):
        if i < len(publish_dates):
            pub_date = publish_dates[i]
            week_num = ((pub_date - start_date).days // 7) + 1
        else:
            pub_date = None
            week_num = None

        calendar.append({
            'week': week_num if week_num else f"Backlog",
            'publish_date': pub_date.strftime('%Y-%m-%d') if pub_date else 'TBD',
            'title': article.get('title', 'Untitled'),
            'target_keyword': article.get('target_keyword', ''),
            'content_type': article.get('content_type', 'cluster'),
            'word_count': article.get('word_count', 1000),
            'priority': article.get('priority', 'medium'),
            'status': 'planned',
            'internal_link_targets': ', '.join(article.get('internal_link_targets', [])),
            'pillar_topic': article.get('pillar_topic', ''),
            'content_category': article.get('content_category', 'evergreen'),
        })

    logger.info(f"✅ Calendar built: {len(calendar)} articles scheduled")
    return calendar


# ─── Output ──────────────────────────────────────────────────────────────────

def output_to_sheets(
    calendar: List[Dict],
    pillars: List[Dict],
    gaps: List[Dict],
    articles: List[Dict],
) -> str:
    """Export all data to a multi-tab Google Sheet."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    title = f"Content Calendar — {date_str}"

    logger.info(f"📤 Exporting to Google Sheet: {title}")

    try:
        exporter = GoogleSheetsExporter()

        # Tab 1: Calendar
        cal_headers = [
            'Week', 'Publish Date', 'Title', 'Target Keyword', 'Content Type',
            'Word Count', 'Priority', 'Status', 'Internal Link Targets',
            'Content Category',
        ]
        cal_rows = [
            [
                str(c['week']), c['publish_date'], c['title'], c['target_keyword'],
                c['content_type'], str(c['word_count']), c['priority'],
                c['status'], c['internal_link_targets'], c['content_category'],
            ]
            for c in calendar
        ]
        sheet_url = exporter.create_sheet(title, cal_headers, cal_rows)
        sheet_id = sheet_url.split('/d/')[1].split('/')[0]

        # Tab 2: Topic Clusters
        cluster_headers = ['Pillar Topic', 'Pillar Keyword', 'Article Title', 'Target Keyword', 'Content Type']
        cluster_rows = []
        for pillar in pillars:
            for article in pillar.get('articles', []):
                cluster_rows.append([
                    pillar.get('pillar_topic', ''),
                    pillar.get('pillar_keyword', ''),
                    article.get('title', ''),
                    article.get('target_keyword', ''),
                    article.get('content_type', ''),
                ])
        exporter.add_sheet_tab(sheet_id, 'Topic Clusters', cluster_headers, cluster_rows)

        # Tab 3: Content Gaps
        gap_headers = ['Keyword', 'Current Impressions', 'Current Position', 'CTR (%)', 'Opportunity Score']
        gap_rows = []
        for g in gaps[:100]:
            opp_score = round(g['impressions'] * (g['position'] - 10) / 100, 1)
            gap_rows.append([
                g['query'], str(g['impressions']), str(g['position']),
                str(g['ctr']), str(opp_score),
            ])
        exporter.add_sheet_tab(sheet_id, 'Content Gaps', gap_headers, gap_rows)

        # Tab 4: Existing Content
        inv_headers = ['Title', 'Handle', 'Blog', 'Published At', 'Tags', 'SEO Title']
        inv_rows = []
        for a in articles:
            inv_rows.append([
                a.get('title', ''),
                a.get('handle', ''),
                (a.get('blog') or {}).get('title', ''),
                a.get('publishedAt', ''),
                ', '.join(a.get('tags', [])),
                (a.get('seo') or {}).get('title', ''),
            ])
        exporter.add_sheet_tab(sheet_id, 'Existing Content', inv_headers, inv_rows)

        # Rename default Sheet1 to Calendar
        try:
            exporter.service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    'requests': [{
                        'updateSheetProperties': {
                            'properties': {'sheetId': 0, 'title': 'Calendar'},
                            'fields': 'title',
                        }
                    }]
                }
            ).execute()
        except Exception:
            pass  # Non-critical

        logger.info(f"✅ Google Sheet ready: {sheet_url}")
        return sheet_url
    except Exception as e:
        logger.error(f"❌ Google Sheets export failed: {e}")
        return ""


def output_to_csv(
    calendar: List[Dict],
    pillars: List[Dict],
    gaps: List[Dict],
    articles: List[Dict],
) -> List[str]:
    """Fallback: export all data to CSV files."""
    logger.info("📤 Exporting to CSV files...")
    paths = []

    # Calendar CSV
    cal_headers = [
        'Week', 'Publish Date', 'Title', 'Target Keyword', 'Content Type',
        'Word Count', 'Priority', 'Status', 'Internal Link Targets', 'Content Category',
    ]
    cal_rows = [
        [
            str(c['week']), c['publish_date'], c['title'], c['target_keyword'],
            c['content_type'], str(c['word_count']), c['priority'],
            c['status'], c['internal_link_targets'], c['content_category'],
        ]
        for c in calendar
    ]
    paths.append(export_to_csv('content_calendar', cal_headers, cal_rows))

    # Gaps CSV
    gap_headers = ['Keyword', 'Impressions', 'Position', 'CTR', 'Opportunity Score']
    gap_rows = [
        [g['query'], str(g['impressions']), str(g['position']), str(g['ctr']),
         str(round(g['impressions'] * (g['position'] - 10) / 100, 1))]
        for g in gaps[:100]
    ]
    paths.append(export_to_csv('content_gaps', gap_headers, gap_rows))

    # Clusters CSV
    cluster_headers = ['Pillar Topic', 'Pillar Keyword', 'Article Title', 'Target Keyword', 'Content Type']
    cluster_rows = []
    for pillar in pillars:
        for article in pillar.get('articles', []):
            cluster_rows.append([
                pillar.get('pillar_topic', ''),
                pillar.get('pillar_keyword', ''),
                article.get('title', ''),
                article.get('target_keyword', ''),
                article.get('content_type', ''),
            ])
    paths.append(export_to_csv('topic_clusters', cluster_headers, cluster_rows))

    logger.info(f"✅ CSV files exported: {len(paths)} files")
    return paths


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🗓️ SEO Content Planner — Beauty Connect Shop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/seo_content_planner.py
  python execution/seo_content_planner.py --months 6 --output csv
  python execution/seo_content_planner.py --skip-gsc --skip-ai --output csv
        """,
    )
    parser.add_argument('--months', type=int, default=3, help='Number of months to plan (default: 3)')
    parser.add_argument('--skip-gsc', action='store_true', help='Skip GSC data fetch (use empty data)')
    parser.add_argument('--skip-ai', action='store_true', help='Skip AI topic generation (use raw opportunities)')
    parser.add_argument('--output', choices=['sheets', 'csv'], default='sheets', help='Output format (default: sheets)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🗓️ SEO Content Planner — Beauty Connect Shop")
    logger.info(f"   Months: {args.months} | Output: {args.output}")
    logger.info(f"   Skip GSC: {args.skip_gsc} | Skip AI: {args.skip_ai}")
    logger.info("=" * 60)

    # ─── Step 1: Gather data ─────────────────────────────────────────────
    gsc_queries = []
    trending = []
    if not args.skip_gsc:
        gsc_queries = fetch_gsc_queries(days=90, row_limit=1000)
        trending = fetch_gsc_trending(days=90)

    existing_articles = fetch_existing_articles()

    # ─── Step 2: Identify opportunities ──────────────────────────────────
    gaps = identify_high_impression_gaps(gsc_queries)
    questions = identify_question_queries(gsc_queries)
    uncovered = identify_uncovered_keywords(existing_articles)

    total_opps = len(gaps) + len(questions) + len(uncovered) + len(trending)
    logger.info(f"📋 Total opportunities identified: {total_opps}")
    logger.info(f"   Gaps: {len(gaps)} | Questions: {len(questions)} | Uncovered: {len(uncovered)} | Trending: {len(trending)}")

    # ─── Step 3: Generate topic clusters ─────────────────────────────────
    if not args.skip_ai:
        pillars = generate_topic_clusters(gaps, questions, uncovered, trending, existing_articles)
    else:
        logger.info("⏭️ Skipping AI — building pillars from raw opportunities")
        # Fallback: create simple pillars from uncovered keywords
        articles_from_gaps = [
            {
                'title': f"Guide to {g['query'].title()}"[:60],
                'target_keyword': g['query'],
                'content_type': 'cluster',
                'word_count': 1200,
                'priority': 'high' if g['impressions'] > 500 else 'medium',
                'internal_link_targets': [],
            }
            for g in gaps[:12]
        ]
        articles_from_questions = [
            {
                'title': q['query'].capitalize()[:60],
                'target_keyword': q['query'],
                'content_type': 'FAQ',
                'word_count': 800,
                'priority': 'medium',
                'internal_link_targets': [],
            }
            for q in questions[:12]
        ]
        articles_from_uncovered = [
            {
                'title': f"{kw} — Complete Guide"[:60],
                'target_keyword': kw.lower(),
                'content_type': 'cluster',
                'word_count': 1000,
                'priority': 'medium',
                'internal_link_targets': [],
            }
            for kw in uncovered[:12]
        ]
        pillars = [
            {
                'pillar_topic': 'Content Gap Opportunities',
                'pillar_keyword': 'k-beauty skincare',
                'articles': articles_from_gaps,
            },
            {
                'pillar_topic': 'FAQ & Question Content',
                'pillar_keyword': 'korean skincare questions',
                'articles': articles_from_questions,
            },
            {
                'pillar_topic': 'Uncovered Keywords',
                'pillar_keyword': 'k-beauty ingredients',
                'articles': articles_from_uncovered,
            },
        ]

    if not pillars:
        logger.error("❌ No topic clusters generated. Exiting.")
        sys.exit(1)

    # ─── Step 4: Build content calendar ──────────────────────────────────
    calendar = build_content_calendar(pillars, months=args.months)

    if not calendar:
        logger.error("❌ No calendar entries generated. Exiting.")
        sys.exit(1)

    # ─── Step 5: Export ──────────────────────────────────────────────────
    if args.output == 'sheets':
        url = output_to_sheets(calendar, pillars, gaps, existing_articles)
        if url:
            logger.info(f"\n🎉 Done! Content Calendar: {url}")
        else:
            logger.warning("⚠ Sheets export failed — falling back to CSV")
            paths = output_to_csv(calendar, pillars, gaps, existing_articles)
            for p in paths:
                logger.info(f"   📄 {p}")
    else:
        paths = output_to_csv(calendar, pillars, gaps, existing_articles)
        logger.info(f"\n🎉 Done! {len(paths)} CSV files exported:")
        for p in paths:
            logger.info(f"   📄 {p}")

    # Summary
    total_articles = sum(len(p.get('articles', [])) for p in pillars)
    logger.info(f"\n📊 Summary:")
    logger.info(f"   Pillars: {len(pillars)}")
    logger.info(f"   Total articles planned: {total_articles}")
    logger.info(f"   Scheduled: {len([c for c in calendar if c['publish_date'] != 'TBD'])}")
    logger.info(f"   Backlog: {len([c for c in calendar if c['publish_date'] == 'TBD'])}")
    logger.info(f"   Date range: {calendar[0]['publish_date']} → {calendar[-1]['publish_date']}")


if __name__ == '__main__':
    main()
