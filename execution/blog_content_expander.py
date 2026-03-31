#!/usr/bin/env python3
"""
Blog Content Expander — Beauty Connect Shop
Expands thin/short blog posts to 1,000+ words using Anthropic Claude API.

Usage:
    python execution/blog_content_expander.py --dry-run
    python execution/blog_content_expander.py --push-live
"""

import os
import sys
import json
import logging
import time
import argparse
import requests
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import ShopifyClient, GoogleSheetsExporter, strip_html, word_count, BASE_DIR

os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('blog_expander')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/blog_content_expander.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

MIN_WORD_COUNT = 1000

# Article IDs to expand (all under 1000 words)
SHORT_ARTICLE_IDS = [
    "gid://shopify/Article/736325599347",  # Zena Algae Peel (429w)
    "gid://shopify/Article/736325632115",  # 10-Step Routine (613w)
    "gid://shopify/Article/736326090867",  # KrX Undereye Darts (509w)
    "gid://shopify/Article/736326385779",  # Integrating K-Skincare (518w)
    "gid://shopify/Article/737735737459",  # Corneotherapy Corthe (692w)
    "gid://shopify/Article/738430484595",  # K-Skincare Essentials (544w)
    "gid://shopify/Article/738492612723",  # Summer-Safe Skincare (562w)
    "gid://shopify/Article/740831658099",  # Mela Cold Pro (499w)
]


def generate_expanded_content(title: str, existing_body: str, current_wc: int) -> str:
    """Use Claude to expand blog content to 1000+ words."""
    api_key = os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.error("No ANTHROPIC_API_KEY found")
        return ""

    additional_needed = max(MIN_WORD_COUNT - current_wc, 400)
    clean_body = existing_body  # Keep HTML

    prompt = f"""You are an SEO content writer for Beauty Connect Shop (beautyconnectshop.com), a Canadian K-beauty professional skincare distributor.

Expand the following blog article to at least {MIN_WORD_COUNT} words (currently {current_wc} words). You need to add approximately {additional_needed} more words.

RULES:
1. Keep ALL existing content — do not remove or rewrite what's already there
2. Add new sections that deepen the topic with professional insights
3. Use proper HTML formatting: <h2>, <h3>, <p>, <ul>/<li>, <strong>
4. Include at least 3 internal links to beautyconnectshop.com collections/products
5. Add a FAQ section at the end with 3-4 questions using <h3> tags
6. CRITICAL: No Health Canada therapeutic claims (no "treats", "cures", "heals", "prevents disease"). Use cosmetic-safe language: "may help improve the appearance of", "supports", "enhances"
7. Write for professional estheticians and skincare practitioners
8. Target keywords should be naturally integrated
9. Return ONLY the full expanded HTML body (no markdown, no code fences)

ARTICLE TITLE: {title}

CURRENT BODY:
{clean_body}

Return the complete expanded article body in HTML. Keep all existing paragraphs and add new content seamlessly."""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data['content'][0]['text'].strip()
            # Remove any markdown code fences if present
            if content.startswith('```'):
                content = '\n'.join(content.split('\n')[1:])
            if content.endswith('```'):
                content = '\n'.join(content.split('\n')[:-1])
            return content
        except Exception as e:
            logger.error(f"Claude attempt {attempt+1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    return ""


def update_article_body(client: ShopifyClient, article_id: str, body: str) -> bool:
    """Update article body via GraphQL."""
    mutation = """
    mutation ArticleUpdate($id: ID!, $article: ArticleUpdateInput!) {
      articleUpdate(id: $id, article: $article) {
        article {
          id
          title
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {"id": article_id, "article": {"body": body}}
    data = client._graphql(mutation, variables)

    if not data:
        return False

    result = data.get('articleUpdate', {})
    errors = result.get('userErrors', [])
    if errors:
        logger.error(f"Update errors: {errors}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Expand thin blog content')
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--push-live', action='store_true')
    args = parser.parse_args()

    if args.push_live:
        args.dry_run = False

    mode = "DRY-RUN" if args.dry_run else "PUSH LIVE"
    print(f"\n{'='*60}")
    print(f"  Blog Content Expander — Beauty Connect Shop")
    print(f"  Mode: {mode}")
    print(f"  Target: {MIN_WORD_COUNT}+ words per article")
    print(f"{'='*60}\n")

    client = ShopifyClient()
    articles = client.fetch_all_blog_articles()

    # Filter to short articles
    short_articles = [a for a in articles if a['id'] in SHORT_ARTICLE_IDS]
    print(f"✓ Found {len(short_articles)} articles to expand\n")

    results = []

    for i, article in enumerate(short_articles):
        title = article['title']
        article_id = article['id']
        body = article.get('body', '') or ''
        current_wc = word_count(body)

        print(f"⏳ [{i+1}/{len(short_articles)}] {title[:55]}... ({current_wc}w)")

        expanded = generate_expanded_content(title, body, current_wc)
        if not expanded:
            print(f"   ❌ Failed to generate expanded content")
            results.append([title, current_wc, current_wc, 'FAILED'])
            continue

        new_wc = word_count(expanded)
        print(f"   ✓ Expanded: {current_wc}w → {new_wc}w (+{new_wc - current_wc}w)")

        if new_wc < MIN_WORD_COUNT:
            print(f"   ⚠ Still under {MIN_WORD_COUNT}w, but better than before")

        if not args.dry_run:
            success = update_article_body(client, article_id, expanded)
            if success:
                print(f"   ✅ Pushed to Shopify")
                results.append([title, current_wc, new_wc, 'PUSHED'])
            else:
                print(f"   ❌ Push failed")
                results.append([title, current_wc, new_wc, 'PUSH_FAILED'])
            time.sleep(1)
        else:
            results.append([title, current_wc, new_wc, 'DRY_RUN'])

        # Save expanded content locally for review
        safe_handle = article.get('handle', 'unknown')[:50]
        with open(f".tmp/expanded_{safe_handle}.html", 'w') as f:
            f.write(expanded)
        print(f"   📁 Saved: .tmp/expanded_{safe_handle}.html")

        time.sleep(2)  # Rate limit between articles

    # Export to Google Sheets
    print(f"\n⏳ Exporting to Google Sheets...")
    try:
        sheets = GoogleSheetsExporter()
        headers = ['Article Title', 'Before (words)', 'After (words)', 'Status']
        sheet_url = sheets.create_sheet(
            title=f"Blog Expansion — {mode} — {time.strftime('%Y-%m-%d %H:%M')}",
            headers=headers,
            rows=results,
        )
        print(f"✓ Sheet: {sheet_url}")
    except Exception as e:
        logger.warning(f"Sheets failed: {e}")
        sheet_url = "N/A"

    print(f"\n{'='*60}")
    print(f"  ✅ PHASE 2 COMPLETE ({mode})")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r[0][:45]:45s} {r[1]:>5}w → {r[2]:>5}w  {r[3]}")
    print(f"  Report: {sheet_url}")
    if args.dry_run:
        print(f"\n  ⚠ DRY-RUN — content saved locally in .tmp/")
        print(f"  Run with --push-live to apply.")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
