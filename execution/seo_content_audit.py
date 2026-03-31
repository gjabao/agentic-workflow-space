#!/usr/bin/env python3
"""
Beauty Connect Shop — Content SEO Audit
DOE Architecture Execution Script v1.0

Performs a comprehensive content inventory and gap analysis across
blog articles, products, and collections. Cross-references with
Google Search Console data to identify quick wins, content gaps,
and keyword cannibalization.

READ-ONLY — no modifications to Shopify.

Usage:
    python execution/seo_content_audit.py
    python execution/seo_content_audit.py --limit 10
    python execution/seo_content_audit.py --skip-gsc
    python execution/seo_content_audit.py --output csv
"""

import os
import sys
import logging
import argparse
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Import shared utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import (
    ShopifyClient, GoogleSheetsExporter, GSCClient,
    export_to_csv, strip_html, word_count,
    K_BEAUTY_KEYWORDS, BASE_DIR,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('seo_content_audit')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/seo_content_audit.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ─── Blog Inventory ──────────────────────────────────────────────────────────

def audit_blog_articles(articles: List[Dict]) -> Tuple[List[List], List[str]]:
    """Audit all blog articles and return (rows, headers)."""
    headers = [
        'Title', 'Handle', 'Blog', 'Published', 'Tags',
        'Word Count', 'Meta Title', 'Meta Title Length',
        'Meta Description', 'Meta Desc Length',
        'Has Image', 'Image Alt Text',
        'Contains K-Beauty Keywords', 'Flags',
    ]
    rows = []

    for article in articles:
        title = article.get('title', '')
        handle = article.get('handle', '')
        blog_title = (article.get('blog') or {}).get('title', '')
        published = (article.get('publishedAt') or '')[:10]
        tags = ', '.join(article.get('tags', []))
        body = article.get('body') or ''
        wc = word_count(body)

        # Articles don't have an 'seo' field in Shopify Admin API;
        # the article title is used as meta title, summary as meta description
        meta_title = article.get('title') or ''
        meta_desc = strip_html(article.get('summary') or '')

        image = article.get('image') or {}
        has_image = bool(image.get('url'))
        alt_text = image.get('altText') or ''

        # Check K-beauty keywords in title + body
        text_lower = (title + ' ' + strip_html(body)).lower()
        matching_kw = [kw for kw in K_BEAUTY_KEYWORDS if kw.lower() in text_lower]
        has_keywords = len(matching_kw) > 0

        # Flags
        flags = []
        if wc < 500:
            flags.append('THIN')
        if not meta_title or not meta_desc:
            flags.append('MISSING_META')
        if not has_image:
            flags.append('MISSING_IMAGE')
        if has_image and not alt_text:
            flags.append('MISSING_ALT')
        if not has_keywords:
            flags.append('NO_KEYWORDS')

        rows.append([
            title, handle, blog_title, published, tags,
            wc, meta_title, len(meta_title),
            meta_desc, len(meta_desc),
            'Yes' if has_image else 'No', alt_text,
            'Yes' if has_keywords else 'No',
            ', '.join(flags) if flags else 'OK',
        ])

    return rows, headers


# ─── Product Content ─────────────────────────────────────────────────────────

def audit_products(products: List[Dict]) -> Tuple[List[List], List[str]]:
    """Audit all products and return (rows, headers)."""
    headers = [
        'Title', 'Handle', 'Type', 'Vendor',
        'Description Word Count',
        'Meta Title', 'Meta Title Length',
        'Meta Description', 'Meta Desc Length',
        'Image Count', 'Images with Alt Text',
        'Flags',
    ]
    rows = []

    for product in products:
        title = product.get('title', '')
        handle = product.get('handle', '')
        product_type = product.get('productType', '')
        vendor = product.get('vendor', '')
        desc_html = product.get('descriptionHtml') or ''
        wc = word_count(desc_html)

        seo = product.get('seo') or {}
        meta_title = seo.get('title') or ''
        meta_desc = seo.get('description') or ''

        images = product.get('images', {}).get('edges', [])
        image_count = len(images)
        alt_count = sum(1 for img in images if (img.get('node') or {}).get('altText'))

        # Flags
        flags = []
        if wc < 100:
            flags.append('THIN_DESC')
        if not meta_title:
            flags.append('MISSING_META_TITLE')
        if not meta_desc:
            flags.append('MISSING_META_DESC')
        if image_count > 0 and alt_count < image_count:
            flags.append('MISSING_ALT')

        rows.append([
            title, handle, product_type, vendor,
            wc,
            meta_title, len(meta_title),
            meta_desc, len(meta_desc),
            image_count, alt_count,
            ', '.join(flags) if flags else 'OK',
        ])

    return rows, headers


# ─── Collection Content ──────────────────────────────────────────────────────

def audit_collections(collections: List[Dict]) -> Tuple[List[List], List[str]]:
    """Audit all collections and return (rows, headers)."""
    headers = [
        'Title', 'Handle', 'Product Count',
        'Description Word Count',
        'Meta Title', 'Meta Title Length',
        'Meta Description', 'Meta Desc Length',
        'Flags',
    ]
    rows = []

    for collection in collections:
        title = collection.get('title', '')
        handle = collection.get('handle', '')
        products_count_obj = collection.get('productsCount') or {}
        product_count = products_count_obj.get('count', 0)
        desc_html = collection.get('descriptionHtml') or ''
        wc = word_count(desc_html)

        seo = collection.get('seo') or {}
        meta_title = seo.get('title') or ''
        meta_desc = seo.get('description') or ''

        # Flags
        flags = []
        if wc == 0:
            flags.append('NO_DESCRIPTION')
        elif wc < 50:
            flags.append('SHORT_DESC')
        if not meta_title or not meta_desc:
            flags.append('MISSING_META')

        rows.append([
            title, handle, product_count,
            wc,
            meta_title, len(meta_title),
            meta_desc, len(meta_desc),
            ', '.join(flags) if flags else 'OK',
        ])

    return rows, headers


# ─── GSC Analysis ────────────────────────────────────────────────────────────

def analyze_gsc_data(gsc_client: GSCClient, site_url: str) -> Dict:
    """
    Pull GSC data and identify quick wins, low-click pages, and cannibalization.
    Returns dict with 'quick_wins', 'low_click_pages', 'cannibalization', 'all_rows'.
    """
    logger.info("⏳ Fetching GSC data (top 500 queries, last 30 days)...")

    # Fetch query + page data
    rows = gsc_client.query(
        site_url=site_url,
        dimensions=['query', 'page'],
        row_limit=5000,
    )
    logger.info(f"✓ GSC returned {len(rows)} query+page rows")

    # Quick wins: impressions > 50, CTR < 2%, position 5-20
    quick_wins = []
    for row in rows:
        keys = row.get('keys', [])
        query = keys[0] if len(keys) > 0 else ''
        page = keys[1] if len(keys) > 1 else ''
        impressions = row.get('impressions', 0)
        clicks = row.get('clicks', 0)
        ctr = row.get('ctr', 0)
        position = row.get('position', 0)

        if impressions > 50 and ctr < 0.02 and 5 <= position <= 20:
            quick_wins.append({
                'query': query,
                'page': page,
                'impressions': impressions,
                'clicks': clicks,
                'ctr': round(ctr * 100, 2),
                'position': round(position, 1),
            })

    quick_wins.sort(key=lambda x: x['impressions'], reverse=True)
    logger.info(f"✓ Quick wins identified: {len(quick_wins)}")

    # High-impression low-click pages
    page_stats = defaultdict(lambda: {'impressions': 0, 'clicks': 0})
    for row in rows:
        keys = row.get('keys', [])
        page = keys[1] if len(keys) > 1 else ''
        page_stats[page]['impressions'] += row.get('impressions', 0)
        page_stats[page]['clicks'] += row.get('clicks', 0)

    low_click_pages = []
    for page, stats in page_stats.items():
        if stats['impressions'] > 100 and stats['clicks'] < 5:
            low_click_pages.append({
                'page': page,
                'impressions': stats['impressions'],
                'clicks': stats['clicks'],
                'ctr': round((stats['clicks'] / stats['impressions']) * 100, 2) if stats['impressions'] > 0 else 0,
            })

    low_click_pages.sort(key=lambda x: x['impressions'], reverse=True)
    logger.info(f"✓ Low-click pages: {len(low_click_pages)}")

    # Cannibalization: same query appearing on multiple pages
    query_pages = defaultdict(set)
    for row in rows:
        keys = row.get('keys', [])
        query = keys[0] if len(keys) > 0 else ''
        page = keys[1] if len(keys) > 1 else ''
        if row.get('impressions', 0) > 10:
            query_pages[query].add(page)

    cannibalization = []
    for query, pages in query_pages.items():
        if len(pages) > 1:
            cannibalization.append({
                'query': query,
                'page_count': len(pages),
                'pages': ' | '.join(sorted(pages)),
            })

    cannibalization.sort(key=lambda x: x['page_count'], reverse=True)
    logger.info(f"✓ Cannibalization issues: {len(cannibalization)}")

    return {
        'quick_wins': quick_wins,
        'low_click_pages': low_click_pages,
        'cannibalization': cannibalization,
        'all_rows': rows,
    }


# ─── Content Gap Analysis ───────────────────────────────────────────────────

def find_content_gaps(articles: List[Dict], products: List[Dict]) -> List[List]:
    """
    Find K-beauty topics with no matching blog post or product page.
    Returns list of [keyword, status] rows.
    """
    # Combine all content text
    all_text_parts = []
    for article in articles:
        all_text_parts.append((article.get('title') or '').lower())
        all_text_parts.append(strip_html(article.get('body') or '').lower())
        all_text_parts.append(' '.join(article.get('tags', [])).lower())

    for product in products:
        all_text_parts.append((product.get('title') or '').lower())
        all_text_parts.append(strip_html(product.get('descriptionHtml') or '').lower())
        all_text_parts.append(' '.join(product.get('tags', [])).lower())

    all_text = ' '.join(all_text_parts)

    gaps = []
    for kw in K_BEAUTY_KEYWORDS:
        if kw.lower() not in all_text:
            gaps.append([kw, 'NOT COVERED'])

    return gaps


# ─── Export Functions ────────────────────────────────────────────────────────

def export_to_sheets(
    blog_rows, blog_headers,
    product_rows, product_headers,
    collection_rows, collection_headers,
    quick_win_rows, quick_win_headers,
    gap_rows, gap_headers,
    cannibal_rows, cannibal_headers,
    summary_rows, summary_headers,
) -> str:
    """Export all tabs to a single Google Sheet. Returns sheet URL."""
    exporter = GoogleSheetsExporter()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    title = f"BeautyConnect Content Audit — {timestamp}"

    # Create sheet with first tab (Blog Inventory)
    sheet_url = exporter.create_sheet(title, blog_headers, blog_rows)
    sheet_id = sheet_url.split('/d/')[1].split('/')[0]

    # Add remaining tabs
    tabs = [
        ('Product Content', product_headers, product_rows),
        ('Collection Content', collection_headers, collection_rows),
        ('Quick Wins', quick_win_headers, quick_win_rows),
        ('Content Gaps', gap_headers, gap_rows),
        ('Cannibalization', cannibal_headers, cannibal_rows),
        ('Summary', summary_headers, summary_rows),
    ]

    for tab_name, headers, rows in tabs:
        try:
            exporter.add_sheet_tab(sheet_id, tab_name, headers, rows)
        except Exception as e:
            logger.warning(f"⚠ Failed to add tab '{tab_name}': {e}")

    # Rename default Sheet1 to Blog Inventory
    try:
        exporter.service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                'requests': [{
                    'updateSheetProperties': {
                        'properties': {'sheetId': 0, 'title': 'Blog Inventory'},
                        'fields': 'title',
                    }
                }]
            },
        ).execute()
    except Exception as e:
        logger.warning(f"⚠ Could not rename first tab: {e}")

    return sheet_url


