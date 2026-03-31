"""
SEO Critical Fixes - Investigate & Fix 5 Critical Issues
DOE Layer: Execution
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE_URL', '').replace('https://', '').replace('http://', '').strip('/')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_ADMIN_API_TOKEN', '')
API_VERSION = '2024-10'
GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"
REST_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}"

HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_TOKEN,
    'Content-Type': 'application/json',
}


def graphql(query, variables=None):
    """Execute GraphQL query with retry."""
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    for attempt in range(3):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        data = resp.json()
        if 'errors' in data:
            print(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
        return data.get('data', {})
    return {}


def rest_get(endpoint):
    """REST API GET."""
    resp = requests.get(f"{REST_URL}/{endpoint}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ============================================================
# ISSUE 2: Find & Fix Register link with myshopify URL
# ============================================================

def investigate_menus():
    """Fetch all navigation menus and their items."""
    query = """
    {
        menus(first: 20) {
            nodes {
                id
                title
                handle
                items {
                    id
                    title
                    type
                    url
                    resourceId
                    tags
                    items {
                        id
                        title
                        type
                        url
                        resourceId
                        tags
                    }
                }
            }
        }
    }
    """
    data = graphql(query)
    menus = data.get('menus', {}).get('nodes', [])

    print("\n" + "="*60)
    print("ISSUE 2: Navigation Menus Investigation")
    print("="*60)

    myshopify_links = []

    for menu in menus:
        print(f"\nMenu: {menu['title']} (handle: {menu['handle']}, id: {menu['id']})")
        for item in menu.get('items', []):
            url = item.get('url', '') or ''
            prefix = "  ⚠️" if 'myshopify.com' in url else "  "
            print(f"{prefix} {item['title']} → {url} (type: {item['type']})")
            if 'myshopify.com' in url:
                myshopify_links.append({
                    'menu_id': menu['id'],
                    'menu_title': menu['title'],
                    'menu_handle': menu['handle'],
                    'item_id': item['id'],
                    'item_title': item['title'],
                    'item_type': item['type'],
                    'current_url': url,
                    'all_items': menu.get('items', []),
                })
            # Check sub-items
            for sub in item.get('items', []):
                sub_url = sub.get('url', '') or ''
                prefix = "    ⚠️" if 'myshopify.com' in sub_url else "    "
                print(f"{prefix} {sub['title']} → {sub_url} (type: {sub['type']})")
                if 'myshopify.com' in sub_url:
                    myshopify_links.append({
                        'menu_id': menu['id'],
                        'menu_title': menu['title'],
                        'menu_handle': menu['handle'],
                        'item_id': sub['id'],
                        'item_title': sub['title'],
                        'item_type': sub['type'],
                        'current_url': sub_url,
                        'parent_item': item,
                        'all_items': menu.get('items', []),
                    })

    if myshopify_links:
        print(f"\n⚠️ Found {len(myshopify_links)} links with myshopify.com URLs!")
    else:
        print("\n✅ No myshopify.com URLs found in navigation menus.")

    return menus, myshopify_links


def fix_menu_links(menus, myshopify_links, dry_run=True):
    """Fix myshopify URLs in menus."""
    if not myshopify_links:
        print("No links to fix.")
        return

    # Group by menu
    menus_to_update = {}
    for link in myshopify_links:
        mid = link['menu_id']
        if mid not in menus_to_update:
            # Find the full menu
            for m in menus:
                if m['id'] == mid:
                    menus_to_update[mid] = m
                    break

    for menu_id, menu in menus_to_update.items():
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixing menu: {menu['title']}")

        # Build updated items - replace myshopify URLs
        def fix_items(items):
            fixed = []
            for item in items:
                url = item.get('url', '') or ''
                new_url = url.replace(f'{SHOPIFY_STORE}', 'beautyconnectshop.com') if 'myshopify.com' in url else url

                if new_url != url:
                    print(f"  🔧 {item['title']}: {url} → {new_url}")

                fixed_item = {
                    'title': item['title'],
                    'type': item['type'],
                }
                # Always include id for existing items
                if item.get('id'):
                    fixed_item['id'] = item['id']
                # For HTTP type, set the URL (fixed or original)
                if item['type'] == 'HTTP':
                    fixed_item['url'] = new_url if 'myshopify.com' in url else url
                # For resource-based types, include resourceId
                if item.get('resourceId'):
                    fixed_item['resourceId'] = item['resourceId']
                # Include tags if present
                if item.get('tags'):
                    fixed_item['tags'] = item['tags']

                # Handle sub-items
                sub_items = item.get('items', [])
                if sub_items:
                    fixed_item['items'] = fix_items(sub_items)

                fixed.append(fixed_item)
            return fixed

        updated_items = fix_items(menu['items'])

        if not dry_run:
            mutation = """
            mutation menuUpdate($id: ID!, $title: String!, $items: [MenuItemUpdateInput!]!) {
                menuUpdate(id: $id, title: $title, items: $items) {
                    menu {
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
            variables = {
                'id': menu_id,
                'title': menu['title'],
                'items': updated_items,
            }
            result = graphql(mutation, variables)
            errors = result.get('menuUpdate', {}).get('userErrors', [])
            if errors:
                print(f"  ❌ Errors: {json.dumps(errors, indent=2)}")
            else:
                print(f"  ✅ Menu updated successfully!")


# ============================================================
# ISSUE 3 & 5: Theme Investigation (EasyLockdown + H1)
# ============================================================

def investigate_theme():
    """Fetch active theme and scan for issues."""
    # Get main theme
    query = """
    {
        themes(roles: [MAIN], first: 1) {
            nodes {
                id
                name
                role
                files(first: 250, filenames: ["*"]) {
                    nodes {
                        filename
                        size
                        contentType
                    }
                }
            }
        }
    }
    """
    data = graphql(query)
    themes = data.get('themes', {}).get('nodes', [])

    if not themes:
        print("❌ No main theme found!")
        return None, [], []

    theme = themes[0]
    theme_id = theme['id']
    print(f"\n{'='*60}")
    print(f"THEME: {theme['name']} (role: {theme['role']})")
    print(f"ID: {theme_id}")
    print(f"{'='*60}")

    # List all liquid files
    files = theme.get('files', {}).get('nodes', [])
    liquid_files = [f['filename'] for f in files if f['filename'].endswith('.liquid')]
    json_files = [f['filename'] for f in files if f['filename'].endswith('.json')]

    print(f"\nLiquid files: {len(liquid_files)}")
    print(f"JSON files: {len(json_files)}")

    return theme_id, liquid_files, json_files


def read_theme_file(theme_id, filename):
    """Read a single theme file's content."""
    query = """
    query($id: ID!, $filenames: [String!]!) {
        theme(id: $id) {
            files(first: 1, filenames: $filenames) {
                nodes {
                    filename
                    body {
                        ... on OnlineStoreThemeFileBodyText {
                            content
                        }
                        ... on OnlineStoreThemeFileBodyBase64 {
                            contentBase64
                        }
                    }
                }
            }
        }
    }
    """
    data = graphql(query, {'id': theme_id, 'filenames': [filename]})
    nodes = data.get('theme', {}).get('files', {}).get('nodes', [])
    if nodes:
        body = nodes[0].get('body', {})
        return body.get('content', '') or ''
    return ''


def scan_theme_for_issues(theme_id, liquid_files):
    """Scan theme files for EasyLockdown message and H1 issues."""

    print(f"\n{'='*60}")
    print("ISSUE 3: Scanning for EasyLockdown message...")
    print("ISSUE 5: Scanning for homepage H1...")
    print(f"{'='*60}")

    # Priority files to check for EasyLockdown
    priority_files = [
        'layout/theme.liquid',
        'templates/index.liquid',
        'templates/index.json',
        'sections/header.liquid',
        'snippets/easylockdown.liquid',
        'snippets/lockdown.liquid',
    ]

    # Also check all snippets for EasyLockdown
    snippet_files = [f for f in liquid_files if f.startswith('snippets/')]
    section_files = [f for f in liquid_files if f.startswith('sections/')]

    easylockdown_files = []
    h1_files = []

    # Check priority files first
    files_to_check = list(set(priority_files + snippet_files + ['layout/theme.liquid']))
    files_to_check = [f for f in files_to_check if f in liquid_files or f.replace('.liquid', '.json') in [j for j in []]]

    for filename in files_to_check:
        if filename not in liquid_files:
            continue
        content = read_theme_file(theme_id, filename)
        if not content:
            continue
        time.sleep(0.5)  # Rate limiting

        # Check for EasyLockdown
        if 'easylockdown' in content.lower() or 'IMPORTANT! If you' in content or 'Customer accounts enabled' in content or 'lockdown' in content.lower():
            print(f"\n⚠️ EasyLockdown found in: {filename}")
            # Find the relevant lines
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in ['easylockdown', 'lockdown', 'important! if you', 'customer accounts']):
                    start = max(0, i - 2)
                    end = min(len(lines), i + 5)
                    print(f"  Lines {start+1}-{end}:")
                    for j in range(start, end):
                        marker = ">>>" if j == i else "   "
                        print(f"  {marker} {j+1}: {lines[j][:120]}")
            easylockdown_files.append({'filename': filename, 'content': content})

        # Check for H1
        if '<h1' in content.lower() and filename in ['layout/theme.liquid', 'templates/index.liquid'] + section_files:
            print(f"\n📌 H1 tag found in: {filename}")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '<h1' in line.lower():
                    start = max(0, i - 1)
                    end = min(len(lines), i + 3)
                    for j in range(start, end):
                        marker = ">>>" if j == i else "   "
                        print(f"  {marker} {j+1}: {lines[j][:150]}")
            h1_files.append({'filename': filename, 'content': content})

    # Also check index.json for section references
    if 'templates/index.json' in [f for f in liquid_files] or True:
        content = read_theme_file(theme_id, 'templates/index.json')
        if content:
            print(f"\n📄 templates/index.json content (section references):")
            try:
                idx_data = json.loads(content)
                sections = idx_data.get('sections', {})
                for key, section in sections.items():
                    print(f"  Section: {key} → type: {section.get('type', 'unknown')}")
                    if section.get('settings', {}).get('heading'):
                        print(f"    heading: {section['settings']['heading']}")
                    if section.get('settings', {}).get('title'):
                        print(f"    title: {section['settings']['title']}")
            except json.JSONDecodeError:
                print("  (not valid JSON)")

    return easylockdown_files, h1_files


# ============================================================
# ISSUE 4: Collection Meta Descriptions
# ============================================================

def investigate_meta_descriptions():
    """Fetch all collection and page meta descriptions."""
    query = """
    {
        collections(first: 50) {
            nodes {
                id
                title
                handle
                seo {
                    title
                    description
                }
                descriptionHtml
            }
        }
    }
    """
    data = graphql(query)
    collections = data.get('collections', {}).get('nodes', [])

    print(f"\n{'='*60}")
    print("ISSUE 4: Collection Meta Descriptions")
    print(f"{'='*60}")

    # Check for duplicates
    desc_map = {}
    for col in collections:
        seo = col.get('seo', {})
        desc = seo.get('description', '') or ''
        title = seo.get('title', '') or ''

        if desc not in desc_map:
            desc_map[desc] = []
        desc_map[desc].append(col['title'])

        status = "⚠️ DUPLICATE" if len(desc_map.get(desc, [])) > 1 else ("⚠️ EMPTY" if not desc else "✅")
        print(f"\n{status} Collection: {col['title']} (/{col['handle']})")
        print(f"  SEO Title: {title or '(empty)'}")
        print(f"  SEO Desc:  {desc[:100] or '(empty)'}{'...' if len(desc) > 100 else ''}")

    # Report duplicates
    print(f"\n--- Duplicate Report ---")
    for desc, cols in desc_map.items():
        if len(cols) > 1:
            print(f"⚠️ {len(cols)} collections share: \"{desc[:80]}...\"")
            for c in cols:
                print(f"   - {c}")

    return collections


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='SEO Critical Fixes')
    parser.add_argument('--investigate', action='store_true', help='Investigate all issues')
    parser.add_argument('--fix-menus', action='store_true', help='Fix myshopify URLs in menus')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run (default)')
    parser.add_argument('--push-live', action='store_true', help='Push changes live')
    args = parser.parse_args()

    dry_run = not args.push_live

    if args.investigate or not (args.fix_menus):
        print("🔍 Investigating all 5 critical SEO issues...\n")

        # Issue 2: Menus
        menus, myshopify_links = investigate_menus()

        # Issue 3 & 5: Theme
        theme_id, liquid_files, json_files = investigate_theme()
        if theme_id:
            easylockdown_files, h1_files = scan_theme_for_issues(theme_id, liquid_files)

        # Issue 4: Meta descriptions
        collections = investigate_meta_descriptions()

        print(f"\n{'='*60}")
        print("INVESTIGATION SUMMARY")
        print(f"{'='*60}")
        print(f"Issue 2 - Myshopify links: {len(myshopify_links)} found")
        print(f"Issue 3 - EasyLockdown files: {len(easylockdown_files)} found")
        print(f"Issue 4 - Collections scanned: {len(collections)}")
        print(f"Issue 5 - H1 locations: {len(h1_files)} found")

    if args.fix_menus:
        menus, myshopify_links = investigate_menus()
        fix_menu_links(menus, myshopify_links, dry_run=dry_run)
