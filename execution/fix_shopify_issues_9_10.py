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
    if variables: payload['variables'] = variables
    for attempt in range(3):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        data = resp.json()
        if 'errors' in data:
            print(f"GraphQL errors: {data['errors']}")
        return data
    return {}

def read_file(theme_id, filename):
    query = '''
    query($id: ID!, $filenames: [String!]!) {
        theme(id: $id) {
            files(first: 1, filenames: $filenames) {
                nodes {
                    filename
                    body {
                        ... on OnlineStoreThemeFileBodyText { content }
                    }
                }
            }
        }
    }
    '''
    data = graphql(query, {'id': theme_id, 'filenames': [filename]})
    nodes = data.get('data', {}).get('theme', {}).get('files', {}).get('nodes', [])
    if nodes:
        return nodes[0].get('body', {}).get('content', '')
    return ''

def write_file(theme_id, filename, content):
    mutation = '''
    mutation($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
        themeFilesUpsert(themeId: $themeId, files: $files) {
            upsertedThemeFiles { filename }
            userErrors { field message }
        }
    }
    '''
    result = graphql(mutation, {
        'themeId': theme_id,
        'files': [{'filename': filename, 'body': {'type': 'TEXT', 'value': content}}]
    })
    errors = result.get('data', {}).get('themeFilesUpsert', {}).get('userErrors', [])
    if errors:
        print(f"ERROR {filename}: {errors}")
        return False
    print(f"SUCCESS: {filename} updated")
    return True

theme_id = 'gid://shopify/OnlineStoreTheme/143671001203'

# ============================================================
# ISSUE 9: Rename blog from "News" to keyword-rich title
# ============================================================
print("=" * 60)
print("ISSUE 9: Rename blog from 'News' to 'Professional Skincare Insights'")
print("=" * 60)

# Step 1: Fetch blogs to find the "News" blog
blogs_query = """
{ blogs(first: 10) { nodes { id title handle } } }
"""
blogs_data = graphql(blogs_query)
blogs = blogs_data.get('data', {}).get('blogs', {}).get('nodes', [])
print(f"Found {len(blogs)} blog(s):")
for b in blogs:
    print(f"  - {b['title']} (handle: {b['handle']}, id: {b['id']})")

# Find the "News" blog
news_blog = None
for b in blogs:
    if b['title'].lower() == 'news':
        news_blog = b
        break

if not news_blog:
    # If no exact match, use the first blog
    if blogs:
        news_blog = blogs[0]
        print(f"No 'News' blog found. Using first blog: {news_blog['title']}")
    else:
        print("ERROR: No blogs found!")

if news_blog:
    print(f"\nUpdating blog: {news_blog['id']} ({news_blog['title']})")

    # Step 2: Update blog title and SEO
    update_mutation = """
    mutation blogUpdate($id: ID!, $blog: BlogInput!) {
        blogUpdate(id: $id, blog: $blog) {
            blog { id title }
            userErrors { field message }
        }
    }
    """
    update_vars = {
        'id': news_blog['id'],
        'blog': {
            'title': 'Professional Skincare Insights',
            'seo': {
                'title': 'Korean Skincare Blog | Beauty Connect Shop'
            }
        }
    }
    result = graphql(update_mutation, update_vars)
    blog_result = result.get('data', {}).get('blogUpdate', {})
    errors = blog_result.get('userErrors', [])
    if errors:
        print(f"ERROR updating blog: {errors}")
    else:
        updated_blog = blog_result.get('blog', {})
        print(f"SUCCESS: Blog renamed to '{updated_blog.get('title')}'")
        print(f"  SEO title set to: 'Korean Skincare Blog | Beauty Connect Shop'")

# ============================================================
# ISSUE 10: Add breadcrumb navigation
# ============================================================
print("\n" + "=" * 60)
print("ISSUE 10: Add breadcrumb navigation to theme")
print("=" * 60)

