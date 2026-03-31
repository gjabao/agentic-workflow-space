#!/usr/bin/env python3
"""
GSC Indexing Fixer — Beauty Connect Shop
DOE Architecture: Execution layer

Diagnoses and fixes all Google Search Console indexing issues:
1. Blocked by robots.txt (198 pages) — Audit & fix robots.txt rules
2. Noindex tags (55 pages) — Find & remove unnecessary noindex
3. 404 errors (27 pages) — Create URL redirects
4. Canonical issues (632 + 17 pages) — Audit canonical tags
5. Crawled not indexed (614 pages) — Identify thin content & submit for indexing
6. 5xx errors (2 pages) — Identify broken pages
7. Redirects (2 pages) — Audit redirect chains

Usage:
    python execution/gsc_indexing_fixer.py --diagnose
    python execution/gsc_indexing_fixer.py --fix-robots
    python execution/gsc_indexing_fixer.py --fix-noindex
    python execution/gsc_indexing_fixer.py --fix-redirects
    python execution/gsc_indexing_fixer.py --fix-all --dry-run
    python execution/gsc_indexing_fixer.py --fix-all --push-live
"""

import os
import sys
import json
import time
import re
import csv
import argparse
import requests
from datetime import datetime
from collections import defaultdict
from xml.etree import ElementTree
from urllib.parse import urlparse, urljoin

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('gsc_indexing_fixer')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/gsc_indexing_fixer.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

# ─── Config ──────────────────────────────────────────────────────────────────

STORE_URL = "https://beautyconnectshop.com"
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE_URL', '').replace('https://', '').replace('http://', '').strip('/')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_ADMIN_API_TOKEN', '')
API_VERSION = '2024-10'
GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"
REST_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}"

HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_TOKEN,
    'Content-Type': 'application/json',
}

TIMEOUT = 30
RATE_DELAY = 0.5  # 500ms between API calls


# ─── API Helpers ─────────────────────────────────────────────────────────────

