#!/usr/bin/env python3
"""
Instantly Webhook Server
Receives webhooks from Instantly and triggers workflows
"""

from flask import Flask, request, jsonify
import os
import json
import re
import subprocess
import logging
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Webhook secret — REQUIRED. Server refuses to start without it.
WEBHOOK_SECRET = os.getenv("INSTANTLY_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError(
        "INSTANTLY_WEBHOOK_SECRET environment variable is required. "
        "Set it in .env before starting the webhook server."
    )

# Input validation limits
MAX_FETCH_COUNT = 50
MAX_STRING_LENGTH = 200
SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s&\-\.,\'\"()/:]+$')


def verify_webhook_auth():
    """Verify webhook secret from request headers. Returns error response or None."""
    secret = request.headers.get('X-Webhook-Secret') or request.headers.get('X-Instantly-Secret')
    if secret != WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook attempt from %s", request.remote_addr)
        return jsonify({"error": "Unauthorized"}), 401
    return None


def validate_string(value, field_name, max_length=MAX_STRING_LENGTH):
    """Validate a string parameter. Returns (cleaned_value, error_response)."""
    if not isinstance(value, str):
        return None, (jsonify({"error": f"{field_name} must be a string"}), 400)
    value = value.strip()
    if len(value) > max_length:
        return None, (jsonify({"error": f"{field_name} exceeds max length of {max_length}"}), 400)
    if not SAFE_STRING_PATTERN.match(value):
        return None, (jsonify({"error": f"{field_name} contains invalid characters"}), 400)
    return value, None


def validate_string_list(values, field_name, max_items=10):
    """Validate a list of strings. Returns (cleaned_list, error_response)."""
    if not isinstance(values, list):
        return None, (jsonify({"error": f"{field_name} must be a list"}), 400)
    if len(values) > max_items:
        return None, (jsonify({"error": f"{field_name} exceeds max {max_items} items"}), 400)
    cleaned = []
    for v in values:
        clean, err = validate_string(v, field_name)
        if err:
            return None, err
        cleaned.append(clean)
    return cleaned, None


@app.route('/webhook/instantly/reply', methods=['POST'])
def handle_reply():
    """Triggered when a lead replies to a campaign email."""
    auth_err = verify_webhook_auth()
    if auth_err:
        return auth_err

    try:
        data = request.json

        logger.info("New reply received — Campaign: %s, Lead: %s",
                     data.get('campaign_id'), data.get('lead_email'))

        # Save to file for processing
        os.makedirs('.tmp/webhooks', exist_ok=True)
        filename = f".tmp/webhooks/reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        # Trigger workflow: Categorize reply
        subprocess.Popen(
            ['python', 'execution/categorize_reply.py', '--reply-file', filename],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        return jsonify({"status": "success", "message": "Reply processing triggered"}), 200

    except Exception as e:
        logger.exception("Error processing reply webhook")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/webhook/instantly/email-sent', methods=['POST'])
def handle_email_sent():
    """Triggered when an email is sent from a campaign."""
    auth_err = verify_webhook_auth()
    if auth_err:
        return auth_err

    try:
        data = request.json

        logger.info("Email sent — Campaign: %s, To: %s, Step: %s",
                     data.get('campaign_id'), data.get('lead_email'), data.get('step_number'))

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.exception("Error processing email-sent webhook")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/webhook/instantly/campaign-completed', methods=['POST'])
def handle_campaign_completed():
    """Triggered when a lead completes all steps in a campaign."""
    auth_err = verify_webhook_auth()
    if auth_err:
        return auth_err

    try:
        data = request.json

        logger.info("Lead completed campaign — Campaign: %s, Lead: %s",
                     data.get('campaign_id'), data.get('lead_email'))

        # Validate campaign_id before passing to subprocess
        campaign_id = data.get('campaign_id', '')
        clean_id, err = validate_string(campaign_id, 'campaign_id', max_length=100)
        if err:
            return err

        subprocess.Popen(
            ['python', 'execution/analyze_completed_leads.py', '--campaign-id', clean_id],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.exception("Error processing campaign-completed webhook")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/webhook/scrape-apify-leads', methods=['POST'])
def handle_scrape_apify_leads():
    """Webhook to trigger Apify lead scraping workflow."""
    auth_err = verify_webhook_auth()
    if auth_err:
        return auth_err

    try:
        data = request.json

        # Validate required field: industry
        industry = data.get('industry')
        if not industry:
            return jsonify({"error": "Missing required field: industry"}), 400
        industry, err = validate_string(industry, 'industry', max_length=100)
        if err:
            return err

        # Validate and cap fetch_count
        try:
            fetch_count = int(data.get('fetch_count', 30))
            fetch_count = max(1, min(fetch_count, MAX_FETCH_COUNT))
        except (ValueError, TypeError):
            fetch_count = 30

        logger.info("Apify lead scraping triggered — Industry: %s, Count: %d, Location: %s",
                     industry, fetch_count, data.get('location', 'N/A'))

        # Save webhook request for audit trail
        os.makedirs('.tmp/webhooks', exist_ok=True)
        filename = f".tmp/webhooks/scrape_request_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        # Build command with validated inputs
        cmd = [
            'python3',
            'execution/scrape_apify_leads.py',
            '--industry', industry,
            '--fetch_count', str(fetch_count)
        ]

        # Validate and add optional string parameters
        for param_name, flag in [('location', '--location'), ('city', '--city'), ('sender_context', '--sender_context')]:
            if data.get(param_name):
                clean_val, err = validate_string(data[param_name], param_name)
                if err:
                    return err
                cmd.extend([flag, clean_val])

        # Validate and add optional list parameters
        for param_name, flag in [('job_title', '--job_title'), ('company_size', '--company_size'),
                                  ('company_keywords', '--company_keywords'), ('company_industry', '--company_industry')]:
            if data.get(param_name):
                clean_list, err = validate_string_list(data[param_name], param_name)
                if err:
                    return err
                for item in clean_list:
                    cmd.extend([flag, item])

        # Boolean flags
        if data.get('skip_test'):
            cmd.append('--skip_test')
        if data.get('valid_only'):
            cmd.append('--valid_only')

        # Trigger scraping workflow in background
        logger.info("Executing scrape command for industry=%s, count=%d", industry, fetch_count)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return jsonify({
            "status": "success",
            "message": "Lead scraping workflow triggered",
            "industry": industry,
            "fetch_count": fetch_count,
            "request_file": filename,
            "process_id": process.pid
        }), 202

    except Exception as e:
        logger.exception("Error processing scrape webhook")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


if __name__ == '__main__':
    # Development: localhost only, debug OFF
    app.run(host='127.0.0.1', port=5000, debug=False)

    # Production: use gunicorn
    # gunicorn -w 4 -b 0.0.0.0:5000 webhook_server:app
