#!/usr/bin/env python3
"""
Custom Cold Email Copy Generator

Analyzes client websites, researches competitors, identifies ICP pain points,
and generates niche-specific cold email copy using Connector Angle + SSM frameworks.

Usage:
    python generate_custom_copy.py --client_url https://veretin.com/ --num_variants 3
"""

import os
import sys
import json
import logging
import argparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List
from openai import AzureOpenAI
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from utils_notifications import notify_success, notify_error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Google Docs API scopes
SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']


class WebsiteAnalyzer:
    """Analyzes websites to extract key information."""
    
    def analyze(self, url: str) -> Dict:
        """Extract key info from website."""
        logger.info(f"Analyzing website: {url}")
        
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract meta description
            meta_desc = soup.find('meta', {'name': 'description'})
            og_desc = soup.find('meta', {'property': 'og:description'})
            description = (meta_desc.get('content') if meta_desc else
                          og_desc.get('content') if og_desc else '')

            # Extract title
            title = soup.find('title')
            title_text = title.text.strip() if title else ''

            # Extract main heading
            h1 = soup.find('h1')
            h1_text = h1.text.strip() if h1 else ''

            # Extract body text (first 1000 chars for analysis)
            body_text = soup.get_text()[:1000]

            return {
                'url': url,
                'title': title_text,
                'description': description,
                'heading': h1_text,
                'body_sample': body_text
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout accessing {url} - site may be slow or unreachable")
            return {'url': url, 'error': 'timeout', 'retryable': True}
        except requests.exceptions.SSLError:
            logger.warning(f"SSL certificate error for {url} - site may have security issues")
            return {'url': url, 'error': 'ssl_error', 'retryable': False}
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection failed for {url} - site may be down")
            return {'url': url, 'error': 'connection_error', 'retryable': True}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return {'url': url, 'error': f'http_{e.response.status_code}', 'retryable': False}
        except Exception as e:
            logger.error(f"Unexpected error analyzing {url}: {e}")
            return {'url': url, 'error': str(e), 'retryable': False}


class CompetitorResearcher:
    """Finds and analyzes competitors."""
    
    def __init__(self):
        self.analyzer = WebsiteAnalyzer()
    
    def find_competitors(self, business_description: str, num: int = 10, provided_urls: List[str] = None) -> List[str]:
        """Find competitor URLs via web search or use provided list."""
        if provided_urls:
            logger.info(f"Using {len(provided_urls)} provided competitors")
            return provided_urls[:num]
            
        logger.info(f"Finding {num} competitors for: {business_description}")
        
        # TODO: Implement real web search here
        # For now, return empty list if no manual URLs provided
        logger.warning("No competitor URLs provided and web search not implemented.")
        return []
    
    def analyze_competitors(self, urls: List[str]) -> List[Dict]:
        """Analyze multiple competitor websites with progress tracking."""
        results = []
        total = len(urls)
        successful = 0
        failed = 0

        logger.info(f"Starting analysis of {total} competitors...")

        for i, url in enumerate(urls, 1):
            try:
                logger.info(f"Analyzing competitor {i}/{total}: {url}")
                data = self.analyzer.analyze(url)
                results.append(data)

                if 'error' not in data:
                    successful += 1
                    logger.info(f"✓ Analyzed: {url}")
                else:
                    failed += 1
                    logger.warning(f"⚠ Partial data from {url}: {data.get('error')}")

            except Exception as e:
                failed += 1
                logger.error(f"❌ Failed to analyze {url}: {e}")
                results.append({'url': url, 'error': str(e)})

        logger.info(f"Competitor analysis complete: {successful} successful, {failed} failed out of {total}")
        return results


class PainPointIdentifier:
    """Identifies ICP pain points from competitor analysis."""
    
    def __init__(self, azure_endpoint: str, api_key: str, deployment: str):
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment = deployment
    
    def identify_pain_points(self, client_info: Dict, competitors_data: List[Dict]) -> List[str]:
        """Synthesize pain points from competitor messaging."""
        logger.info("Identifying ICP pain points...")

        # Compile competitor info (limit to first 100 chars per description to save tokens)
        competitor_summary = "\\n".join([
            f"- {c['title']}: {c.get('description', '')[:100]}"
            for c in competitors_data if 'error' not in c
        ][:8])  # Limit to 8 competitors max

        prompt = f"""
B2B ICP pain point analysis.

CLIENT: {client_info.get('title', '')} - {client_info.get('description', '')[:150]}

COMPETITORS:
{competitor_summary}

TASK: Return JSON array of 5 specific pain points (operator-style, ranked).

OUTPUT: {{"pain_points": ["struggle to...", "waste time on..."]}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a B2B marketing analyst. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            pain_points = result.get('pain_points', [])
            logger.info(f"✓ Identified {len(pain_points)} pain points")
            return pain_points
            
        except Exception as e:
            logger.error(f"Error identifying pain points: {e}")
            return []


class EmailCopyGenerator:
    """Generates Connector Angle + SSM email copy."""
    
    def __init__(self, azure_endpoint: str, api_key: str, deployment: str):
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version="2024-02-15-preview"
        )
        self.deployment = deployment
    
    def generate_variant(self, client_info: Dict, pain_points: List[str], angle: str) -> Dict:
        """Generate one email variant using Connector Angle + SSM SOP + Spartan tone."""
        logger.info(f"Generating email variant: {angle}")
        
        prompt = f"""
        You are an expert cold email copywriter trained in Connector Angle, Anti-Fragile Method, and SSM SOP.
        
        CLIENT INFO:
        - Business: {client_info.get('title', '')}
        - Description: {client_info.get('description', '')}
        
        ICP PAIN POINTS:
        {json.dumps(pain_points[:3], indent=2)}
        
        ANGLE: {angle}
        
        TASK: Write ONE complete cold email using Connector Angle + SSM SOP framework.
        
        REQUIRED OUTPUT (JSON):
        {{
            "subject": "...",
            "body": "...",
            "follow_up_1": "...",
            "follow_up_2": "..."
        }}
        
        CRITICAL SPARTAN/LACONIC TONE RULES (MUST FOLLOW ALL):
        1. ✅ **NO PUNCTUATION** at end of sentences/CTAs
           - ❌ "Worth exploring?"
           - ✅ "Worth exploring"
        
        2. ✅ **Simple language ONLY** - Ban these jargon words:
           - leverage, optimize, streamline, synergy, solutions, innovative, cutting-edge
           - robust, paradigm, scalable, ecosystem, disruptive, revolutionary
           - If you use ANY of these words, the email FAILS
        
        3. ✅ **Short and direct** 
           - 5-7 sentences maximum
           - Under 100 words total
           - No fluff, no filler
        
        4. ✅ **Shorten company names**
           - ❌ "XYZ Professional Services"
           - ✅ "XYZ"
        
        5. ✅ **Focus on WHAT not HOW**
           - ❌ "We use a proprietary 7-step system to identify prospects"
           - ✅ "We connect you with companies actively hiring"
        
        6. ✅ **Strategic lowercase** - Keep it casual but professional
        
        7. ✅ **Imply familiarity** - Show shared beliefs/interests when relevant
        
        SSM SOP STRUCTURE:
        - Line 1: SSM opener using {{{{companyName}}}} or observation
          Examples:
          * "Noticed {{{{companyName}}}} is scaling fast in {{{{City}}}}"
          * "Saw you're hiring for {{{{role}}}}"
          * "Most {{{{industry}}}} founders I talk to struggle with {{{{pain}}}}"
        
        - Lines 2-3: Bridge connecting to their pain/situation
        
        - Line 4: Specific outcome with NUMBERS
          Examples:
          * "5-10 qualified calls per month"
          * "15+ appointments in 30 days"
          * "€90K in job orders that same quarter"
        
        - Line 5: Easy CTA with NO PUNCTUATION
          Examples:
          * "Worth exploring"
          * "Want me to intro you"
          * "Open to seeing candidates"
        
        - End: "Sent from my iPhone"
        
        CONNECTOR ANGLE (Position as introducer, not seller):
        - ❌ Direct pitch: "I run ads, hire me"
        - ✅ Connector: "I know someone who helped {{{{similar_company}}}} achieve {{{{result}}}}. Want me to intro you?"
        
        ANGLES EXPLAINED:
        - **Problem-Solving**: Address pain directly → offer connector intro to solution
          Example: "Most principals struggle with X. I know someone who solved this for {{{{similar_company}}}}. Want intro?"
        
        - **Opportunity**: Highlight what they're missing → show hidden opportunity
          Example: "Best candidates aren't on job boards. I know someone who headhunts top talent. Worth exploring?"
        
        - **Authority**: Reference case study → position as expert
          Example: "We only do X specialization. Recently helped {{{{company}}}} achieve {{{{result}}}}. Worth a call?"
        
        VARIABLES TO USE:
        - {{{{firstName}}}}
        - {{{{companyName}}}}
        - {{{{City}}}} (optional)
        
        FOLLOW-UPS (Use these EXACT texts):
        - Day 3: "Hey {{{{firstName}}}}, worth intro'ing you"
        - Day 7: "Hey {{{{firstName}}}}, maybe this isn't something you're interested in — wishing you the best"
        
        Generate for angle: {angle}
        """

        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert cold email copywriter. Output valid JSON only. Follow Spartan tone rules strictly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            variant = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Generated variant: {angle}")
            return variant
            
        except Exception as e:
            logger.error(f"Error generating variant: {e}")
            return {}
    
    def generate_all_variants(self, client_info: Dict, pain_points: List[str], num_variants: int = 3) -> List[Dict]:
        """Generate multiple email variants."""
        angles = ["Problem-Solving", "Opportunity", "Authority", "Referral", "Case Study"]
        variants = []
        
        for i in range(num_variants):
            angle = angles[i % len(angles)]
            variant = self.generate_variant(client_info, pain_points, angle)
            if variant:
                variant['angle'] = angle
                variants.append(variant)
        
        return variants


class GoogleDocsExporter:
    """Exports results to Google Docs."""
    
    def __init__(self):
        self.creds = self._get_credentials()
        self.docs_service = build('docs', 'v1', credentials=self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)
    
    def _get_credentials(self):
        """Get Google OAuth credentials."""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("credentials.json not found")
                    raise FileNotFoundError("Google OAuth credentials.json not found")
                
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def create_doc(self, title: str, content_data: Dict) -> str:
        """Create formatted Google Doc."""
        logger.info(f"Creating Google Doc: {title}")
        
        # Create document
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc['documentId']
        
        # Build content
        requests_list = self._build_content_requests(content_data)
        
        # Update document
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests_list}
        ).execute()
        
        # Make doc publicly viewable (optional)
        self.drive_service.permissions().create(
            fileId=doc_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info(f"✓ Created Google Doc: {doc_url}")
        return doc_url
    
    def _build_content_requests(self, data: Dict) -> List[Dict]:
        """Build Google Docs API requests for formatting."""
        # This is complex - simplified version here
        # Full implementation would use Google Docs API to format headers, paragraphs, etc.
        
        content = f"""# Custom Copy for {data['client']['title']}

## 1. Client Overview
- Business: {data['client'].get('title', '')}
- Description: {data['client'].get('description', '')}
- Target ICP: {data.get('target_icp', 'Not specified')}

## 2. Competitor Analysis
"""
        
        for i, comp in enumerate(data.get('competitors', [])[:5], 1):
            if 'error' not in comp:
                content += f"{i}. {comp.get('title', 'Unknown')}: {comp.get('description', '')[:100]}...\\n"
        
        content += f"""
## 3. ICP Pain Points (Ranked)
"""
        for i, pain in enumerate(data.get('pain_points', []), 1):
            content += f"{i}. {pain}\\n"
        
        content += """
## 4. Email Variants
"""
        
        for i, variant in enumerate(data.get('variants', []), 1):
            content += f"""
### Variant {chr(64+i)}: {variant.get('angle', 'Unknown')} Angle

**Subject:** {variant.get('subject', '')}

**Body:**
{variant.get('body', '')}

**Follow-up 1 (Day 3):**
{variant.get('follow_up_1', '')}

**Follow-up 2 (Day 7):**
{variant.get('follow_up_2', '')}

---
"""
        
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }
        ]
        
        return requests


def main():
    parser = argparse.ArgumentParser(description='Generate custom cold email copy')
    parser.add_argument('--client_url', required=True, help='Client website URL')
    parser.add_argument('--num_competitors', type=int, default=10, help='Number of competitors to research')
    parser.add_argument('--num_variants', type=int, default=3, help='Number of email variants to generate')
    parser.add_argument('--output_dir', default='.tmp/custom_copy', help='Output directory for backups')
    parser.add_argument('--competitors', help='Comma-separated list of competitor URLs')
    
    args = parser.parse_args()
    
    # Parse competitors if provided
    provided_competitors = args.competitors.split(',') if args.competitors else None
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize components
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([azure_endpoint, azure_key, azure_deployment]):
        logger.error("Missing Azure OpenAI credentials in .env")
        sys.exit(1)
    
    analyzer = WebsiteAnalyzer()
    researcher = CompetitorResearcher()
    pain_identifier = PainPointIdentifier(azure_endpoint, azure_key, azure_deployment)
    copy_generator = EmailCopyGenerator(azure_endpoint, azure_key, azure_deployment)
    # docs_exporter = GoogleDocsExporter()  # Moved to Phase 5
    
    # Phase 1: Analyze client
    logger.info("\\n" + "="*60)
    logger.info("PHASE 1: Analyzing Client Website")
    logger.info("="*60)
    client_info = analyzer.analyze(args.client_url)
    
    # Phase 2: Research competitors
    logger.info("\\n" + "="*60)
    logger.info(f"PHASE 2: Researching {args.num_competitors} Competitors")
    logger.info("="*60)
    competitor_urls = researcher.find_competitors(
        client_info.get('description', ''), 
        args.num_competitors,
        provided_urls=provided_competitors
    )
    competitors_data = researcher.analyze_competitors(competitor_urls)
    
    # Phase 3: Identify pain points
    logger.info("\\n" + "="*60)
    logger.info("PHASE 3: Identifying ICP Pain Points")
    logger.info("="*60)
    pain_points = pain_identifier.identify_pain_points(client_info, competitors_data)
    
    # Phase 4: Generate email variants
    logger.info("\\n" + "="*60)
    logger.info(f"PHASE 4: Generating {args.num_variants} Email Variants")
    logger.info("="*60)
    variants = copy_generator.generate_all_variants(client_info, pain_points, args.num_variants)
    
    # Compile all data
    output_data = {
        'client': client_info,
        'competitors': competitors_data,
        'pain_points': pain_points,
        'variants': variants,
        'generated_at': datetime.now().isoformat()
    }
    
    # Save backup locally
    backup_file = os.path.join(args.output_dir, f"custom_copy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(backup_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    logger.info(f"✓ Saved backup: {backup_file}")
    
    # Save as Markdown (Primary Output)
    # Sanitize filename
    safe_title = "".join([c for c in client_info.get('title', 'client') if c.isalnum() or c in (' ', '_', '-')]).strip()
    md_filename = f"custom_copy_{safe_title.lower().replace(' ', '_')}.md"
    md_file = os.path.join(args.output_dir, md_filename)
    
    md_content = f"""# Custom Copy for {client_info.get('title', 'Client')}

## 1. Client Overview
- **Business:** {client_info.get('title', '')}
- **Description:** {client_info.get('description', '')}
- **Target ICP:** {client_info.get('target_audience', '')}
- **Key Offer:** {client_info.get('value_prop', '')}

## 2. Competitor Analysis ({len(competitors_data)} Companies)
"""
    for comp in competitors_data:
        md_content += f"1. **{comp.get('name', 'Competitor')}**: {comp.get('positioning', '')}\n"
        
    md_content += f"""
## 3. ICP Pain Points (Ranked)
"""
    for i, pain in enumerate(pain_points, 1):
        md_content += f"{i}. {pain}\n"
        
    md_content += f"""
## 4. Email Variants
"""
    for i, variant in enumerate(variants, 1):
        angle = variant.get('angle', f'Variant {i}')
        md_content += f"""
### Variant {chr(64+i)}: {angle}
**Subject:** {variant.get('subject', '')}

**Body:**
{variant.get('body', '')}

**Follow-up 1 (Day 3):**
{variant.get('follow_up_1', '')}

**Follow-up 2 (Day 7):**
{variant.get('follow_up_2', '')}

---
"""
    
    with open(md_file, 'w') as f:
        f.write(md_content)
    logger.info(f"✓ Saved markdown: {md_file}")

    # Phase 5: Export to Google Docs (Optional)
    doc_url = "Skipped (Auth Error)"
    try:
        docs_exporter = GoogleDocsExporter()
        logger.info("\\n" + "="*60)
        logger.info("PHASE 5: Exporting to Google Docs")
        logger.info("="*60)
        doc_title = f"Custom Copy - {client_info.get('title', 'Client')} - {datetime.now().strftime('%Y-%m-%d')}"
        doc_url = docs_exporter.create_doc(doc_title, output_data)
        logger.info(f"📄 Google Doc: {doc_url}")
    except Exception as e:
        logger.warning(f"⚠️ Could not export to Google Docs: {e}")
        logger.info("Skipping Google Docs export. Use the generated Markdown file.")
    
    # Summary
    logger.info("\\n" + "="*60)
    logger.info("✓ WORKFLOW COMPLETE!")
    logger.info("="*60)
    logger.info(f"📊 Analyzed: {args.client_url}")
    logger.info(f"🔍 Competitors researched: {len(competitors_data)}")
    logger.info(f"💡 Pain points identified: {len(pain_points)}")
    logger.info(f"📧 Email variants generated: {len(variants)}")
    logger.info(f"📝 Markdown File: {md_file}")
    logger.info(f"💾 JSON Backup: {backup_file}")
    logger.info("="*60)

    notify_success()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        notify_error()
        sys.exit(1)
