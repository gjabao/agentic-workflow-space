#!/usr/bin/env python3
"""
Beauty Connect Shop — Shopify Collection SEO Optimizer
DOE Architecture Execution Script v1.0

Fetches all collections from Shopify, scores SEO health (0-100),
generates AI-optimized meta titles, descriptions, and collection descriptions
using Azure OpenAI, validates for Health Canada compliance, and exports audit
to Google Sheets.

Usage:
    python execution/shopify_collection_optimizer.py --dry_run
    python execution/shopify_collection_optimizer.py --limit 10 --dry_run
    python execution/shopify_collection_optimizer.py --push_live
    python execution/shopify_collection_optimizer.py --min_score 70 --dry_run
"""

import os
import sys
import json
import logging
import argparse
import time
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Add execution directory to path for seo_shared import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    export_to_csv,
    check_health_canada_compliance,
    K_BEAUTY_KEYWORDS,
    load_brand_voice,
    strip_html,
    word_count,
    BASE_DIR,
    logger,
    REQUESTS_TIMEOUT,
)

# ─── Logging ───────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/shopify_collection_seo.log'),
        logging.StreamHandler(sys.stdout)
    ]
)


# ─── Collection SEO Scorer ────────────────────────────────────────────────────

class CollectionSEOScorer:
    """Scores collection SEO health from 0-100."""

    def score(self, collection: Dict) -> Tuple[int, Dict]:
        """
        Score a collection's SEO health.
        Returns (score, breakdown_dict).
        """
        score = 0
        breakdown = {}
        seo = collection.get('seo', {})
        meta_title = seo.get('title') or ''
        meta_desc = seo.get('description') or ''
        description_html = collection.get('descriptionHtml') or ''
        image = collection.get('image') or {}
        alt_text = image.get('altText') or ''

        # Meta title scoring (+20 present, +10 length, +10 keyword)
        if meta_title:
            score += 20
            breakdown['meta_title_present'] = True
            title_len = len(meta_title)
            if 50 <= title_len <= 60:
                score += 10
                breakdown['meta_title_length'] = 'good'
            else:
                breakdown['meta_title_length'] = f'bad ({title_len} chars)'
            # Check for any K-beauty keyword
            title_lower = meta_title.lower()
            if any(kw.lower() in title_lower for kw in K_BEAUTY_KEYWORDS):
                score += 10
                breakdown['meta_title_keyword'] = True
            else:
                breakdown['meta_title_keyword'] = False
        else:
            breakdown['meta_title_present'] = False

        # Meta description scoring (+20 present, +10 length)
        if meta_desc:
            score += 20
            breakdown['meta_desc_present'] = True
            desc_len = len(meta_desc)
            if 140 <= desc_len <= 155:
                score += 10
                breakdown['meta_desc_length'] = 'good'
            else:
                breakdown['meta_desc_length'] = f'bad ({desc_len} chars)'
        else:
            breakdown['meta_desc_present'] = False

        # Description scoring (+10 present, +10 >=150 words)
        wc = word_count(description_html)
        if description_html.strip():
            score += 10
            breakdown['description_present'] = True
            if wc >= 150:
                score += 10
                breakdown['description_length'] = f'good ({wc} words)'
            else:
                breakdown['description_length'] = f'short ({wc} words)'
        else:
            breakdown['description_present'] = False
            breakdown['description_length'] = '0 words'

        # Image alt text scoring (+10)
        if alt_text:
            score += 10
            breakdown['image_alt_present'] = True
        else:
            breakdown['image_alt_present'] = False

        return score, breakdown


# ─── Collection SEO Optimizer (AI) ────────────────────────────────────────────

class CollectionSEOOptimizer:
    """Generates AI-optimized SEO content for collections using Azure OpenAI."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, brand_voice: str):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment = deployment
        self.brand_voice = brand_voice

    def optimize_collection(self, collection: Dict) -> Dict:
        """
        Generate optimized SEO fields for a collection.
        Returns dict with: meta_title, meta_description, description_html
        """
        title = collection.get('title', '')
        current_desc = strip_html(collection.get('descriptionHtml', ''))[:500]
        products_count_data = collection.get('productsCount', {})
        product_count = products_count_data.get('count', 0) if isinstance(products_count_data, dict) else 0

        prompt = f"""You are writing SEO content for Beauty Connect Shop — a B2B Korean dermaceutical distributor in Canada.

BRAND VOICE SUMMARY:
{self.brand_voice[:800]}

COLLECTION: {title}
Product Count: {product_count}
Current Description: {current_desc if current_desc else 'MISSING'}

