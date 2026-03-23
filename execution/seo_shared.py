#!/usr/bin/env python3
"""
SEO Shared Utilities — Beauty Connect Shop
DOE Architecture: Shared execution module

Provides reusable classes and functions for all SEO scripts:
- ShopifyClient: GraphQL API client with rate limiting & retry
- GoogleSheetsExporter: Create & populate Google Sheets reports
- GSCClient: Google Search Console data retrieval
- Health Canada compliance checker
- K-Beauty keyword list
- Common helpers

Usage:
    from seo_shared import ShopifyClient, GoogleSheetsExporter, GSCClient
    from seo_shared import check_health_canada_compliance, K_BEAUTY_KEYWORDS
"""

import os
import sys
import json
import logging
import re
import time
import pickle
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
os.makedirs('.tmp', exist_ok=True)

logger = logging.getLogger('seo_shared')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('.tmp/seo_shared.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

# ─── Constants ────────────────────────────────────────────────────────────────
REQUESTS_TIMEOUT = 30
SHOPIFY_API_VERSION = "2024-10"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']


# ─── Health Canada Compliance ─────────────────────────────────────────────────
# ASC "Guidelines for Non-therapeutic Advertising and Labelling Claims"
# Column II = therapeutic/health claims requiring DIN/NPN pre-market authorization
# Any match = FORBIDDEN for cosmetic products without Health Canada approval

HEALTH_CANADA_FORBIDDEN = [
    # SKIN CARE / MAKEUP
    r'\bheals?\b(?!\s+dry\s+skin)',
    r'\brepairs?\s+(?:damaged\s+)?(?:the\s+)?skin\b',
    r'\brepairs?\s+(?:the\s+)?skin\'?s?\s+moisture\s+barrier\b',
    r'\btreats?\s+(?:acne|rosacea|eczema|dermatitis|psoriasis|infection|burns?|cellulite)',
    r'\bcures?\b',
    r'\bprevents?\s+(?:disease|infection|acne|breakout)',
    r'\bprevents?\s+(?:new\s+)?(?:spots?|age\s+spots?)\s+(?:from\s+)?appear',
    r'\bprevents?\s+(?:the\s+)?(?:onset|emergence)\s+of\s+age\s+spots?\b',
    r'\bprevents?\s+photoaging\b',
    r'\bskin\s+de-?pigmentation\b',
    r'\beliminates?\s+age\s+spots?\b',
    r'\banti-inflammatory\b',
    r'\bantibacterial\b',
    r'\bantifungal\b',
    r'\bantiseptic\b',
    r'\bdisinfectant\b',
    r'\bsanitizer\b',
    r'\bfungicid\w*\b',
    r'\bgermicid\w*\b',
    r'\bprescription[\s.-]?strength\b',
    r'\bmedical[\s.-]?grade\b',
    r'\bclinical[\s.-]?(?:strength|effect|action)\b',
    r'\bclinical\s+protection\b(?!\s+\()',
    r'\btherapeutic[\s.-]?(?:strength|effect|action)\b',
    r'\b(?:Rx|Pr)\b',
    r'\bstimulates?\s+(?:cell|cellular|hair|eyelash|collagen|genital)',
    r'\bprevents?\s+hair\s+loss\b',
    r'\bprevents?\s+(?:hair\s+)?thinning\b',
    r'\btreats?\s+alopecia\b',
    r'\binhibits?\s+hair\s+growth\b',
    r'\bstops?\s+hair\s+growth\b',
    r'\bstimulates?\s+(?:hair|eyelash)\s+growth\b',
    r'\bspf\s*\d*\b',
    r'\bsunscreen\b',
    r'\bsunburn\s+protectant\b',
    r'\b(?:uva|uvb|uv)\s+protect\w*\b',
    r'\bprotects?\s+sun\s+damaged\s+skin\b',
    r'\bclears?\s+(?:skin\s+)?(?:acne|blemish)',
    r'\banti-?blemish\b',
    r'\bheals?\s+(?:acne|pimples?|blemish)',
    r'\bstops?\s+(?:acne|pimples?|breakout)',
    r'\bfights?\s+(?:bacteria|germs|pathogens)\b',
    r'\bkills?\s+(?:bacteria|germs|pathogens)\b(?!.*odou?r)',
    r'\baction\s+(?:at\s+)?(?:a\s+)?cellular\s+level\b',
    r'\breference\s+to\s+(?:action\s+on\s+)?(?:tissue|body|cells)\b',
    r'\bremoves?\s+(?:permanent\s+)?scars?\b',
    r'\breduces?\s+(?:scars?|redness)\s+due\s+to\s+(?:rosacea|sunburn)',
    r'\brosacea\b',
    r'\breduces?\s+(?:cellulite|swelling|edema)\b',
    r'\bremoves?\s+cellulite\b',
    r'\bweight\s+(?:management|loss)\b',
    r'\bfat\s+loss\b',
    r'\blipodraining\b',
    r'\bcleans?\s+wounds?\b',
    r'\bnumbs?\b',
    r'\bdesensitiz\w*\b',
    r'\bmedical\b.*\bprocedure\b',
    r'\bsurgical\b.*\bprocedure\b',
    # NAIL CARE
    r'\bpromotes?\s+nail\s+growth\b(?!.*physical\s+damage)',
    # HAIR CARE
    r'\banti-?dandruff\b',
    r'\bcontrols?\s+dandruff\b',
    r'\beliminates?\s+dandruff\b',
    r'\bprevents?\s+dandruff\b',
    r'\beffect\s+on\s+(?:living\s+)?(?:tissue|hair\s+follicle)',
    r'\bstimulates?\s+eyelash\s+growth\b',
    # ORAL CARE
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
    # ANTIPERSPIRANTS
    r'\bhyperhidrosis\b',
    r'\bexcessive\s+perspiration\b',
    r'\bproblem\s+perspiration\b',
    r'\bhormonal\b.*\bperspiration\b',
    r'\bendocrine\b.*\bperspiration\b',
    # INTIMATE PRODUCTS
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
    # OTHER CLAIMS (INGREDIENTS / ENDORSEMENTS)
    r'\bactive\s+ingredient\b',
    r'\bmedicinal\s+ingredient\b',
    r'\btherapeutic\s+ingredient\b',
    r'\beffective\s+ingredient\b',
    r'\bfree\s+radical\s+scaveng\w*\b',
    r'\brepairing\s+damage\b',
    r'\baction\s+at\s+(?:a\s+)?cellular\s+level\b',
    r'\bdose\s+units?\b',
    r'\b\d+\s*IU\b',
    r'\bpromotes?\s+health\b',
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


def check_health_canada_compliance(text: str) -> List[str]:
    """
    Validate text against Health Canada therapeutic claim restrictions.
    Returns list of violation patterns found (empty = compliant).
    """
    violations = []
    text_lower = text.lower()
    for pattern in HEALTH_CANADA_FORBIDDEN:
        if re.search(pattern, text_lower, re.IGNORECASE):
            violations.append(pattern)
    return violations


def load_brand_voice() -> str:
    """Load brand voice guidelines from template file."""
    paths = [
        os.path.join(BASE_DIR, 'templates', 'brand_voice.md'),
        os.path.join(BASE_DIR, 'directives', 'brand', 'brand_voice.md'),
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
    logger.warning("⚠ brand_voice.md not found — using default guidelines")
    return "Professional Korean skincare brand for estheticians in Canada. Warm, educational tone. Health Canada compliant."


def load_brand_config() -> Dict:
    """Load brand configuration from JSON."""
    config_path = os.path.join(BASE_DIR, 'templates', 'brand_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    logger.warning("⚠ brand_config.json not found — using defaults")
    return {
        "brand_name": "Beauty Connect Shop",
        "store_url": "https://beautyconnectshop.com",
        "social": {}
    }


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', ' ', text).strip()


def word_count(text: str) -> int:
    """Count words in text (strips HTML first)."""
    clean = strip_html(text)
    return len(clean.split()) if clean else 0


# ─── Shopify Client ───────────────────────────────────────────────────────────

class ShopifyClient:
    """Handles Shopify Admin GraphQL API calls with rate limiting & retry."""

    def __init__(self, store_url: str = None, access_token: str = None):
        self.store_url = (store_url or os.getenv('SHOPIFY_STORE_URL', '')).rstrip('/')
        self.access_token = access_token or os.getenv('SHOPIFY_ADMIN_API_TOKEN', '')

        if not self.store_url or not self.access_token:
            raise ValueError("❌ Missing SHOPIFY_STORE_URL or SHOPIFY_ADMIN_API_TOKEN")

        self.base_url = f"https://{self.store_url}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        self.rest_base = f"https://{self.store_url}/admin/api/{SHOPIFY_API_VERSION}"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
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

    def _rest_get(self, endpoint: str) -> Dict:
        """Execute a REST API GET request."""
        url = f"{self.rest_base}/{endpoint}"
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, timeout=REQUESTS_TIMEOUT)
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"REST GET failed: {e}")
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
                vendor
                images(first: 5) {
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

    def fetch_all_collections(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all collections with SEO fields."""
        query = """
        query FetchCollections($cursor: String) {
          collections(first: 50, after: $cursor) {
            edges {
              node {
                id
                title
                handle
                descriptionHtml
                productsCount {
                  count
                }
                image {
                  url
                  altText
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
        collections = []
        cursor = None

        while True:
            variables = {'cursor': cursor} if cursor else {}
            data = self._graphql(query, variables)

            if not data or 'collections' not in data:
                break

            edges = data['collections']['edges']
            for edge in edges:
                collections.append(edge['node'])
                if limit and len(collections) >= limit:
                    return collections

            page_info = data['collections']['pageInfo']
            if not page_info['hasNextPage']:
                break

            cursor = page_info['endCursor']
            time.sleep(self._delay)

        logger.info(f"✓ Fetched {len(collections)} total collections")
        return collections

    def fetch_all_blog_articles(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all blog articles with SEO fields."""
        query = """
        query FetchArticles($cursor: String) {
          articles(first: 50, after: $cursor) {
            edges {
              node {
                id
                title
                handle
                body
                summary
                tags
                publishedAt
                blog {
                  title
                  handle
                }
                seo {
                  title
                  description
                }
                image {
                  url
                  altText
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
        articles = []
        cursor = None

        while True:
            variables = {'cursor': cursor} if cursor else {}
            data = self._graphql(query, variables)

            if not data or 'articles' not in data:
                break

            edges = data['articles']['edges']
            for edge in edges:
                articles.append(edge['node'])
                if limit and len(articles) >= limit:
                    return articles

            page_info = data['articles']['pageInfo']
            if not page_info['hasNextPage']:
                break

            cursor = page_info['endCursor']
            time.sleep(self._delay)

        logger.info(f"✓ Fetched {len(articles)} total articles")
        return articles

    def fetch_shop_info(self) -> Dict:
        """Fetch basic shop information."""
        query = """
        {
          shop {
            name
            url
            primaryDomain {
              url
              host
            }
            description
          }
        }
        """
        data = self._graphql(query)
        return data.get('shop', {})

    def update_product_seo(self, product_id: str, seo_title: str, seo_description: str, body_html: str = None) -> bool:
        """Update product SEO title, description, and optionally body HTML."""
        mutation = """
        mutation UpdateProductSEO($input: ProductInput!) {
          productUpdate(input: $input) {
            product { id }
            userErrors { field message }
          }
        }
        """
        input_data = {
            'id': product_id,
            'seo': {'title': seo_title, 'description': seo_description}
        }
        if body_html:
            input_data['descriptionHtml'] = body_html

        data = self._graphql(mutation, {'input': input_data})
        errors = data.get('productUpdate', {}).get('userErrors', [])
        if errors:
            logger.error(f"Failed to update {product_id}: {errors}")
            return False
        time.sleep(self._delay)
        return True

    def update_collection_seo(self, collection_id: str, seo_title: str, seo_description: str, description_html: str = None) -> bool:
        """Update collection SEO fields."""
        mutation = """
        mutation UpdateCollectionSEO($input: CollectionInput!) {
          collectionUpdate(input: $input) {
            collection { id }
            userErrors { field message }
          }
        }
        """
        input_data = {
            'id': collection_id,
            'seo': {'title': seo_title, 'description': seo_description}
        }
        if description_html:
            input_data['descriptionHtml'] = description_html

        data = self._graphql(mutation, {'input': input_data})
        errors = data.get('collectionUpdate', {}).get('userErrors', [])
        if errors:
            logger.error(f"Failed to update collection {collection_id}: {errors}")
            return False
        time.sleep(self._delay)
        return True

    def update_image_alt_text(self, product_id: str, image_id: str, alt_text: str) -> bool:
        """Update image alt text via REST API."""
        product_num = product_id.split('/')[-1]
        image_num = image_id.split('/')[-1]
        url = f"{self.rest_base}/products/{product_num}/images/{image_num}.json"
        payload = {'image': {'id': int(image_num), 'alt': alt_text}}

        for attempt in range(3):
            try:
                response = requests.put(url, headers=self.headers, json=payload, timeout=REQUESTS_TIMEOUT)
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


# ─── Google Sheets Exporter ───────────────────────────────────────────────────

class GoogleSheetsExporter:
    """Create & populate Google Sheets reports."""

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        token_path = os.path.join(BASE_DIR, 'token.json')
        creds_path = os.path.join(BASE_DIR, 'credentials.json')

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, GOOGLE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        return build('sheets', 'v4', credentials=creds)

    def create_sheet(self, title: str, headers: List[str], rows: List[List]) -> str:
        """Create a Google Sheet with headers and data. Returns sheet URL."""
        spreadsheet = self.service.spreadsheets().create(
            body={'properties': {'title': title}},
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        sheet_id = spreadsheet['spreadsheetId']
        sheet_url = spreadsheet['spreadsheetUrl']

        all_rows = [headers] + rows
        self.service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body={'values': all_rows}
        ).execute()

        # Bold headers + freeze row 1
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                'requests': [
                    {
                        'repeatCell': {
                            'range': {'sheetId': 0, 'startRowIndex': 0, 'endRowIndex': 1},
                            'cell': {
                                'userEnteredFormat': {
                                    'textFormat': {'bold': True},
                                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.95}
                                }
                            },
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

    def add_sheet_tab(self, spreadsheet_id: str, tab_name: str, headers: List[str], rows: List[List]):
        """Add a new tab to an existing spreadsheet."""
        # Create the new sheet tab
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                'requests': [{
                    'addSheet': {'properties': {'title': tab_name}}
                }]
            }
        ).execute()

        # Write data
        all_rows = [headers] + rows
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{tab_name}!A1',
            valueInputOption='RAW',
            body={'values': all_rows}
        ).execute()


# ─── GSC Client ───────────────────────────────────────────────────────────────

class GSCClient:
    """Google Search Console API client."""

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_path = os.path.join(BASE_DIR, 'token_gsc.pickle')
        creds_path = os.path.join(BASE_DIR, 'credentials.json')

        creds = None
        if os.path.exists(token_path):
            with open(token_path, 'rb') as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, GSC_SCOPES)
                creds = flow.run_local_server(port=8080)
            with open(token_path, 'wb') as f:
                pickle.dump(creds, f)

        return build('searchconsole', 'v1', credentials=creds)

    def query(self, site_url: str, start_date: str = None, end_date: str = None,
              dimensions: List[str] = None, row_limit: int = 5000,
              dimension_filters: List[Dict] = None) -> List[Dict]:
        """Query search analytics. Returns list of row dicts."""
        if not end_date:
            end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not dimensions:
            dimensions = ['query', 'page']

        request_body = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': dimensions,
            'rowLimit': row_limit,
        }
        if dimension_filters:
            request_body['dimensionFilterGroups'] = [{
                'filters': dimension_filters
            }]

        response = self.service.searchanalytics().query(
            siteUrl=site_url,
            body=request_body
        ).execute()

        return response.get('rows', [])

    def list_sites(self) -> List[Dict]:
        """List all verified sites."""
        result = self.service.sites().list().execute()
        return result.get('siteEntry', [])


# ─── CSV Fallback ─────────────────────────────────────────────────────────────

def export_to_csv(filename: str, headers: List[str], rows: List[List]) -> str:
    """Export data to CSV as fallback when Google Sheets fails."""
    import csv
    os.makedirs('.tmp', exist_ok=True)
    filepath = f".tmp/{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    logger.info(f"✓ CSV exported: {filepath}")
    return filepath
