#!/usr/bin/env python3
"""
Bing IndexNow Integration — Beauty Connect Shop
DOE Architecture: Execution layer

Submits URLs to IndexNow API for instant indexing across Bing, Yandex, and other
participating search engines.

Usage:
    python execution/bing_indexnow.py --urls https://beautyconnectshop.com/products/new-product
    python execution/bing_indexnow.py --sitemap
    python execution/bing_indexnow.py --recent 10
"""

import os
import sys
import csv
import argparse
import secrets
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

# Add parent dir so we can import seo_shared when running from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_shared import logger, BASE_DIR, ShopifyClient

load_dotenv()

# ─── Constants ────────────────────────────────────────────────────────────────
HOST = "beautyconnectshop.com"
SITE_URL = f"https://{HOST}"
INDEXNOW_API = "https://api.indexnow.org/indexnow"
KEY_FILE = os.path.join(BASE_DIR, ".tmp", "indexnow_key.txt")
LOG_FILE = os.path.join(BASE_DIR, ".tmp", "indexnow_log.csv")
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"


# ─── Key Management ──────────────────────────────────────────────────────────

def get_or_create_key() -> str:
    """Load existing IndexNow key or generate a new one (32-char hex)."""
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)

    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            key = f.read().strip()
        if key:
            logger.info(f"🔑 Loaded existing IndexNow key: {key}")
            return key

    key = secrets.token_hex(16)  # 32 hex chars
    with open(KEY_FILE, "w") as f:
        f.write(key)
    logger.info(f"🔑 Generated new IndexNow key: {key}")
    return key


# ─── Logging ──────────────────────────────────────────────────────────────────

def log_submission(url: str, status_code: int, response_text: str):
    """Append submission result to CSV log."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_exists = os.path.exists(LOG_FILE)

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "url", "status_code", "response"])
        writer.writerow([
            datetime.now().isoformat(),
            url,
            status_code,
            response_text[:200]
        ])


# ─── Submit URLs ──────────────────────────────────────────────────────────────

def submit_single(url: str, key: str) -> tuple:
    """Submit a single URL via GET request. Returns (status_code, response_text)."""
    try:
        resp = requests.get(INDEXNOW_API, params={
            "url": url,
            "key": key,
        }, timeout=15)
        return resp.status_code, resp.text
    except Exception as e:
        logger.error(f"❌ Request failed for {url}: {e}")
        return 0, str(e)


def submit_batch(urls: list, key: str) -> tuple:
    """Submit a batch of URLs via POST request. Returns (status_code, response_text)."""
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{SITE_URL}/{key}.txt",
        "urlList": urls,
    }
    try:
        resp = requests.post(INDEXNOW_API, json=payload, timeout=30)
        return resp.status_code, resp.text
    except Exception as e:
        logger.error(f"❌ Batch request failed: {e}")
        return 0, str(e)


def submit_urls(urls: list, key: str):
    """Submit URLs — single GET for 1 URL, batch POST for multiple."""
    print(f"\n📤 Submitting {len(urls)} URL(s) to IndexNow...\n")

    if len(urls) == 1:
        url = urls[0]
        status, resp_text = submit_single(url, key)
        status_label = "OK" if status in (200, 202) else f"({resp_text[:50]})"
        icon = "✓" if status in (200, 202) else "✗"
        print(f"  {icon} {url} — {status} {status_label}")
        log_submission(url, status, resp_text)
    else:
        # Batch submit (up to 10,000 per request)
        for i in range(0, len(urls), 10000):
            batch = urls[i:i + 10000]
            status, resp_text = submit_batch(batch, key)
            status_label = "OK" if status in (200, 202) else f"({resp_text[:80]})"
            icon = "✓" if status in (200, 202) else "✗"

            for url in batch:
                print(f"  {icon} {url} — {status} {status_label}")
                log_submission(url, status, resp_text)

    success_count = len(urls)  # Batch returns one status for all
    print(f"\n✅ Submitted {success_count} URL(s) successfully")


# ─── Input Modes ──────────────────────────────────────────────────────────────

def fetch_sitemap_urls() -> list:
    """Fetch all URLs from sitemap.xml (handles sitemap index too)."""
    urls = []
    logger.info(f"📡 Fetching sitemap: {SITEMAP_URL}")

    try:
        resp = requests.get(SITEMAP_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"❌ Failed to fetch sitemap: {e}")
        return urls

    root = ET.fromstring(resp.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    # Check if this is a sitemap index
    sitemaps = root.findall("sm:sitemap/sm:loc", ns)
    if sitemaps:
        logger.info(f"📋 Found sitemap index with {len(sitemaps)} sub-sitemaps")
        for sitemap_loc in sitemaps:
            sub_url = sitemap_loc.text.strip()
            try:
                sub_resp = requests.get(sub_url, timeout=15)
                sub_resp.raise_for_status()
                sub_root = ET.fromstring(sub_resp.content)
                for loc in sub_root.findall("sm:url/sm:loc", ns):
                    urls.append(loc.text.strip())
            except Exception as e:
                logger.warning(f"⚠ Failed to fetch sub-sitemap {sub_url}: {e}")
    else:
        # Regular sitemap
        for loc in root.findall("sm:url/sm:loc", ns):
            urls.append(loc.text.strip())

    logger.info(f"✓ Found {len(urls)} URLs in sitemap")
    return urls


def fetch_recent_urls(n: int) -> list:
    """Fetch the N most recently modified products and blog posts from Shopify."""
    urls = []
    try:
        client = ShopifyClient()
    except ValueError as e:
        logger.error(f"❌ {e}")
        return urls

    # Fetch products
    logger.info(f"📡 Fetching recent products & articles from Shopify...")
    products = client.fetch_all_products()
    articles = client.fetch_all_blog_articles()

    # Build URL list from products
    for p in products:
        handle = p.get("handle", "")
        if handle:
            urls.append(f"{SITE_URL}/products/{handle}")

    # Build URL list from articles
    for a in articles:
        handle = a.get("handle", "")
        blog = a.get("blog", {})
        blog_handle = blog.get("handle", "news") if blog else "news"
        if handle:
            urls.append(f"{SITE_URL}/blogs/{blog_handle}/{handle}")

    # Sort by most recent (articles have publishedAt, products don't have a simple sort)
    # Take the last N as a proxy for "most recent"
    urls = urls[-n:] if len(urls) > n else urls

    logger.info(f"✓ Selected {len(urls)} recent URLs from Shopify")
    return urls


# ─── Setup Instructions ──────────────────────────────────────────────────────

def print_setup_instructions(key: str):
    """Print setup instructions for hosting the key file."""
    print(f"""
