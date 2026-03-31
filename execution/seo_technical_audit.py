#!/usr/bin/env python3
"""
Beauty Connect Shop — Technical SEO Audit (READ-ONLY)
DOE Architecture Execution Script v1.0

Performs a comprehensive technical SEO audit without modifying any data:
  A. Shopify Data Audit — meta titles, descriptions, alt text, thin content
  B. Site Crawl Audit — robots.txt, sitemap, schema markup, canonical tags
  C. GSC Index Status — indexed pages, top queries baseline
  D. Core Web Vitals — PageSpeed Insights for mobile performance

Exports results to Google Sheets (multi-tab) with CSV fallback.

Usage:
    python execution/seo_technical_audit.py
    python execution/seo_technical_audit.py --site https://beautyconnectshop.com
    python execution/seo_technical_audit.py --limit 50
    python execution/seo_technical_audit.py --skip-pagespeed
"""

import os
import sys
import json
import logging
import argparse
import re
import time
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter
from xml.etree import ElementTree

from dotenv import load_dotenv

load_dotenv()

# Add execution dir to path so seo_shared imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    GSCClient,
    export_to_csv,
    strip_html,
    word_count,
    BASE_DIR,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('seo_technical_audit')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/seo_technical_audit.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

# ─── Constants ────────────────────────────────────────────────────────────────
REQUESTS_TIMEOUT = 30
DEFAULT_SITE = "https://beautyconnectshop.com"
GSC_SITE_URL = "sc-domain:beautyconnectshop.com"

META_TITLE_MIN = 50
META_TITLE_MAX = 60
META_DESC_MIN = 140
META_DESC_MAX = 155
THIN_CONTENT_THRESHOLD = 200  # words

AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "PerplexityBot", "Google-Extended"]

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


# ═══════════════════════════════════════════════════════════════════════════════
# A. SHOPIFY DATA AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

def audit_products(client: ShopifyClient, limit: Optional[int] = None) -> Tuple[List[Dict], Dict]:
    """Audit all products for SEO issues. Returns (issues_list, summary_dict)."""
    logger.info("📦 Fetching products from Shopify...")
    products = client.fetch_all_products(limit=limit)
    logger.info(f"✓ Fetched {len(products)} products")

    issues = []
    meta_titles = []
    meta_descs = []
    stats = {
        'total': len(products),
        'missing_meta_title': 0,
        'short_meta_title': 0,
        'long_meta_title': 0,
        'missing_meta_desc': 0,
        'short_meta_desc': 0,
        'long_meta_desc': 0,
        'missing_alt_text': 0,
        'thin_content': 0,
        'duplicate_titles': 0,
        'duplicate_descs': 0,
    }

    for p in products:
        title = p.get('title', '')
        handle = p.get('handle', '')
        seo = p.get('seo', {}) or {}
        seo_title = seo.get('title', '') or ''
        seo_desc = seo.get('description', '') or ''
        body = p.get('descriptionHtml', '') or ''
        images = [e['node'] for e in (p.get('images', {}).get('edges', []))]

        row_issues = []

        # Meta title checks
        if not seo_title.strip():
            row_issues.append("Missing meta title")
            stats['missing_meta_title'] += 1
        else:
            meta_titles.append(seo_title.strip())
            tlen = len(seo_title.strip())
            if tlen < META_TITLE_MIN:
                row_issues.append(f"Short meta title ({tlen} chars, need {META_TITLE_MIN}-{META_TITLE_MAX})")
                stats['short_meta_title'] += 1
            elif tlen > META_TITLE_MAX:
                row_issues.append(f"Long meta title ({tlen} chars, need {META_TITLE_MIN}-{META_TITLE_MAX})")
                stats['long_meta_title'] += 1

        # Meta description checks
        if not seo_desc.strip():
            row_issues.append("Missing meta description")
            stats['missing_meta_desc'] += 1
        else:
            meta_descs.append(seo_desc.strip())
            dlen = len(seo_desc.strip())
            if dlen < META_DESC_MIN:
                row_issues.append(f"Short meta desc ({dlen} chars, need {META_DESC_MIN}-{META_DESC_MAX})")
                stats['short_meta_desc'] += 1
            elif dlen > META_DESC_MAX:
                row_issues.append(f"Long meta desc ({dlen} chars, need {META_DESC_MIN}-{META_DESC_MAX})")
                stats['long_meta_desc'] += 1

        # Image alt text
        missing_alts = [img for img in images if not (img.get('altText') or '').strip()]
        if missing_alts:
            row_issues.append(f"Missing alt text on {len(missing_alts)}/{len(images)} images")
            stats['missing_alt_text'] += len(missing_alts)

        # Thin content
        wc = word_count(body)
        if wc < THIN_CONTENT_THRESHOLD:
            row_issues.append(f"Thin content ({wc} words, need {THIN_CONTENT_THRESHOLD}+)")
            stats['thin_content'] += 1

        if row_issues:
            issues.append({
                'title': title,
                'handle': handle,
                'seo_title': seo_title,
                'seo_desc': seo_desc[:80] + '...' if len(seo_desc) > 80 else seo_desc,
                'word_count': wc,
                'issues': '; '.join(row_issues),
            })

    # Duplicate detection
    title_counts = Counter(meta_titles)
    desc_counts = Counter(meta_descs)
    dup_titles = {t for t, c in title_counts.items() if c > 1}
    dup_descs = {d for d, c in desc_counts.items() if c > 1}

    for issue in issues:
        extra = []
        if issue['seo_title'] in dup_titles:
            extra.append("Duplicate meta title")
            stats['duplicate_titles'] += 1
        if issue['seo_desc'].rstrip('...') in dup_descs or issue['seo_desc'] in dup_descs:
            extra.append("Duplicate meta description")
            stats['duplicate_descs'] += 1
        if extra:
            issue['issues'] += '; ' + '; '.join(extra)

    # Also flag products that have duplicates but no other issues
    for p in products:
        seo = p.get('seo', {}) or {}
        st = (seo.get('title', '') or '').strip()
        sd = (seo.get('description', '') or '').strip()
        handle = p.get('handle', '')
        already = any(i['handle'] == handle for i in issues)
        if not already:
            extra = []
            if st in dup_titles:
                extra.append("Duplicate meta title")
                stats['duplicate_titles'] += 1
            if sd in dup_descs:
                extra.append("Duplicate meta description")
                stats['duplicate_descs'] += 1
            if extra:
                issues.append({
                    'title': p.get('title', ''),
                    'handle': handle,
                    'seo_title': st,
                    'seo_desc': sd[:80] + '...' if len(sd) > 80 else sd,
                    'word_count': word_count(p.get('descriptionHtml', '') or ''),
                    'issues': '; '.join(extra),
                })

    logger.info(f"✓ Product audit complete — {len(issues)} products with issues")
    return issues, stats


