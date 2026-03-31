#!/usr/bin/env python3
"""
SEO Internal Link Analyzer — Beauty Connect Shop (Shopify)
DOE Architecture: Execution layer

READ-ONLY analysis tool. Builds a content inventory, maps internal links,
identifies orphan pages, and generates link suggestions using keyword matching.

Usage:
    python execution/seo_internal_linker.py [--skip-gsc] [--output sheets|csv]
"""

import argparse
import os
import re
import sys
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from html.parser import HTMLParser
from dotenv import load_dotenv

load_dotenv()

# Add parent dir to path so we can import seo_shared
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_shared import (
    ShopifyClient,
    GoogleSheetsExporter,
    GSCClient,
    export_to_csv,
    strip_html,
    K_BEAUTY_KEYWORDS,
    BASE_DIR,
    logger,
)

# ─── Constants ────────────────────────────────────────────────────────────────

OVER_LINKED_THRESHOLD = 20
STORE_DOMAIN = os.getenv("SHOPIFY_STORE_URL", "beautyconnectshop.com").rstrip("/")


# ─── HTML Link Extractor ─────────────────────────────────────────────────────

class LinkExtractor(HTMLParser):
    """Extract <a href="...">anchor text</a> from HTML."""

    def __init__(self):
        super().__init__()
        self.links: List[Dict] = []  # [{"href": ..., "anchor": ...}]
        self._current_href: Optional[str] = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attr_dict = dict(attrs)
            href = attr_dict.get("href", "")
            if href:
                self._current_href = href
                self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href is not None:
            anchor = " ".join(self._current_text).strip()
            self.links.append({"href": self._current_href, "anchor": anchor})
            self._current_href = None
            self._current_text = []


def extract_links(html: str) -> List[Dict]:
    """Extract all links from HTML body. Returns [{"href": ..., "anchor": ...}]."""
    if not html:
        return []
    parser = LinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.links


# ─── URL Helpers ──────────────────────────────────────────────────────────────

def normalize_url(href: str) -> str:
    """Normalize a URL/path to a consistent format for comparison."""
    href = href.strip()
    # Strip protocol + domain to get path
    for prefix in [f"https://{STORE_DOMAIN}", f"http://{STORE_DOMAIN}", f"https://www.{STORE_DOMAIN}", f"http://www.{STORE_DOMAIN}"]:
        if href.startswith(prefix):
            href = href[len(prefix):]
            break
    # Remove trailing slash, query string, fragment
    href = href.split("?")[0].split("#")[0].rstrip("/")
    return href.lower() if href else "/"


def build_page_url(page_type: str, handle: str, blog_handle: str = None) -> str:
    """Build a relative URL path for a Shopify page."""
    if page_type == "product":
        return f"/products/{handle}"
    elif page_type == "collection":
        return f"/collections/{handle}"
    elif page_type == "article":
        if blog_handle:
            return f"/blogs/{blog_handle}/{handle}"
        return f"/blogs/news/{handle}"
    return f"/{handle}"


# ─── Keyword Matching ────────────────────────────────────────────────────────

def extract_keywords_from_title(title: str) -> Set[str]:
    """Extract meaningful words from a title (2+ chars, lowercased)."""
    words = re.findall(r"[a-zA-Z]{2,}", title.lower())
    # Filter out very common stopwords
    stopwords = {"the", "and", "for", "with", "from", "this", "that", "your",
                 "our", "all", "set", "new", "best", "top", "how", "why",
                 "what", "are", "has", "have", "been", "will", "can", "not"}
    return {w for w in words if w not in stopwords}


def find_keyword_matches(text: str, target_keywords: Set[str]) -> List[str]:
    """Find which target keywords appear in text."""
    text_lower = text.lower()
    return [kw for kw in target_keywords if kw in text_lower]


# ─── Core Analysis ────────────────────────────────────────────────────────────

