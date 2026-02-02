#!/usr/bin/env python3
"""
Extract partial enrichment results from log file
"""
import re
import csv
from datetime import datetime

log_file = ".tmp/enrich_leads.log"

# Parse log to extract decision-makers
decision_makers = []
current_company = None
current_website = None

with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        # Extract company name
        if "🏢 Company:" in line:
            current_company = line.split("🏢 Company:")[1].strip()

        # Extract website
        if "✓ Website from sheet:" in line:
            current_website = line.split("✓ Website from sheet:")[1].strip()

        # Extract decision-maker
        if "★ Found decision-maker:" in line:
            # Format: "★ Found decision-maker: Name (Title)"
            match = re.search(r'★ Found decision-maker: (.+?) \((.+?)\)', line)
            if match:
                full_name = match.group(1).strip()
                job_title = match.group(2).strip()

                # Split name
                name_parts = full_name.split()
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

                decision_makers.append({
                    'First Name': first_name,
                    'Last Name': last_name,
                    'Full Name': full_name,
                    'Job Title': job_title,
                    'Email': '',  # Not in logs
                    'LinkedIn URL': '',  # Not in logs
                    'Company Name': current_company or '',
                    'Company Website': current_website or '',
                    'Enrichment Date': datetime.now().strftime('%Y-%m-%d'),
                    'Source': 'Email-First Enrichment v2.0 (Partial)'
                })

# Export to CSV
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_filename = f"enriched_leads_partial_{timestamp}.csv"

if decision_makers:
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = decision_makers[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(decision_makers)

    print(f"✅ Exported {len(decision_makers)} decision-makers to {csv_filename}")
else:
    print("❌ No decision-makers found in logs")