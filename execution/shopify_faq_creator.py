#!/usr/bin/env python3
"""
Beauty Connect Shop — Shopify FAQ Content Generator
DO Architecture Execution Script v1.0

Fetches products/collections from Shopify, optionally pulls related GSC queries,
generates FAQ Q&A pairs using Azure OpenAI, builds FAQ JSON-LD schema,
validates Health Canada compliance, and exports to Google Sheets.

Usage:
    python execution/shopify_faq_creator.py --dry_run
    python execution/shopify_faq_creator.py --limit 10 --dry_run
    python execution/shopify_faq_creator.py --push_live
    python execution/shopify_faq_creator.py --product_id "gid://shopify/Product/123"
    python execution/shopify_faq_creator.py --collection_id "gid://shopify/Collection/456"
    python execution/shopify_faq_creator.py --skip-gsc --schema-only --dry_run
"""

import os
import sys
import json
import logging
import argparse
import time
import re
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Import shared utilities
from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    GSCClient,
    export_to_csv,
    check_health_canada_compliance,
    K_BEAUTY_KEYWORDS,
    load_brand_voice,
    strip_html,
    BASE_DIR,
    logger,
    REQUESTS_TIMEOUT,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)

faq_logger = logging.getLogger('shopify_faq_creator')
if not faq_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/shopify_faq.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


# ─── FAQ Generator (AI) ──────────────────────────────────────────────────────

class FAQGenerator:
    """Generates FAQ Q&A pairs using Azure OpenAI."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, brand_voice: str):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment = deployment
        self.brand_voice = brand_voice

    def generate_faqs(self, title: str, product_type: str, description: str,
                      gsc_queries: List[str] = None) -> List[Dict]:
        """
        Generate 5-8 FAQ Q&A pairs for a product/collection.
        Returns list of {"question": "...", "answer": "..."} dicts.
        """
        description_snippet = strip_html(description)[:600] if description else ''
        queries_str = ', '.join(gsc_queries[:15]) if gsc_queries else 'None available'

        prompt = f"""Generate 5-8 FAQ questions and answers for this product page.

Product: {title}
Type: {product_type}
Description: {description_snippet}
Related search queries from GSC: {queries_str}

BRAND VOICE:
{self.brand_voice[:600]}

Requirements:
- Questions should match how people actually search (use "People Also Ask" style)
- Answers: 40-80 words each, concise and factual
- Include at least 1 question about: ingredients, how to use, skin type suitability
- Include 1 question about shipping/availability in Canada
- Health Canada compliant — NO therapeutic claims
- Natural keyword inclusion for SEO

HEALTH CANADA COMPLIANCE (mandatory):
This product is a COSMETIC. Only Column I (non-therapeutic) claims are allowed.
FORBIDDEN: heals (unqualified), repairs skin, treats acne/rosacea/eczema, cures,
prevents disease/infection, anti-inflammatory, antibacterial, antifungal, antiseptic,
clinical/therapeutic strength, stimulates cell/hair growth, SPF/UV claims,
anti-blemish, clears acne, active ingredient, medicinal ingredient, promotes health.
ALLOWED: hydrates, moisturizes, soothes dry skin, reduces the look of, improves texture,
deep cleans pores, professional-grade, dermatologist tested.

