#!/usr/bin/env python3
"""
Blog Publisher v2.0: Google Doc → AI Metadata + Multi-Image Pipeline → Shopify Draft
DO Architecture Execution Script

Reads a Google Doc, generates SEO metadata with Claude, creates 4-5 images from
3 sources (AI-generated, stock photos, product photos), and publishes as a
DRAFT blog article on Shopify.

Image Sources:
  1. AI-generated featured image (gpt-image-1)
  2. Stock photos from Pexels, redesigned with AI
  3. Shopify product photos with AI-redesigned backgrounds

Usage:
    python execution/publish_blog_to_shopify.py --doc_id DOC_ID
    python execution/publish_blog_to_shopify.py --doc_id DOC_ID --dry_run
    python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_stock
    python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_products
    python execution/publish_blog_to_shopify.py --doc_id DOC_ID --skip_images

Requirements in .env:
    SHOPIFY_STORE_URL, SHOPIFY_ADMIN_API_TOKEN
    ANTHROPIC_API_KEY   (metadata generation)
    OPENAI_API_KEY      (gpt-image-1 generation + editing)
    PEXELS_API_KEY      (stock photo search — optional)
    Google OAuth2: credentials.json + token.json in project root
"""

import os
import sys
import json
import logging
import argparse
import time
import re
import requests
import base64
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ───────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/publish_blog.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
SHOPIFY_API_VERSION = "2024-10"
REQUESTS_TIMEOUT = 30
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


# ─── Google Auth ──────────────────────────────────────────────────────────────

def get_google_credentials():
    """Get/refresh Google OAuth2 credentials. Reuses existing token.json."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "❌ credentials.json not found. Download from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', GOOGLE_SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


# ─── Step 1: Read Google Doc ──────────────────────────────────────────────────

def read_google_doc(doc_id: str) -> Tuple[str, str]:
    """
    Read a Google Doc by ID. Returns (plain_text, html_content).
    Converts doc structure to clean HTML suitable for Shopify.
    """
    from googleapiclient.discovery import build

    logger.info(f"📄 Reading Google Doc: {doc_id}")
    creds = get_google_credentials()
    service = build('docs', 'v1', credentials=creds)

    doc = service.documents().get(documentId=doc_id).execute()
    title = doc.get('title', 'Untitled')
    body = doc.get('body', {})
    content = body.get('content', [])

    plain_parts = []
    html_parts = []

    for element in content:
        paragraph = element.get('paragraph')
        if not paragraph:
            continue

        style = paragraph.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
        text_runs = paragraph.get('elements', [])

        para_text = ''
        para_html = ''
        for run in text_runs:
            text_run = run.get('textRun')
            if not text_run:
                continue
            text = text_run.get('content', '')
            ts = text_run.get('textStyle', {})

            if not text.strip():
                para_text += text
                para_html += text
                continue

            plain_part = text
            html_part = text.replace('<', '&lt;').replace('>', '&gt;')

            if ts.get('bold'):
                html_part = f'<strong>{html_part}</strong>'
            if ts.get('italic'):
                html_part = f'<em>{html_part}</em>'
            if ts.get('link'):
                url = ts['link'].get('url', '')
                html_part = f'<a href="{url}">{html_part}</a>'

            para_text += plain_part
            para_html += html_part

        para_text = para_text.strip()
        para_html = para_html.strip()

        if not para_text:
            continue

        plain_parts.append(para_text)

        if style == 'HEADING_1':
            html_parts.append(f'<h1>{para_html}</h1>')
        elif style == 'HEADING_2':
            html_parts.append(f'<h2>{para_html}</h2>')
        elif style == 'HEADING_3':
            html_parts.append(f'<h3>{para_html}</h3>')
        elif style == 'HEADING_4':
            html_parts.append(f'<h4>{para_html}</h4>')
        else:
            html_parts.append(f'<p>{para_html}</p>')

    plain_text = '\n\n'.join(plain_parts)
    html_content = '\n'.join(html_parts)

    logger.info(f"✓ Doc read: '{title}' — {len(plain_text)} chars, {len(html_parts)} paragraphs")
    return plain_text, html_content


# ─── Step 2: Generate SEO Metadata via Claude ─────────────────────────────────

def generate_seo_metadata(content: str, doc_title: str = '') -> Dict:
    """
    Use Claude to generate SEO metadata + image search keywords.
    Returns dict with keys: title, meta_description, slug, tags, image_prompt, image_search_keywords
    """
    import anthropic

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("❌ ANTHROPIC_API_KEY not found in .env")

    client = anthropic.Anthropic(api_key=api_key)

    preview = content[:3000]
    if len(content) > 3000:
        preview += '\n... [content truncated for analysis]'

    prompt = f"""You are an SEO expert for a K-beauty skincare brand in Canada.

