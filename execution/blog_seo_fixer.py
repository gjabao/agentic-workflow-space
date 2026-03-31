#!/usr/bin/env python3
"""
Blog SEO Fixer — Beauty Connect Shop
Fixes: missing meta descriptions (summary), missing image alt text
Uses Anthropic Claude API to generate SEO-optimized content,
then pushes via Shopify Admin API.

Usage:
    python execution/blog_seo_fixer.py --dry-run       # Preview changes
    python execution/blog_seo_fixer.py --push-live      # Apply changes
"""

import os
import sys
import json
import logging
import time
import argparse
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import ShopifyClient, GoogleSheetsExporter, strip_html, word_count, BASE_DIR

os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('blog_seo_fixer')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/blog_seo_fixer.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

# ─── AI Content Generation ──────────────────────────────────────────────────

def generate_with_anthropic(prompt: str) -> str:
    """Generate content using Anthropic Claude API."""
    api_key = os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY found")
        return ""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data['content'][0]['text'].strip()
        except Exception as e:
            logger.warning(f"Anthropic attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return ""


def generate_batch_descriptions(articles_data: List[Dict]) -> Dict[str, Dict]:
    """Generate meta descriptions and alt text for multiple articles in fewer API calls."""
    results = {}

    for article in articles_data:
        title = article['title']
        article_id = article['id']
        snippet = strip_html(article.get('body', ''))[:400]
        needs_desc = article.get('needs_desc', False)
        needs_alt = article.get('needs_alt', False)

        parts = []
        if needs_desc:
            parts.append("META_DESCRIPTION")
        if needs_alt:
            parts.append("ALT_TEXT")

        prompt = f"""Generate SEO content for a blog on beautyconnectshop.com (Canadian K-beauty professional skincare).

Article: "{title}"
Content preview: {snippet}

Generate the following (return ONLY the requested items, no extra text):
"""
        if needs_desc:
            prompt += """
META_DESCRIPTION: Write exactly 140-155 characters. Include primary keyword. Compelling, click-worthy. No therapeutic claims (no "treats/cures/heals"). Return on one line after "META_DESCRIPTION: "
"""
        if needs_alt:
            prompt += """
ALT_TEXT: Write 50-100 characters for the featured image. Descriptive, keyword-rich. No "image of" prefix. Return on one line after "ALT_TEXT: "
"""

        response = generate_with_anthropic(prompt)
        if not response:
            results[article_id] = {'desc': '', 'alt': ''}
            continue

        desc = ''
        alt = ''
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('META_DESCRIPTION:'):
                desc = line.replace('META_DESCRIPTION:', '').strip().strip('"\'')
                if len(desc) > 160:
                    desc = desc[:157] + "..."
            elif line.startswith('ALT_TEXT:'):
                alt = line.replace('ALT_TEXT:', '').strip().strip('"\'')
                if len(alt) > 125:
                    alt = alt[:122] + "..."

        results[article_id] = {'desc': desc, 'alt': alt}
        time.sleep(0.2)  # Rate limit

    return results


# ─── Shopify Update ─────────────────────────────────────────────────────────

def update_article(client: ShopifyClient, article_id: str, updates: Dict) -> bool:
    """Update a blog article via GraphQL articleUpdate mutation."""
    mutation = """
    mutation ArticleUpdate($id: ID!, $article: ArticleUpdateInput!) {
      articleUpdate(id: $id, article: $article) {
        article {
          id
          title
          summary
          image {
            altText
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {"id": article_id, "article": updates}
    data = client._graphql(mutation, variables)

    if not data:
        return False

    result = data.get('articleUpdate', {})
    errors = result.get('userErrors', [])
    if errors:
        logger.error(f"Update errors for {article_id}: {errors}")
        return False

    return True


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Fix blog SEO issues')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview changes without pushing')
    parser.add_argument('--push-live', action='store_true', help='Apply changes to Shopify')
    args = parser.parse_args()

    if args.push_live:
        args.dry_run = False

    mode = "DRY-RUN" if args.dry_run else "PUSH LIVE"
    print(f"\n{'='*60}")
    print(f"  Blog SEO Fixer — Beauty Connect Shop")
    print(f"  Mode: {mode}")
    print(f"{'='*60}\n")

    client = ShopifyClient()
    articles = client.fetch_all_blog_articles()
    print(f"✓ Fetched {len(articles)} articles\n")

    # Identify articles needing fixes
    to_fix = []
    for article in articles:
        summary = article.get('summary', '') or ''
        image = article.get('image') or {}
        alt_text = image.get('altText', '') or ''
        image_url = image.get('url', '') or ''

        needs_desc = not summary.strip()
        needs_alt = bool(image_url) and not alt_text.strip()

        if needs_desc or needs_alt:
            to_fix.append({
                'id': article.get('id', ''),
                'title': article.get('title', ''),
                'body': article.get('body', '') or '',
                'image_url': image_url,
                'needs_desc': needs_desc,
                'needs_alt': needs_alt,
            })

    print(f"⏳ Generating SEO content for {len(to_fix)} articles via Anthropic Claude...\n")

    # Generate AI content
    ai_results = generate_batch_descriptions(to_fix)

    changes = []
    pushed = 0
    failed = 0

    for article in to_fix:
        title = article['title']
        article_id = article['id']
        ai = ai_results.get(article_id, {})

        updates = {}
        change_record = {"title": title, "id": article_id, "fixes": []}

        # Meta description
        if article['needs_desc']:
            desc = ai.get('desc', '')
            if not desc:
                # Fallback: clean first sentence
                body_text = strip_html(article['body'])
                desc = body_text[:150].rsplit(' ', 1)[0] + "..."
                print(f"  ⚠ [{title[:50]}] Fallback desc ({len(desc)}ch)")
            else:
                print(f"  ✓ [{title[:50]}] Meta desc ({len(desc)}ch): {desc[:70]}...")
            updates["summary"] = desc
            change_record["fixes"].append(("meta_description", "", desc))

        # Alt text
        if article['needs_alt']:
            alt = ai.get('alt', '')
            if not alt:
                alt = title[:125]
                print(f"  ⚠ [{title[:50]}] Fallback alt: {alt[:60]}")
            else:
                print(f"  ✓ [{title[:50]}] Alt text ({len(alt)}ch): {alt}")
            updates["image"] = {"altText": alt, "url": article['image_url']}
            change_record["fixes"].append(("alt_text", "", alt))

        # Push if live mode
        if updates and not args.dry_run:
            success = update_article(client, article_id, updates)
            if success:
                print(f"    ✅ Pushed to Shopify")
                pushed += 1
            else:
                print(f"    ❌ Failed to push")
                failed += 1
            time.sleep(0.5)

        changes.append(change_record)

    # Export summary to Google Sheets
    print(f"\n⏳ Exporting summary to Google Sheets...")
    try:
        sheets = GoogleSheetsExporter()
        headers = ['Article Title', 'Fix Type', 'Before', 'After', 'Char Count']
        rows = []
        for c in changes:
            for fix_type, before, after in c['fixes']:
                rows.append([c['title'], fix_type, before, after, len(after)])

        sheet_url = sheets.create_sheet(
            title=f"Blog SEO Fixes — {mode} — {time.strftime('%Y-%m-%d %H:%M')}",
            headers=headers,
            rows=rows,
        )
        print(f"✓ Google Sheet: {sheet_url}")
    except Exception as e:
        logger.warning(f"Sheets export failed: {e}")
        sheet_url = "N/A"

    # Summary
    total_desc = sum(1 for c in changes for f in c['fixes'] if f[0] == 'meta_description')
    total_alt = sum(1 for c in changes for f in c['fixes'] if f[0] == 'alt_text')

    print(f"\n{'='*60}")
    print(f"  ✅ PHASE 1 COMPLETE ({mode})")
    print(f"{'='*60}")
    print(f"  Meta descriptions generated: {total_desc}")
    print(f"  Alt texts generated:         {total_alt}")
    print(f"  Total articles fixed:        {len(changes)}")
    if not args.dry_run:
        print(f"  Pushed:                      {pushed}")
        print(f"  Failed:                      {failed}")
    print(f"  Report: {sheet_url}")
    if args.dry_run:
        print(f"\n  ⚠ DRY-RUN mode — no changes pushed.")
        print(f"  Run with --push-live to apply changes.")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