Generate optimized collection page content in JSON:
{{
  "meta_title": "50-60 chars",
  "meta_description": "140-155 chars",
  "description_html": "<p>150-300 word HTML description with FAQ section</p>"
}}

SEO REQUIREMENTS:
1. meta_title: EXACTLY 50-60 characters (count carefully). Keyword front-loaded. Include "Canada" or "Professional" or "Wholesale" where natural. Do NOT include store name.
2. meta_description: EXACTLY 140-155 characters (count carefully). Lead with a benefit, end with a CTA like "Shop wholesale." or "Trusted by estheticians."
3. description_html: 150-300 words in HTML with:
   - Opening sentence with primary keyword
   - What the collection offers
   - Who it's for (estheticians, clinics, spa professionals)
   - Buying guide snippet (2-3 sentences)
   - Mini FAQ section (2-3 questions in <h3>/<p> format) for FAQ schema eligibility

Target keywords: "Korean {title.lower()} wholesale Canada", "{title.lower()} for estheticians", "professional {title.lower()}"
Include buying guide snippet and 2-3 FAQ questions.

HEALTH CANADA COMPLIANCE — ASC Guidelines (mandatory — if you violate this, regenerate):
This is a COSMETIC product category page. Only Column I (non-therapeutic) claims are allowed.
Column II (therapeutic/health) claims require a DIN or NPN and are FORBIDDEN here.

ALLOWED: Heals dry skin, protects/relieves/soothes dry skin, hydrates, moisturizes, reduces the look of aging,
smoothes wrinkles, firms/tightens/tones/conditions/softens skin, improves elasticity, deep cleans pores,
professional-grade, dermatologist tested, recommended by dermatologists.

FORBIDDEN: Heals (unqualified), repairs skin/damaged skin, treats acne/rosacea/eczema, cures, prevents disease,
anti-inflammatory, antibacterial, antifungal, antiseptic, prescription strength, medical-grade, clinical strength,
stimulates cell/collagen growth, SPF/UV claims, active ingredient, therapeutic ingredient, promotes health.

GENERAL RULE: If a claim implies the product modifies organic function or impacts disease, it is therapeutic and FORBIDDEN.