def audit_collections(client: ShopifyClient, limit: Optional[int] = None) -> Tuple[List[Dict], Dict]:
    """Audit all collections for SEO issues."""
    logger.info("📁 Fetching collections from Shopify...")
    collections = client.fetch_all_collections(limit=limit)
    logger.info(f"✓ Fetched {len(collections)} collections")

    issues = []
    meta_titles = []
    meta_descs = []
    stats = {
        'total': len(collections),
        'missing_meta_title': 0,
        'short_meta_title': 0,
        'missing_meta_desc': 0,
        'short_meta_desc': 0,
        'missing_image_alt': 0,
        'thin_content': 0,
        'duplicate_titles': 0,
        'duplicate_descs': 0,
    }

    for c in collections:
        title = c.get('title', '')
        handle = c.get('handle', '')
        seo = c.get('seo', {}) or {}
        seo_title = seo.get('title', '') or ''
        seo_desc = seo.get('description', '') or ''
        body = c.get('descriptionHtml', '') or ''
        image = c.get('image') or {}

        row_issues = []

        # Meta title
        if not seo_title.strip():
            row_issues.append("Missing meta title")
            stats['missing_meta_title'] += 1
        else:
            meta_titles.append(seo_title.strip())
            tlen = len(seo_title.strip())
            if tlen < META_TITLE_MIN:
                row_issues.append(f"Short meta title ({tlen} chars)")
                stats['short_meta_title'] += 1

        # Meta description
        if not seo_desc.strip():
            row_issues.append("Missing meta description")
            stats['missing_meta_desc'] += 1
        else:
            meta_descs.append(seo_desc.strip())
            dlen = len(seo_desc.strip())
            if dlen < META_DESC_MIN:
                row_issues.append(f"Short meta desc ({dlen} chars)")
                stats['short_meta_desc'] += 1

        # Collection image alt
        if image.get('url') and not (image.get('altText') or '').strip():
            row_issues.append("Missing collection image alt text")
            stats['missing_image_alt'] += 1

        # Thin content
        wc = word_count(body)
        if wc < THIN_CONTENT_THRESHOLD:
            row_issues.append(f"Thin content ({wc} words)")
            stats['thin_content'] += 1

        if row_issues:
            issues.append({
                'title': title,
                'handle': handle,
                'seo_title': seo_title,
                'seo_desc': seo_desc[:80] + '...' if len(seo_desc) > 80 else seo_desc,
                'word_count': wc,
                'issues': '; '.join(row_issues),
            })

    # Duplicates
    title_counts = Counter(meta_titles)
    desc_counts = Counter(meta_descs)
    dup_titles = {t for t, c in title_counts.items() if c > 1}
    dup_descs = {d for d, c in desc_counts.items() if c > 1}
    stats['duplicate_titles'] = sum(c - 1 for t, c in title_counts.items() if c > 1)
    stats['duplicate_descs'] = sum(c - 1 for d, c in desc_counts.items() if c > 1)

    for issue in issues:
        if issue['seo_title'] in dup_titles:
            issue['issues'] += '; Duplicate meta title'
        if issue['seo_desc'].rstrip('...') in dup_descs:
            issue['issues'] += '; Duplicate meta description'

    logger.info(f"✓ Collection audit complete — {len(issues)} collections with issues")
    return issues, stats


