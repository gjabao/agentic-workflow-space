#!/usr/bin/env python3
"""
Instantly Webhook Server
Receives webhooks from Instantly and triggers workflows
"""

from flask import Flask, request, jsonify
import os
import json
import subprocess
from datetime import datetime

app = Flask(__name__)

# Webhook secret for verification
WEBHOOK_SECRET = os.getenv("INSTANTLY_WEBHOOK_SECRET", "")

@app.route('/webhook/instantly/reply', methods=['POST'])
def handle_reply():
    """
    Triggered when a lead replies to a campaign email.

    Webhook payload example:
    {
      "event": "lead.reply",
      "campaign_id": "...",
      "lead_email": "john@example.com",
      "reply_content": "...",
      "timestamp": "2025-12-23T10:00:00Z"
    }
    """
    try:
        # Verify webhook (optional but recommended)
        webhook_secret = request.headers.get('X-Instantly-Secret')
        if WEBHOOK_SECRET and webhook_secret != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

        # Parse payload
        data = request.json

        print(f"📨 New reply received!")
        print(f"   Campaign: {data.get('campaign_id')}")
        print(f"   Lead: {data.get('lead_email')}")
        print(f"   Reply: {data.get('reply_content', '')[:100]}...")

        # Save to file for processing
        os.makedirs('.tmp/webhooks', exist_ok=True)
        filename = f".tmp/webhooks/reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        # Trigger workflow: Categorize reply
        subprocess.Popen([
            'python',
            'execution/categorize_reply.py',
            '--reply-file', filename
        ])

        return jsonify({"status": "success", "message": "Reply processing triggered"}), 200

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/webhook/instantly/email-sent', methods=['POST'])
def handle_email_sent():
    """
    Triggered when an email is sent from a campaign.
    """
    try:
        data = request.json

        print(f"✉️  Email sent!")
        print(f"   Campaign: {data.get('campaign_id')}")
        print(f"   To: {data.get('lead_email')}")
        print(f"   Step: {data.get('step_number')}")

        # Log to tracking sheet
        # (You can add Google Sheets integration here)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/webhook/instantly/campaign-completed', methods=['POST'])
def handle_campaign_completed():
    """
    Triggered when a lead completes all steps in a campaign.
    """
    try:
        data = request.json

        print(f"✅ Lead completed campaign!")
        print(f"   Campaign: {data.get('campaign_id')}")
        print(f"   Lead: {data.get('lead_email')}")

        # Trigger workflow: Analyze completed leads
        subprocess.Popen([
            'python',
            'execution/analyze_completed_leads.py',
            '--campaign-id', data.get('campaign_id')
        ])

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/webhook/scrape-apify-leads', methods=['POST'])
def handle_scrape_apify_leads():
    """
    Webhook to trigger Apify lead scraping workflow.

    Webhook payload example:
    {
      "industry": "Marketing Agency",
      "fetch_count": 30,
      "location": "united states",
      "company_keywords": ["digital marketing", "PPC agency"],
      "job_title": ["CEO", "Founder"],
      "company_industry": ["marketing & advertising"],
      "skip_test": true,
      "valid_only": true,
      "sender_context": "We help marketing agencies scale their PPC campaigns"
    }
    """
    try:
        # Verify webhook secret if configured
        webhook_secret = request.headers.get('X-Webhook-Secret')
        if WEBHOOK_SECRET and webhook_secret != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

        # Parse payload
        data = request.json

        # Required fields
        industry = data.get('industry')
        fetch_count = data.get('fetch_count', 30)

        if not industry:
            return jsonify({"error": "Missing required field: industry"}), 400

        print(f"🚀 Apify lead scraping triggered via webhook!")
        print(f"   Industry: {industry}")
        print(f"   Fetch Count: {fetch_count}")
        print(f"   Location: {data.get('location', 'Not specified')}")
        print(f"   Valid Only: {data.get('valid_only', False)}")

        # Save webhook request for audit trail
        os.makedirs('.tmp/webhooks', exist_ok=True)
        filename = f".tmp/webhooks/scrape_request_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        # Build command to execute scrape_apify_leads.py
        cmd = [
            'python3',
            'execution/scrape_apify_leads.py',
            '--industry', industry,
            '--fetch_count', str(fetch_count)
        ]

        # Add optional parameters
        if data.get('location'):
            cmd.extend(['--location', data['location']])

        if data.get('city'):
            cmd.extend(['--city', data['city']])

        if data.get('job_title'):
            for title in data['job_title']:
                cmd.extend(['--job_title', title])

        if data.get('company_size'):
            for size in data['company_size']:
                cmd.extend(['--company_size', size])

        if data.get('company_keywords'):
            for keyword in data['company_keywords']:
                cmd.extend(['--company_keywords', keyword])

        if data.get('company_industry'):
            for ind in data['company_industry']:
                cmd.extend(['--company_industry', ind])

        if data.get('skip_test'):
            cmd.append('--skip_test')

        if data.get('valid_only'):
            cmd.append('--valid_only')

        if data.get('sender_context'):
            cmd.extend(['--sender_context', data['sender_context']])

        # Trigger scraping workflow in background
        print(f"   Executing: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return jsonify({
            "status": "success",
            "message": "Lead scraping workflow triggered",
            "industry": industry,
            "fetch_count": fetch_count,
            "request_file": filename,
            "process_id": process.pid
        }), 202  # 202 = Accepted (processing asynchronously)

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


if __name__ == '__main__':
    # For development
    app.run(host='0.0.0.0', port=5000, debug=True)

    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