⚠  SETUP REQUIRED:
1. Host the key file at: {SITE_URL}/{key}.txt
2. The file must contain exactly: {key}

   Option A — Shopify Theme Assets:
     Online Store → Themes → Edit Code → Assets → Add new asset
     Upload a file named "{key}.txt" containing: {key}

   Option B — Shopify Page:
     Create a page at /{key} with content: {key}
     (May not work if URL doesn't end in .txt)

   Option C — Redirect (if assets don't serve .txt):
     Settings → Navigation → URL Redirects
     Not recommended — IndexNow requires exact file content.

   Verify: curl {SITE_URL}/{key}.txt
""")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🔗 Bing IndexNow — Submit URLs for instant indexing"
    )
    parser.add_argument("--urls", nargs="+", help="Specific URLs to submit")
    parser.add_argument("--sitemap", action="store_true", help="Fetch sitemap.xml and submit all URLs")
    parser.add_argument("--recent", type=int, metavar="N", help="Submit N most recent products/articles from Shopify")
    args = parser.parse_args()

    if not any([args.urls, args.sitemap, args.recent]):
        parser.print_help()
        sys.exit(1)

    # Get or create key
    key = get_or_create_key()
    print(f"🔑 IndexNow Key: {key}")

    # Collect URLs
    urls = []
    if args.urls:
        urls = args.urls
    elif args.sitemap:
        urls = fetch_sitemap_urls()
    elif args.recent:
        urls = fetch_recent_urls(args.recent)

    if not urls:
        print("❌ No URLs to submit.")
        sys.exit(1)

    # Submit
    submit_urls(urls, key)

    # Log location
    print(f"📝 Log: {LOG_FILE}")

    # Setup instructions
    print_setup_instructions(key)


if __name__ == "__main__":
    main()