Analyze this blog post content and generate SEO metadata.

{f'Document title hint: {doc_title}' if doc_title else ''}

Content:
{preview}

Return ONLY valid JSON (no markdown, no explanation) with exactly these fields:
{{
  "title": "SEO title — 50-60 characters, keyword-rich, compelling",
  "meta_description": "Meta description — 140-155 characters, includes benefit + soft CTA",
  "slug": "url-friendly-slug-no-spaces-all-lowercase",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "image_prompt": "Detailed DALL-E prompt for the blog featured image — describe visual scene, style, mood, colors. No text in image.",
  "image_search_keywords": ["keyword1 for stock photo search", "keyword2", "keyword3"]
}}

Rules:
- title: exactly 50-60 characters
- meta_description: exactly 140-155 characters
- slug: lowercase, hyphens only, no special chars
- tags: 5-8 tags, mix of broad + specific terms
- image_prompt: visual description for a professional blog header photo
- image_search_keywords: 3-5 specific search terms for finding ingredient/lifestyle stock photos (e.g. "niacinamide serum texture", "korean skincare routine morning")"""

    logger.info("🤖 Generating SEO metadata with Claude...")

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text.strip()

            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

            metadata = json.loads(response_text)

            required = ['title', 'meta_description', 'slug', 'tags', 'image_prompt']
            for key in required:
                if key not in metadata:
                    raise ValueError(f"Missing key: {key}")

            # Default image_search_keywords from tags if not provided
            if 'image_search_keywords' not in metadata:
                metadata['image_search_keywords'] = metadata['tags'][:3]

            logger.info(f"✓ Title: {metadata['title']} ({len(metadata['title'])} chars)")
            logger.info(f"✓ Meta: {metadata['meta_description'][:60]}... ({len(metadata['meta_description'])} chars)")
            logger.info(f"✓ Slug: {metadata['slug']}")
            logger.info(f"✓ Tags: {', '.join(metadata['tags'])}")
            logger.info(f"✓ Image search keywords: {', '.join(metadata['image_search_keywords'])}")
            return metadata

        except json.JSONDecodeError as e:
            logger.warning(f"⚠ JSON parse error on attempt {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Metadata generation failed: {e}")
            if attempt < 2:
                time.sleep(2)

    raise RuntimeError("❌ Failed to generate metadata after 3 attempts")


# ─── Step 3a: Generate AI Featured Image ──────────────────────────────────────

def _get_openai_client():
    """Get OpenAI client. Raises ValueError if API key missing."""
    from openai import OpenAI
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError(
            "❌ OPENAI_API_KEY not found in .env\n"
            "   Add it: OPENAI_API_KEY=sk-...\n"
            "   Get it from: https://platform.openai.com/api-keys"
        )
    return OpenAI(api_key=api_key)


def generate_featured_image(title: str, image_prompt: str) -> bytes:
    """Generate a blog featured image using gpt-image-1. Returns PNG bytes."""
    client = _get_openai_client()

    full_prompt = (
        f"{image_prompt} "
        f"Blog header for: '{title}'. "
        f"Professional photography style, soft natural lighting, "
        f"clean composition, no text, no watermarks, no logos. "
        f"High quality, 4K resolution."
    )

    logger.info("🎨 Generating featured image with gpt-image-1...")
    logger.info(f"   Prompt: {full_prompt[:100]}...")

    for attempt in range(3):
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=full_prompt,
                size="1536x1024",
                n=1
            )
            b64_data = response.data[0].b64_json
            image_bytes = base64.b64decode(b64_data)
            logger.info(f"✓ Featured image generated ({len(image_bytes) / 1024:.0f} KB)")
            return image_bytes

        except Exception as e:
            logger.warning(f"⚠ Featured image attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError("❌ Failed to generate featured image after 3 attempts")


# ─── Step 3b: Search Stock Photos (Pexels) ───────────────────────────────────

def search_stock_photos(keywords: List[str], count: int = 2) -> List[Dict]:
    """
    Search Pexels for stock photos matching keywords.
    Returns list of dicts: {url, alt, attribution, photographer, source_url}
    """
    api_key = os.getenv('PEXELS_API_KEY')
    if not api_key:
        logger.warning("⚠ PEXELS_API_KEY not found — skipping stock photos")
        return []

    headers = {'Authorization': api_key}
    results = []

    for keyword in keywords[:count]:
        try:
            resp = requests.get(
                'https://api.pexels.com/v1/search',
                headers=headers,
                params={
                    'query': keyword,
                    'per_page': 1,
                    'orientation': 'landscape',
                    'size': 'large'
                },
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            photos = data.get('photos', [])
            if photos:
                photo = photos[0]
                results.append({
                    'url': photo['src']['large'],  # 940px wide
                    'alt': f"{keyword} — skincare lifestyle",
                    'attribution': f"Photo by {photo['photographer']} on Pexels",
                    'photographer': photo['photographer'],
                    'source_url': photo['url'],
                    'type': 'stock'
                })
                logger.info(f"✓ Stock photo found: '{keyword}' by {photo['photographer']}")
            else:
                logger.info(f"  No stock photo for: '{keyword}'")

            time.sleep(0.5)  # Pexels rate limit: 200 req/min

        except Exception as e:
            logger.warning(f"⚠ Pexels search failed for '{keyword}': {e}")

    return results


# ─── Step 3c: Fetch & Match Shopify Product Images ───────────────────────────

def fetch_shopify_products(store_url: str, access_token: str) -> List[Dict]:
    """Fetch all products with titles and image URLs from Shopify via GraphQL."""
    graphql_url = f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    query = """
    query FetchProducts($cursor: String) {
      products(first: 100, after: $cursor) {
        edges {
          node {
            id
            title
            handle
            images(first: 1) {
              edges {
                node {
                  url
                  altText
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

    all_products = []
    cursor = None

    while True:
        variables = {'cursor': cursor} if cursor else {}
        try:
            resp = requests.post(
                graphql_url, headers=headers,
                json={'query': query, 'variables': variables},
                timeout=REQUESTS_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json().get('data', {}).get('products', {})
        except Exception as e:
            logger.warning(f"⚠ Failed to fetch products: {e}")
            break

        for edge in data.get('edges', []):
            node = edge['node']
            images = node.get('images', {}).get('edges', [])
            image_url = images[0]['node']['url'] if images else None
            image_alt = images[0]['node'].get('altText', '') if images else ''
            if image_url:
                all_products.append({
                    'title': node['title'],
                    'handle': node['handle'],
                    'image_url': image_url,
                    'image_alt': image_alt
                })

        page_info = data.get('pageInfo', {})
        if page_info.get('hasNextPage'):
            cursor = page_info['endCursor']
            time.sleep(0.5)
        else:
            break

    logger.info(f"✓ Fetched {len(all_products)} products with images from Shopify")
    return all_products


def match_products_to_blog(blog_text: str, products: List[Dict], max_matches: int = 2) -> List[Dict]:
    """
    Fuzzy match product names in blog text.
    Returns top matched products sorted by match score.
    """
    from fuzzywuzzy import fuzz

    blog_lower = blog_text.lower()
    scored = []

    for product in products:
        title = product['title']
        # Try exact substring first
        if title.lower() in blog_lower:
            scored.append((100, product))
            continue

        # Fuzzy partial match
        score = fuzz.partial_ratio(title.lower(), blog_lower)
        if score >= 75:
            scored.append((score, product))

    # Sort by score descending, take top matches
    scored.sort(key=lambda x: x[0], reverse=True)
    matches = [p for _, p in scored[:max_matches]]

    if matches:
        logger.info(f"✓ Matched {len(matches)} products: {', '.join(p['title'] for p in matches)}")
    else:
        logger.info("  No product matches found in blog content")

    return matches


# ─── Step 3d: AI Image Redesign ──────────────────────────────────────────────

def redesign_stock_image(image_url: str, blog_topic: str) -> Optional[bytes]:
    """
    Download stock photo and redesign with gpt-image-1 to match brand aesthetic.
    Returns redesigned image bytes, or None on failure.
    """
    try:
        client = _get_openai_client()

        # Download original image
        logger.info(f"  Downloading stock image...")
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        original_bytes = img_resp.content

        # Save to temp file (gpt-image-1 edit needs file-like object)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(original_bytes)
            tmp_path = tmp.name

        try:
            logger.info(f"  Redesigning stock image with AI...")
            with open(tmp_path, 'rb') as img_file:
                response = client.images.edit(
                    model="gpt-image-1",
                    image=img_file,
                    prompt=(
                        f"Enhance this photo to match a premium Korean skincare brand aesthetic. "
                        f"Apply soft pastel color grading, gentle natural lighting, clean composition. "
                        f"Topic: {blog_topic}. Keep the main subject intact. "
                        f"Make it look professional and magazine-quality. No text overlays."
                    ),
                    size="1536x1024"
                )
            b64_data = response.data[0].b64_json
            result = base64.b64decode(b64_data)
            logger.info(f"  ✓ Stock image redesigned ({len(result) / 1024:.0f} KB)")
            return result
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.warning(f"  ⚠ Stock image redesign failed: {e} — using original")
        # Return original image as fallback
        try:
            return requests.get(image_url, timeout=30).content
        except Exception:
            return None


def redesign_product_background(image_url: str, blog_topic: str) -> Optional[bytes]:
    """
    Download Shopify product image and redesign ONLY the background with AI.
    Preserves product label, shape, and structure.
    Returns redesigned image bytes, or None on failure.
    """
    try:
        client = _get_openai_client()

        logger.info(f"  Downloading product image...")
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        original_bytes = img_resp.content

        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(original_bytes)
            tmp_path = tmp.name

        try:
            logger.info(f"  Redesigning product background with AI...")
            with open(tmp_path, 'rb') as img_file:
                response = client.images.edit(
                    model="gpt-image-1",
                    image=img_file,
                    prompt=(
                        f"Keep the product bottle/packaging EXACTLY as-is — do NOT alter the label, "
                        f"text, shape, colors, or any part of the product itself. "
                        f"ONLY change the background. New background: soft gradient with subtle "
                        f"botanical elements, premium Korean skincare aesthetic. "
                        f"Topic: {blog_topic}. Soft natural lighting, clean composition. "
                        f"The product must remain perfectly intact and unmodified."
                    ),
                    size="1536x1024"
                )
            b64_data = response.data[0].b64_json
            result = base64.b64decode(b64_data)
            logger.info(f"  ✓ Product background redesigned ({len(result) / 1024:.0f} KB)")
            return result
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.warning(f"  ⚠ Product background redesign failed: {e} — using original")
        try:
            return requests.get(image_url, timeout=30).content
        except Exception:
            return None


# ─── Step 4: Upload Images to Shopify Files API ──────────────────────────────

def upload_image_to_shopify(store_url: str, access_token: str, image_bytes: bytes, filename: str) -> Optional[str]:
    """
    Upload image to Shopify via Files API (stagedUploadsCreate → upload → fileCreate → poll).
    Returns the public CDN URL, or None on failure.
    """
    graphql_url = f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    def _gql(query: str, variables: Dict = None) -> Dict:
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        resp = requests.post(graphql_url, headers=headers, json=payload, timeout=REQUESTS_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get('data', {})

    try:
        # Step 1: Create staged upload target
        staged_data = _gql("""
            mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
              stagedUploadsCreate(input: $input) {
                stagedTargets {
                  url
                  resourceUrl
                  parameters { name value }
                }
                userErrors { field message }
              }
            }
        """, {
            "input": [{
                "resource": "FILE",
                "filename": filename,
                "mimeType": "image/png",
                "httpMethod": "POST"
            }]
        })

        targets = staged_data.get('stagedUploadsCreate', {}).get('stagedTargets', [])
        if not targets:
            errors = staged_data.get('stagedUploadsCreate', {}).get('userErrors', [])
            logger.warning(f"⚠ Staged upload failed: {errors}")
            return None

        target = targets[0]
        upload_url = target['url']
        resource_url = target['resourceUrl']
        params = {p['name']: p['value'] for p in target['parameters']}

        # Step 2: Upload file to staged URL
        files = {'file': (filename, image_bytes, 'image/png')}
        upload_resp = requests.post(upload_url, data=params, files=files, timeout=60)
        if upload_resp.status_code not in (200, 201):
            logger.warning(f"⚠ File upload failed: {upload_resp.status_code}")
            return None

        # Step 3: Create file record
        file_data = _gql("""
            mutation fileCreate($files: [FileCreateInput!]!) {
              fileCreate(files: $files) {
                files {
                  id
                  alt
                  fileStatus
                }
                userErrors { field message }
              }
            }
        """, {
            "files": [{
                "alt": filename.replace('.png', '').replace('-', ' '),
                "contentType": "IMAGE",
                "originalSource": resource_url
            }]
        })

        files_created = file_data.get('fileCreate', {}).get('files', [])
        if not files_created:
            errors = file_data.get('fileCreate', {}).get('userErrors', [])
            logger.warning(f"⚠ File create failed: {errors}")
            return None

        file_id = files_created[0]['id']

        # Step 4: Poll for CDN URL (file processing is async)
        for poll in range(10):
            time.sleep(2)
            node_data = _gql("""
                query getFile($id: ID!) {
                  node(id: $id) {
                    ... on MediaImage {
                      fileStatus
                      image {
                        url
                      }
                    }
                    ... on GenericFile {
                      fileStatus
                      url
                    }
                  }
                }
            """, {"id": file_id})

            node = node_data.get('node', {})
            status = node.get('fileStatus', '')

            if status == 'READY':
                cdn_url = None
                if 'image' in node and node['image']:
                    cdn_url = node['image']['url']
                elif 'url' in node:
                    cdn_url = node['url']

                if cdn_url:
                    logger.info(f"  ✓ Image uploaded to Shopify CDN: {filename}")
                    return cdn_url

            if status in ('FAILED', 'CANCELLED'):
                logger.warning(f"⚠ File processing {status} for {filename}")
                return None

        logger.warning(f"⚠ Timeout waiting for file processing: {filename}")
        return None

    except Exception as e:
        logger.warning(f"⚠ Shopify file upload failed for {filename}: {e}")
        return None


# ─── Step 5: Inject Images into HTML ─────────────────────────────────────────

def inject_images_into_html(html_content: str, images: List[Dict]) -> str:
    """
    Insert <figure><img> blocks after H2 headings in blog HTML.
    Each image dict: {cdn_url, alt, attribution (optional), type}
    """
    if not images:
        return html_content

    # Find all H2 positions
    h2_pattern = re.compile(r'(<h2>.*?</h2>)', re.DOTALL)
    h2_matches = list(h2_pattern.finditer(html_content))

    if not h2_matches:
        # No H2s — append images at the end
        for img in images:
            html_content += _make_figure_html(img)
        return html_content

    # Insert one image after the first <p> following each H2
    result = html_content
    offset = 0  # track position shifts from insertions
    image_idx = 0

    for h2_match in h2_matches:
        if image_idx >= len(images):
            break

        # Find the next </p> after this H2
        search_start = h2_match.end() + offset
        next_p_end = result.find('</p>', search_start)

        if next_p_end == -1:
            # No paragraph after this H2 — insert right after H2
            insert_pos = search_start
        else:
            insert_pos = next_p_end + len('</p>')

        figure_html = _make_figure_html(images[image_idx])
        result = result[:insert_pos] + '\n' + figure_html + '\n' + result[insert_pos:]
        offset += len(figure_html) + 2  # +2 for the \n chars
        image_idx += 1

    # If extra images remain, append before last paragraph
    while image_idx < len(images):
        result += '\n' + _make_figure_html(images[image_idx])
        image_idx += 1

    return result


def _make_figure_html(img: Dict) -> str:
    """Create a <figure> HTML block for an image."""
    caption = ''
    if img.get('attribution'):
        source_url = img.get('source_url', '#')
        caption = (
            f'<figcaption style="font-size: 0.85em; color: #888; margin-top: 0.5em;">'
            f'{img["attribution"]}'
            f'</figcaption>'
        )

    return (
        f'<figure style="margin: 2em 0; text-align: center;">'
        f'<img src="{img["cdn_url"]}" alt="{img.get("alt", "Blog image")}" '
        f'style="max-width: 100%; height: auto; border-radius: 8px;" loading="lazy" />'
        f'{caption}'
        f'</figure>'
    )


# ─── Shopify Blog Client ─────────────────────────────────────────────────────

class ShopifyBlogClient:
    """Handles Shopify Admin REST API calls for blog articles."""

    def __init__(self, store_url: str, access_token: str):
        self.store_url = store_url.rstrip('/')
        self.access_token = access_token
        self.base_url = f"https://{self.store_url}/admin/api/{SHOPIFY_API_VERSION}"
        self.headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }

    def _get(self, endpoint: str) -> Dict:
        """GET request with retry."""
        for attempt in range(3):
            try:
                resp = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=REQUESTS_TIMEOUT
                )
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.warning(f"GET {endpoint} attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
        return {}

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        """POST request with retry."""
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    json=payload,
                    timeout=REQUESTS_TIMEOUT
                )
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError:
                logger.error(f"HTTP error {resp.status_code}: {resp.text[:200]}")
                raise
            except Exception as e:
                logger.warning(f"POST {endpoint} attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
        return {}

    def get_blogs(self) -> List[Dict]:
        """Fetch all blogs from the store."""
        data = self._get('/blogs.json')
        return data.get('blogs', [])

    def get_blog_id(self, blog_name: Optional[str] = None) -> int:
        """Get blog ID by name, or return the first blog's ID."""
        blogs = self.get_blogs()
        if not blogs:
            raise RuntimeError(
                "❌ No blogs found in your Shopify store.\n"
                "   Create one: Shopify Admin → Online Store → Blog Posts → Manage blogs"
            )

        if blog_name:
            for blog in blogs:
                if blog_name.lower() in blog['title'].lower():
                    logger.info(f"✓ Found blog: '{blog['title']}' (ID: {blog['id']})")
                    return blog['id']
            logger.warning(f"⚠ Blog '{blog_name}' not found — using first blog: '{blogs[0]['title']}'")

        blog = blogs[0]
        logger.info(f"✓ Using blog: '{blog['title']}' (ID: {blog['id']})")
        return blog['id']

    def create_draft_article(
        self,
        blog_id: int,
        title: str,
        body_html: str,
        slug: str,
        meta_title: str,
        meta_description: str,
        tags: List[str],
        author: str,
        image_bytes: Optional[bytes] = None,
        image_filename: str = 'featured-image.png'
    ) -> Dict:
        """Create a DRAFT blog article on Shopify."""
        # Append timestamp to slug to avoid conflicts with existing articles
        from datetime import datetime
        unique_slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M')}"

        article_payload = {
            "title": title,
            "body_html": body_html,
            "handle": unique_slug,
            "author": author,
            "tags": ', '.join(tags),
            "published": False,
            "metafields": [
                {
                    "key": "title_tag",
                    "value": meta_title,
                    "type": "single_line_text_field",
                    "namespace": "global"
                },
                {
                    "key": "description_tag",
                    "value": meta_description,
                    "type": "single_line_text_field",
                    "namespace": "global"
                }
            ]
        }

        # Upload featured image via Files API (more reliable than base64 attachment)
        if image_bytes:
            logger.info("📤 Uploading featured image via Shopify Files API...")
            cdn_url = upload_image_to_shopify(
                self.store_url, self.access_token,
                image_bytes, image_filename
            )
            if cdn_url:
                article_payload["image"] = {
                    "src": cdn_url,
                    "alt": title
                }
                logger.info(f"✓ Featured image CDN URL: {cdn_url}")
            else:
                logger.warning("⚠ Featured image upload failed — proceeding without image")

        logger.info("📤 Creating Shopify draft article...")
        result = self._post(f'/blogs/{blog_id}/articles.json', {"article": article_payload})

        article = result.get('article', {})
        if not article.get('id'):
            raise RuntimeError(f"❌ Failed to create article. Response: {result}")

        return article


# ─── Main Orchestrator ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Publish a Google Doc as a Shopify blog draft with AI images (v2.0)'
    )
    parser.add_argument('--doc_id', required=True, help='Google Doc ID (from the doc URL)')
    parser.add_argument('--blog_name', default=None, help='Target Shopify blog name (default: first blog)')
    parser.add_argument('--author', default='Beauty Connect', help='Blog post author name')
    parser.add_argument('--dry_run', action='store_true', help='Preview only — do NOT post to Shopify')
    parser.add_argument('--skip_images', action='store_true', help='Skip all image generation (text only)')
    parser.add_argument('--skip_stock', action='store_true', help='Skip stock photo sourcing')
    parser.add_argument('--skip_products', action='store_true', help='Skip product image matching')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🚀 Blog Publisher v2.0 — Multi-Image Pipeline")
    logger.info("=" * 60)

    # ── Load credentials ──
    store_url = os.getenv('SHOPIFY_STORE_URL')
    admin_token = os.getenv('SHOPIFY_ADMIN_API_TOKEN')
    if not store_url or not admin_token:
        logger.error("❌ SHOPIFY_STORE_URL or SHOPIFY_ADMIN_API_TOKEN missing in .env")
        sys.exit(1)

    try:
        # ══════════════════════════════════════════════════════════════
        # Step 1: Read Google Doc
        # ══════════════════════════════════════════════════════════════
        plain_text, html_content = read_google_doc(args.doc_id)

        if not plain_text.strip():
            logger.error("❌ Google Doc appears to be empty")
            sys.exit(1)

        # ══════════════════════════════════════════════════════════════
        # Step 2: Generate SEO Metadata
        # ══════════════════════════════════════════════════════════════
        metadata = generate_seo_metadata(plain_text)
        title = metadata['title']
        meta_description = metadata['meta_description']
        slug = metadata['slug']
        tags = metadata['tags']
        image_prompt = metadata['image_prompt']
        image_keywords = metadata.get('image_search_keywords', tags[:3])

        # ══════════════════════════════════════════════════════════════
        # Step 3: Image Pipeline (3 sources → 4-5 images)
        # ══════════════════════════════════════════════════════════════
        featured_image_bytes = None
        in_body_images = []  # List of {cdn_url, alt, attribution, type}

        if not args.skip_images:
            logger.info("\n" + "─" * 40)
            logger.info("🖼  IMAGE PIPELINE")
            logger.info("─" * 40)

            # ── Source 1: AI Featured Image ──
            logger.info("\n[1/3] AI Featured Image")
            try:
                featured_image_bytes = generate_featured_image(title, image_prompt)
            except (ValueError, RuntimeError) as e:
                logger.warning(str(e))
                logger.warning("⚠ Proceeding without featured image.")

            # ── Source 2: Stock Photos (Pexels) ──
            if not args.skip_stock:
                logger.info("\n[2/3] Stock Photos (Pexels)")
                stock_photos = search_stock_photos(image_keywords, count=2)

                for i, stock in enumerate(stock_photos):
                    logger.info(f"  Redesigning stock photo {i+1}/{len(stock_photos)}...")
                    redesigned = redesign_stock_image(stock['url'], title)
                    if redesigned:
                        # Upload to Shopify Files API
                        cdn_url = upload_image_to_shopify(
                            store_url, admin_token, redesigned,
                            f"{slug}-stock-{i+1}.png"
                        )
                        if cdn_url:
                            in_body_images.append({
                                'cdn_url': cdn_url,
                                'alt': stock['alt'],
                                'attribution': stock['attribution'],
                                'source_url': stock.get('source_url', ''),
                                'type': 'stock'
                            })
            else:
                logger.info("\n[2/3] Stock Photos — SKIPPED (--skip_stock)")

            # ── Source 3: Product Images ──
            if not args.skip_products:
                logger.info("\n[3/3] Product Images (Shopify)")
                products = fetch_shopify_products(store_url, admin_token)
                matched = match_products_to_blog(plain_text, products, max_matches=2)

                for i, product in enumerate(matched):
                    logger.info(f"  Redesigning product: {product['title']}")
                    redesigned = redesign_product_background(product['image_url'], title)
                    if redesigned:
                        cdn_url = upload_image_to_shopify(
                            store_url, admin_token, redesigned,
                            f"{slug}-product-{i+1}.png"
                        )
                        if cdn_url:
                            in_body_images.append({
                                'cdn_url': cdn_url,
                                'alt': f"{product['title']} — Korean skincare",
                                'attribution': None,
                                'type': 'product'
                            })
            else:
                logger.info("\n[3/3] Product Images — SKIPPED (--skip_products)")

            logger.info(f"\n✓ Image pipeline complete: 1 featured + {len(in_body_images)} in-body images")

        # ══════════════════════════════════════════════════════════════
        # Step 4: Inject in-body images into HTML
        # ══════════════════════════════════════════════════════════════
        if in_body_images:
            logger.info(f"📐 Injecting {len(in_body_images)} images after H2 headings...")
            html_content = inject_images_into_html(html_content, in_body_images)

        # ══════════════════════════════════════════════════════════════
        # Dry Run: Print preview and exit
        # ══════════════════════════════════════════════════════════════
        if args.dry_run:
            logger.info("\n" + "=" * 60)
            logger.info("📋 DRY RUN — Preview (nothing posted to Shopify)")
            logger.info("=" * 60)
            logger.info(f"  Title:             {title}")
            logger.info(f"  Meta description:  {meta_description}")
            logger.info(f"  Slug/Handle:       {slug}")
            logger.info(f"  Tags:              {', '.join(tags)}")
            logger.info(f"  Author:            {args.author}")
            logger.info(f"  Featured image:    {'✓' if featured_image_bytes else '✗'}")
            logger.info(f"  In-body images:    {len(in_body_images)}")
            for img in in_body_images:
                logger.info(f"    - [{img['type']}] {img['alt'][:50]}...")
            logger.info(f"  Content length:    {len(html_content)} chars HTML")
            logger.info("=" * 60)
            return

        # ══════════════════════════════════════════════════════════════
        # Step 5: Create Shopify Draft
        # ══════════════════════════════════════════════════════════════
        client = ShopifyBlogClient(store_url, admin_token)
        blog_id = client.get_blog_id(args.blog_name)

        image_filename = f"{slug[:50]}.png" if featured_image_bytes else None

        article = client.create_draft_article(
            blog_id=blog_id,
            title=title,
            body_html=html_content,
            slug=slug,
            meta_title=title,
            meta_description=meta_description,
            tags=tags,
            author=args.author,
            image_bytes=featured_image_bytes,
            image_filename=image_filename or 'featured-image.png'
        )

        article_id = article['id']
        article_handle = article.get('handle', slug)
        admin_url = f"https://{store_url}/admin/articles/{article_id}"
        preview_url = f"https://{store_url}/blogs/{article.get('blog_id', blog_id)}/{article_handle}"

        logger.info("\n" + "=" * 60)
        logger.info("✅ Blog draft created successfully!")
        logger.info("=" * 60)
        logger.info(f"  Title:          {title}")
        logger.info(f"  Status:         DRAFT (not published)")
        logger.info(f"  Author:         {args.author}")
        logger.info(f"  Tags:           {', '.join(tags)}")
        logger.info(f"  Featured image: {'✓ Attached' if featured_image_bytes else '✗ None'}")
        logger.info(f"  In-body images: {len(in_body_images)}")
        for img in in_body_images:
            logger.info(f"    - [{img['type']}] {img['alt'][:50]}")
        logger.info(f"")
        logger.info(f"  📝 Review draft:  {admin_url}")
        logger.info(f"  🔗 Preview URL:   {preview_url}")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n⚠ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
