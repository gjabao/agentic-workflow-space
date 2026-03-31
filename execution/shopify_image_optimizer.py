#!/usr/bin/env python3
"""
Beauty Connect Shop — Shopify Image SEO Optimizer
DOE Architecture Execution Script v1.0

Audits all product images for alt text quality, generates AI-optimized alt text
using Azure OpenAI, validates Health Canada compliance, and exports audit to Google Sheets.

Usage:
    python execution/shopify_image_optimizer.py --dry_run
    python execution/shopify_image_optimizer.py --limit 10 --dry_run
    python execution/shopify_image_optimizer.py --push_live
    python execution/shopify_image_optimizer.py --dry_run --skip-ai
"""

import os
import sys
import logging
import argparse
import time
import re
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Add execution dir to path for seo_shared import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    export_to_csv,
    check_health_canada_compliance,
    K_BEAUTY_KEYWORDS,
    load_brand_voice,
    BASE_DIR,
    logger,
    REQUESTS_TIMEOUT,
)

# ─── Logging ───────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)
img_logger = logging.getLogger('image_optimizer')
if not img_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/shopify_image_seo.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

# ─── Constants ─────────────────────────────────────────────────────────────────
GENERIC_ALT_PATTERNS = [
    r'^image$', r'^photo$', r'^picture$', r'^img$',
    r'^image\s+\d+$', r'^photo\s+\d+$',
    r'^product\s+image$', r'^product\s+photo$',
    r'^untitled$', r'^default$', r'^placeholder$',
    r'^image\s+of\b', r'^photo\s+of\b', r'^picture\s+of\b',
    r'^screenshot', r'^img_\d+', r'^dsc_?\d+', r'^img-\d+',
]

ALT_TEXT_MIN_LENGTH = 50
ALT_TEXT_MAX_LENGTH = 125


# ─── Image Auditor ─────────────────────────────────────────────────────────────

class ImageAuditor:
    """Audits product images for alt text quality."""

    def audit_image(self, product_title: str, image: Dict, position: int, total: int) -> Dict:
        """
        Audit a single image and return a detailed report.
        Returns dict with audit fields.
        """
        alt_text = (image.get('altText') or '').strip()
        image_url = image.get('url', '')
        image_id = image.get('id', '')

        has_alt = bool(alt_text)
        alt_length = len(alt_text) if has_alt else 0
        length_ok = ALT_TEXT_MIN_LENGTH <= alt_length <= ALT_TEXT_MAX_LENGTH if has_alt else False
        has_product_name = product_title.lower() in alt_text.lower() if has_alt else False
        is_generic = self._is_generic(alt_text) if has_alt else False

        # Determine status
        if not has_alt:
            status = "❌ Missing"
        elif is_generic:
            status = "⚠️ Generic"
        elif alt_length < ALT_TEXT_MIN_LENGTH:
            status = "⚠️ Too Short"
        elif alt_length > ALT_TEXT_MAX_LENGTH:
            status = "⚠️ Too Long"
        elif not has_product_name:
            status = "⚠️ No Product Name"
        else:
            status = "✅ Good"

        needs_optimization = status != "✅ Good"

        return {
            'product_title': product_title,
            'image_id': image_id,
            'image_url': image_url,
            'position': position,
            'total_images': total,
            'current_alt': alt_text,
            'has_alt': has_alt,
            'alt_length': alt_length,
            'length_ok': length_ok,
            'has_product_name': has_product_name,
            'is_generic': is_generic,
            'status': status,
            'needs_optimization': needs_optimization,
            'suggested_alt': '',
        }

    def _is_generic(self, alt_text: str) -> bool:
        """Check if alt text is generic/non-descriptive."""
        text_lower = alt_text.lower().strip()
        for pattern in GENERIC_ALT_PATTERNS:
            if re.match(pattern, text_lower, re.IGNORECASE):
                return True
        return False


# ─── AI Alt Text Generator ─────────────────────────────────────────────────────