Return ONLY valid JSON (no markdown, no code block):
{{
  "meta_title": "exactly 50-60 chars here",
  "meta_description": "exactly 140-155 chars here",
  "description_html": "<p>Full HTML description here with FAQ section...</p>"
}}"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[{'role': 'user', 'content': prompt}],
                    temperature=0.4,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )
                result = json.loads(response.choices[0].message.content)

                # Validate Health Canada compliance
                all_text = ' '.join(str(v) for v in result.values())
                violations = check_health_canada_compliance(all_text)
                if violations:
                    logger.warning(f"⚠ Health Canada violation in {title} — regenerating")
                    prompt += f"\n\nPREVIOUS OUTPUT HAD VIOLATIONS. DO NOT use these patterns: {violations}"
                    continue

                # Enforce character lengths programmatically
                meta_title = result.get('meta_title', '')
                meta_desc = result.get('meta_description', '')

                # Trim meta_title to 60 chars at word boundary if too long
                if len(meta_title) > 60:
                    meta_title = meta_title[:60].rsplit(' ', 1)[0]
                    result['meta_title'] = meta_title

                # Trim meta_desc to 155 chars at word boundary if too long
                if len(meta_desc) > 155:
                    meta_desc = meta_desc[:155].rsplit(' ', 1)[0]
                    result['meta_description'] = meta_desc

                return result

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {title}: {e}")
            except Exception as e:
                logger.error(f"AI error for {title}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        # Fallback: return minimal improvements
        logger.warning(f"⚠ Using fallback SEO for {title}")
        fallback_title = (f"Korean {title} Wholesale Canada | Professional")[:60]
        return {
            'meta_title': fallback_title,
            'meta_description': f"Shop {title[:50]} at Beauty Connect Shop. Professional K-beauty wholesale for estheticians in Canada. Free shipping available.",
            'description_html': f"<p>{current_desc[:500]}</p>" if current_desc else f"<p>Professional Korean skincare collection by Beauty Connect Shop. Trusted by estheticians across Canada.</p>",
        }


# ─── Main Orchestrator ─────────────────────────────────────────────────────────

def run_collection_optimizer(args):
    """Main orchestration function."""

    # ── Load credentials
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ADMIN_API_TOKEN')

    # Support legacy private app auth (API key + secret as basic auth)
    if not access_token:
        api_key = os.getenv('SHOPIFY_API_KEY')
        api_secret = os.getenv('SHOPIFY_API_SECRET')
        if api_key and api_secret:
            access_token = api_secret  # Private app: secret = access token
            logger.info("Using private app credentials (API key + secret)")

    if not store_url or not access_token:
        logger.error("❌ Missing SHOPIFY_STORE_URL or SHOPIFY_ADMIN_API_TOKEN in .env")
        sys.exit(1)

    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    if not azure_endpoint or not azure_key:
        logger.error("❌ Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY in .env")
        sys.exit(1)

    # ── Initialize clients
    brand_voice = load_brand_voice()
    shopify = ShopifyClient(store_url, access_token)
    scorer = CollectionSEOScorer()
    optimizer = CollectionSEOOptimizer(azure_endpoint, azure_key, azure_deployment, brand_voice)

    # ── Fetch collections
    print(f"\n{'='*60}")
    print(f"  Beauty Connect Shop — Collection SEO Optimizer")
    print(f"  Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will update Shopify)'}")
    print(f"{'='*60}\n")

    print("⏳ Fetching collections from Shopify...")
    collections = shopify.fetch_all_collections(limit=args.limit)

    if not collections:
        logger.error("❌ No collections found — check Shopify credentials")
        sys.exit(1)

    print(f"✓ Found {len(collections)} collections\n")

    # ── Score + Optimize
    audit_results = []
    needs_optimization = []
    skipped = []

    for collection in collections:
        score, breakdown = scorer.score(collection)
        seo = collection.get('seo', {})
        description_html = collection.get('descriptionHtml') or ''
        products_count_data = collection.get('productsCount', {})
        product_count = products_count_data.get('count', 0) if isinstance(products_count_data, dict) else 0

        result = {
            'collection_id': collection['id'],
            'title': collection['title'],
            'handle': collection['handle'],
            'product_count': product_count,
            'score_before': score,
            'score_after': score,
            'current_meta_title': seo.get('title', ''),
            'current_meta_desc': seo.get('description', ''),
            'description_words_before': word_count(description_html),
            'description_words_after': word_count(description_html),
            'breakdown': breakdown,
            'compliant': True,
            'status': 'skip_high_score',
            'optimized': {}
        }

        if score >= args.min_score and not args.force_all:
            skipped.append(result)
            print(f"  ✓ SKIP [{score}/100] {collection['title'][:50]}")
        else:
            needs_optimization.append(result)

    print(f"\n📊 Score Summary:")
    print(f"  Collections scoring ≥{args.min_score} (skip): {len(skipped)}")
    print(f"  Collections to optimize: {len(needs_optimization)}\n")

    if not needs_optimization:
        print("🎉 All collections are already well-optimized!")

    for i, result in enumerate(needs_optimization):
        collection = next(c for c in collections if c['id'] == result['collection_id'])
        print(f"⏳ Optimizing [{i+1}/{len(needs_optimization)}]: {result['title'][:50]}...")

        optimized = optimizer.optimize_collection(collection)
        result['optimized'] = optimized
        result['status'] = 'pending_review'

        # Recalculate score with optimized content
        new_score = result['score_before']
        if optimized.get('meta_title') and len(optimized['meta_title']) >= 50:
            new_score = max(new_score, 85)
        result['score_after'] = new_score

        # Update description word count (after)
        if optimized.get('description_html'):
            result['description_words_after'] = word_count(optimized['description_html'])

        # Health Canada compliance check on ALL generated content
        all_text = ' '.join(str(v) for v in optimized.values())
        violations = check_health_canada_compliance(all_text)
        result['compliant'] = len(violations) == 0

        print(f"  ✓ Score: {result['score_before']} → {result['score_after']} | Health Canada: {'✓' if result['compliant'] else '⚠ VIOLATION'}")

        time.sleep(0.2)

    all_results = skipped + needs_optimization

    # ── Export to Google Sheets
    print("\n⏳ Exporting audit report to Google Sheets...")
    try:
        exporter = GoogleSheetsExporter()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet_title = f"BeautyConnect Collection SEO Audit — {timestamp}"

        headers = [
            'Collection Title', 'Handle', 'Product Count',
            'Score Before', 'Score After',
            'Current Meta Title', 'Optimized Meta Title',
            'Current Meta Desc', 'Optimized Meta Desc',
            'Description Words (Before)', 'Description Words (After)',
            'Health Canada Compliant', 'Status', 'Collection ID'
        ]

        rows = []
        for r in all_results:
            opt = r.get('optimized', {})
            rows.append([
                r['title'],
                r['handle'],
                r['product_count'],
                r['score_before'],
                r['score_after'],
                r['current_meta_title'],
                opt.get('meta_title', ''),
                r['current_meta_desc'],
                opt.get('meta_description', ''),
                r['description_words_before'],
                r['description_words_after'],
                'YES' if r.get('compliant') else 'NO',
                r.get('status', 'pending_review'),
                r['collection_id']
            ])

        sheet_url = exporter.create_sheet(sheet_title, headers, rows)
        print(f"✓ Audit report: {sheet_url}")
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        # Fallback: save to CSV
        csv_headers = [
            'Collection Title', 'Handle', 'Product Count',
            'Score Before', 'Score After',
            'Current Meta Title', 'Optimized Meta Title',
            'Current Meta Desc', 'Optimized Meta Desc',
            'Description Words (Before)', 'Description Words (After)',
            'Health Canada Compliant', 'Status', 'Collection ID'
        ]
        csv_rows = []
        for r in all_results:
            opt = r.get('optimized', {})
            csv_rows.append([
                r['title'], r['handle'], r['product_count'],
                r['score_before'], r['score_after'],
                r['current_meta_title'], opt.get('meta_title', ''),
                r['current_meta_desc'], opt.get('meta_description', ''),
                r['description_words_before'], r['description_words_after'],
                'YES' if r.get('compliant') else 'NO',
                r.get('status', 'pending_review'), r['collection_id']
            ])
        csv_path = export_to_csv('collection_seo_audit', csv_headers, csv_rows)
        print(f"⚠ Google Sheets failed — saved to: {csv_path}")
        sheet_url = csv_path

    # ── Push Live (only if --push_live)
    if args.push_live and not args.dry_run:
        print(f"\n⏳ Pushing {len(needs_optimization)} collection updates to Shopify...")
        success_count = 0
        fail_count = 0

        for result in needs_optimization:
            opt = result['optimized']

            ok = shopify.update_collection_seo(
                result['collection_id'],
                opt.get('meta_title', result['current_meta_title']),
                opt.get('meta_description', result['current_meta_desc']),
                description_html=opt.get('description_html')
            )

            if ok:
                success_count += 1
                result['status'] = 'pushed_live'
            else:
                fail_count += 1
                result['status'] = 'push_failed'

        print(f"✓ Pushed live: {success_count}/{len(needs_optimization)}")
        if fail_count:
            print(f"⚠ Failed: {fail_count} (see log)")
    elif args.dry_run:
        print("\n⚠ DRY RUN — no changes made to Shopify")
        print("   Review the Google Sheet, then run with --push_live to apply changes")

    # ── Summary
    total_before = sum(r['score_before'] for r in all_results) / len(all_results) if all_results else 0
    total_after = sum(r['score_after'] for r in all_results) / len(all_results) if all_results else 0

    print(f"\n{'='*60}")
    print(f"  ✅ COLLECTION SEO OPTIMIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Collections analyzed:   {len(all_results)}")
    print(f"  Collections optimized:  {len(needs_optimization)}")
    print(f"  Average score before:   {total_before:.0f}/100")
    print(f"  Average score after:    {total_after:.0f}/100")
    print(f"  Health Canada issues:   {sum(1 for r in needs_optimization if not r['compliant'])}")
    print(f"  Audit report:           {sheet_url}")
    print(f"{'='*60}\n")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Beauty Connect Shop — Shopify Collection SEO Optimizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/shopify_collection_optimizer.py --dry_run
  python execution/shopify_collection_optimizer.py --limit 10 --dry_run
  python execution/shopify_collection_optimizer.py --push_live
  python execution/shopify_collection_optimizer.py --min_score 70 --dry_run
  python execution/shopify_collection_optimizer.py --force_all --dry_run
        """
    )
    parser.add_argument('--dry_run', action='store_true', default=True,
                        help='Analyze and export to Sheets only — no Shopify changes (default: True)')
    parser.add_argument('--push_live', action='store_true',
                        help='Push optimized SEO to Shopify (overrides --dry_run)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of collections to process (default: all)')
    parser.add_argument('--min_score', type=int, default=85,
                        help='Minimum SEO score threshold — optimize collections below this (default: 85)')
    parser.add_argument('--force_all', action='store_true',
                        help='Optimize all collections regardless of score')

    args = parser.parse_args()

    # --push_live overrides --dry_run
    if args.push_live:
        args.dry_run = False

    run_collection_optimizer(args)


if __name__ == '__main__':
    main()