# ═══════════════════════════════════════════════════════════════════════════════
# B. SITE CRAWL AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

def audit_robots_txt(site_url: str) -> Dict:
    """Fetch and analyze robots.txt."""
    logger.info("🤖 Checking robots.txt...")
    result = {
        'url': f"{site_url}/robots.txt",
        'status': 'unknown',
        'has_sitemap': False,
        'sitemap_urls': [],
        'ai_crawler_directives': [],
        'issues': [],
    }

    try:
        resp = requests.get(f"{site_url}/robots.txt", timeout=REQUESTS_TIMEOUT)
        if resp.status_code != 200:
            result['status'] = f"HTTP {resp.status_code}"
            result['issues'].append(f"robots.txt returned {resp.status_code}")
            return result

        result['status'] = 'OK'
        content = resp.text

        # Check sitemap references
        for line in content.splitlines():
            line_stripped = line.strip()
            if line_stripped.lower().startswith('sitemap:'):
                result['has_sitemap'] = True
                sitemap_url = line_stripped.split(':', 1)[1].strip()
                result['sitemap_urls'].append(sitemap_url)

        if not result['has_sitemap']:
            result['issues'].append("No Sitemap directive found in robots.txt")

        # Check AI crawler directives
        for crawler in AI_CRAWLERS:
            pattern = re.compile(rf'user-agent:\s*{re.escape(crawler)}', re.IGNORECASE)
            if pattern.search(content):
                # Find the associated directives
                in_block = False
                directives = []
                for line in content.splitlines():
                    if pattern.match(line.strip()):
                        in_block = True
                        continue
                    if in_block:
                        if line.strip().lower().startswith('user-agent:'):
                            break
                        if line.strip():
                            directives.append(line.strip())
                result['ai_crawler_directives'].append({
                    'crawler': crawler,
                    'directives': directives or ['(block found, check details)'],
                })
            else:
                result['ai_crawler_directives'].append({
                    'crawler': crawler,
                    'directives': ['Not mentioned — default allow'],
                })

    except Exception as e:
        result['status'] = f"Error: {e}"
        result['issues'].append(f"Failed to fetch robots.txt: {e}")

    logger.info(f"✓ robots.txt — status: {result['status']}")
    return result


def audit_sitemap(site_url: str, sitemap_urls: List[str] = None) -> Dict:
    """Fetch and validate sitemap.xml."""
    logger.info("🗺️  Checking sitemap...")
    result = {
        'url': '',
        'status': 'unknown',
        'url_count': 0,
        'issues': [],
    }

    # Try sitemap URLs from robots.txt first, then default
    urls_to_try = (sitemap_urls or []) + [f"{site_url}/sitemap.xml"]
    seen = set()
    urls_to_try = [u for u in urls_to_try if u not in seen and not seen.add(u)]

    for url in urls_to_try:
        try:
            resp = requests.get(url, timeout=REQUESTS_TIMEOUT)
            if resp.status_code != 200:
                continue

            result['url'] = url
            result['status'] = 'OK'

            # Parse XML
            try:
                root = ElementTree.fromstring(resp.content)
                ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

                # Could be a sitemap index or a urlset
                urls = root.findall('.//sm:url', ns)
                sitemaps = root.findall('.//sm:sitemap', ns)

                if sitemaps:
                    result['url_count'] = len(sitemaps)
                    result['type'] = 'sitemap_index'
                    # Count URLs across child sitemaps
                    total_urls = 0
                    for sm in sitemaps[:10]:  # sample up to 10 child sitemaps
                        loc = sm.find('sm:loc', ns)
                        if loc is not None and loc.text:
                            try:
                                child_resp = requests.get(loc.text, timeout=REQUESTS_TIMEOUT)
                                if child_resp.status_code == 200:
                                    child_root = ElementTree.fromstring(child_resp.content)
                                    child_urls = child_root.findall('.//sm:url', ns)
                                    total_urls += len(child_urls)
                            except Exception:
                                pass
                    result['total_urls_sampled'] = total_urls
                    result['child_sitemaps'] = len(sitemaps)
                elif urls:
                    result['url_count'] = len(urls)
                    result['type'] = 'urlset'
                else:
                    result['issues'].append("Sitemap parsed but no URLs or sitemaps found")

            except ElementTree.ParseError as e:
                result['status'] = 'Parse Error'
                result['issues'].append(f"XML parse error: {e}")

            break  # Found a working sitemap

        except Exception as e:
            continue

    if result['status'] == 'unknown':
        result['issues'].append("No sitemap found at any expected URL")

    logger.info(f"✓ Sitemap — {result.get('url_count', 0)} entries, status: {result['status']}")
    return result