def build_content_inventory(shopify: ShopifyClient) -> Dict[str, Dict]:
    """
    Build full content inventory from Shopify.
    Returns dict keyed by normalized URL path.
    """
    inventory = {}

    # 1. Products
    logger.info("📦 Fetching products...")
    products = shopify.fetch_all_products()
    for p in products:
        url = build_page_url("product", p["handle"])
        text = strip_html(p.get("descriptionHtml", ""))
        keywords = extract_keywords_from_title(p["title"])
        keywords.update(t.lower() for t in p.get("tags", []))
        inventory[url] = {
            "url": url,
            "title": p["title"],
            "type": "product",
            "handle": p["handle"],
            "description": text[:300],
            "tags": p.get("tags", []),
            "keywords": keywords,
            "body_html": p.get("descriptionHtml", ""),
        }
    logger.info(f"  ✅ {len(products)} products indexed")

    # 2. Collections
    logger.info("🗂️  Fetching collections...")
    collections = shopify.fetch_all_collections()
    for c in collections:
        url = build_page_url("collection", c["handle"])
        text = strip_html(c.get("descriptionHtml", ""))
        keywords = extract_keywords_from_title(c["title"])
        inventory[url] = {
            "url": url,
            "title": c["title"],
            "type": "collection",
            "handle": c["handle"],
            "description": text[:300],
            "tags": [],
            "keywords": keywords,
            "body_html": c.get("descriptionHtml", ""),
        }
    logger.info(f"  ✅ {len(collections)} collections indexed")

    # 3. Blog articles
    logger.info("📝 Fetching blog articles...")
    articles = shopify.fetch_all_blog_articles()
    for a in articles:
        blog_handle = a.get("blog", {}).get("handle", "news")
        url = build_page_url("article", a["handle"], blog_handle)
        text = strip_html(a.get("body", ""))
        keywords = extract_keywords_from_title(a["title"])
        keywords.update(t.lower() for t in a.get("tags", []))
        inventory[url] = {
            "url": url,
            "title": a["title"],
            "type": "article",
            "handle": a["handle"],
            "description": text[:300],
            "tags": a.get("tags", []),
            "keywords": keywords,
            "body_html": a.get("body", ""),
        }
    logger.info(f"  ✅ {len(articles)} articles indexed")

    logger.info(f"📊 Total content inventory: {len(inventory)} pages")
    return inventory


