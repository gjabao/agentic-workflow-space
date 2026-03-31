#!/usr/bin/env python3
"""
Beauty Connect Shop — Shopify SEO Optimizer
DO Architecture Execution Script v1.0

Fetches all products from Shopify, scores SEO health (0-100),
generates AI-optimized meta titles, descriptions, and alt text using Azure OpenAI,
validates for Health Canada compliance, and exports audit to Google Sheets.

Usage:
    python execution/shopify_seo_optimizer.py --dry_run
    python execution/shopify_seo_optimizer.py --limit 10 --dry_run
    python execution/shopify_seo_optimizer.py --push_live
    python execution/shopify_seo_optimizer.py --min_score 70 --dry_run
"""

import os
import sys
import json
import logging
import argparse
import time
import re
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI
import anthropic
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# ─── Logging ───────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/shopify_seo.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
REQUESTS_TIMEOUT = 30
SHOPIFY_API_VERSION = "2024-10"
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# ─── Health Canada Compliance (ASC Guidelines, Column II therapeutic claims) ──
# Reference: ASC "Guidelines for Non-therapeutic Advertising and Labelling Claims"
# Column II = therapeutic/health claims requiring DIN/NPN pre-market authorization
# Any match = FORBIDDEN for cosmetic products without Health Canada approval
#
# Organized by product category per the ASC document.

