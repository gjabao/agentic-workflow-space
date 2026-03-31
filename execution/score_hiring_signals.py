#!/usr/bin/env python3
"""
Hiring Signal Scorer & Weekly Brief Generator

Combines outputs from all job scrapers + employee departure tracker into a single
scored lead list. Deduplicates by company domain, stacks signals, and generates
a Google Sheet brief for recruitment agency clients.

Usage:
    # Score from specific CSV files
    python3 execution/score_hiring_signals.py \
        --linkedin .tmp/linkedin_jobs_20260330.csv \
        --indeed .tmp/indeed_jobs_20260330.csv \
        --glassdoor .tmp/glassdoor_jobs_20260330.csv \
        --departures active/leads/employee-departures/employee_departures_20260330.csv \
        --output active/leads/hiring-signals \
        --min-score 40 \
        --sheet-name "Weekly Hiring Brief - March 30"

    # Score from latest files in .tmp/
    python3 execution/score_hiring_signals.py \
        --auto-detect \
        --output active/leads/hiring-signals \
        --min-score 40

Directive: directives/hiring_signal_pipeline.md
"""

import os
import sys
import csv
import json
import glob
import logging
import argparse
import re
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Setup Logging
os.makedirs(os.path.join(BASE_DIR, 'active', 'leads', 'hiring-signals'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, '.tmp'), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, '.tmp', 'hiring_signal_scorer.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# SCORING MODEL
# ============================================================================

SCORING_WEIGHTS = {
    'departure_signal': 35,       # Someone left the company (highest quality)
    'job_age_30_plus': 25,        # Job posted 30+ days ago (struggling to fill)
    'job_age_14_29': 15,          # Job posted 14-29 days ago (active need)
    'multiple_roles': 20,         # 3+ open roles (scaling = budget confirmed)
    'no_internal_recruiter': 15,  # No in-house TA team
    'company_size_sweet': 10,     # 20-150 employees (ideal for agency)
    'company_size_medium': 5,     # 150-300 employees (possible)
    'poor_glassdoor': 10,         # Rating < 3.5 (employer brand problem)
    'has_dm_email': 5,            # Actionable: verified decision-maker email
}

HEAT_LEVELS = {
    'HOT': (70, 100),
    'WARM': (50, 69),
    'WATCH': (40, 49),
}


class CompanyRecord:
    """Unified company record that accumulates signals from multiple sources."""

    def __init__(self, domain: str, name: str):
        self.domain = domain
        self.name = name
        self.website = ''
        self.company_size = 0
        self.industry = ''
        self.glassdoor_rating = 0.0
        self.sources = []
        self.open_roles = []
        self.stale_jobs_count = 0
        self.departure_info = None  # (person_name, role_they_left, left_date)
        self.has_internal_recruiter = False
        self.dm_name = ''
        self.dm_title = ''
        self.dm_email = ''
        self.dm_linkedin = ''
        self.suggested_angle = ''
        self.date_added = datetime.now().strftime('%Y-%m-%d')
        self._signals = set()

    def add_signal(self, signal: str):
        self._signals.add(signal)

    def calculate_score(self) -> int:
        score = 0
        for signal in self._signals:
            score += SCORING_WEIGHTS.get(signal, 0)
        return min(score, 100)

    @property
    def score(self) -> int:
        return self.calculate_score()

    @property
    def heat_level(self) -> str:
        s = self.score
        for level, (low, high) in HEAT_LEVELS.items():
            if low <= s <= high:
                return level
        return 'SKIP'

    def to_dict(self) -> dict:
        return {
            'Hiring Score': self.score,
            'Heat Level': self.heat_level,
            'Company Name': self.name,
            'Company Website': self.website,
            'Company Size': self.company_size,
            'Industry': self.industry,
            'Signal Sources': ' + '.join(sorted(self.sources)),
            'Open Roles': len(self.open_roles),
            'Stale Jobs (30d+)': self.stale_jobs_count,
            'Key Departure': f"{self.departure_info[0]} ({self.departure_info[1]})" if self.departure_info else '',
            'DM Name': self.dm_name,
            'DM Title': self.dm_title,
            'DM Email': self.dm_email,
            'DM LinkedIn': self.dm_linkedin,
            'Suggested Angle': self.suggested_angle,
            'Signals Detail': ', '.join(sorted(self._signals)),
            'Date Added': self.date_added,
        }


# ============================================================================
# PARSERS — One per data source
# ============================================================================

def normalize_domain(url_or_domain: str) -> str:
    """Extract clean domain from URL or domain string."""
    if not url_or_domain:
        return ''
    url = url_or_domain.strip().lower()
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.replace('www.', '').strip('/')
        return domain
    except Exception:
        return url_or_domain.strip().lower()


def parse_job_csv(filepath: str, source_name: str, companies: Dict[str, CompanyRecord]):
    """Parse output from LinkedIn/Indeed/Glassdoor/Reed scrapers."""
    if not filepath or not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return

    logger.info(f"Parsing {source_name}: {filepath}")
    count = 0

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract company info — handle different column naming conventions
            company_name = (
                row.get('Company Name', '') or
                row.get('company_name', '') or
                row.get('company', '') or ''
            ).strip()

            if not company_name or company_name.lower() in ('confidential', 'company', 'n/a', ''):
                continue

            website = (
                row.get('Company Website', '') or
                row.get('Company Domain', '') or
                row.get('company_website', '') or
                row.get('website', '') or ''
            ).strip()

            domain = normalize_domain(website) or company_name.lower().replace(' ', '')

            # Get or create company record
            if domain not in companies:
                companies[domain] = CompanyRecord(domain, company_name)
            company = companies[domain]

            # Update basic info
            if website and not company.website:
                company.website = website
            if source_name not in company.sources:
                company.sources.append(source_name)

            # Job title
            job_title = (
                row.get('Job Title', '') or
                row.get('job_title', '') or
                row.get('title', '') or ''
            )
            if job_title:
                company.open_roles.append(job_title)

            # Company size
            size_str = (
                row.get('Company Size', '') or
                row.get('company_size', '') or
                row.get('Employee Count', '') or ''
            )
            if size_str:
                size_num = re.sub(r'[^\d]', '', str(size_str).split('-')[0].split('+')[0])
                if size_num:
                    company.company_size = max(company.company_size, int(size_num))

            # Job age / pain level
            pain = (row.get('Pain Level', '') or row.get('pain_level', '') or '').upper()
            job_age_str = row.get('Job Age (Days)', '') or row.get('job_age', '') or ''
            job_age = 0
            if job_age_str:
                try:
                    job_age = int(float(job_age_str))
                except (ValueError, TypeError):
                    pass

            if pain == 'HIGH' or job_age >= 30:
                company.add_signal('job_age_30_plus')
                company.stale_jobs_count += 1
            elif pain == 'MEDIUM' or job_age >= 14:
                company.add_signal('job_age_14_29')

            # Decision maker info (use first found)
            dm_email = (
                row.get('DM Email', '') or
                row.get('dm_email', '') or
                row.get('email', '') or ''
            ).strip()
            if dm_email and '@' in dm_email and not company.dm_email:
                company.dm_email = dm_email
                company.dm_name = (
                    f"{row.get('DM First Name', '') or row.get('dm_first_name', '')} "
                    f"{row.get('DM Last Name', '') or row.get('dm_last_name', '')}"
                ).strip()
                company.dm_title = (
                    row.get('DM Title', '') or
                    row.get('DM Job Title', '') or
                    row.get('dm_job_title', '') or
                    row.get('dm_title', '') or ''
                )
                company.dm_linkedin = (
                    row.get('DM LinkedIn', '') or
                    row.get('dm_linkedin_url', '') or
                    row.get('dm_linkedin', '') or ''
                )
                company.add_signal('has_dm_email')

            # Industry
            industry = (
                row.get('Company Type', '') or
                row.get('Industry', '') or
                row.get('industry', '') or ''
            )
            if industry and not company.industry:
                company.industry = industry

            count += 1

    logger.info(f"  Parsed {count} rows from {source_name}")


def parse_departures_csv(filepath: str, companies: Dict[str, CompanyRecord]):
    """Parse output from employee departure tracker."""
    if not filepath or not os.path.exists(filepath):
        logger.warning(f"Departures file not found: {filepath}")
        return

    logger.info(f"Parsing departures: {filepath}")
    count = 0

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            company_name = (row.get('previous_company', '') or '').strip()
            if not company_name:
                continue

            website = (row.get('company_website', '') or '').strip()
            domain = normalize_domain(website) or company_name.lower().replace(' ', '')

            if domain not in companies:
                companies[domain] = CompanyRecord(domain, company_name)
            company = companies[domain]

            if website and not company.website:
                company.website = website
            if 'Departures' not in company.sources:
                company.sources.append('Departures')

            # The departure signal itself
            departed_name = f"{row.get('departed_first_name', '')} {row.get('departed_last_name', '')}".strip()
            role_left = row.get('role_they_left', '')
            left_date = row.get('left_date', '')

            if departed_name and not company.departure_info:
                company.departure_info = (departed_name, role_left, left_date)
                company.add_signal('departure_signal')

            # Decision maker from the departure data
            dm_email = (row.get('dm_email', '') or '').strip()
            if dm_email and '@' in dm_email and not company.dm_email:
                company.dm_email = dm_email
                company.dm_name = f"{row.get('dm_first_name', '')} {row.get('dm_last_name', '')}".strip()
                company.dm_title = row.get('dm_job_title', '') or ''
                company.dm_linkedin = row.get('dm_linkedin_url', '') or ''
                company.add_signal('has_dm_email')

            count += 1

    logger.info(f"  Parsed {count} departure rows")


# ============================================================================
# SCORING LOGIC
# ============================================================================

def apply_scoring(companies: Dict[str, CompanyRecord]):
    """Apply scoring signals based on accumulated data."""
    for domain, company in companies.items():
        # Multiple roles signal
        if len(company.open_roles) >= 3:
            company.add_signal('multiple_roles')

        # Company size scoring
        if 20 <= company.company_size <= 150:
            company.add_signal('company_size_sweet')
        elif 150 < company.company_size <= 300:
            company.add_signal('company_size_medium')

        # Glassdoor rating (if we have it)
        if company.glassdoor_rating and company.glassdoor_rating < 3.5:
            company.add_signal('poor_glassdoor')

        # No internal recruiter (default to true — LinkedIn scraper sets this when detected)
        if not company.has_internal_recruiter:
            company.add_signal('no_internal_recruiter')


def generate_suggested_angle(company: CompanyRecord) -> str:
    """Generate a 2-line suggested outreach angle based on signals."""
    parts = []

    if company.departure_info:
        name, role, _ = company.departure_info
        parts.append(f"Their {role} ({name}) recently left")

    if company.stale_jobs_count > 0:
        parts.append(f"{company.stale_jobs_count} role(s) open 30+ days")

    if len(company.open_roles) >= 3:
        parts.append(f"scaling with {len(company.open_roles)} open positions")

    if not parts:
        parts.append("Active hiring detected")

    angle = '. '.join(parts) + '.'

    # Add suggested opener
    if company.departure_info:
        angle += " Lead with backfill urgency — they need someone fast."
    elif company.stale_jobs_count > 0:
        angle += " Lead with pain — they've been trying to fill this for weeks."
    elif len(company.open_roles) >= 3:
        angle += " Lead with scale — they need recruiting capacity, not just one hire."

    return angle


# ============================================================================
# OUTPUT
# ============================================================================

def export_to_csv(companies: Dict[str, CompanyRecord], output_dir: str, min_score: int) -> str:
    """Export scored companies to CSV, sorted by score descending."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(output_dir, f'hiring_signals_{timestamp}.csv')

    scored = []
    for domain, company in companies.items():
        company.suggested_angle = generate_suggested_angle(company)
        if company.score >= min_score:
            scored.append(company.to_dict())

    scored.sort(key=lambda x: x['Hiring Score'], reverse=True)

    if not scored:
        logger.warning("No companies met the minimum score threshold.")
        return ''

    fieldnames = list(scored[0].keys())
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored)

    logger.info(f"Exported {len(scored)} scored companies to {filepath}")
    return filepath


def export_to_sheets(companies: Dict[str, CompanyRecord], min_score: int, sheet_name: str) -> Optional[str]:
    """Export scored companies to Google Sheets."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
    except ImportError:
        logger.warning("Google API libraries not available. Skipping Sheets export.")
        return None

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    token_path = os.path.join(BASE_DIR, 'token.json')
    creds_path = os.path.join(BASE_DIR, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif os.path.exists(creds_path):
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            logger.warning("No Google credentials found. Skipping Sheets export.")
            return None

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    service = build('sheets', 'v4', credentials=creds)

    # Create new spreadsheet
    spreadsheet = service.spreadsheets().create(body={
        'properties': {'title': sheet_name or f'Hiring Signals Brief - {datetime.now().strftime("%Y-%m-%d")}'},
    }).execute()
    sheet_id = spreadsheet['spreadsheetId']
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    # Prepare data
    scored = []
    for domain, company in companies.items():
        company.suggested_angle = generate_suggested_angle(company)
        if company.score >= min_score:
            scored.append(company.to_dict())

    scored.sort(key=lambda x: x['Hiring Score'], reverse=True)

    if not scored:
        logger.warning("No companies to export to Sheets.")
        return sheet_url

    headers = list(scored[0].keys())
    rows = [headers] + [[str(row.get(h, '')) for h in headers] for row in scored]

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='A1',
        valueInputOption='RAW',
        body={'values': rows}
    ).execute()

    logger.info(f"Exported {len(scored)} companies to Google Sheets: {sheet_url}")
    return sheet_url


def print_summary(companies: Dict[str, CompanyRecord], min_score: int):
    """Print a quick summary to console."""
    scored = [(d, c) for d, c in companies.items() if c.score >= min_score]
    scored.sort(key=lambda x: x[1].score, reverse=True)

    hot = sum(1 for _, c in scored if c.heat_level == 'HOT')
    warm = sum(1 for _, c in scored if c.heat_level == 'WARM')
    watch = sum(1 for _, c in scored if c.heat_level == 'WATCH')

    print(f"\n{'='*60}")
    print(f"  HIRING SIGNAL BRIEF SUMMARY")
    print(f"{'='*60}")
    print(f"  Total companies scored: {len(companies)}")
    print(f"  Above threshold (>={min_score}): {len(scored)}")
    print(f"  HOT (70-100): {hot}")
    print(f"  WARM (50-69): {warm}")
    print(f"  WATCH (40-49): {watch}")
    print(f"{'='*60}")

    if scored:
        print(f"\n  TOP 10 TARGETS:")
        print(f"  {'Score':<6} {'Heat':<6} {'Company':<30} {'Signals'}")
        print(f"  {'-'*6} {'-'*6} {'-'*30} {'-'*30}")
        for _, company in scored[:10]:
            print(f"  {company.score:<6} {company.heat_level:<6} {company.name[:30]:<30} {', '.join(company.sources)}")

    print()


# ============================================================================
# AUTO-DETECT LATEST FILES
# ============================================================================

def find_latest_csv(directory: str, pattern: str) -> Optional[str]:
    """Find the most recently modified CSV matching a pattern."""
    search_path = os.path.join(directory, pattern)
    files = glob.glob(search_path)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def auto_detect_inputs(base_dir: str) -> dict:
    """Auto-detect the latest CSV files from each scraper."""
    tmp_dir = os.path.join(base_dir, '.tmp')
    departures_dir = os.path.join(base_dir, 'active', 'leads', 'employee-departures')

    detected = {
        'linkedin': find_latest_csv(tmp_dir, 'linkedin_jobs_*.csv'),
        'indeed': find_latest_csv(tmp_dir, 'indeed_jobs_*.csv'),
        'glassdoor': find_latest_csv(tmp_dir, 'glassdoor_jobs_*.csv'),
        'reed': find_latest_csv(tmp_dir, 'reed_jobs_*.csv'),
        'departures': find_latest_csv(departures_dir, 'employee_departures_*.csv'),
    }

    for source, path in detected.items():
        if path:
            logger.info(f"Auto-detected {source}: {path}")
        else:
            logger.info(f"No file found for {source}")

    return detected


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Score hiring signals and generate weekly brief')
    parser.add_argument('--linkedin', help='Path to LinkedIn jobs CSV')
    parser.add_argument('--indeed', help='Path to Indeed jobs CSV')
    parser.add_argument('--glassdoor', help='Path to Glassdoor jobs CSV')
    parser.add_argument('--reed', help='Path to Reed jobs CSV')
    parser.add_argument('--departures', help='Path to employee departures CSV')
    parser.add_argument('--auto-detect', action='store_true', help='Auto-detect latest CSV files from .tmp/')
    parser.add_argument('--output', default=os.path.join(BASE_DIR, 'active', 'leads', 'hiring-signals'),
                        help='Output directory for scored CSV')
    parser.add_argument('--min-score', type=int, default=40, help='Minimum score to include (default: 40)')
    parser.add_argument('--sheet-name', help='Google Sheet name (creates new sheet if provided)')
    parser.add_argument('--no-sheets', action='store_true', help='Skip Google Sheets export')

    args = parser.parse_args()

    # Resolve input files
    if args.auto_detect:
        detected = auto_detect_inputs(BASE_DIR)
        linkedin_file = args.linkedin or detected.get('linkedin')
        indeed_file = args.indeed or detected.get('indeed')
        glassdoor_file = args.glassdoor or detected.get('glassdoor')
        reed_file = args.reed or detected.get('reed')
        departures_file = args.departures or detected.get('departures')
    else:
        linkedin_file = args.linkedin
        indeed_file = args.indeed
        glassdoor_file = args.glassdoor
        reed_file = args.reed
        departures_file = args.departures

    if not any([linkedin_file, indeed_file, glassdoor_file, reed_file, departures_file]):
        logger.error("No input files specified. Use --auto-detect or provide file paths.")
        sys.exit(1)

    # Parse all sources into unified company records
    companies: Dict[str, CompanyRecord] = {}

    parse_job_csv(linkedin_file, 'LinkedIn', companies)
    parse_job_csv(indeed_file, 'Indeed', companies)
    parse_job_csv(glassdoor_file, 'Glassdoor', companies)
    parse_job_csv(reed_file, 'Reed', companies)
    parse_departures_csv(departures_file, companies)

    logger.info(f"Total unique companies: {len(companies)}")

    # Apply scoring
    apply_scoring(companies)

    # Output
    os.makedirs(args.output, exist_ok=True)
    csv_path = export_to_csv(companies, args.output, args.min_score)

    # Google Sheets export
    sheet_url = None
    if not args.no_sheets and (args.sheet_name or args.auto_detect):
        sheet_url = export_to_sheets(companies, args.min_score, args.sheet_name)

    # Print summary
    print_summary(companies, args.min_score)

    if csv_path:
        print(f"  CSV: {csv_path}")
    if sheet_url:
        print(f"  Google Sheet: {sheet_url}")
    print()


if __name__ == '__main__':
    main()
