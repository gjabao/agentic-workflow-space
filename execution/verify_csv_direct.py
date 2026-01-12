#!/usr/bin/env python3
"""
Email Verification from CSV File
---------------------------------
Reads leads from a CSV file, verifies emails with SSMasters,
exports ONLY valid emails to a new CSV file.

Usage:
    python execution/verify_csv_direct.py <csv_file_path>

Example:
    python execution/verify_csv_direct.py "leads (3).csv"
"""

import os
import sys
import logging
import time
import requests
import csv
import io
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def read_csv(file_path: str) -> List[Dict]:
    """
    Read leads from CSV file.

    Args:
        file_path: Path to CSV file

    Returns:
        List of lead dictionaries
    """
    logger.info(f"📂 Reading CSV file: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"❌ File not found: {file_path}")
        return []

    try:
        leads = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads.append(row)

        logger.info(f"✓ Read {len(leads)} leads from CSV")
        return leads

    except Exception as e:
        logger.error(f"❌ Error reading CSV: {e}")
        return []


def verify_single_batch(batch_emails: List[str], api_key: str, batch_num: int, total_batches: int) -> Dict[str, str]:
    """
    Verify a single batch of emails using SSMasters bulk API.

    Args:
        batch_emails: List of email addresses (max 50)
        api_key: SSMasters API key
        batch_num: Current batch number
        total_batches: Total number of batches

    Returns:
        Dict mapping email -> status (Valid, Invalid, Catch-All, etc.)
    """
    if not batch_emails:
        return {}

    logger.info(f"   📦 Batch {batch_num}/{total_batches}: Verifying {len(batch_emails)} emails...")

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['email'])
    for email in batch_emails:
        writer.writerow([email])
    csv_content = output.getvalue()

    # Upload for verification
    try:
        files = {
            'csvFile': (f'batch_{batch_num}.csv', csv_content, 'text/csv')
        }
        data = {'apiKey': api_key}

        response = requests.post(
            "https://ssmasters.com/api/v1/public/verify/bulk",
            files=files,
            data=data,
            timeout=30
        )

        if response.status_code != 202:
            logger.error(f"      ❌ Batch {batch_num} upload failed: {response.status_code}")
            return {}

        result = response.json()
        if not result.get('success'):
            logger.error(f"      ❌ Batch {batch_num} failed: {result.get('message')}")
            return {}

        request_id = result['requestId']

        # Poll for results with exponential backoff
        max_retries = 60
        poll_interval = 2  # Start with 2 seconds

        for attempt in range(max_retries):
            time.sleep(poll_interval)
            try:
                status_response = requests.get(
                    f"https://ssmasters.com/api/v1/public/request/{request_id}/status",
                    params={'apiKey': api_key},
                    timeout=30
                )

                if status_response.status_code != 200:
                    continue

                data = status_response.json()
                status = data['request']['status']

                if status == 'completed':
                    results = {}
                    for item in data['request']['results']:
                        results[item['email'].lower()] = item['status']
                    logger.info(f"      ✓ Batch {batch_num} complete ({len(results)} emails)")
                    return results

                if status == 'failed':
                    logger.error(f"      ❌ Batch {batch_num} failed during processing")
                    return {}

                # Exponential backoff: increase poll interval gradually
                if attempt > 10:
                    poll_interval = min(10, poll_interval * 1.2)

            except Exception as e:
                continue

        logger.error(f"      ❌ Batch {batch_num} timed out")
        return {}

    except Exception as e:
        logger.error(f"      ❌ Batch {batch_num} error: {e}")
        return {}


def verify_emails_batch(emails: List[str], api_key: str) -> Dict[str, str]:
    """
    Verify emails using SSMasters bulk API with batching and parallel processing.

    Args:
        emails: List of email addresses
        api_key: SSMasters API key

    Returns:
        Dict mapping email -> status (Valid, Invalid, Catch-All, etc.)
    """
    if not emails:
        return {}

    logger.info(f"⏳ Verifying {len(emails)} emails...")

    # Deduplicate emails
    unique_emails = list(set([e.strip().lower() for e in emails if e]))
    logger.info(f"   ({len(unique_emails)} unique emails after deduplication)")

    # Split into batches of 50
    batch_size = 50
    batches = [unique_emails[i:i+batch_size] for i in range(0, len(unique_emails), batch_size)]
    total_batches = len(batches)

    logger.info(f"   Processing {total_batches} batches in parallel (up to 5 concurrent)...\n")

    # Process batches in parallel
    all_results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all batch jobs
        future_to_batch = {
            executor.submit(verify_single_batch, batch, api_key, i+1, total_batches): i+1
            for i, batch in enumerate(batches)
        }

        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                batch_results = future.result()
                all_results.update(batch_results)
            except Exception as e:
                logger.error(f"      ❌ Batch {batch_num} exception: {e}")

    logger.info(f"\n✓ All batches complete: {len(all_results)} emails verified")
    return all_results