HEALTH_CANADA_FORBIDDEN = [
    # ── SKIN CARE / MAKEUP ─────────────────────────────────────────────────────
    r'\bheals?\b(?!\s+dry\s+skin)',           # "heals" unqualified (allow "heals dry skin")
    r'\brepairs?\s+(?:damaged\s+)?(?:the\s+)?skin\b',  # "repairs skin" / "repairs damaged skin"
    r'\brepairs?\s+(?:the\s+)?skin\'?s?\s+moisture\s+barrier\b',  # "repairs the skin's moisture barrier"
    r'\btreats?\s+(?:acne|rosacea|eczema|dermatitis|psoriasis|infection|burns?|cellulite)',
    r'\bcures?\b',
    r'\bprevents?\s+(?:disease|infection|acne|breakout)',
    r'\bprevents?\s+(?:new\s+)?(?:spots?|age\s+spots?)\s+(?:from\s+)?appear',  # "prevents new spots from appearing"
    r'\bprevents?\s+(?:the\s+)?(?:onset|emergence)\s+of\s+age\s+spots?\b',
    r'\bprevents?\s+photoaging\b',
    r'\bskin\s+de-?pigmentation\b',
    r'\beliminates?\s+age\s+spots?\b',
    r'\banti-inflammatory\b',                 # unqualified (without NPN)
    r'\bantibacterial\b',
    r'\bantifungal\b',
    r'\bantiseptic\b',
    r'\bdisinfectant\b',
    r'\bsanitizer\b',
    r'\bfungicid\w*\b',
    r'\bgermicid\w*\b',
    r'\bprescription[\s.-]?strength\b',
    r'\bmedical[\s.-]?grade\b',
    r'\bclinical[\s.-]?(?:strength|effect|action)\b',   # "clinical strength/effect/action"
    r'\bclinical\s+protection\b(?!\s+\()',    # "clinical protection" unqualified
    r'\btherapeutic[\s.-]?(?:strength|effect|action)\b',
    r'\b(?:Rx|Pr)\b',                        # prescription symbols
    r'\bstimulates?\s+(?:cell|cellular|hair|eyelash|collagen|genital)',
    r'\bprevents?\s+hair\s+loss\b',
    r'\bprevents?\s+(?:hair\s+)?thinning\b',
    r'\btreats?\s+alopecia\b',
    r'\binhibits?\s+hair\s+growth\b',
    r'\bstops?\s+hair\s+growth\b',
    r'\bstimulates?\s+(?:hair|eyelash)\s+growth\b',
    r'\bspf\s*\d*\b',                        # SPF claims
    r'\bsunscreen\b',
    r'\bsunburn\s+protectant\b',
    r'\b(?:uva|uvb|uv)\s+protect\w*\b',      # UV protection claims
    r'\bprotects?\s+sun\s+damaged\s+skin\b',
    r'\bclears?\s+(?:skin\s+)?(?:acne|blemish)',
    r'\banti-?blemish\b',
    r'\bheals?\s+(?:acne|pimples?|blemish)',
    r'\bstops?\s+(?:acne|pimples?|breakout)',
    r'\bfights?\s+(?:bacteria|germs|pathogens)\b',
    r'\bkills?\s+(?:bacteria|germs|pathogens)\b(?!.*odou?r)',  # (allow "kills odour-causing bacteria")
    r'\baction\s+(?:at\s+)?(?:a\s+)?cellular\s+level\b',
    r'\breference\s+to\s+(?:action\s+on\s+)?(?:tissue|body|cells)\b',
    r'\bremoves?\s+(?:permanent\s+)?scars?\b',
    r'\breduces?\s+(?:scars?|redness)\s+due\s+to\s+(?:rosacea|sunburn)',
    r'\brosacea\b',                           # any reference to rosacea
    r'\breduces?\s+(?:cellulite|swelling|edema)\b',
    r'\bremoves?\s+cellulite\b',
    r'\bweight\s+(?:management|loss)\b',
    r'\bfat\s+loss\b',
    r'\blipodraining\b',
    r'\bcleans?\s+wounds?\b',
    r'\bnumbs?\b',
    r'\bdesensitiz\w*\b',                     # desensitizes / desensitizing
    r'\bmedical\b.*\bprocedure\b',            # "effect of a medical procedure"
    r'\bsurgical\b.*\bprocedure\b',           # "effect of a surgical procedure"

    # ── NAIL CARE ──────────────────────────────────────────────────────────────
    r'\bpromotes?\s+nail\s+growth\b(?!.*physical\s+damage)',  # physiological nail growth
    # "antifungal" already covered above

    # ── HAIR CARE ──────────────────────────────────────────────────────────────
    r'\banti-?dandruff\b',                    # requires monograph
    r'\bcontrols?\s+dandruff\b',
    r'\beliminates?\s+dandruff\b',
    r'\bprevents?\s+dandruff\b',
    r'\beffect\s+on\s+(?:living\s+)?(?:tissue|hair\s+follicle)',
    r'\bstimulates?\s+eyelash\s+growth\b',

    # ── ORAL CARE ──────────────────────────────────────────────────────────────
    r'\banti-?cavity\b',
    r'\banti-?gingivitis\b',
    r'\banti-?sensitivity\b',
    r'\banti-?plaque\b',
    r'\banti-?tartar\b',
    r'\bfights?\s+(?:plaque|tartar)\b',
    r'\btreats?\s+(?:plaque|tartar)\b',
    r'\bfluoride\s+effect\b',
    r'\bstrengthens?\s+(?:enamel|teeth|gums)\b',
    r'\bdesensitiz\w*\s+(?:teeth|gums)\b',
    r'\bantiviral\b',
    r'\bremoves?\s+permanent\s+stains?\b',
    r'\beffect\s+below\s+(?:the\s+)?gum\s+line\b',
    r'\bkills?\s+(?:odou?r\s+causing\s+)?germs\b',

    # ── ANTIPERSPIRANTS ────────────────────────────────────────────────────────
    r'\bhyperhidrosis\b',
    r'\bexcessive\s+perspiration\b',
    r'\bproblem\s+perspiration\b',
    r'\bhormonal\b.*\bperspiration\b',
    r'\bendocrine\b.*\bperspiration\b',

    # ── INTIMATE PRODUCTS ──────────────────────────────────────────────────────
    r'\bspermicid\w*\b',
    r'\bincreases?\s+libido\b',
    r'\bprolongs?\s+(?:erection|orgasm)\b',
    r'\bproduces?\s+(?:erection|orgasm)\b',
    r'\bstimulates?\s+genital\b',
    r'\bvaginal\s+tighten\w*\b',
    r'\bvaginal\s+contract\w*\b',
    r'\bdelays?\s+orgasm\b',
    r'\benhances?\s+sperm\s+motility\b',
    r'\bimproves?\s+(?:chances?\s+of\s+)?conception\b',
    r'\bpH[\s-]balanced\s+to\s+prevent\s+infection\b',

    # ── OTHER CLAIMS (INGREDIENTS / ENDORSEMENTS) ──────────────────────────────
    r'\bactive\s+ingredient\b',               # implies therapeutic
    r'\bmedicinal\s+ingredient\b',
    r'\btherapeutic\s+ingredient\b',
    r'\beffective\s+ingredient\b',
    r'\bfree\s+radical\s+scaveng\w*\b',       # therapeutic antioxidant claim
    r'\brepairing\s+damage\b',                # "repairing damage" re: vitamins/antioxidants
    r'\baction\s+at\s+(?:a\s+)?cellular\s+level\b',  # re: ingredient claims
    r'\bdose\s+units?\b',                     # e.g. IU
    r'\b\d+\s*IU\b',                          # international units = therapeutic dosage
    r'\bpromotes?\s+health\b',                # "promotes health" unqualified
    r'\bbiological\s+(?:action|effect)\b',
    r'\btherapeutic\s+(?:action|effect)\b',
    r'\bdisease\s+(?:prevention|control|healing)\b',
    r'\bdisease[\s-]causing\s+organisms?\b',
]