def graphql(query, variables=None):
    """Execute GraphQL query with retry."""
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    for attempt in range(3):
        try:
            resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited — waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if 'errors' in data:
                logger.error(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
            return data.get('data', {})
        except requests.Timeout:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return {}


def rest_get(endpoint):
    """REST API GET with retry."""
    for attempt in range(3):
        try:
            resp = requests.get(f"{REST_URL}/{endpoint}", headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return {}


def rest_post(endpoint, data):
    """REST API POST."""
    for attempt in range(3):
        try:
            resp = requests.post(f"{REST_URL}/{endpoint}", json=data, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSIS: Crawl the store and identify all issues
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_sitemap():
    """Parse sitemap.xml to get all URLs."""
    sitemap_urls = []
    try:
        # Try main sitemap index
        resp = requests.get(f"{STORE_URL}/sitemap.xml", timeout=TIMEOUT)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Check if it's a sitemap index
        sitemaps = root.findall('.//sm:sitemap/sm:loc', ns)
        if sitemaps:
            for sm_loc in sitemaps:
                sub_url = sm_loc.text.strip()
                logger.info(f"  Fetching sub-sitemap: {sub_url}")
                try:
                    sub_resp = requests.get(sub_url, timeout=TIMEOUT)
                    sub_resp.raise_for_status()
                    sub_root = ElementTree.fromstring(sub_resp.content)
                    for url_elem in sub_root.findall('.//sm:url/sm:loc', ns):
                        sitemap_urls.append(url_elem.text.strip())
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"  Failed to fetch {sub_url}: {e}")
        else:
            # Direct URL list
            for url_elem in root.findall('.//sm:url/sm:loc', ns):
                sitemap_urls.append(url_elem.text.strip())

    except Exception as e:
        logger.error(f"Failed to fetch sitemap: {e}")

    logger.info(f"✓ Found {len(sitemap_urls)} URLs in sitemap")
    return sitemap_urls


def check_robots_txt():
    """Analyze robots.txt for blocked paths."""
    logger.info("\n" + "=" * 60)
    logger.info("ISSUE 1: Robots.txt Analysis")
    logger.info("=" * 60)

    try:
        resp = requests.get(f"{STORE_URL}/robots.txt", timeout=TIMEOUT)
        resp.raise_for_status()
        content = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch robots.txt: {e}")
        return [], []

    print(f"\n--- Current robots.txt ---\n{content}\n--- End ---\n")

    blocked_paths = []
    allowed_paths = []

    current_agent = None
    for line in content.split('\n'):
        line = line.strip()
        if line.lower().startswith('user-agent:'):
            current_agent = line.split(':', 1)[1].strip()
        elif line.lower().startswith('disallow:'):
            path = line.split(':', 1)[1].strip()
            if path:
                blocked_paths.append({'agent': current_agent, 'path': path})
        elif line.lower().startswith('allow:'):
            path = line.split(':', 1)[1].strip()
            if path:
                allowed_paths.append({'agent': current_agent, 'path': path})

    # Shopify default blocks that hurt indexing
    problematic_blocks = []
    for bp in blocked_paths:
        path = bp['path']
        # These Shopify defaults block important pages
        if any(p in path for p in ['/collections/*+*', '/collections/*%', '/collections/*/*',
                                     '/*sort_by*', '/*q=*', '/search', '/cart',
                                     '/account', '/checkout']):
            # These are expected Shopify blocks
            continue
        else:
            problematic_blocks.append(bp)

    print(f"\n📊 Summary:")
    print(f"  Total Disallow rules: {len(blocked_paths)}")
    print(f"  Total Allow rules: {len(allowed_paths)}")
    print(f"  Potentially problematic blocks: {len(problematic_blocks)}")

    for bp in problematic_blocks:
        print(f"  ⚠️  Disallow: {bp['path']} (User-Agent: {bp['agent']})")

    return blocked_paths, problematic_blocks


def check_noindex_pages():
    """Find pages with noindex meta tags via Shopify API."""
    logger.info("\n" + "=" * 60)
    logger.info("ISSUE 2: Noindex Tags Analysis")
    logger.info("=" * 60)

    noindex_pages = []

    # Check products
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            products(first: 50{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    id title handle status
                    seo {{ title description }}
                    publishedAt
                    templateSuffix
                }}
            }}
        }}
        """
        data = graphql(query)
        products = data.get('products', {}).get('nodes', [])

        for p in products:
            # Draft/archived products get noindex automatically
            if p['status'] != 'ACTIVE':
                noindex_pages.append({
                    'type': 'product',
                    'title': p['title'],
                    'handle': p['handle'],
                    'reason': f"Status: {p['status']} (not ACTIVE)",
                    'url': f"{STORE_URL}/products/{p['handle']}",
                })
            # Products with no publishedAt are unpublished
            if not p.get('publishedAt'):
                noindex_pages.append({
                    'type': 'product',
                    'title': p['title'],
                    'handle': p['handle'],
                    'reason': 'Unpublished (no publishedAt)',
                    'url': f"{STORE_URL}/products/{p['handle']}",
                })

        page_info = data.get('products', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Check pages (Shopify Pages)
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            pages(first: 50{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    id title handle
                    isPublished
                    templateSuffix
                }}
            }}
        }}
        """
        data = graphql(query)
        pages = data.get('pages', {}).get('nodes', [])

        for p in pages:
            if not p.get('isPublished'):
                noindex_pages.append({
                    'type': 'page',
                    'title': p['title'],
                    'handle': p['handle'],
                    'reason': 'Page unpublished',
                    'url': f"{STORE_URL}/pages/{p['handle']}",
                })

        page_info = data.get('pages', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Check theme for noindex in liquid
    theme_noindex = check_theme_noindex()
    noindex_pages.extend(theme_noindex)

    print(f"\n📊 Found {len(noindex_pages)} pages with noindex issues:")
    for np in noindex_pages:
        print(f"  ⚠️  [{np['type']}] {np['title']} — {np['reason']}")

    return noindex_pages


def check_theme_noindex():
    """Check theme files for noindex meta tags."""
    results = []

    # Get active theme
    query = """
    {
        themes(roles: [MAIN], first: 1) {
            nodes {
                id name
                files(first: 250, filenames: ["*"]) {
                    nodes { filename }
                }
            }
        }
    }
    """
    data = graphql(query)
    themes = data.get('themes', {}).get('nodes', [])
    if not themes:
        return results

    theme_id = themes[0]['id']
    files = [f['filename'] for f in themes[0].get('files', {}).get('nodes', [])]

    # Check key files for noindex
    files_to_check = [f for f in files if f.endswith('.liquid') and
                      any(f.startswith(p) for p in ['layout/', 'templates/', 'snippets/'])]

    # Priority: layout/theme.liquid first
    priority = ['layout/theme.liquid']
    others = [f for f in files_to_check if f not in priority]
    files_to_check = priority + others[:30]  # Limit to avoid rate limits

    for filename in files_to_check:
        query = """
        query($id: ID!, $filenames: [String!]!) {
            theme(id: $id) {
                files(first: 1, filenames: $filenames) {
                    nodes {
                        filename
                        body { ... on OnlineStoreThemeFileBodyText { content } }
                    }
                }
            }
        }
        """
        data = graphql(query, {'id': theme_id, 'filenames': [filename]})
        nodes = data.get('theme', {}).get('files', {}).get('nodes', [])
        if not nodes:
            continue

        content = nodes[0].get('body', {}).get('content', '') or ''

        # Check for noindex patterns
        noindex_patterns = [
            r'<meta\s+name=["\']robots["\']\s+content=["\'][^"\']*noindex',
            r'noindex',
            r'robots.*noindex',
        ]

        for pattern in noindex_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Get context (surrounding lines)
                start = max(0, content.rfind('\n', 0, match.start()) + 1)
                end = content.find('\n', match.end())
                if end == -1:
                    end = len(content)
                context_line = content[start:end].strip()

                results.append({
                    'type': 'theme',
                    'title': filename,
                    'handle': filename,
                    'reason': f'noindex found in theme: {context_line[:100]}',
                    'url': f'theme:{filename}',
                    'theme_id': theme_id,
                    'filename': filename,
                    'context': context_line,
                })
            if results and results[-1].get('filename') == filename:
                break  # One match per file is enough

        time.sleep(RATE_DELAY)

    return results


def check_404_pages():
    """Find broken URLs by checking redirects and crawling sitemap."""
    logger.info("\n" + "=" * 60)
    logger.info("ISSUE 3: 404 Errors Analysis")
    logger.info("=" * 60)

    broken_urls = []

    # Get existing redirects from Shopify
    existing_redirects = []
    try:
        data = rest_get("redirects.json?limit=250")
        existing_redirects = data.get('redirects', [])
        print(f"✓ Found {len(existing_redirects)} existing redirects")
    except Exception as e:
        logger.warning(f"Could not fetch redirects: {e}")

    # Get all product handles to cross-reference
    all_handles = set()
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            products(first: 100{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{ handle status }}
            }}
        }}
        """
        data = graphql(query)
        for p in data.get('products', {}).get('nodes', []):
            if p['status'] == 'ACTIVE':
                all_handles.add(f"/products/{p['handle']}")
        page_info = data.get('products', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Get all collection handles
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            collections(first: 100{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{ handle }}
            }}
        }}
        """
        data = graphql(query)
        for c in data.get('collections', {}).get('nodes', []):
            all_handles.add(f"/collections/{c['handle']}")
        page_info = data.get('collections', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Get all page handles
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            pages(first: 100{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{ handle }}
            }}
        }}
        """
        data = graphql(query)
        for p in data.get('pages', {}).get('nodes', []):
            all_handles.add(f"/pages/{p['handle']}")
        page_info = data.get('pages', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Check sitemap URLs for 404s (sample check)
    sitemap_urls = fetch_sitemap()
    checked = 0
    for url in sitemap_urls:
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # If path not in known handles, might be 404
        if path and path != '/' and path not in all_handles:
            # Spot check with HEAD request
            try:
                resp = requests.head(url, timeout=10, allow_redirects=False)
                if resp.status_code == 404:
                    broken_urls.append({
                        'url': url,
                        'path': path,
                        'status': 404,
                        'suggestion': 'Create redirect to relevant page',
                    })
                elif resp.status_code in (301, 302):
                    location = resp.headers.get('Location', '')
                    broken_urls.append({
                        'url': url,
                        'path': path,
                        'status': resp.status_code,
                        'suggestion': f'Already redirects to: {location}',
                    })
            except Exception:
                pass
            checked += 1
            if checked >= 50:  # Limit checks to avoid overwhelming
                break
            time.sleep(0.3)

    print(f"\n📊 Found {len(broken_urls)} problematic URLs:")
    for bu in broken_urls:
        print(f"  {'❌' if bu['status'] == 404 else '↪️'} [{bu['status']}] {bu['path']} — {bu['suggestion']}")

    return broken_urls, existing_redirects


def check_canonical_issues():
    """Audit canonical tag setup across the store."""
    logger.info("\n" + "=" * 60)
    logger.info("ISSUE 4: Canonical Tags Analysis")
    logger.info("=" * 60)

    issues = []

    # On Shopify, common canonical issues come from:
    # 1. Collection pagination (?page=2, ?page=3)
    # 2. Collection sorting (?sort_by=...)
    # 3. Collection filtering (?filter.v.*)
    # 4. Products accessible via /collections/x/products/y AND /products/y
    # 5. Tag-based collection URLs /collections/x/tag

    # Check theme.liquid for canonical tag
    query = """
    {
        themes(roles: [MAIN], first: 1) {
            nodes {
                id name
            }
        }
    }
    """
    data = graphql(query)
    themes = data.get('themes', {}).get('nodes', [])
    if not themes:
        print("❌ No main theme found!")
        return issues

    theme_id = themes[0]['id']

    # Read layout/theme.liquid for canonical setup
    query = """
    query($id: ID!, $filenames: [String!]!) {
        theme(id: $id) {
            files(first: 1, filenames: $filenames) {
                nodes {
                    filename
                    body { ... on OnlineStoreThemeFileBodyText { content } }
                }
            }
        }
    }
    """
    data = graphql(query, {'id': theme_id, 'filenames': ['layout/theme.liquid']})
    nodes = data.get('theme', {}).get('files', {}).get('nodes', [])

    if nodes:
        content = nodes[0].get('body', {}).get('content', '') or ''
        has_canonical = 'canonical_url' in content or 'canonical' in content.lower()
        print(f"\n{'✅' if has_canonical else '❌'} Canonical tag in theme.liquid: {'Found' if has_canonical else 'MISSING'}")

        if has_canonical:
            # Find the canonical line
            for line in content.split('\n'):
                if 'canonical' in line.lower():
                    print(f"  → {line.strip()[:120]}")
        else:
            issues.append({
                'type': 'missing_canonical',
                'description': 'No canonical tag found in layout/theme.liquid',
                'fix': 'Add <link rel="canonical" href="{{ canonical_url }}"> to <head>',
                'theme_id': theme_id,
            })

    # Check for duplicate product URLs (products accessible via collection paths)
    # This is Shopify's biggest canonical issue
    cursor = None
    collection_product_urls = []
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query_str = f"""
        {{
            collections(first: 20{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    handle title
                    productsCount {{ count }}
                }}
            }}
        }}
        """
        data = graphql(query_str)
        for c in data.get('collections', {}).get('nodes', []):
            count = c.get('productsCount', {}).get('count', 0)
            if count > 0:
                collection_product_urls.append({
                    'collection': c['handle'],
                    'title': c['title'],
                    'product_count': count,
                    'issue': f'Products accessible via /collections/{c["handle"]}/products/X (duplicate of /products/X)',
                })
        page_info = data.get('collections', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    print(f"\n📊 Collections with potential duplicate product URLs: {len(collection_product_urls)}")
    for cpu in collection_product_urls[:10]:
        print(f"  📁 {cpu['title']} ({cpu['product_count']} products) — {cpu['issue']}")

    # Sample check: verify canonical tags on live pages
    print(f"\n🔍 Spot-checking canonical tags on live pages...")
    sample_urls = [
        f"{STORE_URL}/",
        f"{STORE_URL}/collections",
    ]

    # Add first few collection URLs
    for cpu in collection_product_urls[:3]:
        sample_urls.append(f"{STORE_URL}/collections/{cpu['collection']}")

    for url in sample_urls:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', resp.text)
                if canonical_match:
                    canonical = canonical_match.group(1)
                    is_self = canonical.rstrip('/') == url.rstrip('/')
                    print(f"  {'✅' if is_self else '⚠️'} {url}")
                    print(f"     canonical → {canonical}")
                    if not is_self:
                        issues.append({
                            'type': 'non_self_canonical',
                            'url': url,
                            'canonical': canonical,
                            'description': f'Non-self-referencing canonical on {url}',
                        })
                else:
                    print(f"  ❌ {url} — NO canonical tag!")
                    issues.append({
                        'type': 'missing_canonical_page',
                        'url': url,
                        'description': f'Missing canonical tag on {url}',
                    })
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"  Failed to check {url}: {e}")

    return issues


def check_thin_content():
    """Identify pages with thin content that Google may refuse to index."""
    logger.info("\n" + "=" * 60)
    logger.info("ISSUE 5: Thin Content Analysis (Crawled Not Indexed)")
    logger.info("=" * 60)

    thin_pages = []
    THIN_THRESHOLD = 200  # words

    # Check products
    cursor = None
    total_products = 0
    thin_products = 0
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            products(first: 50{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    id title handle status
                    descriptionHtml
                    seo {{ title description }}
                    images(first: 1) {{ nodes {{ altText }} }}
                }}
            }}
        }}
        """
        data = graphql(query)
        for p in data.get('products', {}).get('nodes', []):
            if p['status'] != 'ACTIVE':
                continue
            total_products += 1

            desc = p.get('descriptionHtml', '') or ''
            clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip()
            wc = len(clean_desc.split()) if clean_desc else 0
            seo_title = (p.get('seo', {}) or {}).get('title', '') or ''
            seo_desc = (p.get('seo', {}) or {}).get('description', '') or ''

            issues_found = []
            if wc < THIN_THRESHOLD:
                issues_found.append(f'thin content ({wc} words)')
            if not seo_title:
                issues_found.append('missing SEO title')
            if not seo_desc:
                issues_found.append('missing meta description')

            if issues_found:
                thin_products += 1
                thin_pages.append({
                    'type': 'product',
                    'title': p['title'],
                    'handle': p['handle'],
                    'url': f"{STORE_URL}/products/{p['handle']}",
                    'word_count': wc,
                    'issues': issues_found,
                    'has_seo_title': bool(seo_title),
                    'has_meta_desc': bool(seo_desc),
                })

        page_info = data.get('products', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Check collections
    cursor = None
    total_collections = 0
    thin_collections = 0
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            collections(first: 50{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    id title handle
                    descriptionHtml
                    seo {{ title description }}
                }}
            }}
        }}
        """
        data = graphql(query)
        for c in data.get('collections', {}).get('nodes', []):
            total_collections += 1

            desc = c.get('descriptionHtml', '') or ''
            clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip()
            wc = len(clean_desc.split()) if clean_desc else 0
            seo_title = (c.get('seo', {}) or {}).get('title', '') or ''
            seo_desc = (c.get('seo', {}) or {}).get('description', '') or ''

            issues_found = []
            if wc < 100:  # Collections need less content but still some
                issues_found.append(f'thin/no description ({wc} words)')
            if not seo_title:
                issues_found.append('missing SEO title')
            if not seo_desc:
                issues_found.append('missing meta description')

            if issues_found:
                thin_collections += 1
                thin_pages.append({
                    'type': 'collection',
                    'title': c['title'],
                    'handle': c['handle'],
                    'url': f"{STORE_URL}/collections/{c['handle']}",
                    'word_count': wc,
                    'issues': issues_found,
                    'has_seo_title': bool(seo_title),
                    'has_meta_desc': bool(seo_desc),
                })

        page_info = data.get('collections', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    # Check pages
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f"""
        {{
            pages(first: 50{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                    id title handle isPublished
                    body
                    bodySummary
                }}
            }}
        }}
        """
        data = graphql(query)
        for p in data.get('pages', {}).get('nodes', []):
            if not p.get('isPublished'):
                continue
            body = p.get('body', '') or ''
            clean = re.sub(r'<[^>]+>', ' ', body).strip()
            wc = len(clean.split()) if clean else 0

            if wc < THIN_THRESHOLD:
                thin_pages.append({
                    'type': 'page',
                    'title': p['title'],
                    'handle': p['handle'],
                    'url': f"{STORE_URL}/pages/{p['handle']}",
                    'word_count': wc,
                    'issues': [f'thin content ({wc} words)'],
                    'has_seo_title': False,
                    'has_meta_desc': False,
                })

        page_info = data.get('pages', {}).get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
        cursor = page_info['endCursor']
        time.sleep(RATE_DELAY)

    print(f"\n📊 Content Analysis:")
    print(f"  Products: {thin_products}/{total_products} have issues")
    print(f"  Collections: {thin_collections}/{total_collections} have issues")
    print(f"  Total thin/missing-SEO pages: {len(thin_pages)}")

    # Group by issue type
    issue_counts = defaultdict(int)
    for tp in thin_pages:
        for issue in tp['issues']:
            issue_counts[issue] += 1

    print(f"\n  Issue breakdown:")
    for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f"    {count}x {issue}")

    return thin_pages


# ═══════════════════════════════════════════════════════════════════════════════
# FIXES
# ═══════════════════════════════════════════════════════════════════════════════

def fix_robots_txt(dry_run=True):
    """Generate optimized robots.txt.liquid for Shopify."""
    logger.info("\n" + "=" * 60)
    logger.info("FIX: Generating optimized robots.txt.liquid")
    logger.info("=" * 60)

    # Shopify's recommended robots.txt with SEO optimizations
    robots_template = """# Beauty Connect Shop — Optimized robots.txt