def export_to_csv(leads: List[Dict], output_path: str) -> bool:
    """
    Export leads to CSV file.

    Args:
        leads: List of leads to export
        output_path: Output CSV file path

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"\n⏳ Exporting to CSV: {output_path}")

    if not leads:
        logger.warning("No leads to export")
        return False

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=leads[0].keys())
            writer.writeheader()
            writer.writerows(leads)

        logger.info(f"✓ Export complete: {len(leads)} leads")
        return True

    except Exception as e:
        logger.error(f"❌ Export error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        logger.error("❌ Usage: python verify_csv_direct.py <csv_file_path>")
        sys.exit(1)

    csv_path = sys.argv[1]

    logger.info("="*60)
    logger.info("🔍 Email Verification System (CSV)")
    logger.info("="*60)

    # Read leads from CSV
    leads = read_csv(csv_path)
    if not leads:
        logger.error("❌ No leads found in CSV")
        return

    # Extract emails
    # Try common column names for email
    email_columns = ['Email', 'email', 'EMAIL', 'Email Address', 'email_address']
    email_key = None

    for col in email_columns:
        if col in leads[0]:
            email_key = col
            break

    if not email_key:
        logger.error(f"❌ No email column found. Looking for one of: {email_columns}")
        logger.info(f"   Available columns: {list(leads[0].keys())}")
        return

    logger.info(f"📧 Found email column: '{email_key}'")

    # Filter leads with emails
    leads_with_emails = [l for l in leads if l.get(email_key, '').strip()]
    logger.info(f"📧 Leads with emails: {len(leads_with_emails)} / {len(leads)}")

    if not leads_with_emails:
        logger.error("❌ No leads with email addresses found")
        return

    # Get API key
    api_key = os.getenv("SSMASTERS_API_KEY")
    if not api_key:
        logger.error("❌ SSMASTERS_API_KEY not found in .env file")
        return

    # Verify emails
    emails = [l[email_key] for l in leads_with_emails]
    verification_results = verify_emails_batch(emails, api_key)

    if not verification_results:
        logger.error("❌ Verification failed")
        return

    # Add verification status to leads
    for lead in leads_with_emails:
        email = lead[email_key].strip().lower()
        lead['Verification Status'] = verification_results.get(email, 'Unknown')

    # Filter to VALID emails only
    valid_leads = [l for l in leads_with_emails if l['Verification Status'] == 'Valid']

    # Calculate stats
    valid_count = len(valid_leads)
    invalid_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Invalid')
    catchall_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Catch-All')
    unknown_count = sum(1 for l in leads_with_emails if l['Verification Status'] == 'Unknown')

    logger.info("\n" + "="*60)
    logger.info("📊 Verification Results")
    logger.info("="*60)
    logger.info(f"Total leads: {len(leads)}")
    logger.info(f"Leads with emails: {len(leads_with_emails)}")
    logger.info(f"✅ Valid: {valid_count} ({valid_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"⚠️  Catch-All: {catchall_count} ({catchall_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"❌ Invalid: {invalid_count} ({invalid_count/len(leads_with_emails)*100:.1f}%)")
    logger.info(f"❓ Unknown: {unknown_count}")
    logger.info("="*60)

    if not valid_leads:
        logger.warning("\n⚠️  No valid emails found. Nothing to export.")
        return

    # Export valid leads only
    base_name = os.path.splitext(csv_path)[0]
    output_path = f"{base_name}_VERIFIED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    success = export_to_csv(valid_leads, output_path)

    if success:
        logger.info("\n" + "="*60)
        logger.info("✓ SUCCESS!")
        logger.info("="*60)
        logger.info(f"📊 Exported {len(valid_leads)} valid emails")
        logger.info(f"📁 Output file: {output_path}")
        logger.info("="*60 + "\n")
    else:
        logger.error("❌ Export failed")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
