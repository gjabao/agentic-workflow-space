#!/usr/bin/env python3
"""
Quick CSV Analysis - Shows stats without verification
"""

import csv
import sys
from collections import Counter

def analyze_csv(file_path):
    print("="*60)
    print("📊 CSV File Analysis")
    print("="*60)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leads = list(reader)

        print(f"✓ Total records: {len(leads)}")

        if not leads:
            print("❌ No data found")
            return

        # Column analysis
        print(f"\n📋 Columns ({len(leads[0].keys())} total):")
        for col in leads[0].keys():
            print(f"   - {col}")

        # Email analysis
        if 'Email' in leads[0]:
            emails = [l['Email'] for l in leads if l.get('Email', '').strip()]
            print(f"\n📧 Email Statistics:")
            print(f"   - Records with emails: {len(emails)}")
            print(f"   - Unique emails: {len(set(emails))}")
            print(f"   - Duplicates: {len(emails) - len(set(emails))}")

            # Email providers
            providers = Counter()
            for email in emails:
                if '@' in email:
                    domain = email.split('@')[1].lower()
                    providers[domain] += 1

            print(f"\n📮 Top Email Domains:")
            for domain, count in providers.most_common(10):
                print(f"   - {domain}: {count}")

        # Email Provider column analysis
        if 'Email Provider' in leads[0]:
            provider_stats = Counter(l['Email Provider'] for l in leads)
            print(f"\n🔐 Email Provider Distribution:")
            for provider, count in provider_stats.most_common():
                pct = (count/len(leads))*100
                print(f"   - {provider}: {count} ({pct:.1f}%)")

        # Lead Status
        if 'Lead Status' in leads[0]:
            status_stats = Counter(l['Lead Status'] for l in leads)
            print(f"\n📊 Lead Status:")
            for status, count in status_stats.most_common():
                print(f"   - {status}: {count}")

        # Location analysis
        if 'location' in leads[0]:
            locations = [l['location'] for l in leads if l.get('location', '').strip()]
            location_stats = Counter(locations)
            print(f"\n🌍 Top Locations:")
            for loc, count in location_stats.most_common(10):
                print(f"   - {loc}: {count}")

        # Company Industry
        if 'Company Industry' in leads[0]:
            industries = [l['Company Industry'] for l in leads if l.get('Company Industry', '').strip()]
            industry_stats = Counter(industries)
            print(f"\n🏢 Top Industries:")
            for ind, count in industry_stats.most_common(10):
                print(f"   - {ind}: {count}")

        # Email Security Gateway
        if 'Email Security Gateway Provider' in leads[0]:
            gateway_stats = Counter(l['Email Security Gateway Provider'] for l in leads)
            print(f"\n🛡️ Email Security Gateways:")
            for gateway, count in gateway_stats.most_common():
                pct = (count/len(leads))*100
                print(f"   - {gateway}: {count} ({pct:.1f}%)")

        print("\n" + "="*60)
        print("✓ Analysis Complete")
        print("="*60)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python quick_csv_analysis.py <csv_file>")
        sys.exit(1)

    analyze_csv(sys.argv[1])
