#!/usr/bin/env python3
"""
Ad Library Scraper + AI Image Spinner - DO Architecture Execution Script

Scrapes Facebook Ad Library via Apify, analyzes ads with Azure OpenAI GPT-4o vision,
generates remixed variants using Flux Kontext Pro (fal.ai), organizes in Google Drive,
and logs everything to a Google Sheet.

Directive: directives/scrape_ad_library.md
"""

import os
import sys
import json
import time
import base64
import logging
import argparse
from typing import Dict, List, Optional
from datetime import datetime

# Third-party imports
try:
    import requests
    from apify_client import ApifyClient
    from openai import AzureOpenAI
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install apify-client requests openai google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv")
    sys.exit(1)

load_dotenv()

# Logging
os.makedirs('.tmp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('.tmp/execution.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

SHEET_HEADERS = [
    "Timestamp", "Ad Archive ID", "Page ID", "Original Image URL",
    "Page Name", "Ad Body", "Date Scraped", "Spun Prompt",
    "Asset Folder", "Source Folder", "Spun Folder", "Direct Spun Image Link"
]


class AdLibrarySpinner:
    """Scrapes Facebook ads and generates AI-remixed variants."""

    def __init__(self, args):
        self.keyword = args.keyword
        self.direct_url = args.url
        self.max_ads = args.max_ads
        self.num_variants = args.variants
        self.style = args.style
        self.folder_name = args.folder_name
        self.test_mode = args.test
        self.folder_id = args.folder_id
        self.sheet_id = args.sheet_id

        # Load credentials (load-use-delete pattern)
        apify_token = os.getenv("APIFY_API_KEY")
        if not apify_token:
            raise ValueError("APIFY_API_KEY not found in .env")
        self.apify_client = ApifyClient(apify_token)
        del apify_token

        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        if not azure_endpoint or not azure_key:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY required in .env")
        self.openai_client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version="2024-02-15-preview"
        )
        del azure_key

        self.fal_key = os.getenv("FAL_KEY")
        if not self.fal_key:
            raise ValueError("FAL_KEY not found in .env")

        # Google services (initialized in setup)
        self.sheets_service = None
        self.drive_service = None

    # ─── Google Auth ──────────────────────────────────────────────────

    def _authenticate_google(self):
        """Authenticate with Google OAuth2 (reuse existing token.json)."""
        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"OAuth token refresh failed: {e}")
                    creds = None

            if not creds:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError("credentials.json not found")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Google auth OK")

    # ─── Google Drive Helpers ─────────────────────────────────────────

    def _create_drive_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Create a Google Drive folder, return its ID."""
        meta = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            meta['parents'] = [parent_id]

        folder = self.drive_service.files().create(
            body=meta, fields='id'
        ).execute()
        return folder['id']

    def _upload_to_drive(self, filename: str, data: bytes, mimetype: str, folder_id: str) -> Dict:
        """Upload binary data to Drive, make public, return file info."""
        media = MediaInMemoryUpload(data, mimetype=mimetype)
        file_meta = {'name': filename, 'parents': [folder_id]}

        uploaded = self.drive_service.files().create(
            body=file_meta, media_body=media, fields='id,webViewLink'
        ).execute()

        # Make publicly accessible
        self.drive_service.permissions().create(
            fileId=uploaded['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return uploaded

    # ─── Google Sheets Helpers ────────────────────────────────────────

    def _create_sheet(self, title: str) -> str:
        """Create Google Sheet with headers, return spreadsheet ID."""
        spreadsheet = self.sheets_service.spreadsheets().create(
            body={'properties': {'title': title}},
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()

        sheet_id = spreadsheet['spreadsheetId']
        sheet_url = spreadsheet['spreadsheetUrl']
        logger.info(f"Created sheet: {sheet_url}")

        # Write headers
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={'values': [SHEET_HEADERS]}
        ).execute()

        # Format: bold blue header + freeze row 1
        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': [
                {
                    "repeatCell": {
                        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)"
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount"
                    }
                }
            ]}
        ).execute()

        # Make sheet public
        self.drive_service.permissions().create(
            fileId=sheet_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return sheet_id

    def _get_existing_ad_ids(self) -> set:
        """Read sheet and return set of already-processed ad archive IDs."""
        if not self.sheet_id:
            return set()

        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id, range="B:B"
            ).execute()
            values = result.get('values', [])
            # Skip header row
            return {row[0] for row in values[1:] if row}
        except Exception as e:
            logger.warning(f"Could not read existing ads: {e}")
            return set()

    def _append_row(self, row: List[str]):
        """Append a single row to the sheet."""
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range="A:L",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={'values': [row]}
        ).execute()

    # ─── Apify: Scrape Facebook Ad Library ────────────────────────────

    def scrape_ads(self) -> List[Dict]:
        """Scrape ads from Facebook Ad Library via Apify."""
        if self.direct_url:
            url = self.direct_url
            logger.info(f"Scraping Facebook Ad Library from URL (max {self.max_ads})...")
        else:
            url = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&q={self.keyword}&search_type=keyword_unordered&media_type=all"
            logger.info(f"Scraping Facebook Ad Library for '{self.keyword}' (max {self.max_ads})...")

        run_input = {
            "urls": [{"url": url}],
            "count": self.max_ads,
            "scrapeAdDetails": True
        }

        try:
            run = self.apify_client.actor("curious_coder~facebook-ads-library-scraper").call(
                run_input=run_input
            )
            items = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items
            logger.info(f"Scraped {len(items)} ads from Ad Library")
            return items
        except Exception as e:
            logger.error(f"Apify scrape failed: {e}")
            # Retry once
            logger.info("Retrying Apify scrape...")
            try:
                run = self.apify_client.actor("curious_coder~facebook-ads-library-scraper").call(
                    run_input=run_input
                )
                items = self.apify_client.dataset(run["defaultDatasetId"]).list_items().items
                logger.info(f"Retry succeeded: {len(items)} ads")
                return items
            except Exception as e2:
                logger.error(f"Retry also failed: {e2}")
                return []

    # ─── Filter: Static Image Ads Only ────────────────────────────────

    def _extract_image_url(self, ad: Dict) -> Optional[str]:
        """Extract the first valid original_image_url from an ad's nested structure."""
        # Check snapshot.cards[] for original_image_url (most common)
        snapshot = ad.get('snapshot', {})
        cards = snapshot.get('cards', [])
        for card in cards:
            img_url = card.get('original_image_url')
            if img_url and img_url.strip():
                return img_url.strip()

        # Check snapshot.images[] as fallback
        images = snapshot.get('images', [])
        for img in images:
            if isinstance(img, dict):
                img_url = img.get('original_image_url') or img.get('url')
                if img_url and img_url.strip():
                    return img_url.strip()
            elif isinstance(img, str) and img.strip():
                return img.strip()

        return None

    def filter_image_ads(self, ads: List[Dict]) -> List[Dict]:
        """Keep only ads with a valid original_image_url (from snapshot.cards or snapshot.images)."""
        before = len(ads)
        filtered = []
        for ad in ads:
            img_url = self._extract_image_url(ad)
            if img_url:
                # Store extracted URL at top level for easy access later
                ad['_extracted_image_url'] = img_url
                filtered.append(ad)
        logger.info(f"Filtered {before} -> {len(filtered)} static image ads")
        return filtered

    # ─── Azure OpenAI: Describe Image ─────────────────────────────────

    def describe_image(self, image_bytes: bytes) -> str:
        """Use GPT-4o vision to describe an ad image in detail."""
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        data_uri = f"data:image/png;base64,{b64}"

        for attempt in range(3):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this ad image in extreme detail. Include: colors, layout, any text on the image, visual style, people or objects, mood, composition, fonts, and overall design approach. Leave nothing out."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_uri}
                            }
                        ]
                    }],
                    max_tokens=1000
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if '429' in str(e) and attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Vision API failed: {e}")
                return ""

    # ─── Azure OpenAI: Generate Variant Prompts ───────────────────────

    def generate_variant_prompts(self, description: str) -> List[str]:
        """Generate N different spin directions based on image description and style."""
        for attempt in range(3):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are an expert creative director for paid advertising.