def audit_schema_markup(site_url: str) -> Dict:
    """Check homepage and sample product page for schema markup."""
    logger.info("🔍 Checking schema markup...")
    result = {
        'homepage': {'url': site_url, 'schemas_found': [], 'issues': []},
        'product_page': {'url': '', 'schemas_found': [], 'issues': []},
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)'
    }

    # Homepage
    try:
        resp = requests.get(site_url, timeout=REQUESTS_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            html = resp.text

            # Find JSON-LD blocks
            jsonld_blocks = re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html, re.DOTALL | re.IGNORECASE
            )

            schema_types = set()
            for block in jsonld_blocks:
                try:
                    data = json.loads(block)
                    if isinstance(data, list):
                        for item in data:
                            if '@type' in item:
                                schema_types.add(item['@type'])
                    elif '@type' in data:
                        schema_types.add(data['@type'])
                    if '@graph' in data if isinstance(data, dict) else False:
                        for item in data['@graph']:
                            if '@type' in item:
                                schema_types.add(item['@type'])
                except json.JSONDecodeError:
                    pass

            result['homepage']['schemas_found'] = list(schema_types)

            if 'Organization' not in schema_types and 'LocalBusiness' not in schema_types:
                result['homepage']['issues'].append("Missing Organization schema (JSON-LD)")
            if 'BreadcrumbList' not in schema_types:
                result['homepage']['issues'].append("Missing BreadcrumbList schema")
            if 'WebSite' not in schema_types:
                result['homepage']['issues'].append("Missing WebSite schema")

            # Check canonical
            canonical = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html)
            if not canonical:
                result['homepage']['issues'].append("Missing canonical tag")

    except Exception as e:
        result['homepage']['issues'].append(f"Failed to fetch homepage: {e}")

    # Find a product page from sitemap or links
    product_url = _find_sample_product_url(site_url)
    if product_url:
        result['product_page']['url'] = product_url
        try:
            resp = requests.get(product_url, timeout=REQUESTS_TIMEOUT, headers=headers)
            if resp.status_code == 200:
                html = resp.text

                jsonld_blocks = re.findall(
                    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                    html, re.DOTALL | re.IGNORECASE
                )

                schema_types = set()
                for block in jsonld_blocks:
                    try:
                        data = json.loads(block)
                        if isinstance(data, list):
                            for item in data:
                                if '@type' in item:
                                    schema_types.add(item['@type'])
                        elif '@type' in data:
                            schema_types.add(data['@type'])
                        if isinstance(data, dict) and '@graph' in data:
                            for item in data['@graph']:
                                if '@type' in item:
                                    schema_types.add(item['@type'])
                    except json.JSONDecodeError:
                        pass

                result['product_page']['schemas_found'] = list(schema_types)

                if 'Product' not in schema_types:
                    result['product_page']['issues'].append("Missing Product schema (JSON-LD)")
                if 'BreadcrumbList' not in schema_types:
                    result['product_page']['issues'].append("Missing BreadcrumbList schema on product page")

                # Check canonical
                canonical = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html)
                if not canonical:
                    result['product_page']['issues'].append("Missing canonical tag on product page")

        except Exception as e:
            result['product_page']['issues'].append(f"Failed to fetch product page: {e}")
    else:
        result['product_page']['issues'].append("Could not find a sample product URL to test")

    logger.info(f"✓ Schema audit complete")
    return result


