#!/usr/bin/env python3
"""
Beauty Connect Shop — Shopify Schema Markup Injector
DOE Architecture Execution Script v1.0

Generates JSON-LD structured data (Product, Organization, BreadcrumbList, FAQ)
and optionally injects into Shopify via Admin API metafields.

Usage:
    python execution/shopify_schema_injector.py --dry_run
    python execution/shopify_schema_injector.py --dry_run --type product --limit 10
    python execution/shopify_schema_injector.py --push_live --type all
    python execution/shopify_schema_injector.py --dry_run --type organization
"""

import os
import sys
import json
import logging
import argparse
import re
import time
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Add parent to path so seo_shared imports work when run from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    export_to_csv,
    load_brand_config,
    strip_html,
    BASE_DIR,
    logger,
)

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)
log_handler = logging.FileHandler('.tmp/shopify_schema.log')
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(log_handler)


# ─── Schema Generators ───────────────────────────────────────────────────────

def generate_product_schema(product: Dict, store_url: str) -> Dict:
    """
    Generate Product JSON-LD schema for a single Shopify product.
    Requires product fetched with variants and images.
    """
    # Extract first variant for price/sku/availability
    variant_edges = product.get('variants', {}).get('edges', [])
    variant = variant_edges[0]['node'] if variant_edges else {}

    sku = variant.get('sku', '')
    price = variant.get('price', '0.00')
    available = variant.get('availableForSale', False)

    # Extract images
    image_edges = product.get('images', {}).get('edges', [])
    images = [edge['node']['url'] for edge in image_edges if edge.get('node', {}).get('url')]

    # Clean description
    description_html = product.get('descriptionHtml', '') or ''
    description = strip_html(description_html).strip()
    if len(description) > 500:
        description = description[:497] + '...'

    # SEO fields
    seo = product.get('seo', {}) or {}
    seo_description = seo.get('description') or description

    handle = product.get('handle', '')
    product_url = f"{store_url}/products/{handle}" if handle else store_url

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.get('title', ''),
        "image": images,
        "description": seo_description or description,
        "sku": sku,
        "brand": {
            "@type": "Brand",
            "name": product.get('vendor', '') or "Beauty Connect Shop"
        },
        "offers": {
            "@type": "Offer",
            "url": product_url,
            "priceCurrency": "CAD",
            "price": price,
            "availability": "https://schema.org/InStock" if available else "https://schema.org/OutOfStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {
                "@type": "Organization",
                "name": "Beauty Connect Shop"
            }
        }
    }

    # Remove empty fields
    if not sku:
        del schema['sku']
    if not images:
        del schema['image']

    return schema


def generate_organization_schema(brand_config: Dict) -> Dict:
    """Generate Organization JSON-LD schema for the homepage."""
    social = brand_config.get('social', {})
    same_as = []
    for key in ['instagram', 'facebook', 'tiktok', 'youtube', 'twitter', 'linkedin']:
        url = social.get(key, '')
        if url:
            same_as.append(url)

    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand_config.get('brand_name', 'Beauty Connect Shop'),
        "url": brand_config.get('store_url', 'https://beautyconnectshop.com'),
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer service"
        }
    }

    logo_url = brand_config.get('logo_url', '')
    if logo_url:
        schema['logo'] = logo_url

    if same_as:
        schema['sameAs'] = same_as

    return schema


def generate_breadcrumb_schema(page_type: str, page_title: str,
                                page_handle: str, store_url: str,
                                collection_title: str = None,
                                collection_handle: str = None) -> Dict:
    """
    Generate BreadcrumbList JSON-LD schema.
    Supports product and collection page types.
    """
    items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": store_url
        }
    ]

    if page_type == 'collection':
        items.append({
            "@type": "ListItem",
            "position": 2,
            "name": page_title,
            "item": f"{store_url}/collections/{page_handle}"
        })
    elif page_type == 'product':
        pos = 2
        if collection_title and collection_handle:
            items.append({
                "@type": "ListItem",
                "position": pos,
                "name": collection_title,
                "item": f"{store_url}/collections/{collection_handle}"
            })
            pos += 1
        items.append({
            "@type": "ListItem",
            "position": pos,
            "name": page_title,
            "item": f"{store_url}/products/{page_handle}"
        })

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items
    }


