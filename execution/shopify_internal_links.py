#!/usr/bin/env python3
"""
Shopify Internal Linking - Issue #18
Adds cross-links between related collections for Beauty Connect Shop.
"""

import os, json, time, requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE_URL', '').replace('https://', '').replace('http://', '').strip('/')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_ADMIN_API_TOKEN', '')
API_VERSION = '2024-10'
GRAPHQL_URL = f'https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json'
HEADERS = {'X-Shopify-Access-Token': SHOPIFY_TOKEN, 'Content-Type': 'application/json'}

def graphql(query, variables=None):
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    for attempt in range(3):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            wait = 2 ** attempt
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        data = resp.json()
        if 'errors' in data:
            print(f"  GraphQL errors: {data['errors']}")
        return data
    return {}

# ── Fetch all collections ──
print("Fetching all collections...")
query = """
{
    collections(first: 50) {
        nodes {
            id
            title
            handle
            descriptionHtml
        }
    }
}
"""
data = graphql(query)
collections = data.get('data', {}).get('collections', {}).get('nodes', [])
print(f"Found {len(collections)} collections")

handle_map = {c['handle']: c for c in collections}

# ── Link relationships ──
LINKS = {
    'krx': [('corthe', 'Corthe'), ('zena-cosmetics', 'Zena Cosmetics'), ('trainings', 'Professional Trainings'), ('peels', 'Peels')],
    'corthe': [('krx', 'KRX Aesthetics'), ('zena-cosmetics', 'Zena Cosmetics'), ('moisturizers', 'Moisturizers'), ('cleansers', 'Cleansers')],
    'zena-cosmetics': [('krx', 'KRX Aesthetics'), ('corthe', 'Corthe'), ('peels', 'Peels'), ('trainings', 'Professional Trainings')],
    'peels': [('masks', 'Masks'), ('treatments', 'Treatments'), ('zena-cosmetics', 'Zena Cosmetics'), ('cleansers', 'Cleansers')],
    'moisturizers': [('serums-ampoules', 'Serums & Ampoules'), ('toners-essences', 'Toners & Essences'), ('corthe', 'Corthe'), ('eye-neck-care', 'Eye & Neck Care')],
    'serums-ampoules': [('moisturizers', 'Moisturizers'), ('treatments', 'Treatments'), ('eye-neck-care', 'Eye & Neck Care'), ('toners-essences', 'Toners & Essences')],
    'cleansers': [('toners-essences', 'Toners & Essences'), ('peels', 'Peels'), ('corthe', 'Corthe'), ('masks', 'Masks')],
    'masks': [('peels', 'Peels'), ('treatments', 'Treatments'), ('hydrofacial-solutions', 'Hydrofacial Solutions'), ('serums-ampoules', 'Serums & Ampoules')],
    'treatments': [('serums-ampoules', 'Serums & Ampoules'), ('peels', 'Peels'), ('masks', 'Masks'), ('moisturizers', 'Moisturizers')],
    'toners-essences': [('cleansers', 'Cleansers'), ('serums-ampoules', 'Serums & Ampoules'), ('moisturizers', 'Moisturizers'), ('corthe', 'Corthe')],
    'eye-neck-care': [('serums-ampoules', 'Serums & Ampoules'), ('moisturizers', 'Moisturizers'), ('treatments', 'Treatments'), ('krx', 'KRX Aesthetics')],
    'hydrofacial-solutions': [('masks', 'Masks'), ('treatments', 'Treatments'), ('tools-supplies', 'Tools & Equipment'), ('peels', 'Peels')],
    'bundle-kits': [('best-sellers', 'Best Sellers'), ('all-products', 'All Products'), ('new-products', 'New Products')],
    'best-sellers': [('new-products', 'New Products'), ('bundle-kits', 'Bundle Kits'), ('all-products', 'All Products')],
    'trainings': [('krx', 'KRX Aesthetics'), ('zena-cosmetics', 'Zena Cosmetics'), ('corthe', 'Corthe')],
    'body-care': [('moisturizers', 'Moisturizers'), ('treatments', 'Treatments'), ('serums-ampoules', 'Serums & Ampoules')],
    'teeth-whitening-supplies': [('tools-supplies', 'Tools & Equipment'), ('trainings', 'Professional Trainings')],
    'lash-supplies': [('tools-supplies', 'Tools & Equipment'), ('cosmetics', 'Cosmetics')],
    'tools-supplies': [('hydrofacial-solutions', 'Hydrofacial Solutions'), ('lash-supplies', 'Lash Supplies'), ('teeth-whitening-supplies', 'Teeth Whitening')],
    'cosmetics': [('lash-supplies', 'Lash Supplies'), ('best-sellers', 'Best Sellers'), ('new-products', 'New Products')],
    'new-products': [('best-sellers', 'Best Sellers'), ('all-products', 'All Products'), ('bundle-kits', 'Bundle Kits')],
    'samples': [('best-sellers', 'Best Sellers'), ('new-products', 'New Products'), ('all-products', 'All Products')],
}