def _find_sample_product_url(site_url: str) -> Optional[str]:
    """Find a product URL from the site for testing."""
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)'}
    try:
        # Try sitemap first
        resp = requests.get(f"{site_url}/sitemap.xml", timeout=REQUESTS_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            root = ElementTree.fromstring(resp.content)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Check for products sitemap in index
            for sm in root.findall('.//sm:sitemap', ns):
                loc = sm.find('sm:loc', ns)
                if loc is not None and 'product' in (loc.text or '').lower():
                    try:
                        child_resp = requests.get(loc.text, timeout=REQUESTS_TIMEOUT, headers=headers)
                        if child_resp.status_code == 200:
                            child_root = ElementTree.fromstring(child_resp.content)
                            for url_el in child_root.findall('.//sm:url/sm:loc', ns):
                                if url_el.text and '/products/' in url_el.text:
                                    return url_el.text
                    except Exception:
                        pass

            # Direct urlset
            for url_el in root.findall('.//sm:url/sm:loc', ns):
                if url_el.text and '/products/' in url_el.text:
                    return url_el.text

        # Fallback: scrape homepage for product links
        resp = requests.get(site_url, timeout=REQUESTS_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            product_links = re.findall(rf'href=["\']({re.escape(site_url)}/products/[^"\'?#]+)', resp.text)
            if product_links:
                return product_links[0]
            # Relative links
            rel_links = re.findall(r'href=["\'](/products/[^"\'?#]+)', resp.text)
            if rel_links:
                return f"{site_url.rstrip('/')}{rel_links[0]}"

    except Exception:
        pass
    return None


def _find_sample_collection_url(site_url: str) -> Optional[str]:
    """Find a collection URL from the site for testing."""
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)'}
    try:
        resp = requests.get(site_url, timeout=REQUESTS_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            coll_links = re.findall(rf'href=["\']({re.escape(site_url)}/collections/[^"\'?#]+)', resp.text)
            if coll_links:
                return coll_links[0]
            rel_links = re.findall(r'href=["\'](/collections/[^"\'?#]+)', resp.text)
            if rel_links:
                return f"{site_url.rstrip('/')}{rel_links[0]}"
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# C. GSC INDEX STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def audit_gsc_baseline() -> Tuple[List[Dict], Dict]:
    """Pull GSC baseline: total indexed pages and top queries."""
    logger.info("📊 Fetching GSC baseline data...")
    gsc_queries = []
    gsc_stats = {
        'status': 'unknown',
        'total_impressions': 0,
        'total_clicks': 0,
        'avg_position': 0,
        'top_query_count': 0,
    }

    try:
        gsc = GSCClient()

        # Top 20 queries by impressions
        rows = gsc.query(
            site_url=GSC_SITE_URL,
            dimensions=['query'],
            row_limit=20,
        )

        if rows:
            gsc_stats['status'] = 'OK'
            total_imp = 0
            total_clicks = 0
            total_pos = 0

            for row in rows:
                query_text = row.get('keys', [''])[0]
                impressions = row.get('impressions', 0)
                clicks = row.get('clicks', 0)
                ctr = row.get('ctr', 0)
                position = row.get('position', 0)

                total_imp += impressions
                total_clicks += clicks
                total_pos += position

                gsc_queries.append({
                    'query': query_text,
                    'impressions': impressions,
                    'clicks': clicks,
                    'ctr': f"{ctr * 100:.1f}%",
                    'position': f"{position:.1f}",
                })

            gsc_stats['total_impressions'] = total_imp
            gsc_stats['total_clicks'] = total_clicks
            gsc_stats['avg_position'] = f"{total_pos / len(rows):.1f}" if rows else 'N/A'
            gsc_stats['top_query_count'] = len(rows)
        else:
            gsc_stats['status'] = 'No data returned'

    except FileNotFoundError:
        gsc_stats['status'] = 'Skipped — credentials not found'
        logger.warning("⚠ GSC credentials not found — skipping GSC audit")
    except Exception as e:
        gsc_stats['status'] = f"Error: {str(e)[:100]}"
        logger.warning(f"⚠ GSC audit failed: {e}")

    logger.info(f"✓ GSC baseline — status: {gsc_stats['status']}")
    return gsc_queries, gsc_stats


# ═══════════════════════════════════════════════════════════════════════════════
# D. CORE WEB VITALS
# ═══════════════════════════════════════════════════════════════════════════════

def audit_core_web_vitals(site_url: str) -> List[Dict]:
    """Test Core Web Vitals via PageSpeed Insights API (mobile)."""
    logger.info("⚡ Running Core Web Vitals tests...")
    results = []

    # Build list of URLs to test
    test_urls = [
        ('Homepage', site_url),
    ]

    # Find a collection page
    coll_url = _find_sample_collection_url(site_url)
    if coll_url:
        test_urls.append(('Collection Page', coll_url))

    # Find a product page
    prod_url = _find_sample_product_url(site_url)
    if prod_url:
        test_urls.append(('Product Page', prod_url))

    for label, url in test_urls:
        logger.info(f"  ⏳ Testing {label}: {url}")
        try:
            resp = requests.get(
                PAGESPEED_API,
                params={'url': url, 'strategy': 'mobile'},
                timeout=60,
            )
            if resp.status_code != 200:
                results.append({
                    'page': label,
                    'url': url,
                    'performance_score': 'Error',
                    'lcp': 'N/A',
                    'fid': 'N/A',
                    'cls': 'N/A',
                    'inp': 'N/A',
                    'notes': f"API returned {resp.status_code}",
                })
                continue

            data = resp.json()
            lighthouse = data.get('lighthouseResult', {})
            categories = lighthouse.get('categories', {})
            audits = lighthouse.get('audits', {})

            perf_score = categories.get('performance', {}).get('score')
            perf_display = f"{int(perf_score * 100)}" if perf_score is not None else 'N/A'

            # Extract CWV metrics
            lcp = audits.get('largest-contentful-paint', {}).get('displayValue', 'N/A')
            fid = audits.get('max-potential-fid', {}).get('displayValue', 'N/A')
            cls_val = audits.get('cumulative-layout-shift', {}).get('displayValue', 'N/A')
            inp = audits.get('interaction-to-next-paint', {}).get('displayValue', 'N/A')

            # Also try CrUX field data if available
            crux = data.get('loadingExperience', {}).get('metrics', {})
            field_lcp = crux.get('LARGEST_CONTENTFUL_PAINT_MS', {}).get('percentile', '')
            field_inp = crux.get('INTERACTION_TO_NEXT_PAINT', {}).get('percentile', '')
            field_cls = crux.get('CUMULATIVE_LAYOUT_SHIFT_SCORE', {}).get('percentile', '')

            notes = []
            if field_lcp:
                notes.append(f"Field LCP: {field_lcp}ms")
            if field_inp:
                notes.append(f"Field INP: {field_inp}ms")
            if field_cls:
                notes.append(f"Field CLS: {field_cls}")

            results.append({
                'page': label,
                'url': url,
                'performance_score': perf_display,
                'lcp': lcp,
                'fid': fid,
                'cls': cls_val,
                'inp': inp,
                'notes': '; '.join(notes) if notes else 'Lab data only',
            })

            logger.info(f"  ✓ {label} — Performance: {perf_display}/100, LCP: {lcp}")

        except requests.Timeout:
            results.append({
                'page': label,
                'url': url,
                'performance_score': 'Timeout',
                'lcp': 'N/A',
                'fid': 'N/A',
                'cls': 'N/A',
                'inp': 'N/A',
                'notes': 'PageSpeed API timed out (60s)',
            })
            logger.warning(f"  ⚠ {label} — PageSpeed API timed out")
        except Exception as e:
            results.append({
                'page': label,
                'url': url,
                'performance_score': 'Error',
                'lcp': 'N/A',
                'fid': 'N/A',
                'cls': 'N/A',
                'inp': 'N/A',
                'notes': str(e)[:100],
            })
            logger.warning(f"  ⚠ {label} — Error: {e}")

    logger.info(f"✓ Core Web Vitals — tested {len(results)} pages")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def build_summary(product_stats: Dict, collection_stats: Dict, robots: Dict,
                   sitemap: Dict, schema: Dict, cwv: List[Dict], gsc_stats: Dict) -> List[List]:
    """Build summary rows for the overview tab."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    rows = [
        ['Audit Date', now],
        ['', ''],
        ['── PRODUCTS ──', ''],
        ['Total Products', product_stats.get('total', 0)],
        ['Missing Meta Title', product_stats.get('missing_meta_title', 0)],
        ['Short/Long Meta Title', product_stats.get('short_meta_title', 0) + product_stats.get('long_meta_title', 0)],
        ['Missing Meta Description', product_stats.get('missing_meta_desc', 0)],
        ['Short/Long Meta Description', product_stats.get('short_meta_desc', 0) + product_stats.get('long_meta_desc', 0)],
        ['Images Missing Alt Text', product_stats.get('missing_alt_text', 0)],
        ['Thin Content (<200 words)', product_stats.get('thin_content', 0)],
        ['Duplicate Meta Titles', product_stats.get('duplicate_titles', 0)],
        ['Duplicate Meta Descriptions', product_stats.get('duplicate_descs', 0)],
        ['', ''],
        ['── COLLECTIONS ──', ''],
        ['Total Collections', collection_stats.get('total', 0)],
        ['Missing Meta Title', collection_stats.get('missing_meta_title', 0)],
        ['Missing Meta Description', collection_stats.get('missing_meta_desc', 0)],
        ['Missing Image Alt', collection_stats.get('missing_image_alt', 0)],
        ['Thin Content', collection_stats.get('thin_content', 0)],
        ['', ''],
        ['── TECHNICAL ──', ''],
        ['robots.txt Status', robots.get('status', 'N/A')],
        ['Sitemap Status', sitemap.get('status', 'N/A')],
        ['Sitemap URLs', sitemap.get('url_count', 0)],
        ['Homepage Schemas', ', '.join(schema.get('homepage', {}).get('schemas_found', []))],
        ['Product Page Schemas', ', '.join(schema.get('product_page', {}).get('schemas_found', []))],
        ['', ''],
        ['── CORE WEB VITALS ──', ''],
    ]

    for c in cwv:
        rows.append([f"{c['page']} Performance", f"{c['performance_score']}/100"])
        rows.append([f"{c['page']} LCP", c['lcp']])

    rows.append(['', ''])
    rows.append(['── GSC BASELINE ──', ''])
    rows.append(['GSC Status', gsc_stats.get('status', 'N/A')])
    rows.append(['Total Impressions (30d)', gsc_stats.get('total_impressions', 0)])
    rows.append(['Total Clicks (30d)', gsc_stats.get('total_clicks', 0)])
    rows.append(['Avg Position', gsc_stats.get('avg_position', 'N/A')])

    return rows


def build_technical_issues(robots: Dict, sitemap: Dict, schema: Dict) -> List[List]:
    """Build rows for the Technical Issues tab."""
    rows = []

    # robots.txt
    for issue in robots.get('issues', []):
        rows.append(['robots.txt', robots.get('url', ''), issue, 'Medium'])

    for ai in robots.get('ai_crawler_directives', []):
        status = '; '.join(ai.get('directives', []))
        severity = 'Info'
        rows.append(['AI Crawler', ai['crawler'], status, severity])

    # Sitemap
    for issue in sitemap.get('issues', []):
        rows.append(['Sitemap', sitemap.get('url', ''), issue, 'High'])

    # Schema — homepage
    for issue in schema.get('homepage', {}).get('issues', []):
        rows.append(['Schema (Homepage)', schema['homepage'].get('url', ''), issue, 'Medium'])

    # Schema — product
    for issue in schema.get('product_page', {}).get('issues', []):
        rows.append(['Schema (Product)', schema['product_page'].get('url', ''), issue, 'Medium'])

    return rows


def export_to_sheets(summary_rows, product_issues, collection_issues,
                     technical_rows, cwv_results, gsc_queries) -> Optional[str]:
    """Export all audit data to a multi-tab Google Sheet."""
    try:
        exporter = GoogleSheetsExporter()
        title = f"SEO Technical Audit — {datetime.now().strftime('%Y-%m-%d')}"

        # Tab 1: Summary (created with the spreadsheet)
        sheet_url = exporter.create_sheet(
            title=title,
            headers=['Metric', 'Value'],
            rows=summary_rows,
        )
        spreadsheet_id = sheet_url.split('/d/')[1].split('/')[0]

        # Tab 2: Product SEO Issues
        exporter.add_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            tab_name='Product SEO Issues',
            headers=['Product', 'Handle', 'Meta Title', 'Meta Desc', 'Word Count', 'Issues'],
            rows=[[i['title'], i['handle'], i['seo_title'], i['seo_desc'],
                   i['word_count'], i['issues']] for i in product_issues],
        )

        # Tab 3: Collection SEO Issues
        exporter.add_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            tab_name='Collection SEO Issues',
            headers=['Collection', 'Handle', 'Meta Title', 'Meta Desc', 'Word Count', 'Issues'],
            rows=[[i['title'], i['handle'], i['seo_title'], i['seo_desc'],
                   i['word_count'], i['issues']] for i in collection_issues],
        )

        # Tab 4: Technical Issues
        exporter.add_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            tab_name='Technical Issues',
            headers=['Category', 'URL/Item', 'Issue', 'Severity'],
            rows=technical_rows,
        )

        # Tab 5: Core Web Vitals
        exporter.add_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            tab_name='Core Web Vitals',
            headers=['Page', 'URL', 'Performance', 'LCP', 'FID', 'CLS', 'INP', 'Notes'],
            rows=[[c['page'], c['url'], c['performance_score'], c['lcp'],
                   c['fid'], c['cls'], c['inp'], c['notes']] for c in cwv_results],
        )

        # Tab 6: GSC Baseline
        exporter.add_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            tab_name='GSC Baseline',
            headers=['Query', 'Impressions', 'Clicks', 'CTR', 'Avg Position'],
            rows=[[q['query'], q['impressions'], q['clicks'],
                   q['ctr'], q['position']] for q in gsc_queries],
        )

        logger.info(f"✓ Google Sheet exported: {sheet_url}")
        return sheet_url

    except Exception as e:
        logger.error(f"❌ Google Sheets export failed: {e}")
        return None


def export_csv_fallback(summary_rows, product_issues, collection_issues,
                        technical_rows, cwv_results, gsc_queries) -> List[str]:
    """Fallback: export each tab as a separate CSV."""
    logger.info("📄 Falling back to CSV export...")
    files = []

    files.append(export_to_csv(
        'seo_audit_summary',
        ['Metric', 'Value'],
        summary_rows,
    ))

    files.append(export_to_csv(
        'seo_audit_products',
        ['Product', 'Handle', 'Meta Title', 'Meta Desc', 'Word Count', 'Issues'],
        [[i['title'], i['handle'], i['seo_title'], i['seo_desc'],
          i['word_count'], i['issues']] for i in product_issues],
    ))

    files.append(export_to_csv(
        'seo_audit_collections',
        ['Collection', 'Handle', 'Meta Title', 'Meta Desc', 'Word Count', 'Issues'],
        [[i['title'], i['handle'], i['seo_title'], i['seo_desc'],
          i['word_count'], i['issues']] for i in collection_issues],
    ))

    files.append(export_to_csv(
        'seo_audit_technical',
        ['Category', 'URL/Item', 'Issue', 'Severity'],
        technical_rows,
    ))

    files.append(export_to_csv(
        'seo_audit_cwv',
        ['Page', 'URL', 'Performance', 'LCP', 'FID', 'CLS', 'INP', 'Notes'],
        [[c['page'], c['url'], c['performance_score'], c['lcp'],
          c['fid'], c['cls'], c['inp'], c['notes']] for c in cwv_results],
    ))

    files.append(export_to_csv(
        'seo_audit_gsc',
        ['Query', 'Impressions', 'Clicks', 'CTR', 'Avg Position'],
        [[q['query'], q['impressions'], q['clicks'],
          q['ctr'], q['position']] for q in gsc_queries],
    ))

    return files


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Technical SEO Audit for Beauty Connect Shop (read-only)',
    )
    parser.add_argument('--site', type=str, default=DEFAULT_SITE,
                        help=f'Site URL to audit (default: {DEFAULT_SITE})')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products/collections to fetch')
    parser.add_argument('--skip-pagespeed', action='store_true',
                        help='Skip Core Web Vitals / PageSpeed tests')
    args = parser.parse_args()

    site_url = args.site.rstrip('/')

    logger.info("=" * 60)
    logger.info(f"🔎 Technical SEO Audit — {site_url}")
    logger.info(f"   Mode: READ-ONLY (no changes will be made)")
    logger.info(f"   Limit: {args.limit or 'all'}")
    logger.info(f"   PageSpeed: {'skip' if args.skip_pagespeed else 'enabled'}")
    logger.info("=" * 60)

    # ── A. Shopify Data Audit ──
    try:
        client = ShopifyClient()
        product_issues, product_stats = audit_products(client, limit=args.limit)
        collection_issues, collection_stats = audit_collections(client, limit=args.limit)
    except Exception as e:
        logger.error(f"❌ Shopify audit failed: {e}")
        product_issues, product_stats = [], {'total': 0}
        collection_issues, collection_stats = [], {'total': 0}

    # ── B. Site Crawl Audit ──
    robots = audit_robots_txt(site_url)
    sitemap = audit_sitemap(site_url, robots.get('sitemap_urls', []))
    schema = audit_schema_markup(site_url)

    # ── C. GSC Baseline ──
    gsc_queries, gsc_stats = audit_gsc_baseline()

    # ── D. Core Web Vitals ──
    if args.skip_pagespeed:
        cwv_results = [{'page': 'Skipped', 'url': '', 'performance_score': 'N/A',
                        'lcp': 'N/A', 'fid': 'N/A', 'cls': 'N/A', 'inp': 'N/A',
                        'notes': 'Skipped via --skip-pagespeed'}]
        logger.info("⏭️  Skipping Core Web Vitals (--skip-pagespeed)")
    else:
        cwv_results = audit_core_web_vitals(site_url)

    # ── Build Reports ──
    summary_rows = build_summary(
        product_stats, collection_stats, robots, sitemap, schema, cwv_results, gsc_stats,
    )
    technical_rows = build_technical_issues(robots, sitemap, schema)

    # ── Export ──
    sheet_url = export_to_sheets(
        summary_rows, product_issues, collection_issues,
        technical_rows, cwv_results, gsc_queries,
    )

    if not sheet_url:
        csv_files = export_csv_fallback(
            summary_rows, product_issues, collection_issues,
            technical_rows, cwv_results, gsc_queries,
        )
        logger.info(f"✓ CSV fallback — {len(csv_files)} files exported")
    else:
        logger.info(f"✓ Report: {sheet_url}")

    # ── Summary ──
    logger.info("")
    logger.info("=" * 60)
    logger.info("📋 AUDIT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Products audited:    {product_stats.get('total', 0)}")
    logger.info(f"  Products with issues: {len(product_issues)}")
    logger.info(f"  Collections audited:  {collection_stats.get('total', 0)}")
    logger.info(f"  Collections w/issues: {len(collection_issues)}")
    logger.info(f"  Technical issues:     {len(technical_rows)}")
    logger.info(f"  CWV pages tested:     {len(cwv_results)}")
    logger.info(f"  GSC queries fetched:  {len(gsc_queries)}")
    if sheet_url:
        logger.info(f"  Report: {sheet_url}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