def generate_faq_schema(description_html: str) -> Optional[Dict]:
    """
    Generate FAQPage JSON-LD schema if product description contains Q&A patterns.
    Looks for patterns like:
      Q: ... / A: ...
      **Q:** ... / **A:** ...
      <strong>Q:</strong> ...
      Question: ... / Answer: ...
    Returns None if no Q&A found.
    """
    text = description_html or ''

    # Pattern 1: Q: ... A: ... (with optional HTML bold tags)
    qa_pattern = re.compile(
        r'(?:<strong>|<b>|\*\*)?'
        r'(?:Q|Question)\s*[:\.]?\s*'
        r'(?:</strong>|</b>|\*\*)?'
        r'\s*(.+?)\s*'
        r'(?:<strong>|<b>|\*\*)?'
        r'(?:A|Answer)\s*[:\.]?\s*'
        r'(?:</strong>|</b>|\*\*)?'
        r'\s*(.+?)(?=(?:<strong>|<b>|\*\*)?(?:Q|Question)\s*[:\.]?|$)',
        re.IGNORECASE | re.DOTALL
    )

    matches = qa_pattern.findall(text)
    if not matches:
        return None

    faq_entries = []
    for question_raw, answer_raw in matches:
        question = strip_html(question_raw).strip()
        answer = strip_html(answer_raw).strip()
        if question and answer and len(question) > 5 and len(answer) > 5:
            faq_entries.append({
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer
                }
            })

    if not faq_entries:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_entries
    }


# ─── Shopify Metafield Push ──────────────────────────────────────────────────