class AltTextGenerator:
    """Generates AI-optimized alt text using Azure OpenAI."""

    def __init__(self, endpoint: str, api_key: str, deployment: str):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment = deployment

    def generate(self, product: Dict, position: int, total: int) -> str:
        """
        Generate optimized alt text for a product image.
        Returns alt text string (max 125 chars).
        """
        title = product.get('title', '')
        product_type = product.get('productType', '')

        prompt = f"""Generate a concise, descriptive alt text for this product image.
Product: {title}
Type: {product_type}
Image position: {position} of {total}

Requirements:
- 50-125 characters
- Include product name
- Describe what's visible (product appearance, packaging, color)
- Include one relevant keyword if natural
- Do NOT use "image of" or "photo of" prefix
- Health Canada compliant (no therapeutic claims)

Return ONLY the alt text string, nothing else."""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an SEO specialist for Beauty Connect Shop, "
                                "a professional Korean skincare brand in Canada. "
                                "Generate alt text that is descriptive, keyword-rich, "
                                "and Health Canada compliant. Return ONLY the alt text."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=100,
                )
                alt_text = response.choices[0].message.content.strip()
                # Strip quotes if AI wraps them
                alt_text = alt_text.strip('"').strip("'")

                # Enforce max length
                if len(alt_text) > ALT_TEXT_MAX_LENGTH:
                    alt_text = alt_text[:ALT_TEXT_MAX_LENGTH - 3].rsplit(' ', 1)[0] + '...'

                # Health Canada compliance check
                violations = check_health_canada_compliance(alt_text)
                if violations:
                    logger.warning(f"⚠ Alt text has Health Canada violations, regenerating: {alt_text}")
                    # Retry with stricter prompt
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    else:
                        logger.warning("⚠ Could not generate compliant alt text after 3 attempts")
                        return ""

                return alt_text

            except Exception as e:
                logger.error(f"Azure OpenAI error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        return ""


# ─── Fetch Products with ALL Images ────────────────────────────────────────────

def fetch_products_with_images(shopify: ShopifyClient, limit: Optional[int] = None) -> List[Dict]:
    """
    Fetch all products with up to 10 images each via GraphQL pagination.
    Uses a custom query with images(first: 10) instead of the default 5.
    """
    query = """
    query FetchProductImages($cursor: String) {
      products(first: 50, after: $cursor) {
        edges {
          node {
            id
            title
            handle
            productType
            tags
            images(first: 10) {
              edges {
                node {
                  id
                  altText
                  url
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """
    products = []
    cursor = None

    while True:
        variables = {'cursor': cursor} if cursor else {}
        data = shopify._graphql(query, variables)

        if not data or 'products' not in data:
            break

        edges = data['products']['edges']
        for edge in edges:
            products.append(edge['node'])
            if limit and len(products) >= limit:
                logger.info(f"✓ Fetched {len(products)} products (limit reached)")
                return products

        page_info = data['products']['pageInfo']
        if not page_info['hasNextPage']:
            break

        cursor = page_info['endCursor']
        time.sleep(0.5)

    logger.info(f"✓ Fetched {len(products)} total products with images")
    return products


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Beauty Connect Shop — Shopify Image SEO Optimizer"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry_run', action='store_true', default=True,
                      help='Audit + generate suggestions only (default)')
    mode.add_argument('--push_live', action='store_true',
                      help='Update alt text on Shopify')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process N products only')
    parser.add_argument('--skip-ai', action='store_true',
                        help='Skip AI alt text generation, just audit')
    args = parser.parse_args()

    # If push_live is set, dry_run should be False
    if args.push_live:
        args.dry_run = False

    # ── Validate credentials
    shopify = ShopifyClient()

    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    generator = None
    if not args.skip_ai:
        if not azure_endpoint or not azure_key:
            logger.error("❌ Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY in .env")
            logger.info("💡 Use --skip-ai to run audit-only mode without Azure OpenAI")
            sys.exit(1)
        generator = AltTextGenerator(azure_endpoint, azure_key, azure_deployment)

    auditor = ImageAuditor()

    # ── Banner
    mode_label = 'DRY RUN (no changes)' if args.dry_run else '🔴 LIVE (will update Shopify)'
    ai_label = 'OFF (audit only)' if args.skip_ai else 'ON (Azure OpenAI)'
    print(f"\n{'=' * 60}")
    print(f"  Beauty Connect Shop — Image SEO Optimizer")
    print(f"  Mode: {mode_label}")
    print(f"  AI Generation: {ai_label}")
    print(f"{'=' * 60}\n")

    # ── Fetch products
    print("⏳ Fetching products with images from Shopify...")
    products = fetch_products_with_images(shopify, limit=args.limit)

    if not products:
        logger.error("❌ No products found — check Shopify credentials")
        sys.exit(1)

    print(f"✓ Found {len(products)} products\n")

    # ── Audit all images
    audit_rows = []
    stats = {
        'total_images': 0,
        'missing_alt': 0,
        'generic_alt': 0,
        'too_short': 0,
        'too_long': 0,
        'no_product_name': 0,
        'good': 0,
        'ai_generated': 0,
        'pushed_live': 0,
    }

    for idx, product in enumerate(products):
        images = product.get('images', {}).get('edges', [])
        total_images = len(images)
        product_title = product.get('title', 'Untitled')

        if total_images == 0:
            logger.info(f"  ⚪ No images: {product_title[:50]}")
            continue

        for img_idx, img_edge in enumerate(images):
            image = img_edge['node']
            position = img_idx + 1
            stats['total_images'] += 1

            # Audit
            audit = auditor.audit_image(product_title, image, position, total_images)
            audit['product_id'] = product['id']

            # Count stats
            if not audit['has_alt']:
                stats['missing_alt'] += 1
            elif audit['is_generic']:
                stats['generic_alt'] += 1
            elif audit['alt_length'] < ALT_TEXT_MIN_LENGTH:
                stats['too_short'] += 1
            elif audit['alt_length'] > ALT_TEXT_MAX_LENGTH:
                stats['too_long'] += 1
            elif not audit['has_product_name']:
                stats['no_product_name'] += 1
            else:
                stats['good'] += 1

            # Generate AI alt text if needed
            if audit['needs_optimization'] and generator and not args.skip_ai:
                suggested = generator.generate(product, position, total_images)
                if suggested:
                    audit['suggested_alt'] = suggested
                    stats['ai_generated'] += 1

                    # Push live if requested
                    if args.push_live and suggested:
                        success = shopify.update_image_alt_text(
                            product['id'], image['id'], suggested
                        )
                        if success:
                            stats['pushed_live'] += 1
                            audit['status'] = "✅ Updated"
                            logger.info(f"  ✅ Updated: {product_title[:40]} — image {position}")
                        else:
                            audit['status'] = "❌ Update Failed"
                            logger.error(f"  ❌ Failed: {product_title[:40]} — image {position}")

            audit_rows.append(audit)

        # Progress update every 10 products
        if (idx + 1) % 10 == 0 or idx == len(products) - 1:
            pct = ((idx + 1) / len(products)) * 100
            print(f"⏳ Progress: {idx + 1}/{len(products)} products ({pct:.0f}%)")

    # ── Print summary
    print(f"\n{'=' * 60}")
    print(f"  📊 Image SEO Audit Summary")
    print(f"{'=' * 60}")
    print(f"  Total images audited:      {stats['total_images']}")
    print(f"  ❌ Missing alt text:        {stats['missing_alt']}")
    print(f"  ⚠️  Generic alt text:       {stats['generic_alt']}")
    print(f"  ⚠️  Too short (<{ALT_TEXT_MIN_LENGTH} chars):  {stats['too_short']}")
    print(f"  ⚠️  Too long (>{ALT_TEXT_MAX_LENGTH} chars):  {stats['too_long']}")
    print(f"  ⚠️  No product name:        {stats['no_product_name']}")
    print(f"  ✅ Good alt text:           {stats['good']}")
    if not args.skip_ai:
        print(f"  🤖 AI suggestions generated: {stats['ai_generated']}")
    if args.push_live:
        print(f"  🚀 Pushed live:            {stats['pushed_live']}")
    print(f"{'=' * 60}\n")

    # ── Export to Google Sheets
    if not audit_rows:
        print("No images to report.")
        return

    headers = [
        "Product Title",
        "Image Position",
        "Current Alt Text",
        "Suggested Alt Text",
        "Alt Length",
        "Has Product Name",
        "Status",
        "Product ID",
        "Image ID",
    ]

    rows = []
    for a in audit_rows:
        rows.append([
            a['product_title'],
            f"{a['position']}/{a['total_images']}",
            a['current_alt'],
            a['suggested_alt'],
            a['alt_length'],
            "Yes" if a['has_product_name'] else "No",
            a['status'],
            a['product_id'],
            a['image_id'],
        ])

    date_str = datetime.now().strftime('%Y-%m-%d')
    sheet_title = f"Image SEO Audit — {date_str}"

    try:
        exporter = GoogleSheetsExporter()
        sheet_url = exporter.create_sheet(sheet_title, headers, rows)
        print(f"✅ Google Sheet: {sheet_url}")
    except Exception as e:
        logger.warning(f"⚠ Google Sheets export failed: {e}")
        logger.info("📄 Falling back to CSV export...")
        csv_path = export_to_csv(f"image_seo_audit", headers, rows)
        print(f"✅ CSV exported: {csv_path}")

    print("\n✓ Image SEO audit complete!")


if __name__ == '__main__':
    main()