Generate exactly {self.num_variants} different image editing prompts. Each prompt should be a detailed instruction
for how to remake the ad image differently while keeping the core message.

Return a JSON object with a single key "variants" containing an array of {self.num_variants} strings.
Each string is a complete image editing instruction.

Example format:
{{"variants": ["Change the background to...", "Redesign using...", "Transform the layout to..."]}}"""
                        },
                        {
                            "role": "user",
                            "content": f"Style direction: {self.style}\n\nOriginal ad description:\n{description}"
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.8,
                    max_tokens=1500
                )
                result = json.loads(response.choices[0].message.content)
                variants = result.get("variants", [])
                if variants:
                    logger.info(f"Generated {len(variants)} variant prompts")
                    return variants[:self.num_variants]
                logger.warning("Empty variants returned, retrying...")
            except Exception as e:
                if '429' in str(e) and attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Variant generation failed: {e}")

        return []

    # ─── fal.ai: Flux Kontext Pro Image Editing ───────────────────────

    def generate_spun_image(self, image_bytes: bytes, prompt: str) -> Optional[bytes]:
        """
        Generate a spun ad image using Flux Kontext Pro via fal.ai queue API.
        Returns the generated image bytes, or None on failure.
        """
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        data_uri = f"data:image/png;base64,{b64}"

        headers = {
            "Authorization": f"Key {self.fal_key}",
            "Content-Type": "application/json"
        }

        # Submit to queue
        try:
            submit_resp = requests.post(
                "https://queue.fal.run/fal-ai/flux-pro/kontext",
                headers=headers,
                json={
                    "prompt": prompt,
                    "image_url": data_uri,
                    "image_size": "square",
                    "num_inference_steps": 50,
                    "output_format": "png",
                    "guidance_scale": 3.5
                },
                timeout=30
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            request_id = submit_data.get("request_id")
            # Use URLs from response (status path differs from submit path)
            status_url = submit_data.get("status_url", f"https://queue.fal.run/fal-ai/flux-pro/requests/{request_id}/status")
            response_url = submit_data.get("response_url", f"https://queue.fal.run/fal-ai/flux-pro/requests/{request_id}")
            if not request_id:
                logger.error(f"fal.ai submit returned no request_id: {submit_resp.text}")
                return None
        except Exception as e:
            logger.error(f"fal.ai submit failed: {e}")
            return None

        # Poll for completion (max 5 minutes)
        logger.info(f"  fal.ai request {request_id[:8]}... waiting for result")
        for attempt in range(60):
            try:
                status_resp = requests.get(
                    status_url,
                    headers={"Authorization": f"Key {self.fal_key}"},
                    timeout=15
                )
                status_data = status_resp.json()
                status = status_data.get("status")

                if status == "COMPLETED":
                    break
                elif status in ("FAILED", "CANCELLED"):
                    logger.error(f"fal.ai request {status}: {status_data}")
                    return None

                time.sleep(5)
            except Exception as e:
                logger.warning(f"Status poll error: {e}")
                time.sleep(5)
        else:
            logger.error("fal.ai request timed out (5 min)")
            return None

        # Fetch result
        try:
            result_resp = requests.get(
                response_url,
                headers={"Authorization": f"Key {self.fal_key}"},
                timeout=30
            )
            result_resp.raise_for_status()
            result_data = result_resp.json()

            # Check for error response
            if "detail" in result_data and isinstance(result_data["detail"], list):
                logger.error(f"fal.ai error: {result_data['detail']}")
                return None

            images = result_data.get("images", [])
            if not images:
                logger.error(f"fal.ai returned no images: {json.dumps(result_data)[:300]}")
                return None

            image_url = images[0].get("url")
            if not image_url:
                logger.error("fal.ai image has no URL")
                return None

            # Download the generated image
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            return img_resp.content

        except Exception as e:
            logger.error(f"fal.ai result fetch failed: {e}")
            return None

    # ─── Main Flow ────────────────────────────────────────────────────

    def run(self):
        """Execute the full ad library scrape + spin flow."""
        start_time = time.time()

        # Step 1: Google auth
        logger.info("Authenticating with Google...")
        self._authenticate_google()

        # Step 2: One-time setup (idempotent)
        if not self.folder_id:
            logger.info(f"Creating master Drive folder: {self.folder_name}")
            self.folder_id = self._create_drive_folder(self.folder_name)
            logger.info(f"Master folder ID: {self.folder_id} (save for reuse with --folder_id)")

        if not self.sheet_id:
            logger.info(f"Creating Google Sheet: {self.folder_name}")
            self.sheet_id = self._create_sheet(self.folder_name)
            # Move sheet into master folder
            self.drive_service.files().update(
                fileId=self.sheet_id,
                addParents=self.folder_id,
                fields='id,parents'
            ).execute()
            logger.info(f"Sheet ID: {self.sheet_id} (save for reuse with --sheet_id)")

        # Step 3: Scrape ads
        ads = self.scrape_ads()
        if not ads:
            logger.error("No ads scraped. Aborting.")
            return

        # Step 4: Filter to static image ads
        ads = self.filter_image_ads(ads)
        if not ads:
            logger.error("No static image ads found after filtering. Aborting.")
            return

        # Step 5: Test limit
        if self.test_mode:
            ads = ads[:2]
            logger.info(f"Test mode: processing {len(ads)} ads")

        # Step 6: Deduplication
        existing_ids = self._get_existing_ad_ids()
        if existing_ids:
            before = len(ads)
            ads = [ad for ad in ads if str(ad.get('ad_archive_id', '')) not in existing_ids]
            skipped = before - len(ads)
            if skipped:
                logger.info(f"Skipping {skipped} already-processed ads")

        if not ads:
            logger.info("All ads already processed. Nothing to do.")
            return

        logger.info(f"Processing {len(ads)} ads x {self.num_variants} variants = {len(ads) * self.num_variants} spun images")

        # Step 7: Process each ad
        total_variants = 0
        failed_ads = 0

        for i, ad in enumerate(ads, 1):
            ad_archive_id = str(ad.get('ad_archive_id', f'unknown_{i}'))
            snapshot = ad.get('snapshot', {})
            page_name = ad.get('page_name') or snapshot.get('page_name', 'Unknown')
            page_id = str(ad.get('page_id') or snapshot.get('page_id', ''))
            # Body text can be nested in snapshot.body.text or snapshot.cards[0].body
            body_obj = snapshot.get('body', {})
            ad_body = body_obj.get('text', '') if isinstance(body_obj, dict) else str(body_obj)
            if not ad_body or ad_body.startswith('{{'):
                # Try getting body from first card
                cards = snapshot.get('cards', [])
                if cards:
                    ad_body = cards[0].get('body', '')
            original_image_url = ad.get('_extracted_image_url', '')

            logger.info(f"\nAd {i}/{len(ads)}: {page_name} (ID: {ad_archive_id})")

            # A. Download original image
            try:
                resp = requests.get(original_image_url, timeout=30)
                resp.raise_for_status()
                image_bytes = resp.content
                logger.info(f"  Downloaded original image ({len(image_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"  Image download failed: {e} - skipping ad")
                failed_ads += 1
                continue

            # B. Create Drive folder structure
            try:
                parent_folder_id = self._create_drive_folder(ad_archive_id, self.folder_id)
                source_folder_id = self._create_drive_folder("1 Source Assets", parent_folder_id)
                spun_folder_id = self._create_drive_folder("2 Spun Assets", parent_folder_id)
                logger.info("  Drive folders created")
            except Exception as e:
                logger.warning(f"  Drive folder creation failed: {e} - skipping ad")
                failed_ads += 1
                continue

            # C. Upload original to Source Assets
            try:
                # Detect mimetype from URL or default to png
                mimetype = 'image/png'
                if '.jpg' in original_image_url.lower() or '.jpeg' in original_image_url.lower():
                    mimetype = 'image/jpeg'
                elif '.webp' in original_image_url.lower():
                    mimetype = 'image/webp'

                ext = mimetype.split('/')[-1]
                if ext == 'jpeg':
                    ext = 'jpg'

                self._upload_to_drive(
                    f"{ad_archive_id}.{ext}", image_bytes, mimetype, source_folder_id
                )
                logger.info("  Original uploaded to Drive")
            except Exception as e:
                logger.warning(f"  Drive upload failed: {e} - continuing anyway")

            # D. Describe image via GPT-4o vision
            logger.info("  Analyzing image with GPT-4o vision...")
            description = self.describe_image(image_bytes)
            if not description:
                logger.warning("  Vision analysis failed - skipping ad")
                failed_ads += 1
                continue
            logger.info(f"  Image described ({len(description)} chars)")

            # E. Generate variant prompts
            logger.info(f"  Generating {self.num_variants} variant prompts...")
            variants = self.generate_variant_prompts(description)
            if not variants:
                logger.warning("  Variant generation failed - skipping ad")
                failed_ads += 1
                continue

            # F. For each variant: generate spun image + upload + log
            for v_idx, variant_prompt in enumerate(variants, 1):
                logger.info(f"  Variant {v_idx}/{len(variants)}: generating spun image...")

                spun_bytes = self.generate_spun_image(image_bytes, variant_prompt)
                if not spun_bytes:
                    logger.warning(f"  Variant {v_idx} failed - skipping")
                    continue

                # Upload spun image
                try:
                    spun_file = self._upload_to_drive(
                        f"{ad_archive_id}_v{v_idx}.png", spun_bytes, 'image/png', spun_folder_id
                    )
                    spun_link = spun_file.get('webViewLink', '')
                    logger.info(f"  Variant {v_idx} uploaded: {spun_link}")
                except Exception as e:
                    logger.warning(f"  Variant {v_idx} upload failed: {e}")
                    spun_link = ''

                # G. Append row to sheet
                asset_folder_link = f"https://drive.google.com/drive/folders/{parent_folder_id}"
                source_folder_link = f"https://drive.google.com/drive/folders/{source_folder_id}"
                spun_folder_link = f"https://drive.google.com/drive/folders/{spun_folder_id}"

                row = [
                    datetime.now().isoformat(),
                    ad_archive_id,
                    page_id,
                    original_image_url,
                    page_name,
                    ad_body[:500] if ad_body else '',  # Truncate long ad bodies
                    datetime.now().strftime('%Y-%m-%d'),
                    variant_prompt[:500],  # Truncate long prompts
                    asset_folder_link,
                    source_folder_link,
                    spun_folder_link,
                    spun_link
                ]

                try:
                    self._append_row(row)
                except Exception as e:
                    logger.warning(f"  Sheet append failed: {e}")
                    # CSV backup
                    csv_path = f".tmp/ad_library_backup_{datetime.now().strftime('%Y%m%d')}.csv"
                    with open(csv_path, 'a') as f:
                        f.write(','.join([f'"{v}"' for v in row]) + '\n')

                total_variants += 1

                # Delay between variants
                if v_idx < len(variants):
                    time.sleep(1)

            logger.info(f"  Ad {i}/{len(ads)} complete")

        # Summary
        elapsed = time.time() - start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"COMPLETE!")
        logger.info(f"  Ads processed: {len(ads) - failed_ads}/{len(ads)}")
        logger.info(f"  Variants generated: {total_variants}")
        logger.info(f"  Time: {elapsed:.0f}s ({elapsed/60:.1f}m)")
        logger.info(f"  Sheet: https://docs.google.com/spreadsheets/d/{self.sheet_id}")
        logger.info(f"  Drive: https://drive.google.com/drive/folders/{self.folder_id}")
        logger.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Ad Library Scraper + AI Image Spinner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test run (2 ads only)
  python3 execution/scrape_ad_library.py --keyword "agency" --style "bright blue maximalist" --test

  # Full run
  python3 execution/scrape_ad_library.py --keyword "agency" --max_ads 20 --style "ultra-maximalist with bold typography"

  # Reuse existing Drive folder and sheet
  python3 execution/scrape_ad_library.py --keyword "agency" --folder_id XXXXX --sheet_id XXXXX --style "minimalist"
        """
    )

    parser.add_argument('--keyword', help='Search keyword for Facebook Ad Library (or use --url)')
    parser.add_argument('--url', help='Direct Facebook Ad Library URL (overrides --keyword)')
    parser.add_argument('--max_ads', type=int, default=20, help='Max ads to scrape (default: 20)')
    parser.add_argument('--variants', type=int, default=3, help='Number of spin variants per ad (default: 3)')
    parser.add_argument('--style', required=True, help='Style direction for the spin (e.g. "bright blue ultra-maximalist")')
    parser.add_argument('--folder_name', default='Ad Library Spins', help='Google Drive master folder name (default: "Ad Library Spins")')
    parser.add_argument('--test', action='store_true', help='Test mode: only process 2 ads')
    parser.add_argument('--folder_id', help='Reuse existing Google Drive folder ID')
    parser.add_argument('--sheet_id', help='Reuse existing Google Sheet ID')

    args = parser.parse_args()

    if not args.keyword and not args.url:
        parser.error("Either --keyword or --url is required")

    try:
        spinner = AdLibrarySpinner(args)
        spinner.run()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