def push_schema_metafield(client: ShopifyClient, owner_id: str, json_ld: str) -> bool:
    """
    Push JSON-LD schema to Shopify via metafieldsSet mutation.
    Uses namespace 'custom' and key 'json_ld'.
    """
    mutation = """
    mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields {
          id
          namespace
          key
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "metafields": [
            {
                "ownerId": owner_id,
                "namespace": "custom",
                "key": "json_ld",
                "type": "json",
                "value": json_ld
            }
        ]
    }

    data = client._graphql(mutation, variables)
    if not data:
        logger.error(f"   Failed to set metafield for {owner_id}")
        return False

    errors = data.get('metafieldsSet', {}).get('userErrors', [])
    if errors:
        logger.error(f"   Metafield errors for {owner_id}: {errors}")
        return False

    return True


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_json_ld(schema: Dict) -> bool:
    """Validate that a schema dict is valid JSON-LD (parseable JSON with @context)."""
    try:
        json_str = json.dumps(schema)
        parsed = json.loads(json_str)
        return '@context' in parsed and '@type' in parsed
    except (json.JSONDecodeError, TypeError):
        return False


# ─── Fetch Products with Variants ─────────────────────────────────────────────

def fetch_products_with_variants(client: ShopifyClient, limit: Optional[int] = None) -> List[Dict]:
    """Fetch products including variant data (price, sku, availability)."""
    query = """
    query FetchProductsSchema($cursor: String) {
      products(first: 50, after: $cursor) {
        edges {
          node {
            id
            title
            handle
            descriptionHtml
            vendor
            variants(first: 1) {
              edges {
                node {
                  sku
                  price
                  availableForSale
                }
              }
            }
            images(first: 3) {
              edges {
                node {
                  url
                  altText
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
    """
    products = []
    cursor = None

    while True:
        variables = {'cursor': cursor} if cursor else {}
        data = client._graphql(query, variables)

        if not data or 'products' not in data:
            break

        edges = data['products']['edges']
        for edge in edges:
            products.append(edge['node'])
            if limit and len(products) >= limit:
                logger.info(f"   Fetched {len(products)} products (limit reached)")
                return products

        page_info = data['products']['pageInfo']
        if not page_info['hasNextPage']:
            break

        cursor = page_info['endCursor']
        time.sleep(0.5)

    logger.info(f"   Fetched {len(products)} total products")
    return products


# ─── Main Runner ──────────────────────────────────────────────────────────────

def run_schema_injector(args):
    """Main execution logic for schema injection."""
    start_time = time.time()
    schema_type = args.type
    dry_run = args.dry_run
    limit = args.limit

    logger.info("=" * 60)
    logger.info("   Beauty Connect Shop — Schema Markup Injector")
    logger.info(f"   Mode: {'DRY RUN' if dry_run else 'PUSH LIVE'}")
    logger.info(f"   Schema type: {schema_type}")
    if limit:
        logger.info(f"   Limit: {limit} products")
    logger.info("=" * 60)

    # Initialize Shopify client
    client = ShopifyClient()
    brand_config = load_brand_config()
    store_url = brand_config.get('store_url', 'https://beautyconnectshop.com').rstrip('/')

    # Collect all schema results for audit export
    audit_rows = []
    all_schemas = []
    push_results = {'success': 0, 'failed': 0}

    # ─── Product Schema ──────────────────────────────────────────────────────
    if schema_type in ('product', 'all'):
        logger.info("\n   Generating Product schemas...")
        products = fetch_products_with_variants(client, limit)

        for i, product in enumerate(products):
            title = product.get('title', 'Unknown')
            product_id = product.get('id', '')

            # Product schema
            product_schema = generate_product_schema(product, store_url)
            is_valid = validate_json_ld(product_schema)
            json_str = json.dumps(product_schema, indent=2)

            logger.info(f"\n   [{i+1}/{len(products)}] {title}")
            if not dry_run and not is_valid:
                logger.warning(f"      Invalid JSON-LD — skipping push")
            elif not dry_run and is_valid:
                # Push to Shopify metafield
                success = push_schema_metafield(client, product_id, json.dumps(product_schema))
                if success:
                    push_results['success'] += 1
                    logger.info(f"      Pushed to Shopify metafield")
                else:
                    push_results['failed'] += 1
                    logger.error(f"      Failed to push metafield")
            else:
                # Dry run — print schema
                print(f"\n--- Product: {title} ---")
                print(json_str)

            audit_rows.append([
                f"/products/{product.get('handle', '')}",
                "Product",
                "Yes" if is_valid else "No",
                str(len(json_str))
            ])
            all_schemas.append(('Product', title, product_schema, is_valid))

            # Breadcrumb for product
            if schema_type == 'all':
                breadcrumb = generate_breadcrumb_schema(
                    'product', title, product.get('handle', ''), store_url
                )
                bc_valid = validate_json_ld(breadcrumb)
                bc_json = json.dumps(breadcrumb, indent=2)

                if dry_run:
                    print(f"\n--- Breadcrumb: {title} ---")
                    print(bc_json)

                audit_rows.append([
                    f"/products/{product.get('handle', '')}",
                    "BreadcrumbList",
                    "Yes" if bc_valid else "No",
                    str(len(bc_json))
                ])

            # FAQ schema if Q&A patterns exist
            faq_schema = generate_faq_schema(product.get('descriptionHtml', ''))
            if faq_schema:
                faq_valid = validate_json_ld(faq_schema)
                faq_json = json.dumps(faq_schema, indent=2)

                if dry_run:
                    print(f"\n--- FAQ: {title} ---")
                    print(faq_json)

                audit_rows.append([
                    f"/products/{product.get('handle', '')}",
                    "FAQPage",
                    "Yes" if faq_valid else "No",
                    str(len(faq_json))
                ])
                all_schemas.append(('FAQPage', title, faq_schema, faq_valid))

            # Progress update every 10 products
            if (i + 1) % 10 == 0:
                logger.info(f"      Progress: {i+1}/{len(products)} products processed")

    # ─── Organization Schema ─────────────────────────────────────────────────
    if schema_type in ('organization', 'all'):
        logger.info("\n   Generating Organization schema...")
        org_schema = generate_organization_schema(brand_config)
        org_valid = validate_json_ld(org_schema)
        org_json = json.dumps(org_schema, indent=2)

        if dry_run:
            print(f"\n--- Organization Schema ---")
            print(org_json)
        else:
            # Push to shop metafield via shop resource
            shop_data = client._graphql("{ shop { id } }")
            shop_id = shop_data.get('shop', {}).get('id', '')
            if shop_id:
                success = push_schema_metafield(client, shop_id, json.dumps(org_schema))
                if success:
                    push_results['success'] += 1
                    logger.info("      Pushed Organization schema to shop metafield")
                else:
                    push_results['failed'] += 1

        audit_rows.append([
            "/",
            "Organization",
            "Yes" if org_valid else "No",
            str(len(org_json))
        ])

    # ─── Breadcrumb Schema (standalone) ──────────────────────────────────────
    if schema_type == 'breadcrumb':
        logger.info("\n   Generating Breadcrumb schemas for products and collections...")
        products = fetch_products_with_variants(client, limit)

        for product in products:
            title = product.get('title', 'Unknown')
            handle = product.get('handle', '')
            breadcrumb = generate_breadcrumb_schema('product', title, handle, store_url)
            bc_valid = validate_json_ld(breadcrumb)
            bc_json = json.dumps(breadcrumb, indent=2)

            if dry_run:
                print(f"\n--- Breadcrumb: {title} ---")
                print(bc_json)

            audit_rows.append([
                f"/products/{handle}",
                "BreadcrumbList",
                "Yes" if bc_valid else "No",
                str(len(bc_json))
            ])

        # Also fetch collections for breadcrumbs
        collections = client.fetch_all_collections(limit)
        for coll in collections:
            title = coll.get('title', 'Unknown')
            handle = coll.get('handle', '')
            breadcrumb = generate_breadcrumb_schema('collection', title, handle, store_url)
            bc_valid = validate_json_ld(breadcrumb)
            bc_json = json.dumps(breadcrumb, indent=2)

            if dry_run:
                print(f"\n--- Breadcrumb: {title} ---")
                print(bc_json)

            audit_rows.append([
                f"/collections/{handle}",
                "BreadcrumbList",
                "Yes" if bc_valid else "No",
                str(len(bc_json))
            ])

    # ─── Export Audit ─────────────────────────────────────────────────────────
    if audit_rows:
        date_str = datetime.now().strftime('%Y-%m-%d')
        sheet_title = f"Schema Audit — {date_str}"
        headers = ["Page", "Schema Type", "Valid JSON", "Character Count"]

        try:
            exporter = GoogleSheetsExporter()
            sheet_url = exporter.create_sheet(sheet_title, headers, audit_rows)
            logger.info(f"\n   Google Sheet: {sheet_url}")
        except Exception as e:
            logger.warning(f"   Google Sheets export failed: {e}")
            logger.info("   Falling back to CSV...")
            csv_path = export_to_csv(f"schema_audit", headers, audit_rows)
            logger.info(f"   CSV exported: {csv_path}")

    # ─── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("   Schema Injection Complete!")
    logger.info(f"   Total schemas generated: {len(audit_rows)}")
    if not dry_run:
        logger.info(f"   Pushed: {push_results['success']}  |  Failed: {push_results['failed']}")
    logger.info(f"   Time: {elapsed:.1f}s")
    logger.info("=" * 60)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Beauty Connect Shop — Shopify Schema Markup Injector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/shopify_schema_injector.py --dry_run
  python execution/shopify_schema_injector.py --dry_run --type product --limit 10
  python execution/shopify_schema_injector.py --push_live --type all
  python execution/shopify_schema_injector.py --dry_run --type organization
        """
    )
    parser.add_argument('--dry_run', action='store_true', default=True,
                        help='Generate schemas and export to Sheet only — no Shopify changes (default: True)')
    parser.add_argument('--push_live', action='store_true',
                        help='Inject schema into Shopify metafields (overrides --dry_run)')
    parser.add_argument('--type', type=str, default='all',
                        choices=['product', 'organization', 'breadcrumb', 'all'],
                        help='Which schema type to generate (default: all)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products to process (default: all)')

    args = parser.parse_args()

    # --push_live overrides --dry_run
    if args.push_live:
        args.dry_run = False

    run_schema_injector(args)


if __name__ == '__main__':
    main()