Return ONLY valid JSON array (no markdown, no code block):
[
  {{"question": "...", "answer": "..."}},
  ...
]"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[{'role': 'user', 'content': prompt}],
                    temperature=0.5,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                parsed = json.loads(content)

                # Handle both {"faqs": [...]} and [...] formats
                if isinstance(parsed, dict):
                    faqs = parsed.get('faqs', parsed.get('questions', parsed.get('faq', [])))
                    if not faqs:
                        # Try to find first list value in the dict
                        for v in parsed.values():
                            if isinstance(v, list):
                                faqs = v
                                break
                elif isinstance(parsed, list):
                    faqs = parsed
                else:
                    faqs = []

                if not faqs:
                    logger.warning(f"Empty FAQ response for {title} — retrying")
                    continue

                # Validate each Q&A pair
                valid_faqs = []
                for faq in faqs:
                    q = faq.get('question', '').strip()
                    a = faq.get('answer', '').strip()
                    if q and a:
                        valid_faqs.append({'question': q, 'answer': a})

                # Check Health Canada compliance on all answers
                all_text = ' '.join(f['answer'] for f in valid_faqs)
                violations = check_health_canada_compliance(all_text)
                if violations:
                    logger.warning(f"Health Canada violation in {title} FAQs — regenerating")
                    prompt += f"\n\nPREVIOUS OUTPUT HAD VIOLATIONS. DO NOT use these patterns: {violations}"
                    continue

                return valid_faqs[:8]  # Cap at 8

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {title}: {e}")
            except Exception as e:
                logger.error(f"AI error for {title}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        # Fallback: return minimal generic FAQ
        logger.warning(f"Using fallback FAQ for {title}")
        return [
            {
                'question': f'What is {title}?',
                'answer': f'{title} is a professional Korean skincare product available at Beauty Connect Shop. Trusted by estheticians across Canada for its quality formulation and visible results.'
            },
            {
                'question': f'How do I use {title}?',
                'answer': f'Apply {title} as directed on the product packaging. For best results, incorporate into your daily Korean skincare routine. Consult a skincare professional for personalized advice.'
            },
            {
                'question': f'Is {title} available for shipping in Canada?',
                'answer': 'Yes, Beauty Connect Shop ships across Canada. We offer fast, reliable delivery so you can enjoy professional K-beauty products from the comfort of your home or spa.'
            },
        ]


# ─── JSON-LD Schema Builder ──────────────────────────────────────────────────

def build_faq_schema(faqs: List[Dict]) -> Dict:
    """Build FAQ JSON-LD structured data from Q&A pairs."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq['question'],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq['answer']
                }
            }
            for faq in faqs
        ]
    }


# ─── FAQ HTML Builder ────────────────────────────────────────────────────────

def build_faq_html(faqs: List[Dict]) -> str:
    """Build FAQ HTML section to append to product descriptions."""
    lines = ['<h2>Frequently Asked Questions</h2>']
    for faq in faqs:
        lines.append('<div class="faq-section">')
        lines.append(f'  <h3>Q: {faq["question"]}</h3>')
        lines.append(f'  <p>{faq["answer"]}</p>')
        lines.append('</div>')
    return '\n'.join(lines)


# ─── GSC Query Fetcher ───────────────────────────────────────────────────────

def fetch_gsc_queries_for_product(gsc_client: GSCClient, site_url: str,
                                   product_title: str) -> List[str]:
    """
    Pull GSC queries related to a product by filtering on product name keywords.
    Returns list of query strings sorted by clicks descending.
    """
    # Extract meaningful keywords from product title (skip short/common words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'for', 'with', 'in', 'of', 'to', 'by', 'set', 'ml', 'oz'}
    keywords = [w.lower() for w in product_title.split() if len(w) > 2 and w.lower() not in stop_words]

    if not keywords:
        return []

    try:
        rows = gsc_client.query(
            site_url=site_url,
            dimensions=['query'],
            row_limit=1000
        )
    except Exception as e:
        logger.warning(f"GSC query failed for {product_title}: {e}")
        return []

    # Filter queries that contain at least one product keyword
    matching = []
    for row in rows:
        query_text = row.get('keys', [''])[0].lower()
        if any(kw in query_text for kw in keywords):
            matching.append({
                'query': row['keys'][0],
                'clicks': row.get('clicks', 0),
                'impressions': row.get('impressions', 0)
            })

    # Sort by clicks descending, return top queries
    matching.sort(key=lambda x: x['clicks'], reverse=True)
    return [m['query'] for m in matching[:20]]


# ─── Shopify Metafield Updater ───────────────────────────────────────────────

def set_product_metafield(shopify: ShopifyClient, product_id: str,
                           namespace: str, key: str, value: str,
                           value_type: str = "json") -> bool:
    """Set a metafield on a product via GraphQL mutation."""
    mutation = """
    mutation SetMetafield($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields {
          id
          key
          value
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        'metafields': [{
            'ownerId': product_id,
            'namespace': namespace,
            'key': key,
            'value': value,
            'type': value_type
        }]
    }

    data = shopify._graphql(mutation, variables)
    errors = data.get('metafieldsSet', {}).get('userErrors', [])
    if errors:
        logger.error(f"Metafield update failed for {product_id}: {errors}")
        return False
    return True


# ─── Fetch Products by Collection ────────────────────────────────────────────

def fetch_products_in_collection(shopify: ShopifyClient, collection_id: str,
                                  limit: Optional[int] = None) -> List[Dict]:
    """Fetch all products within a specific collection."""
    query = """
    query FetchCollectionProducts($id: ID!, $cursor: String) {
      collection(id: $id) {
        title
        products(first: 50, after: $cursor) {
          edges {
            node {
              id
              title
              handle
              descriptionHtml
              tags
              productType
              vendor
              images(first: 5) {
                edges {
                  node {
                    id
                    altText
                    url
                  }
                }
              }
              seo {
                title
                description
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """
    products = []
    cursor = None

    while True:
        variables = {'id': collection_id}
        if cursor:
            variables['cursor'] = cursor

        data = shopify._graphql(query, variables)
        collection = data.get('collection', {})
        if not collection:
            logger.error(f"Collection {collection_id} not found")
            break

        edges = collection.get('products', {}).get('edges', [])
        for edge in edges:
            products.append(edge['node'])
            if limit and len(products) >= limit:
                return products

        page_info = collection.get('products', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(0.5)

    logger.info(f"Fetched {len(products)} products from collection {collection_id}")
    return products


# ─── Fetch Single Product ────────────────────────────────────────────────────

def fetch_single_product(shopify: ShopifyClient, product_id: str) -> Optional[Dict]:
    """Fetch a single product by GID."""
    query = """
    query FetchProduct($id: ID!) {
      product(id: $id) {
        id
        title
        handle
        descriptionHtml
        tags
        productType
        vendor
        images(first: 5) {
          edges {
            node {
              id
              altText
              url
            }
          }
        }
        seo {
          title
          description
        }
      }
    }
    """
    data = shopify._graphql(query, {'id': product_id})
    return data.get('product')


# ─── Main Orchestrator ───────────────────────────────────────────────────────

def run_faq_creator(args):
    """Main orchestration function."""

    # ── Load credentials
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ADMIN_API_TOKEN')

    if not access_token:
        api_key = os.getenv('SHOPIFY_API_KEY')
        api_secret = os.getenv('SHOPIFY_API_SECRET')
        if api_key and api_secret:
            access_token = api_secret
            logger.info("Using private app credentials (API key + secret)")

    if not store_url or not access_token:
        logger.error("Missing SHOPIFY_STORE_URL or SHOPIFY_ADMIN_API_TOKEN in .env")
        sys.exit(1)

    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    if not azure_endpoint or not azure_key:
        logger.error("Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY in .env")
        sys.exit(1)

    gsc_site_url = os.getenv('GSC_SITE_URL', '')

    # ── Initialize clients
    brand_voice = load_brand_voice()
    shopify = ShopifyClient(store_url, access_token)
    faq_gen = FAQGenerator(azure_endpoint, azure_key, azure_deployment, brand_voice)

    gsc_client = None
    if not args.skip_gsc and gsc_site_url:
        try:
            gsc_client = GSCClient()
            logger.info("GSC client initialized")
        except Exception as e:
            logger.warning(f"GSC init failed — skipping GSC data: {e}")
            gsc_client = None

    # ── Fetch products
    mode_label = 'DRY RUN (no changes)' if args.dry_run else 'LIVE (will update Shopify)'
    if args.schema_only:
        mode_label += ' | SCHEMA ONLY'

    print(f"\n{'='*60}")
    print(f"  Beauty Connect Shop — FAQ Content Generator")
    print(f"  Mode: {mode_label}")
    print(f"{'='*60}\n")

    print("Fetching products from Shopify...")

    if args.product_id:
        product = fetch_single_product(shopify, args.product_id)
        products = [product] if product else []
    elif args.collection_id:
        products = fetch_products_in_collection(shopify, args.collection_id, limit=args.limit)
    else:
        products = shopify.fetch_all_products(limit=args.limit)

    if not products:
        logger.error("No products found — check Shopify credentials or IDs")
        sys.exit(1)

    print(f"Found {len(products)} products\n")

    # ── Generate FAQs
    results = []
    total = len(products)

    for i, product in enumerate(products):
        title = product.get('title', 'Untitled')
        product_type = product.get('productType', '')
        description = product.get('descriptionHtml', '')
        handle = product.get('handle', '')
        product_id = product.get('id', '')

        print(f"[{i+1}/{total}] Generating FAQs for: {title[:50]}...")

        # Optionally fetch GSC queries
        gsc_queries = []
        if gsc_client and gsc_site_url:
            gsc_queries = fetch_gsc_queries_for_product(gsc_client, gsc_site_url, title)
            if gsc_queries:
                print(f"  Found {len(gsc_queries)} related GSC queries")

        # Generate FAQ Q&A pairs
        faqs = faq_gen.generate_faqs(title, product_type, description, gsc_queries)
        print(f"  Generated {len(faqs)} FAQ pairs")

        # Build JSON-LD schema
        schema = build_faq_schema(faqs)
        schema_json = json.dumps(schema, indent=2)

        # Validate Health Canada compliance on each Q&A
        for faq in faqs:
            combined = f"{faq['question']} {faq['answer']}"
            violations = check_health_canada_compliance(combined)
            faq['compliant'] = len(violations) == 0
            faq['violations'] = violations
            if violations:
                logger.warning(f"  Health Canada violation in FAQ for {title}: {violations}")

        all_compliant = all(f['compliant'] for f in faqs)

        # Build per-FAQ rows for the sheet
        for faq in faqs:
            word_ct = len(faq['answer'].split())
            results.append({
                'product_title': title,
                'handle': handle,
                'product_id': product_id,
                'question': faq['question'],
                'answer': faq['answer'],
                'word_count': word_ct,
                'hc_ok': faq['compliant'],
                'schema_json': schema_json,
                'status': 'pending_review',
                'faqs': faqs,
                'description_html': description,
            })

        status_icon = 'OK' if all_compliant else 'HC VIOLATION'
        print(f"  Health Canada: {status_icon}\n")

        time.sleep(0.3)

    # ── Export to Google Sheets
    print("Exporting FAQ report to Google Sheets...")

    headers = [
        'Product Title', 'Handle', 'Question', 'Answer',
        'Word Count', 'Health Canada OK', 'Schema JSON', 'Status'
    ]
    rows = []
    for r in results:
        rows.append([
            r['product_title'],
            r['handle'],
            r['question'],
            r['answer'],
            r['word_count'],
            'YES' if r['hc_ok'] else 'NO',
            r['schema_json'] if rows == [] or rows[-1][0] != r['product_title'] else '(see above)',
            r['status'],
        ])

    timestamp = datetime.now().strftime("%Y-%m-%d")
    sheet_title = f"FAQ Content — {timestamp}"
    sheet_url = None

    try:
        exporter = GoogleSheetsExporter()
        sheet_url = exporter.create_sheet(sheet_title, headers, rows)
        print(f"Google Sheet: {sheet_url}")
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        csv_path = export_to_csv(f"faq_content", headers, rows)
        print(f"Google Sheets failed — saved to: {csv_path}")
        sheet_url = csv_path

    # ── Push Live (only if --push_live and not --dry_run)
    if args.push_live and not args.dry_run:
        print(f"\nPushing FAQ updates to Shopify...")
        processed_products = set()
        success_count = 0
        fail_count = 0

        for r in results:
            pid = r['product_id']
            if pid in processed_products:
                continue
            processed_products.add(pid)

            # Gather all FAQs for this product
            faqs = r['faqs']
            schema = build_faq_schema(faqs)
            schema_json = json.dumps(schema)

            ok_schema = set_product_metafield(
                shopify, pid,
                namespace='custom',
                key='faq_schema',
                value=schema_json,
                value_type='json'
            )

            ok_html = True
            if not args.schema_only:
                # Append FAQ HTML to product description
                faq_html = build_faq_html(faqs)
                current_html = r['description_html'] or ''

                # Remove existing FAQ section if present
                current_html = re.sub(
                    r'<h2>Frequently Asked Questions</h2>.*',
                    '', current_html, flags=re.DOTALL
                ).strip()

                new_html = f"{current_html}\n\n{faq_html}"
                ok_html = shopify.update_product_seo(
                    pid,
                    seo_title=None,
                    seo_description=None,
                    body_html=new_html
                )

            if ok_schema and ok_html:
                success_count += 1
                for row in results:
                    if row['product_id'] == pid:
                        row['status'] = 'pushed_live'
            else:
                fail_count += 1
                for row in results:
                    if row['product_id'] == pid:
                        row['status'] = 'push_failed'

            print(f"  {'OK' if ok_schema and ok_html else 'FAIL'} — {r['product_title'][:50]}")

        print(f"\nPushed live: {success_count}/{len(processed_products)}")
        if fail_count:
            print(f"Failed: {fail_count} (see log)")

    elif args.dry_run:
        print("\nDRY RUN — no changes made to Shopify")
        print("Review the Google Sheet, then run with --push_live to apply changes")

    # ── Summary
    unique_products = len(set(r['product_id'] for r in results))
    total_faqs = len(results)
    hc_issues = sum(1 for r in results if not r['hc_ok'])

    print(f"\n{'='*60}")
    print(f"  FAQ GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Products processed:   {unique_products}")
    print(f"  Total FAQ pairs:      {total_faqs}")
    print(f"  Health Canada issues: {hc_issues}")
    print(f"  Report:               {sheet_url}")
    print(f"{'='*60}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Beauty Connect Shop — Shopify FAQ Content Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/shopify_faq_creator.py --dry_run
  python execution/shopify_faq_creator.py --limit 10 --dry_run
  python execution/shopify_faq_creator.py --push_live
  python execution/shopify_faq_creator.py --product_id "gid://shopify/Product/123"
  python execution/shopify_faq_creator.py --collection_id "gid://shopify/Collection/456"
  python execution/shopify_faq_creator.py --skip-gsc --schema-only --dry_run
        """
    )
    parser.add_argument('--dry_run', action='store_true', default=True,
                        help='Generate FAQs and export to Sheets only — no Shopify changes (default: True)')
    parser.add_argument('--push_live', action='store_true',
                        help='Inject FAQ HTML + schema into Shopify (overrides --dry_run)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products to process (default: all)')
    parser.add_argument('--product_id', type=str, default=None,
                        help='Process a single product by Shopify GID')
    parser.add_argument('--collection_id', type=str, default=None,
                        help='Process all products in a collection by Shopify GID')
    parser.add_argument('--skip-gsc', action='store_true',
                        help='Skip pulling Google Search Console data')
    parser.add_argument('--schema-only', action='store_true',
                        help='Generate JSON-LD schema only — do not modify product descriptions')

    args = parser.parse_args()

    # --push_live overrides --dry_run
    if args.push_live:
        args.dry_run = False

    run_faq_creator(args)


if __name__ == '__main__':
    main()