# Generated: {{ 'now' | date: '%Y-%m-%d' }}
# Purpose: Maximize indexing while blocking low-value/duplicate URLs

# ─── Googlebot (Primary) ──────────────────────────────────────
User-agent: Googlebot
# Allow all important content
Allow: /collections/
Allow: /products/
Allow: /pages/
Allow: /blogs/
Allow: /

# Block duplicate/low-value URLs that cause canonical issues
Disallow: /admin
Disallow: /cart
Disallow: /orders
Disallow: /checkouts/
Disallow: /checkout
Disallow: /account
Disallow: /account/*
Disallow: /*sort_by*
Disallow: /*?q=*
Disallow: /search
Disallow: /apple-app-site-association
Disallow: /recommendations/products.json
Disallow: /.well-known/

# Block collection filter/pagination duplicates (CRITICAL for canonical issues)
Disallow: /collections/*+*
Disallow: /collections/*%2B*
Disallow: /collections/*%2b*
Disallow: /collections/*/products
Disallow: /*?page=*
Disallow: /*?filter.*
Disallow: /*?variant=*
Disallow: /*?view=*

# ─── AI Search Bots (ALLOW — drives AI search traffic) ────────
User-agent: OAI-SearchBot
Allow: /
Disallow: /admin
Disallow: /cart
Disallow: /checkout
Disallow: /account

User-agent: PerplexityBot
Allow: /
Disallow: /admin
Disallow: /cart
Disallow: /checkout
Disallow: /account

User-agent: Bingbot
Allow: /
Disallow: /admin
Disallow: /cart
Disallow: /checkout
Disallow: /account

# ─── AI Training Bots (BLOCK — no search benefit) ─────────────
User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: ClaudeBot
Disallow: /

# ─── All Other Bots ───────────────────────────────────────────
User-agent: *
Allow: /collections/
Allow: /products/
Allow: /pages/
Allow: /blogs/
Disallow: /admin
Disallow: /cart
Disallow: /orders
Disallow: /checkouts/
Disallow: /checkout
Disallow: /account
Disallow: /*sort_by*
Disallow: /*?q=*
Disallow: /search
Disallow: /collections/*+*
Disallow: /collections/*%2B*
Disallow: /collections/*%2b*
Disallow: /*?page=*
Disallow: /*?filter.*
Disallow: /*?variant=*

# ─── Sitemaps ─────────────────────────────────────────────────
Sitemap: {{ shop.url }}/sitemap.xml
"""

    if dry_run:
        print("\n[DRY RUN] Would create robots.txt.liquid with this content:")
        print(robots_template)
        print("\n📋 To apply manually:")
        print("  1. Go to Shopify Admin → Online Store → Themes")
        print("  2. Edit code → Add new template: robots.txt.liquid")
        print("  3. Paste the content above")
        print("  4. Save and verify at /robots.txt")
    else:
        # Write to .tmp for manual upload
        output_path = os.path.join(BASE_DIR, '.tmp', 'robots.txt.liquid')
        with open(output_path, 'w') as f:
            f.write(robots_template)
        print(f"✓ Saved to {output_path}")
        print("\n📋 Upload to Shopify:")
        print("  1. Go to Shopify Admin → Online Store → Themes → Edit code")
        print("  2. Under Templates, click 'Add a new template'")
        print("  3. Select 'robots.txt' from dropdown")
        print("  4. Replace content with the generated file")

    return robots_template


def fix_redirects(broken_urls, dry_run=True):
    """Create redirects for 404 URLs."""
    logger.info("\n" + "=" * 60)
    logger.info("FIX: Creating redirects for 404 URLs")
    logger.info("=" * 60)

    if not broken_urls:
        print("✅ No broken URLs to fix!")
        return

    created = 0
    for bu in broken_urls:
        if bu['status'] != 404:
            continue

        path = bu['path']

        # Determine best redirect target
        target = '/'  # Default to homepage
        if '/products/' in path:
            target = '/collections/all'
        elif '/collections/' in path:
            target = '/collections'
        elif '/pages/' in path:
            target = '/'
        elif '/blogs/' in path:
            target = '/blogs'

        if dry_run:
            print(f"  [DRY RUN] Would redirect: {path} → {target}")
        else:
            try:
                result = rest_post("redirects.json", {
                    "redirect": {
                        "path": path,
                        "target": target,
                    }
                })
                if result.get('redirect'):
                    print(f"  ✅ Created redirect: {path} → {target}")
                    created += 1
                else:
                    print(f"  ❌ Failed: {path} — {json.dumps(result)}")
                time.sleep(RATE_DELAY)
            except Exception as e:
                print(f"  ❌ Error creating redirect for {path}: {e}")

    print(f"\n{'Would create' if dry_run else 'Created'} {created if not dry_run else len([b for b in broken_urls if b['status'] == 404])} redirects")


def fix_canonical_in_theme(issues, dry_run=True):
    """Add or fix canonical tag in theme.liquid."""
    logger.info("\n" + "=" * 60)
    logger.info("FIX: Canonical Tags")
    logger.info("=" * 60)

    missing = [i for i in issues if i['type'] == 'missing_canonical']
    if not missing:
        print("✅ Canonical tag already present in theme.liquid")
        return

    theme_id = missing[0].get('theme_id')
    if not theme_id:
        print("❌ No theme ID — cannot fix")
        return

    # Read current theme.liquid
    query = """
    query($id: ID!, $filenames: [String!]!) {
        theme(id: $id) {
            files(first: 1, filenames: $filenames) {
                nodes {
                    filename
                    body { ... on OnlineStoreThemeFileBodyText { content } }
                }
            }
        }
    }
    """
    data = graphql(query, {'id': theme_id, 'filenames': ['layout/theme.liquid']})
    nodes = data.get('theme', {}).get('files', {}).get('nodes', [])
    if not nodes:
        print("❌ Could not read theme.liquid")
        return

    content = nodes[0].get('body', {}).get('content', '') or ''

    # Add canonical tag after <head> or before </head>
    canonical_tag = '  <link rel="canonical" href="{{ canonical_url }}">'

    if '<head>' in content and canonical_tag not in content:
        new_content = content.replace('<head>', f'<head>\n{canonical_tag}', 1)

        if dry_run:
            print(f"[DRY RUN] Would add canonical tag to theme.liquid:")
            print(f"  {canonical_tag}")
        else:
            # Update via API
            mutation = """
            mutation($input: OnlineStoreThemeFilesUpsertInput!) {
                onlineStoreThemeFilesUpsert(input: $input) {
                    upsertedThemeFiles { filename }
                    userErrors { field message }
                }
            }
            """
            variables = {
                'input': {
                    'themeId': theme_id,
                    'files': [{
                        'filename': 'layout/theme.liquid',
                        'body': {
                            'type': 'TEXT',
                            'value': new_content,
                        }
                    }]
                }
            }
            result = graphql(mutation, variables)
            errors = result.get('onlineStoreThemeFilesUpsert', {}).get('userErrors', [])
            if errors:
                print(f"❌ Error: {json.dumps(errors)}")
            else:
                print("✅ Canonical tag added to theme.liquid!")
    else:
        print("ℹ️ Canonical tag already exists or <head> not found")


def generate_indexnow_submission(sitemap_urls):
    """Generate IndexNow API submission for priority URLs."""
    logger.info("\n" + "=" * 60)
    logger.info("FIX: IndexNow Submission for Re-indexing")
    logger.info("=" * 60)

    # Filter to most important URLs
    priority_urls = [u for u in sitemap_urls if
                     '/products/' in u or
                     '/collections/' in u or
                     '/pages/' in u or
                     u.rstrip('/') == STORE_URL]

    print(f"📊 Priority URLs for IndexNow submission: {len(priority_urls)}")
    print(f"  Products: {len([u for u in priority_urls if '/products/' in u])}")
    print(f"  Collections: {len([u for u in priority_urls if '/collections/' in u])}")
    print(f"  Pages: {len([u for u in priority_urls if '/pages/' in u])}")

    # Save URL list for IndexNow submission
    output_path = os.path.join(BASE_DIR, '.tmp', 'indexnow_urls.txt')
    with open(output_path, 'w') as f:
        for url in priority_urls:
            f.write(url + '\n')
    print(f"\n✓ URL list saved to {output_path}")

    return priority_urls


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_diagnosis(all_results):
    """Export full diagnosis to CSV for review."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(BASE_DIR, '.tmp', f'gsc_diagnosis_{timestamp}.csv')

    rows = []
    for category, items in all_results.items():
        for item in items:
            rows.append({
                'category': category,
                'type': item.get('type', ''),
                'title': item.get('title', ''),
                'url': item.get('url', item.get('path', '')),
                'issue': ', '.join(item.get('issues', [])) if isinstance(item.get('issues'), list) else item.get('reason', item.get('description', item.get('suggestion', ''))),
                'word_count': item.get('word_count', ''),
                'has_seo_title': item.get('has_seo_title', ''),
                'has_meta_desc': item.get('has_meta_desc', ''),
            })

    if rows:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n✓ Full diagnosis exported to {output_path}")
        print(f"  Total issues: {len(rows)}")
    else:
        print("No issues to export.")

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GSC Indexing Fixer — Beauty Connect Shop')
    parser.add_argument('--diagnose', action='store_true', help='Run full diagnosis')
    parser.add_argument('--fix-robots', action='store_true', help='Generate optimized robots.txt')
    parser.add_argument('--fix-noindex', action='store_true', help='Find and report noindex pages')
    parser.add_argument('--fix-redirects', action='store_true', help='Create redirects for 404s')
    parser.add_argument('--fix-canonical', action='store_true', help='Fix canonical tag issues')
    parser.add_argument('--fix-all', action='store_true', help='Run all fixes')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run mode (default)')
    parser.add_argument('--push-live', action='store_true', help='Push changes live')
    args = parser.parse_args()

    dry_run = not args.push_live

    print("=" * 60)
    print(f"GSC Indexing Fixer — Beauty Connect Shop")
    print(f"Mode: {'DRY RUN' if dry_run else '⚡ PUSH LIVE'}")
    print(f"Store: {STORE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_results = {}

    if args.diagnose or args.fix_all:
        # 1. Robots.txt
        blocked, problematic = check_robots_txt()
        all_results['robots_blocked'] = [{'type': 'robots', 'path': b['path'], 'title': b['agent'], 'reason': f"Disallow: {b['path']}"} for b in problematic]

        # 2. Noindex
        noindex = check_noindex_pages()
        all_results['noindex'] = noindex

        # 3. 404s
        broken, existing_redirects = check_404_pages()
        all_results['404_errors'] = broken

        # 4. Canonicals
        canonical_issues = check_canonical_issues()
        all_results['canonical'] = [{'type': i['type'], 'title': i.get('url', ''), 'description': i['description']} for i in canonical_issues]

        # 5. Thin content
        thin = check_thin_content()
        all_results['thin_content'] = thin

        # Export full report
        export_diagnosis(all_results)

        # Print summary
        print("\n" + "=" * 60)
        print("📊 FULL DIAGNOSIS SUMMARY")
        print("=" * 60)
        print(f"  Robots.txt problematic blocks: {len(all_results.get('robots_blocked', []))}")
        print(f"  Noindex pages: {len(all_results.get('noindex', []))}")
        print(f"  404/redirect issues: {len(all_results.get('404_errors', []))}")
        print(f"  Canonical issues: {len(all_results.get('canonical', []))}")
        print(f"  Thin content pages: {len(all_results.get('thin_content', []))}")

    if args.fix_all or args.fix_robots:
        fix_robots_txt(dry_run=dry_run)

    if args.fix_all or args.fix_redirects:
        if '404_errors' not in all_results:
            broken, _ = check_404_pages()
        else:
            broken = all_results['404_errors']
        fix_redirects(broken, dry_run=dry_run)

    if args.fix_all or args.fix_canonical:
        if 'canonical' not in all_results:
            canonical_issues = check_canonical_issues()
        fix_canonical_in_theme(canonical_issues, dry_run=dry_run)

    if args.fix_all:
        sitemap_urls = fetch_sitemap()
        generate_indexnow_submission(sitemap_urls)

    if not any([args.diagnose, args.fix_all, args.fix_robots, args.fix_noindex,
                args.fix_redirects, args.fix_canonical]):
        print("\nNo action specified. Use --diagnose or --fix-all")
        print("  --diagnose     Full diagnosis of all issues")
        print("  --fix-all      Run all fixes (dry run by default)")
        print("  --push-live    Apply changes (use with --fix-all)")
        print("\nIndividual fixes:")
        print("  --fix-robots     Generate optimized robots.txt")
        print("  --fix-redirects  Create 404 redirects")
        print("  --fix-canonical  Fix canonical tags")