# Step 1: Create snippets/breadcrumbs.liquid
breadcrumbs_content = """{%- unless template == 'index' -%}
<nav class="breadcrumbs" aria-label="Breadcrumb" style="padding: 12px 20px; font-size: 13px; color: #8B7D6B; max-width: 1200px; margin: 0 auto;">
  <ol style="list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 4px; align-items: center;" itemscope itemtype="https://schema.org/BreadcrumbList">
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
      <a itemprop="item" href="/" style="color: #8B7D6B; text-decoration: none;">
        <span itemprop="name">Home</span>
      </a>
      <meta itemprop="position" content="1" />
      <span style="margin: 0 6px; color: #ccc;">/</span>
    </li>

    {%- if template contains 'collection' -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        <span itemprop="name" style="color: #2C1810; font-weight: 500;">{{ collection.title }}</span>
        <link itemprop="item" href="{{ shop.url }}/collections/{{ collection.handle }}" />
        <meta itemprop="position" content="2" />
      </li>

    {%- elsif template contains 'product' -%}
      {%- if product.collections.size > 0 -%}
        <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
          <a itemprop="item" href="{{ product.collections.first.url }}" style="color: #8B7D6B; text-decoration: none;">
            <span itemprop="name">{{ product.collections.first.title }}</span>
          </a>
          <meta itemprop="position" content="2" />
          <span style="margin: 0 6px; color: #ccc;">/</span>
        </li>
      {%- endif -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        <span itemprop="name" style="color: #2C1810; font-weight: 500;">{{ product.title }}</span>
        <link itemprop="item" href="{{ shop.url }}{{ product.url }}" />
        <meta itemprop="position" content="{{ product.collections.size | plus: 2 }}" />
      </li>

    {%- elsif template contains 'blog' -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        {%- if template contains 'article' -%}
          <a itemprop="item" href="{{ blog.url }}" style="color: #8B7D6B; text-decoration: none;">
            <span itemprop="name">{{ blog.title }}</span>
          </a>
          <meta itemprop="position" content="2" />
          <span style="margin: 0 6px; color: #ccc;">/</span>
        </li>
        <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
          <span itemprop="name" style="color: #2C1810; font-weight: 500;">{{ article.title }}</span>
          <link itemprop="item" href="{{ shop.url }}{{ article.url }}" />
          <meta itemprop="position" content="3" />
        {%- else -%}
          <span itemprop="name" style="color: #2C1810; font-weight: 500;">{{ blog.title }}</span>
          <link itemprop="item" href="{{ shop.url }}{{ blog.url }}" />
          <meta itemprop="position" content="2" />
        {%- endif -%}
      </li>

    {%- elsif template contains 'page' -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        <span itemprop="name" style="color: #2C1810; font-weight: 500;">{{ page.title }}</span>
        <link itemprop="item" href="{{ shop.url }}{{ page.url }}" />
        <meta itemprop="position" content="2" />
      </li>

    {%- elsif template contains 'search' -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        <span itemprop="name" style="color: #2C1810; font-weight: 500;">Search Results</span>
        <meta itemprop="position" content="2" />
      </li>

    {%- elsif template contains 'cart' -%}
      <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem" style="display: flex; align-items: center;">
        <span itemprop="name" style="color: #2C1810; font-weight: 500;">Cart</span>
        <meta itemprop="position" content="2" />
      </li>
    {%- endif -%}
  </ol>
</nav>
{%- endunless -%}"""

print("\nStep 1: Creating snippets/breadcrumbs.liquid...")
success1 = write_file(theme_id, 'snippets/breadcrumbs.liquid', breadcrumbs_content)

# Step 2: Read theme.liquid and inject breadcrumbs
print("\nStep 2: Reading layout/theme.liquid...")
theme_liquid = read_file(theme_id, 'layout/theme.liquid')

if not theme_liquid:
    print("ERROR: Could not read layout/theme.liquid")
else:
    print(f"  Read {len(theme_liquid)} characters from theme.liquid")

    # Check if breadcrumbs already included
    if "render 'breadcrumbs'" in theme_liquid:
        print("  Breadcrumbs already included in theme.liquid - skipping")
    else:
        # Find <main id="MainContent" and inject after the opening tag
        import re

        # Match <main ...> tag with MainContent
        main_pattern = r'(<main[^>]*id="MainContent"[^>]*>)'
        match = re.search(main_pattern, theme_liquid)

        if match:
            main_tag = match.group(1)
            injection = main_tag + "\n      {% render 'breadcrumbs' %}"
            new_theme_liquid = theme_liquid.replace(main_tag, injection, 1)

            print(f"  Found main tag: {main_tag[:80]}...")
            print("  Injecting breadcrumbs render after <main> tag...")

            success2 = write_file(theme_id, 'layout/theme.liquid', new_theme_liquid)
        else:
            # Try alternative patterns
            alt_pattern = r'(<main[^>]*MainContent[^>]*>)'
            match = re.search(alt_pattern, theme_liquid)
            if match:
                main_tag = match.group(1)
                injection = main_tag + "\n      {% render 'breadcrumbs' %}"
                new_theme_liquid = theme_liquid.replace(main_tag, injection, 1)
                print(f"  Found main tag (alt): {main_tag[:80]}...")
                success2 = write_file(theme_id, 'layout/theme.liquid', new_theme_liquid)
            else:
                print("  WARNING: Could not find <main id=\"MainContent\"> tag")
                # Show context around 'main' or 'MainContent'
                for keyword in ['MainContent', '<main', 'content_for_layout']:
                    idx = theme_liquid.find(keyword)
                    if idx >= 0:
                        snippet = theme_liquid[max(0,idx-50):idx+100]
                        print(f"  Found '{keyword}' at pos {idx}: ...{snippet}...")

print("\n" + "=" * 60)
print("DONE - Both issues processed")
print("=" * 60)