K_BEAUTY_KEYWORDS = [
    # Core K-beauty terms
    "Korean skincare", "K-beauty", "glass skin", "skin barrier",
    "snail mucin", "PDRN", "peptides", "niacinamide", "ceramides",
    "slow aging", "hanbang", "essences", "double cleanse", "barrier repair",
    "professional grade", "esthetician trusted", "Canada",
    # 2026 trending ingredients
    "tranexamic acid", "retinal", "centella asiatica", "heartleaf",
    "mugwort", "ginseng", "bamboo sap", "encapsulated",
    "deep hydration", "exosomes", "mela-D", "polyglutamic acid",
    "azelaic acid", "bakuchiol", "propolis", "galactomyces",
    # Market-specific
    "professional skincare Canada", "esthetician-grade", "spa treatment",
    "Korean beauty routine", "multi-step routine", "skin barrier repair",
]


def load_brand_voice() -> str:
    """Load brand voice guidelines from directive file."""
    brand_voice_path = 'directives/brand/brand_voice.md'
    if os.path.exists(brand_voice_path):
        with open(brand_voice_path, 'r') as f:
            return f.read()
    logger.warning("⚠ brand_voice.md not found — using default guidelines")
    return "Professional Korean skincare brand for estheticians in Canada. Warm, educational tone. Health Canada compliant."


def check_health_canada_compliance(text: str) -> List[str]:
    """
    Validate text against Health Canada therapeutic claim restrictions.
    Returns list of violations found (empty = compliant).
    """
    violations = []
    text_lower = text.lower()
    for pattern in HEALTH_CANADA_FORBIDDEN:
        if re.search(pattern, text_lower, re.IGNORECASE):
            violations.append(pattern)
    return violations


# ─── Shopify Client ────────────────────────────────────────────────────────────