def analyze_internal_links(inventory: Dict[str, Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Analyze internal links across all pages.
    Returns:
        link_map: [{"source": ..., "target": ..., "anchor": ..., "link_type": ...}]
        inbound_counts: {url: count} of inbound internal links
    """
    logger.info("🔗 Analyzing internal links...")

    link_map = []
    inbound_counts = defaultdict(int)
    all_urls = set(inventory.keys())

    for url, page in inventory.items():
        html = page.get("body_html", "")
        if not html:
            continue

        raw_links = extract_links(html)
        for link in raw_links:
            target_path = normalize_url(link["href"])

            # Only count internal links (links to pages in our inventory)
            if target_path in all_urls:
                source_type = page["type"]
                target_type = inventory[target_path]["type"]
                link_type = f"{source_type} -> {target_type}"

                link_map.append({
                    "source": url,
                    "source_title": page["title"],
                    "target": target_path,
                    "target_title": inventory[target_path]["title"],
                    "anchor": link["anchor"][:100],
                    "link_type": link_type,
                })
                inbound_counts[target_path] += 1

    logger.info(f"  ✅ Found {len(link_map)} internal links")
    return link_map, dict(inbound_counts)


def identify_orphan_pages(inventory: Dict[str, Dict], inbound_counts: Dict[str, int]) -> List[Dict]:
    """Find pages with zero inbound internal links."""
    orphans = []
    for url, page in inventory.items():
        if inbound_counts.get(url, 0) == 0:
            orphans.append({
                "url": url,
                "type": page["type"],
                "title": page["title"],
                "inbound_links": 0,
            })
    # Sort: products first (most important to link to), then collections
    type_priority = {"product": 0, "collection": 1, "article": 2}
    orphans.sort(key=lambda x: type_priority.get(x["type"], 99))
    logger.info(f"  🔍 Found {len(orphans)} orphan pages (0 inbound links)")
    return orphans


def identify_overlinked_pages(inbound_counts: Dict[str, int], inventory: Dict[str, Dict]) -> List[Dict]:
    """Find pages with more than OVER_LINKED_THRESHOLD inbound links."""
    overlinked = []
    for url, count in inbound_counts.items():
        if count > OVER_LINKED_THRESHOLD and url in inventory:
            overlinked.append({
                "url": url,
                "type": inventory[url]["type"],
                "title": inventory[url]["title"],
                "inbound_links": count,
            })
    overlinked.sort(key=lambda x: x["inbound_links"], reverse=True)
    return overlinked


def generate_link_suggestions(inventory: Dict[str, Dict], inbound_counts: Dict[str, int]) -> List[Dict]:
    """
    Generate link suggestions by matching blog content to product/collection keywords.
    Prioritizes pages with 0 inbound links.
    """
    logger.info("💡 Generating link suggestions...")

    suggestions = []
    seen_pairs = set()

    # Target pages: products and collections
    targets = {url: page for url, page in inventory.items() if page["type"] in ("product", "collection")}

    # Source pages: articles (blogs are where we add links)
    sources = {url: page for url, page in inventory.items() if page["type"] == "article"}

    for source_url, source_page in sources.items():
        source_text = strip_html(source_page.get("body_html", "")).lower()
        if not source_text:
            continue

        for target_url, target_page in targets.items():
            pair_key = (source_url, target_url)
            if pair_key in seen_pairs:
                continue

            # Check if any target keywords appear in the blog body
            matching = find_keyword_matches(source_text, target_page["keywords"])

            if len(matching) >= 2:  # Require at least 2 keyword matches for relevance
                inbound = inbound_counts.get(target_url, 0)
                # Priority: 0 inbound = highest priority
                if inbound == 0:
                    priority = "🔴 High"
                elif inbound < 3:
                    priority = "🟡 Medium"
                else:
                    priority = "🟢 Low"

                # Suggest anchor text from the target title
                suggested_anchor = target_page["title"]

                suggestions.append({
                    "source_url": source_url,
                    "source_title": source_page["title"],
                    "target_url": target_url,
                    "target_title": target_page["title"],
                    "target_type": target_page["type"],
                    "matching_keywords": ", ".join(matching[:5]),
                    "current_inbound": inbound,
                    "priority": priority,
                    "suggested_anchor": suggested_anchor,
                })
                seen_pairs.add(pair_key)

    # Sort by priority (orphans first), then by number of keyword matches
    priority_order = {"🔴 High": 0, "🟡 Medium": 1, "🟢 Low": 2}
    suggestions.sort(key=lambda x: (priority_order.get(x["priority"], 99), -len(x["matching_keywords"])))

    logger.info(f"  ✅ Generated {len(suggestions)} link suggestions")
    return suggestions


def enrich_with_gsc(orphans: List[Dict], suggestions: List[Dict], skip_gsc: bool) -> Tuple[List[Dict], List[Dict]]:
    """Optionally enrich orphan pages and suggestions with GSC impressions/clicks."""
    if skip_gsc:
        logger.info("⏭️  Skipping GSC enrichment (--skip-gsc)")
        for o in orphans:
            o["gsc_impressions"] = "N/A"
            o["gsc_clicks"] = "N/A"
        for s in suggestions:
            s["gsc_impressions"] = "N/A"
        return orphans, suggestions

    try:
        logger.info("📈 Enriching with GSC data...")
        gsc = GSCClient()
        site_url = os.getenv("GSC_SITE_URL", f"sc-domain:{STORE_DOMAIN}")

        # Fetch page-level data
        rows = gsc.query(
            site_url=site_url,
            dimensions=["page"],
            row_limit=5000,
        )

        # Build lookup: URL path -> {impressions, clicks}
        gsc_lookup = {}
        for row in rows:
            page_url = row.get("keys", [""])[0]
            path = normalize_url(page_url)
            gsc_lookup[path] = {
                "impressions": row.get("impressions", 0),
                "clicks": row.get("clicks", 0),
            }

        # Enrich orphans
        for o in orphans:
            data = gsc_lookup.get(o["url"], {})
            o["gsc_impressions"] = data.get("impressions", 0)
            o["gsc_clicks"] = data.get("clicks", 0)

        # Enrich suggestions — higher impression targets are higher value
        for s in suggestions:
            data = gsc_lookup.get(s["target_url"], {})
            s["gsc_impressions"] = data.get("impressions", 0)

        # Re-sort suggestions: within same priority, higher impressions first
        priority_order = {"🔴 High": 0, "🟡 Medium": 1, "🟢 Low": 2}
        suggestions.sort(key=lambda x: (
            priority_order.get(x["priority"], 99),
            -x.get("gsc_impressions", 0),
        ))

        logger.info(f"  ✅ GSC data applied to {len(orphans)} orphans & {len(suggestions)} suggestions")

    except Exception as e:
        logger.warning(f"⚠️  GSC enrichment failed: {e}. Continuing without GSC data.")
        for o in orphans:
            o["gsc_impressions"] = "N/A"
            o["gsc_clicks"] = "N/A"
        for s in suggestions:
            s["gsc_impressions"] = "N/A"

    return orphans, suggestions


# ─── Output ───────────────────────────────────────────────────────────────────

def output_to_sheets(link_map, orphans, overlinked, suggestions, inventory, inbound_counts):
    """Export all tabs to a Google Sheet."""
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"Internal Link Analysis — {today}"

    logger.info(f"📊 Creating Google Sheet: {title}")
    exporter = GoogleSheetsExporter()

    # Tab 1: Link Map
    headers_links = ["Source Page", "Source Title", "Target Page", "Target Title", "Anchor Text", "Link Type"]
    rows_links = [
        [lm["source"], lm["source_title"], lm["target"], lm["target_title"], lm["anchor"], lm["link_type"]]
        for lm in link_map
    ]
    sheet_url = exporter.create_sheet(title, headers_links, rows_links)
    sheet_id = sheet_url.split("/d/")[1].split("/")[0]

    # Tab 2: Orphan Pages
    headers_orphans = ["Page URL", "Page Type", "Title", "GSC Impressions", "GSC Clicks"]
    rows_orphans = [
        [o["url"], o["type"], o["title"], o.get("gsc_impressions", "N/A"), o.get("gsc_clicks", "N/A")]
        for o in orphans
    ]
    exporter.add_sheet_tab(sheet_id, "Orphan Pages", headers_orphans, rows_orphans)

    # Tab 3: Link Suggestions
    headers_sugg = ["Source Page", "Source Title", "Target Page", "Target Title", "Matching Keywords",
                     "Priority", "Suggested Anchor Text", "GSC Impressions"]
    rows_sugg = [
        [s["source_url"], s["source_title"], s["target_url"], s["target_title"],
         s["matching_keywords"], s["priority"], s["suggested_anchor"], s.get("gsc_impressions", "N/A")]
        for s in suggestions
    ]
    exporter.add_sheet_tab(sheet_id, "Link Suggestions", headers_sugg, rows_sugg)

    # Tab 4: Summary
    total_pages = len(inventory)
    total_links = len(link_map)
    orphan_count = len(orphans)
    overlinked_count = len(overlinked)
    suggestion_count = len(suggestions)
    type_counts = defaultdict(int)
    for page in inventory.values():
        type_counts[page["type"]] += 1

    headers_summary = ["Metric", "Value"]
    rows_summary = [
        ["Total Pages", total_pages],
        ["  Products", type_counts.get("product", 0)],
        ["  Collections", type_counts.get("collection", 0)],
        ["  Blog Articles", type_counts.get("article", 0)],
        ["Total Internal Links Found", total_links],
        ["Orphan Pages (0 inbound)", orphan_count],
        ["Over-linked Pages (>20 inbound)", overlinked_count],
        ["Link Suggestions Generated", suggestion_count],
        ["Analysis Date", today],
    ]
    exporter.add_sheet_tab(sheet_id, "Summary", headers_summary, rows_summary)

    # Rename default Sheet1 tab to "Link Map"
    try:
        exporter.service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {"sheetId": 0, "title": "Link Map"},
                        "fields": "title",
                    }
                }]
            }
        ).execute()
    except Exception:
        pass  # Non-critical

    return sheet_url


def output_to_csv(link_map, orphans, overlinked, suggestions, inventory, inbound_counts):
    """Export all data to CSV files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = []

    # Link Map
    headers = ["Source Page", "Source Title", "Target Page", "Target Title", "Anchor Text", "Link Type"]
    rows = [[lm["source"], lm["source_title"], lm["target"], lm["target_title"], lm["anchor"], lm["link_type"]]
            for lm in link_map]
    paths.append(export_to_csv(f"link_map_{timestamp}", headers, rows))

    # Orphan Pages
    headers = ["Page URL", "Page Type", "Title", "GSC Impressions", "GSC Clicks"]
    rows = [[o["url"], o["type"], o["title"], o.get("gsc_impressions", "N/A"), o.get("gsc_clicks", "N/A")]
            for o in orphans]
    paths.append(export_to_csv(f"orphan_pages_{timestamp}", headers, rows))

    # Link Suggestions
    headers = ["Source Page", "Source Title", "Target Page", "Target Title", "Matching Keywords",
               "Priority", "Suggested Anchor Text", "GSC Impressions"]
    rows = [[s["source_url"], s["source_title"], s["target_url"], s["target_title"],
             s["matching_keywords"], s["priority"], s["suggested_anchor"], s.get("gsc_impressions", "N/A")]
            for s in suggestions]
    paths.append(export_to_csv(f"link_suggestions_{timestamp}", headers, rows))

    # Summary
    total_pages = len(inventory)
    type_counts = defaultdict(int)
    for page in inventory.values():
        type_counts[page["type"]] += 1
    headers = ["Metric", "Value"]
    rows = [
        ["Total Pages", total_pages],
        ["Products", type_counts.get("product", 0)],
        ["Collections", type_counts.get("collection", 0)],
        ["Blog Articles", type_counts.get("article", 0)],
        ["Total Internal Links", len(link_map)],
        ["Orphan Pages", len(orphans)],
        ["Over-linked Pages", len(overlinked)],
        ["Link Suggestions", len(suggestions)],
    ]
    paths.append(export_to_csv(f"link_summary_{timestamp}", headers, rows))

    return paths


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🔗 SEO Internal Link Analyzer — Beauty Connect Shop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/seo_internal_linker.py
  python execution/seo_internal_linker.py --skip-gsc
  python execution/seo_internal_linker.py --output csv
  python execution/seo_internal_linker.py --skip-gsc --output csv
        """,
    )
    parser.add_argument("--skip-gsc", action="store_true", help="Skip Google Search Console enrichment")
    parser.add_argument("--output", choices=["sheets", "csv"], default="sheets", help="Output format (default: sheets)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🔗 SEO Internal Link Analyzer — Beauty Connect Shop")
    logger.info("=" * 60)

    # Step 1: Build content inventory
    logger.info("\n📦 Step 1/5: Building content inventory...")
    shopify = ShopifyClient()
    inventory = build_content_inventory(shopify)

    if not inventory:
        logger.error("❌ No pages found in Shopify. Check your API credentials.")
        sys.exit(1)

    # Step 2: Analyze internal links
    logger.info("\n🔗 Step 2/5: Analyzing internal links...")
    link_map, inbound_counts = analyze_internal_links(inventory)

    # Step 3: Identify issues
    logger.info("\n🔍 Step 3/5: Identifying issues...")
    orphans = identify_orphan_pages(inventory, inbound_counts)
    overlinked = identify_overlinked_pages(inbound_counts, inventory)

    if overlinked:
        logger.info(f"  ⚠️  {len(overlinked)} over-linked pages (>{OVER_LINKED_THRESHOLD} inbound)")

    # Step 4: Generate suggestions
    logger.info("\n💡 Step 4/5: Generating link suggestions...")
    suggestions = generate_link_suggestions(inventory, inbound_counts)

    # Step 5: GSC enrichment
    logger.info("\n📈 Step 5/5: GSC enrichment...")
    orphans, suggestions = enrich_with_gsc(orphans, suggestions, args.skip_gsc)

    # Output
    logger.info("\n📊 Exporting results...")
    if args.output == "sheets":
        try:
            sheet_url = output_to_sheets(link_map, orphans, overlinked, suggestions, inventory, inbound_counts)
            logger.info(f"\n✅ Analysis complete!")
            logger.info(f"📊 Google Sheet: {sheet_url}")
        except Exception as e:
            logger.warning(f"⚠️  Google Sheets export failed: {e}")
            logger.info("Falling back to CSV...")
            paths = output_to_csv(link_map, orphans, overlinked, suggestions, inventory, inbound_counts)
            logger.info(f"\n✅ Analysis complete! CSV files:")
            for p in paths:
                logger.info(f"  📄 {p}")
    else:
        paths = output_to_csv(link_map, orphans, overlinked, suggestions, inventory, inbound_counts)
        logger.info(f"\n✅ Analysis complete! CSV files:")
        for p in paths:
            logger.info(f"  📄 {p}")

    # Print summary to console
    type_counts = defaultdict(int)
    for page in inventory.values():
        type_counts[page["type"]] += 1

    logger.info("\n" + "=" * 60)
    logger.info("📋 SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Pages:        {len(inventory)} (🛍️ {type_counts['product']} products, 🗂️ {type_counts['collection']} collections, 📝 {type_counts['article']} articles)")
    logger.info(f"  Links found:  {len(link_map)}")
    logger.info(f"  Orphans:      {len(orphans)} pages with 0 inbound links")
    logger.info(f"  Over-linked:  {len(overlinked)} pages with >{OVER_LINKED_THRESHOLD} inbound links")
    logger.info(f"  Suggestions:  {len(suggestions)} link opportunities")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