def export_all_csv(
    blog_rows, blog_headers,
    product_rows, product_headers,
    collection_rows, collection_headers,
    quick_win_rows, quick_win_headers,
    gap_rows, gap_headers,
    cannibal_rows, cannibal_headers,
    summary_rows, summary_headers,
) -> str:
    """Export all data to CSV files. Returns directory path."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = f"content_audit_{ts}"

    paths = []
    datasets = [
        ('blog_inventory', blog_headers, blog_rows),
        ('product_content', product_headers, product_rows),
        ('collection_content', collection_headers, collection_rows),
        ('quick_wins', quick_win_headers, quick_win_rows),
        ('content_gaps', gap_headers, gap_rows),
        ('cannibalization', cannibal_headers, cannibal_rows),
        ('summary', summary_headers, summary_rows),
    ]

    for name, headers, rows in datasets:
        path = export_to_csv(f"{prefix}_{name}", headers, rows)
        paths.append(path)

    return ', '.join(paths)


# ─── Main ────────────────────────────────────────────────────────────────────

def run_content_audit(args):
    """Main orchestration function."""

    print(f"\n{'='*60}")
    print(f"  Beauty Connect Shop — Content SEO Audit")
    print(f"  Mode: READ-ONLY (no Shopify modifications)")
    print(f"  GSC: {'SKIP' if args.skip_gsc else 'ENABLED'}")
    print(f"  Output: {args.output.upper()}")
    print(f"{'='*60}\n")

    # ── Initialize Shopify client
    shopify = ShopifyClient()

    # ── A. Content Inventory ──────────────────────────────────────────────────

    # 1. Blog Articles
    print("⏳ Fetching blog articles...")
    articles = shopify.fetch_all_blog_articles(limit=args.limit)
    blog_rows, blog_headers = audit_blog_articles(articles)
    thin_blogs = sum(1 for r in blog_rows if 'THIN' in r[-1])
    print(f"✓ Blog articles: {len(articles)} (thin: {thin_blogs})")

    # 2. Products
    print("⏳ Fetching products...")
    products = shopify.fetch_all_products(limit=args.limit)
    product_rows, product_headers = audit_products(products)
    missing_meta_products = sum(1 for r in product_rows if 'MISSING_META' in r[-1])
    print(f"✓ Products: {len(products)} (missing meta: {missing_meta_products})")

    # 3. Collections
    print("⏳ Fetching collections...")
    collections = shopify.fetch_all_collections(limit=args.limit)
    collection_rows, collection_headers = audit_collections(collections)
    no_desc_collections = sum(1 for r in collection_rows if 'NO_DESCRIPTION' in r[-1])
    print(f"✓ Collections: {len(collections)} (no description: {no_desc_collections})")

    # ── B. GSC Cross-Reference ────────────────────────────────────────────────

    quick_win_headers = ['Query', 'Page', 'Impressions', 'Clicks', 'CTR (%)', 'Position']
    quick_win_rows = []
    cannibal_headers = ['Query', 'Page Count', 'Pages']
    cannibal_rows = []
    gsc_data = None

    if not args.skip_gsc:
        try:
            site_url = os.getenv('GSC_SITE_URL', '')
            if not site_url:
                logger.warning("⚠ GSC_SITE_URL not set in .env — skipping GSC analysis")
            else:
                gsc_client = GSCClient()
                gsc_data = analyze_gsc_data(gsc_client, site_url)

                # Quick wins rows
                for qw in gsc_data['quick_wins']:
                    quick_win_rows.append([
                        qw['query'], qw['page'],
                        qw['impressions'], qw['clicks'],
                        qw['ctr'], qw['position'],
                    ])

                # Cannibalization rows
                for c in gsc_data['cannibalization']:
                    cannibal_rows.append([
                        c['query'], c['page_count'], c['pages'],
                    ])

        except Exception as e:
            logger.error(f"⚠ GSC analysis failed: {e}")
            logger.info("   Continuing without GSC data...")
    else:
        print("⏭ Skipping GSC analysis (--skip-gsc)")

    # ── C. Content Gap Analysis ───────────────────────────────────────────────

    print("⏳ Analyzing content gaps...")
    gap_data = find_content_gaps(articles, products)
    gap_headers = ['Keyword / Topic', 'Status']
    gap_rows = gap_data
    print(f"✓ Content gaps: {len(gap_rows)} topics not covered")

    # ── Summary Tab ───────────────────────────────────────────────────────────

    summary_headers = ['Metric', 'Value']

    # Compute averages
    blog_wc_avg = round(sum(r[5] for r in blog_rows) / len(blog_rows), 1) if blog_rows else 0
    product_wc_avg = round(sum(r[4] for r in product_rows) / len(product_rows), 1) if product_rows else 0

    summary_rows = [
        ['Total Blog Articles', len(articles)],
        ['Thin Articles (<500 words)', thin_blogs],
        ['Avg Blog Word Count', blog_wc_avg],
        ['Blogs Missing Meta', sum(1 for r in blog_rows if 'MISSING_META' in r[-1])],
        ['Blogs Missing Image', sum(1 for r in blog_rows if 'MISSING_IMAGE' in r[-1])],
        ['Blogs No Keywords', sum(1 for r in blog_rows if 'NO_KEYWORDS' in r[-1])],
        ['', ''],
        ['Total Products', len(products)],
        ['Thin Descriptions (<100 words)', sum(1 for r in product_rows if 'THIN_DESC' in r[-1])],
        ['Avg Product Desc Word Count', product_wc_avg],
        ['Products Missing Meta Title', sum(1 for r in product_rows if 'MISSING_META_TITLE' in r[-1])],
        ['Products Missing Meta Desc', sum(1 for r in product_rows if 'MISSING_META_DESC' in r[-1])],
        ['Products Missing Alt Text', sum(1 for r in product_rows if 'MISSING_ALT' in r[-1])],
        ['', ''],
        ['Total Collections', len(collections)],
        ['Collections No Description', no_desc_collections],
        ['Collections Missing Meta', sum(1 for r in collection_rows if 'MISSING_META' in r[-1])],
        ['Collections Short Desc (<50)', sum(1 for r in collection_rows if 'SHORT_DESC' in r[-1])],
        ['', ''],
        ['Quick Wins (GSC)', len(quick_win_rows)],
        ['Content Gaps', len(gap_rows)],
        ['Cannibalization Issues', len(cannibal_rows)],
        ['', ''],
        ['Audit Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]

    # ── Export ────────────────────────────────────────────────────────────────

    export_args = (
        blog_rows, blog_headers,
        product_rows, product_headers,
        collection_rows, collection_headers,
        quick_win_rows, quick_win_headers,
        gap_rows, gap_headers,
        cannibal_rows, cannibal_headers,
        summary_rows, summary_headers,
    )

    output_location = ''
    if args.output == 'sheets':
        print("\n⏳ Exporting to Google Sheets...")
        try:
            output_location = export_to_sheets(*export_args)
            print(f"✓ Google Sheet: {output_location}")
        except Exception as e:
            logger.error(f"⚠ Google Sheets export failed: {e}")
            print("⚠ Falling back to CSV...")
            output_location = export_all_csv(*export_args)
            print(f"✓ CSV files: {output_location}")
    else:
        print("\n⏳ Exporting to CSV...")
        output_location = export_all_csv(*export_args)
        print(f"✓ CSV files: {output_location}")

    # ── Summary Print ─────────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"  ✅ CONTENT AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"  Blog articles:          {len(articles)} (thin: {thin_blogs})")
    print(f"  Products:               {len(products)} (missing meta: {missing_meta_products})")
    print(f"  Collections:            {len(collections)} (no description: {no_desc_collections})")
    print(f"  Quick wins identified:  {len(quick_win_rows)}")
    print(f"  Content gaps:           {len(gap_rows)} topics")
    print(f"  Cannibalization issues: {len(cannibal_rows)}")
    print(f"  Output:                 {output_location}")
    print(f"{'='*60}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Beauty Connect Shop — Content SEO Audit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/seo_content_audit.py
  python execution/seo_content_audit.py --limit 10
  python execution/seo_content_audit.py --skip-gsc
  python execution/seo_content_audit.py --output csv
        """,
    )
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of items to fetch per content type (default: all)')
    parser.add_argument('--skip-gsc', action='store_true',
                        help='Skip Google Search Console analysis')
    parser.add_argument('--output', type=str, choices=['sheets', 'csv'], default='sheets',
                        help='Output format: sheets or csv (default: sheets)')

    args = parser.parse_args()
    run_content_audit(args)


if __name__ == '__main__':
    main()