# Collections that should get blog/training links (skincare-related ones)
SKINCARE_HANDLES = {
    'krx', 'corthe', 'zena-cosmetics', 'peels', 'moisturizers', 'serums-ampoules',
    'cleansers', 'masks', 'treatments', 'toners-essences', 'eye-neck-care',
    'hydrofacial-solutions', 'body-care'
}

def build_related_html(handle, links):
    """Build the related collections HTML block."""
    # Build link pills
    link_pills = []
    for target_handle, label in links:
        link_pills.append(
            f'<a href="/collections/{target_handle}" style="display: inline-block; padding: 8px 16px; '
            f'background: #FAF8F5; border: 1px solid #F0E0CC; border-radius: 20px; color: #2C1810; '
            f'text-decoration: none; font-size: 14px;">{label}</a>'
        )

    pills_html = '\n    '.join(link_pills)

    html = f'''<div class="related-collections" style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #F0E0CC;">
  <h3 style="color: #2C1810; font-size: 18px; margin-bottom: 12px;">Explore Related Collections</h3>
  <div style="display: flex; flex-wrap: wrap; gap: 8px;">
    {pills_html}
  </div>
</div>'''

    # Add blog/training links for skincare collections
    if handle in SKINCARE_HANDLES:
        html += f'''
<p style="margin-top: 16px; font-size: 14px; color: #8B7D6B;">
  📚 <a href="/blogs/news" style="color: #DFBA90;">Read our professional skincare blog</a> |
  🎓 <a href="/collections/trainings" style="color: #DFBA90;">Browse training courses</a>
</p>'''

    return html

# ── Update mutation ──
UPDATE_MUTATION = """
mutation collectionUpdate($input: CollectionInput!) {
    collectionUpdate(input: $input) {
        collection {
            id
            title
            handle
        }
        userErrors {
            field
            message
        }
    }
}
"""

# ── Process each collection ──
updated = 0
skipped = 0
not_found = 0

print(f"\nProcessing {len(LINKS)} collections for internal linking...\n")

for handle, links in LINKS.items():
    if handle not in handle_map:
        print(f"  SKIP: '{handle}' not found in store")
        not_found += 1
        continue

    collection = handle_map[handle]
    current_html = collection.get('descriptionHtml', '') or ''

    # Check if already has related-collections
    if 'related-collections' in current_html:
        print(f"  SKIP: '{collection['title']}' already has internal links")
        skipped += 1
        continue

    # Build and append
    related_html = build_related_html(handle, links)
    new_html = current_html + '\n' + related_html

    # Update via GraphQL
    variables = {
        'input': {
            'id': collection['id'],
            'descriptionHtml': new_html
        }
    }

    result = graphql(UPDATE_MUTATION, variables)
    time.sleep(0.5)  # Rate limit safety

    user_errors = result.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
    if user_errors:
        print(f"  ERROR: '{collection['title']}': {user_errors}")
    else:
        updated_title = result.get('data', {}).get('collectionUpdate', {}).get('collection', {}).get('title', handle)
        print(f"  OK: '{updated_title}' - added {len(links)} internal links")
        updated += 1

# ── Summary ──
print(f"\n{'='*50}")
print(f"Internal Linking Complete!")
print(f"  Updated:   {updated}")
print(f"  Skipped:   {skipped} (already had links)")
print(f"  Not found: {not_found}")
print(f"  Total:     {updated + skipped + not_found}")
print(f"{'='*50}")