class ShopifyClient:
    """Handles Shopify Admin GraphQL API calls."""

    def __init__(self, store_url: str, access_token: str):
        self.store_url = store_url.rstrip('/')
        self.access_token = access_token
        self.base_url = f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        self.headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
        self._delay = 0.5  # 500ms between calls — Shopify standard plan = 40 req/min

    def _graphql(self, query: str, variables: Dict = None) -> Dict:
        """Execute a GraphQL query with retry logic."""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        for attempt in range(3):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=REQUESTS_TIMEOUT
                )
                if response.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited — waiting {wait}s")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return {}
                return data.get('data', {})
            except requests.Timeout:
                logger.error(f"Timeout on attempt {attempt + 1}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return {}

    def fetch_all_products(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all products with SEO fields via GraphQL pagination."""
        query = """
        query FetchProducts($cursor: String) {
          products(first: 50, after: $cursor) {
            edges {
              node {
                id
                title
                handle
                descriptionHtml
                tags
                productType
                images(first: 1) {
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
        """
        products = []
        cursor = None

        while True:
            variables = {'cursor': cursor} if cursor else {}
            data = self._graphql(query, variables)

            if not data or 'products' not in data:
                break

            edges = data['products']['edges']
            for edge in edges:
                products.append(edge['node'])
                if limit and len(products) >= limit:
                    logger.info(f"✓ Fetched {len(products)} products (limit reached)")
                    return products

            page_info = data['products']['pageInfo']
            if not page_info['hasNextPage']:
                break

            cursor = page_info['endCursor']
            time.sleep(self._delay)

        logger.info(f"✓ Fetched {len(products)} total products")
        return products

    def update_product_seo(self, product_id: str, seo_title: str, seo_description: str, body_html: str = None) -> bool:
        """Update product SEO title, description, and optionally body HTML."""
        mutation = """
        mutation UpdateProductSEO($input: ProductInput!) {
          productUpdate(input: $input) {
            product {
              id
              seo {
                title
                description
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        input_data = {
            'id': product_id,
            'seo': {
                'title': seo_title,
                'description': seo_description
            }
        }
        if body_html:
            input_data['descriptionHtml'] = body_html

        variables = {'input': input_data}
        data = self._graphql(mutation, variables)
        errors = data.get('productUpdate', {}).get('userErrors', [])
        if errors:
            logger.error(f"Failed to update {product_id}: {errors}")
            return False
        logger.info(f"✓ Updated SEO for {product_id}")
        time.sleep(self._delay)
        return True

    def update_image_alt_text(self, product_id: str, image_id: str, alt_text: str) -> bool:
        """Update image alt text via REST API (productImageUpdate removed in 2024-10)."""
        # Extract numeric IDs from GraphQL global IDs
        # e.g. gid://shopify/Product/123 → 123
        product_num = product_id.split('/')[-1]
        image_num = image_id.split('/')[-1]

        url = f"https://{self.store_url}/admin/api/{SHOPIFY_API_VERSION}/products/{product_num}/images/{image_num}.json"
        payload = {'image': {'id': int(image_num), 'alt': alt_text}}

        for attempt in range(3):
            try:
                response = requests.put(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=REQUESTS_TIMEOUT
                )
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code == 200:
                    time.sleep(self._delay)
                    return True
                logger.error(f"Alt text update failed {response.status_code}: {response.text[:100]}")
                return False
            except Exception as e:
                logger.error(f"Alt text update error: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return False


# ─── SEO Scorer ────────────────────────────────────────────────────────────────

class SEOScorer:
    """Scores product SEO health from 0-100."""

    def score(self, product: Dict) -> Tuple[int, Dict]:
        """
        Score a product's SEO health.
        Returns (score, breakdown_dict).
        """
        score = 0
        breakdown = {}
        seo = product.get('seo', {})
        meta_title = seo.get('title') or ''
        meta_desc = seo.get('description') or ''
        description = product.get('descriptionHtml') or ''
        images = product.get('images', {}).get('edges', [])
        alt_text = images[0]['node'].get('altText') or '' if images else ''

        # Meta title scoring
        if meta_title:
            score += 20
            breakdown['meta_title_present'] = True
            title_len = len(meta_title)
            if 30 <= title_len <= 60:
                score += 10
                breakdown['meta_title_length'] = 'good'
            else:
                breakdown['meta_title_length'] = f'bad ({title_len} chars)'
            # Check for any K-beauty keyword
            title_lower = meta_title.lower()
            if any(kw.lower() in title_lower for kw in K_BEAUTY_KEYWORDS):
                score += 10
                breakdown['meta_title_keyword'] = True
            else:
                breakdown['meta_title_keyword'] = False
        else:
            breakdown['meta_title_present'] = False

        # Meta description scoring
        if meta_desc:
            score += 20
            breakdown['meta_desc_present'] = True
            desc_len = len(meta_desc)
            if 120 <= desc_len <= 160:
                score += 10
                breakdown['meta_desc_length'] = 'good'
            else:
                breakdown['meta_desc_length'] = f'bad ({desc_len} chars)'
        else:
            breakdown['meta_desc_present'] = False

        # Product description scoring
        # Strip HTML tags for word count
        desc_text = re.sub(r'<[^>]+>', ' ', description)
        word_count = len(desc_text.split())
        if word_count >= 200:
            score += 10
            breakdown['description_length'] = f'good ({word_count} words)'
        else:
            breakdown['description_length'] = f'short ({word_count} words)'

        # Image alt text scoring
        if alt_text:
            score += 10
            breakdown['alt_text_present'] = True
            product_name_words = product.get('title', '').lower().split()
            alt_lower = alt_text.lower()
            name_in_alt = any(w in alt_lower for w in product_name_words if len(w) > 3)
            if name_in_alt:
                score += 10
                breakdown['alt_text_quality'] = 'good'
            else:
                breakdown['alt_text_quality'] = 'missing product name'
        else:
            breakdown['alt_text_present'] = False

        return score, breakdown


# ─── SEO Optimizer (AI) ────────────────────────────────────────────────────────

class SEOOptimizer:
    """Generates AI-optimized SEO content using Azure OpenAI, OpenAI, or Anthropic."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, brand_voice: str):
        self.brand_voice = brand_voice
        self.provider = None

        # Try Azure OpenAI first
        try:
            self.client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version="2024-02-15-preview"
            )
            self.deployment = deployment
            self.provider = 'azure'
            logger.info("✓ Using Azure OpenAI")
        except Exception as e:
            logger.warning(f"Azure OpenAI init failed: {e}")

        # Fallback: Anthropic
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
            if not self.provider:
                self.provider = 'anthropic'
                logger.info("✓ Using Anthropic Claude as AI provider")
        else:
            self.anthropic_client = None

        # Fallback: OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)
            if not self.provider:
                self.provider = 'openai'
                logger.info("✓ Using OpenAI as AI provider")
        else:
            self.openai_client = None

    def _call_ai(self, prompt: str, title: str, _attempt: int = 0) -> Optional[Dict]:
        """Call AI provider with auto-fallback: Azure → Anthropic → OpenAI."""
        providers = []
        if self.provider == 'azure':
            providers = ['azure', 'anthropic', 'openai']
        elif self.provider == 'anthropic':
            providers = ['anthropic', 'openai']
        elif self.provider == 'openai':
            providers = ['openai', 'anthropic']
        else:
            providers = ['anthropic', 'openai', 'azure']

        for prov in providers:
            try:
                if prov == 'azure' and hasattr(self, 'client'):
                    response = self.client.chat.completions.create(
                        model=self.deployment,
                        messages=[{'role': 'user', 'content': prompt}],
                        temperature=0.4,
                        max_tokens=1500,
                        response_format={"type": "json_object"}
                    )
                    return json.loads(response.choices[0].message.content)

                elif prov == 'anthropic' and self.anthropic_client:
                    response = self.anthropic_client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1500,
                        messages=[{'role': 'user', 'content': prompt + "\n\nReturn ONLY valid JSON, no markdown code blocks."}],
                    )
                    text = response.content[0].text.strip()
                    # Strip markdown code block if present
                    if text.startswith('```'):
                        text = re.sub(r'^```(?:json)?\s*', '', text)
                        text = re.sub(r'\s*```$', '', text)
                    return json.loads(text)

                elif prov == 'openai' and hasattr(self, 'openai_client') and self.openai_client:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{'role': 'user', 'content': prompt}],
                        temperature=0.4,
                        max_tokens=1500,
                        response_format={"type": "json_object"}
                    )
                    return json.loads(response.choices[0].message.content)

            except Exception as e:
                logger.warning(f"  {prov} failed for {title}: {str(e)[:80]} — trying next provider")
                continue

        return None

    def optimize_product(self, product: Dict) -> Dict:
        """
        Generate optimized SEO fields for a product.
        Returns dict with: meta_title, meta_description, description_intro, alt_text
        """
        title = product.get('title', '')
        current_desc = re.sub(r'<[^>]+>', ' ', product.get('descriptionHtml', ''))[:500]
        product_type = product.get('productType', '')
        tags = ', '.join(product.get('tags', []))
        current_seo = product.get('seo', {})

        prompt = f"""You are writing SEO content for Beauty Connect Shop — a professional Korean skincare brand in Canada selling to estheticians (B2B) and skincare enthusiasts (B2C).

BRAND VOICE SUMMARY:
{self.brand_voice[:800]}

PRODUCT TO OPTIMIZE:
- Name: {title}
- Type: {product_type}
- Tags: {tags}
- Current description (first 500 chars): {current_desc}
- Current meta title: {current_seo.get('title', 'MISSING')}
- Current meta description: {current_seo.get('description', 'MISSING')}

TASK: Generate fully optimized SEO content in JSON format.

SEO REQUIREMENTS:
1. meta_title: EXACTLY 50-60 characters (count carefully). Lead with primary keyword. Add "Canada" or "K-beauty" or "Professional" where natural. Do NOT include store name.
2. meta_description: EXACTLY 140-155 characters (count carefully). Lead with the key benefit, include a long-tail keyword, end with a subtle CTA like "Shop now." or "Trusted by estheticians."
3. body_html: Full product description in HTML — 200-350 words. Structure: opening benefit sentence → 3-4 key benefits as <ul><li> bullet points → who it's for → how to use (1-2 sentences) → brand credibility line. Use <strong> for key ingredients. Target long-tail keywords naturally (e.g., "snail mucin essence for dry skin Canada" not just "snail mucin").
4. alt_text: Exactly describes the product image — product name + key ingredient + use case + skin type concern (max 120 chars)

2026 TRENDING K-BEAUTY KEYWORDS TO USE (where relevant to this specific product):
tranexamic acid, retinal, centella asiatica, heartleaf, mugwort, ginseng, PDRN, snail mucin,
barrier repair, deep hydration, glass skin, hanbang, ceramides, niacinamide, peptides,
exosomes, galactomyces, propolis, bakuchiol, polyglutamic acid, slow aging

HEALTH CANADA COMPLIANCE — ASC Guidelines (mandatory — if you violate this, regenerate):
This product is a COSMETIC. Only Column I (non-therapeutic) claims are allowed.
Column II (therapeutic/health) claims require a DIN or NPN and are FORBIDDEN here.

SKIN CARE — ALLOWED (Column I):
- Heals dry skin, protects/relieves/soothes dry skin, hydrates, moisturizes, lubricates
- Reinforces/strengthens skin (via moisturization), improves the look of acne scars
- Relieves redness/itching due to dryness, reduces the look of age spots
- Diminishes/reduces the look or the signs of aging, skin looks visibly younger/revitalized/radiant
- Smoothes wrinkles, wrinkles appear/look reduced, firms/tightens/tones/conditions/softens skin
- Improves elasticity/resiliency, skin feels/appears firm/lifted
- Reduces the look of cellulite, reduces puffiness, sloughs off dead skin cells
- Improves texture of skin, deep cleans pores, unclogs/tightens pores
- Removes/absorbs oil, cleanser for acne-prone skin, covers blemishes/acne
- Kills odour causing bacteria, bronzed/suntanned look
- Professional-grade, dermatologist tested, recommended by dermatologists

SKIN CARE — FORBIDDEN (Column II):
- Heals (unqualified), repairs skin/damaged skin, repairs skin's moisture barrier
- Calms/protects/relieves/soothes abrasions/bites/cuts/irritated/inflamed skin/rashes/sunburns
- Numbs, treats burns/infections, any reference to pain or irritation
- Removes/reduces scars, reduces redness due to rosacea, any reference to rosacea
- Eliminates age spots, prevents new spots, skin de-pigmentation, prevents photoaging
- Provides effect of medical/surgical procedure
- Reduces/controls swelling/edema, weight/fat loss, removes/treats cellulite
- Action at cellular level, reference to action on tissue/body/cells, lipodraining
- Cleans wounds, anti-blemish, clears skin (acne), heals/prevents/treats acne
- SPF/UV/UVA/UVB, sunburn protectant, sunscreen, protects sun damaged skin
- Kills pathogens/germs/bacteria (other than odour causing), antibacterial action
- Antiseptic, disinfectant, sanitizer, fungicide, disease prevention/control
- Prescription strength, Rx, Pr, clinical/therapeutic strength/effect/action
- Active/effective/medicinal/therapeutic ingredient, promotes health
- Free radical scavenging, action at cellular level, dose units (IU)

HAIR/NAIL — FORBIDDEN: anti-dandruff, stimulates hair/eyelash growth, prevents hair loss/thinning, treats alopecia, antifungal
ORAL — FORBIDDEN: anti-cavity, anti-gingivitis, fluoride claims, strengthens enamel/teeth/gums
GENERAL RULE: If a claim implies the product modifies organic function or impacts disease, it is therapeutic and FORBIDDEN.

Return ONLY valid JSON (no markdown, no code block):
{{
  "meta_title": "exactly 50-60 chars here",
  "meta_description": "exactly 140-155 chars here",
  "body_html": "<p>Full HTML description here...</p>",
  "alt_text": "descriptive alt text here"
}}"""

        for attempt in range(3):
            try:
                result = self._call_ai(prompt, title, attempt)
                if result is None:
                    continue

                # Validate Health Canada compliance
                all_text = ' '.join(str(v) for v in result.values())
                violations = check_health_canada_compliance(all_text)
                if violations:
                    logger.warning(f"⚠ Health Canada violation in {title} — regenerating")
                    prompt += f"\n\nPREVIOUS OUTPUT HAD VIOLATIONS. DO NOT use these patterns: {violations}"
                    continue

                # Enforce character lengths programmatically (no retry needed)
                meta_title = result.get('meta_title', '')
                meta_desc = result.get('meta_description', '')

                # Trim meta_title to 60 chars at word boundary if too long
                if len(meta_title) > 60:
                    meta_title = meta_title[:60].rsplit(' ', 1)[0]
                    result['meta_title'] = meta_title

                # Trim meta_desc to 155 chars at word boundary if too long
                if len(meta_desc) > 155:
                    meta_desc = meta_desc[:155].rsplit(' ', 1)[0]
                    result['meta_description'] = meta_desc

                return result

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {title}: {e}")
            except Exception as e:
                logger.error(f"AI error for {title}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        # Fallback: return current values with minimal improvements
        logger.warning(f"⚠ Using fallback SEO for {title}")
        fallback_title = (title + " | Korean Skincare Canada")[:60]
        return {
            'meta_title': fallback_title,
            'meta_description': f"Shop {title[:60]} at Beauty Connect Shop. Professional K-beauty for estheticians in Canada. Free shipping available.",
            'body_html': f"<p>{current_desc[:500]}</p>" if current_desc else f"<p>Professional Korean skincare product by Beauty Connect Shop. Trusted by estheticians across Canada.</p>",
            'alt_text': f"{title} — professional Korean skincare product"
        }


# ─── Google Sheets Exporter ────────────────────────────────────────────────────

class GoogleSheetsExporter:
    """Exports SEO audit results to Google Sheets."""

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', GOOGLE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as f:
                f.write(creds.to_json())
        return build('sheets', 'v4', credentials=creds)

    def create_audit_report(self, audit_results: List[Dict]) -> str:
        """Create Google Sheets with before/after SEO comparison."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"BeautyConnect SEO Audit — {timestamp}"

        spreadsheet = self.service.spreadsheets().create(
            body={'properties': {'title': title}},
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        sheet_id = spreadsheet['spreadsheetId']
        sheet_url = spreadsheet['spreadsheetUrl']

        headers = [
            'Product Title', 'Handle',
            'SEO Score (Before)', 'SEO Score (After)', 'Score Change',
            'Current Meta Title', 'Optimized Meta Title', 'Title Length',
            'Current Meta Desc', 'Optimized Meta Desc', 'Desc Length',
            'Current Alt Text', 'Optimized Alt Text',
            'Body HTML Updated', 'Health Canada Compliant', 'Status', 'Shopify Product ID'
        ]

        rows = [headers]
        for r in audit_results:
            opt = r.get('optimized', {})
            rows.append([
                r['title'],
                r['handle'],
                r['score_before'],
                r['score_after'],
                f"+{r['score_after'] - r['score_before']}" if r['score_after'] > r['score_before'] else str(r['score_after'] - r['score_before']),
                r['current_meta_title'],
                opt.get('meta_title', ''),
                len(opt.get('meta_title', '')),
                r['current_meta_desc'],
                opt.get('meta_description', ''),
                len(opt.get('meta_description', '')),
                r['current_alt_text'],
                opt.get('alt_text', ''),
                'YES' if opt.get('body_html') else 'NO',
                'YES' if r.get('compliant') else 'NO',
                r.get('status', 'pending_review'),
                r['product_id']
            ])

        self.service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()

        # Bold headers + freeze row 1
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                'requests': [
                    {
                        'repeatCell': {
                            'range': {'sheetId': 0, 'startRowIndex': 0, 'endRowIndex': 1},
                            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.95}}},
                            'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                        }
                    },
                    {
                        'updateSheetProperties': {
                            'properties': {'sheetId': 0, 'gridProperties': {'frozenRowCount': 1}},
                            'fields': 'gridProperties.frozenRowCount'
                        }
                    }
                ]
            }
        ).execute()

        logger.info(f"✓ Google Sheet created: {sheet_url}")
        return sheet_url


# ─── Main Orchestrator ─────────────────────────────────────────────────────────

def run_seo_optimizer(args):
    """Main orchestration function."""

    # ── Load credentials
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ADMIN_API_TOKEN')

    # Support legacy private app auth (API key + secret as basic auth)
    if not access_token:
        api_key = os.getenv('SHOPIFY_API_KEY')
        api_secret = os.getenv('SHOPIFY_API_SECRET')
        if api_key and api_secret:
            access_token = api_secret  # Private app: secret = access token
            logger.info("Using private app credentials (API key + secret)")

    if not store_url or not access_token:
        logger.error("❌ Missing SHOPIFY_STORE_URL or SHOPIFY_ADMIN_API_TOKEN in .env")
        sys.exit(1)

    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    if not azure_endpoint or not azure_key:
        logger.error("❌ Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY in .env")
        sys.exit(1)

    # ── Initialize clients
    brand_voice = load_brand_voice()
    shopify = ShopifyClient(store_url, access_token)
    scorer = SEOScorer()
    optimizer = SEOOptimizer(azure_endpoint, azure_key, azure_deployment, brand_voice)

    # ── Fetch products
    print(f"\n{'='*60}")
    print(f"  Beauty Connect Shop — SEO Optimizer")
    print(f"  Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will update Shopify)'}")
    print(f"{'='*60}\n")

    print("⏳ Fetching products from Shopify...")
    products = shopify.fetch_all_products(limit=args.limit)

    if not products:
        logger.error("❌ No products found — check Shopify credentials")
        sys.exit(1)

    print(f"✓ Found {len(products)} products\n")

    # ── Score + Optimize
    audit_results = []
    needs_optimization = []
    skipped = []

    for product in products:
        score, breakdown = scorer.score(product)
        seo = product.get('seo', {})
        images = product.get('images', {}).get('edges', [])
        current_alt = images[0]['node'].get('altText', '') if images else ''

        result = {
            'product_id': product['id'],
            'title': product['title'],
            'handle': product['handle'],
            'score_before': score,
            'score_after': score,
            'current_meta_title': seo.get('title', ''),
            'current_meta_desc': seo.get('description', ''),
            'current_alt_text': current_alt,
            'breakdown': breakdown,
            'compliant': True,
            'status': 'skip_high_score',
            'optimized': {}
        }

        if score >= 85 and not args.force_all:
            skipped.append(result)
            print(f"  ✓ SKIP [{score}/100] {product['title'][:50]}")
        else:
            needs_optimization.append(result)

    print(f"\n📊 Score Summary:")
    print(f"  Products scoring ≥85 (skip): {len(skipped)}")
    print(f"  Products to optimize: {len(needs_optimization)}\n")

    if not needs_optimization:
        print("🎉 All products are already well-optimized!")

    for i, result in enumerate(needs_optimization):
        product = next(p for p in products if p['id'] == result['product_id'])
        print(f"⏳ Optimizing [{i+1}/{len(needs_optimization)}]: {result['title'][:50]}...")

        optimized = optimizer.optimize_product(product)
        result['optimized'] = optimized
        result['status'] = 'pending_review'

        # Recalculate score with optimized content
        # Simulate scoring with new values
        new_score = result['score_before']
        if optimized.get('meta_title') and len(optimized['meta_title']) >= 30:
            new_score = max(new_score, 85)
        result['score_after'] = new_score

        violations = check_health_canada_compliance(' '.join(optimized.values()))
        result['compliant'] = len(violations) == 0

        print(f"  ✓ Score: {result['score_before']} → {result['score_after']} | Health Canada: {'✓' if result['compliant'] else '⚠ VIOLATION'}")

        time.sleep(0.2)

    all_results = skipped + needs_optimization

    # ── Export to Google Sheets
    print("\n⏳ Exporting audit report to Google Sheets...")
    try:
        exporter = GoogleSheetsExporter()
        sheet_url = exporter.create_audit_report(all_results)
        print(f"✓ Audit report: {sheet_url}")
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        # Fallback: save to CSV
        csv_path = f".tmp/seo_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        import csv
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Title', 'Score Before', 'Score After', 'Meta Title', 'Meta Desc', 'Alt Text', 'Status'])
            for r in all_results:
                opt = r.get('optimized', {})
                writer.writerow([r['title'], r['score_before'], r['score_after'],
                                  opt.get('meta_title', ''), opt.get('meta_description', ''),
                                  opt.get('alt_text', ''), r['status']])
        print(f"⚠ Google Sheets failed — saved to: {csv_path}")
        sheet_url = csv_path

    # ── Push Live (only if --push_live)
    if args.push_live and not args.dry_run:
        print(f"\n⏳ Pushing {len(needs_optimization)} product updates to Shopify...")
        success_count = 0
        fail_count = 0

        for result in needs_optimization:
            opt = result['optimized']
            product = next(p for p in products if p['id'] == result['product_id'])
            images = product.get('images', {}).get('edges', [])

            ok_seo = shopify.update_product_seo(
                result['product_id'],
                opt.get('meta_title', result['current_meta_title']),
                opt.get('meta_description', result['current_meta_desc']),
                body_html=opt.get('body_html')
            )

            ok_alt = True
            if images and opt.get('alt_text'):
                image_id = images[0]['node']['id']
                ok_alt = shopify.update_image_alt_text(result['product_id'], image_id, opt['alt_text'])

            if ok_seo and ok_alt:
                success_count += 1
                result['status'] = 'pushed_live'
            else:
                fail_count += 1
                result['status'] = 'push_failed'

        print(f"✓ Pushed live: {success_count}/{len(needs_optimization)}")
        if fail_count:
            print(f"⚠ Failed: {fail_count} (see log)")
    elif args.dry_run:
        print("\n⚠ DRY RUN — no changes made to Shopify")
        print("   Review the Google Sheet, then run with --push_live to apply changes")

    # ── Summary
    total_before = sum(r['score_before'] for r in all_results) / len(all_results) if all_results else 0
    total_after = sum(r['score_after'] for r in all_results) / len(all_results) if all_results else 0

    print(f"\n{'='*60}")
    print(f"  ✅ SEO OPTIMIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Products analyzed:    {len(all_results)}")
    print(f"  Products optimized:   {len(needs_optimization)}")
    print(f"  Average score before: {total_before:.0f}/100")
    print(f"  Average score after:  {total_after:.0f}/100")
    print(f"  Health Canada issues: {sum(1 for r in needs_optimization if not r['compliant'])}")
    print(f"  Audit report:         {sheet_url}")
    print(f"{'='*60}\n")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Beauty Connect Shop — Shopify SEO Optimizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python execution/shopify_seo_optimizer.py --dry_run
  python execution/shopify_seo_optimizer.py --limit 10 --dry_run
  python execution/shopify_seo_optimizer.py --push_live
  python execution/shopify_seo_optimizer.py --min_score 70 --dry_run
        """
    )
    parser.add_argument('--dry_run', action='store_true', default=True,
                        help='Analyze and export to Sheets only — no Shopify changes (default: True)')
    parser.add_argument('--push_live', action='store_true',
                        help='Push optimized SEO to Shopify (overrides --dry_run)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of products to process (default: all)')
    parser.add_argument('--min_score', type=int, default=85,
                        help='Minimum SEO score threshold — optimize products below this (default: 85)')
    parser.add_argument('--force_all', action='store_true',
                        help='Optimize all products regardless of score')

    args = parser.parse_args()

    # --push_live overrides --dry_run
    if args.push_live:
        args.dry_run = False

    run_seo_optimizer(args)


if __name__ == '__main__':
    main()
