"""
Modal Cloud Workflow: Daily Campaign Report
Sends daily Instantly campaign performance report via Gmail

Deployment:
    modal deploy modal_workflows/email_campaign_report.py

Manual Run:
    modal run modal_workflows/email_campaign_report.py

View Logs:
    modal app logs anti-gravity-workflows
"""

import modal
import os
import json
import requests
import base64
from email.message import EmailMessage
from datetime import datetime

# Create Modal app
app = modal.App("anti-gravity-workflows")

# Define container image with required dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(
        "requests",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib"
    )
)

@app.function(
    image=image,
    schedule=modal.Cron("0 0 * * *"),  # Midnight UTC = 7 AM Hanoi time
    secrets=[modal.Secret.from_name("anti-gravity-secrets")],
    timeout=600  # 10 minutes max
)
def daily_campaign_report():
    """
    Fetch Instantly campaigns and send performance report via Gmail API

    Required secrets in Modal (modal.com/secrets):
    - INSTANTLY_API_KEY: Your Instantly API key
    - GMAIL_CREDENTIALS_JSON: OAuth credentials.json content
    - GMAIL_TOKEN_JSON: OAuth token.json content (after first auth)
    - REPORT_EMAIL: Email to send reports to (default: giabaongb0305@gmail.com)
    """

    print(f"🔍 Starting daily campaign report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        # Initialize reporter
        reporter = EmailReporter()

        # Fetch active campaigns
        campaigns = reporter.get_active_campaigns_analytics()

        if not campaigns:
            print("⚠️ No active campaigns found")
            return

        print(f"✓ Found {len(campaigns)} active campaigns")

        # Analyze each campaign
        campaigns_data = []
        for campaign in campaigns:
            result = reporter.analyze_campaign(campaign)
            if result:
                campaigns_data.append(result)

        if not campaigns_data:
            print("ℹ️ No campaign data to report")
            return

        # Generate HTML email
        html_content = reporter.generate_html_email(campaigns_data)

        # Create subject line with summary
        critical = sum(1 for c in campaigns_data if '🚨' in c['health'])
        excellent = sum(1 for c in campaigns_data if '🎉' in c['health'])

        if critical > 0:
            subject = f"🚨 Instantly Report: {critical} Critical Issue(s) - {datetime.now().strftime('%b %d')}"
        elif excellent > 0:
            subject = f"🎉 Instantly Report: {excellent} Winner(s) - {datetime.now().strftime('%b %d')}"
        else:
            subject = f"📊 Instantly Daily Report - {datetime.now().strftime('%b %d')}"

        # Send email
        success = reporter.send_email(html_content, subject)

        if success:
            print("✅ Daily report sent successfully!")
        else:
            print("❌ Failed to send daily report")

    except Exception as e:
        print(f"❌ Error in daily_campaign_report: {e}")
        import traceback
        traceback.print_exc()
        raise


class EmailReporter:
    """Sends campaign performance reports via email"""

    def __init__(self):
        self.api_key = os.environ.get('INSTANTLY_API_KEY')
        self.report_recipient = os.environ.get('REPORT_EMAIL', 'giabaongb0305@gmail.com')

        if not self.api_key:
            raise ValueError("INSTANTLY_API_KEY not found in Modal secrets")

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        self.gmail_service = None

    def get_active_campaigns_analytics(self):
        """Fetch analytics for active campaigns only"""
        try:
            response = requests.get(
                'https://api.instantly.ai/api/v2/campaigns/analytics',
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            campaigns = response.json()

            # Filter for active campaigns
            active_campaigns = []

            for campaign in campaigns:
                campaign_id = campaign.get('campaign_id')
                try:
                    detail_response = requests.get(
                        f'https://api.instantly.ai/api/v2/campaigns/{campaign_id}',
                        headers=self.headers,
                        timeout=10
                    )
                    if detail_response.status_code == 200:
                        details = detail_response.json()
                        status = details.get('status')
                        # Status 1 = Active, 2 = Paused
                        if status in [1, 2]:
                            campaign['status'] = status
                            campaign['status_text'] = 'Active' if status == 1 else 'Paused'
                            active_campaigns.append(campaign)
                except:
                    campaign['status'] = None
                    campaign['status_text'] = 'Unknown'
                    active_campaigns.append(campaign)

            return active_campaigns

        except Exception as e:
            print(f"❌ Error fetching analytics: {e}")
            return []

    def analyze_campaign(self, campaign):
        """Analyze campaign and return summary"""
        campaign_name = campaign.get('campaign_name', 'Unknown')
        status_text = campaign.get('status_text', 'Unknown')
        leads_count = campaign.get('leads_count', 0)
        emails_sent = campaign.get('emails_sent_count', 0)
        replies_unique = campaign.get('reply_count_unique', 0)
        replies_auto = campaign.get('reply_count_automatic_unique', 0)
        bounced = campaign.get('bounced_count', 0)
        opportunities = campaign.get('total_opportunities', 0)

        # Skip if no activity
        if emails_sent == 0 or leads_count == 0:
            return None

        # Calculate metrics
        real_replies = replies_unique - replies_auto
        real_reply_rate = (real_replies / leads_count * 100) if leads_count > 0 else 0
        bounce_rate = (bounced / emails_sent * 100) if emails_sent > 0 else 0
        opp_rate = (opportunities / leads_count * 100) if leads_count > 0 else 0

        # Determine health status
        if bounce_rate > 5:
            health = '🚨 Critical'
        elif real_reply_rate < 1 and emails_sent > 100:
            health = '⚠️ Warning'
        elif real_reply_rate >= 3:
            health = '🎉 Excellent'
        else:
            health = '✅ Healthy'

        return {
            'name': campaign_name,
            'status': status_text,
            'health': health,
            'leads': leads_count,
            'sent': emails_sent,
            'reply_rate': round(real_reply_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'opportunities': opportunities,
            'opp_rate': round(opp_rate, 2)
        }

    def generate_html_email(self, campaigns_data):
        """Generate beautiful HTML email report"""
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')

        # Count health statuses
        critical = sum(1 for c in campaigns_data if '🚨' in c['health'])
        warnings = sum(1 for c in campaigns_data if '⚠️' in c['health'])
        excellent = sum(1 for c in campaigns_data if '🎉' in c['health'])
        healthy = sum(1 for c in campaigns_data if '✅' in c['health'])

        # Sort by health (critical first)
        campaigns_data.sort(key=lambda x: (
            0 if '🚨' in x['health'] else
            1 if '⚠️' in x['health'] else
            2 if '🎉' in x['health'] else 3
        ))

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 24px;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .summary {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .summary-card {{
            flex: 1;
            min-width: 150px;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .summary-card.critical {{ background-color: #fee; border-left: 4px solid #e74c3c; }}
        .summary-card.warning {{ background-color: #fff3cd; border-left: 4px solid #f39c12; }}
        .summary-card.excellent {{ background-color: #d4edda; border-left: 4px solid #27ae60; }}
        .summary-card.healthy {{ background-color: #e8f4f8; border-left: 4px solid #3498db; }}
        .summary-card .number {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .summary-card .label {{
            font-size: 12px;
            text-transform: uppercase;
            color: #7f8c8d;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #ecf0f1;
            font-size: 13px;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .metric-good {{ color: #27ae60; font-weight: 600; }}
        .metric-warning {{ color: #f39c12; font-weight: 600; }}
        .metric-bad {{ color: #e74c3c; font-weight: 600; }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .status-active {{ background-color: #d4edda; color: #155724; }}
        .status-paused {{ background-color: #fff3cd; color: #856404; }}
        .cloud-badge {{
            background-color: #e8f4f8;
            color: #3498db;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            margin-left: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Instantly Campaign Performance Report <span class="cloud-badge">☁️ Modal Cloud</span></h1>
        <div class="timestamp">{timestamp}</div>

        <div class="summary">
            <div class="summary-card critical">
                <div class="number">{critical}</div>
                <div class="label">🚨 Critical</div>
            </div>
            <div class="summary-card warning">
                <div class="number">{warnings}</div>
                <div class="label">⚠️ Warnings</div>
            </div>
            <div class="summary-card excellent">
                <div class="number">{excellent}</div>
                <div class="label">🎉 Excellent</div>
            </div>
            <div class="summary-card healthy">
                <div class="number">{healthy}</div>
                <div class="label">✅ Healthy</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Campaign</th>
                    <th>Status</th>
                    <th>Health</th>
                    <th>Leads</th>
                    <th>Sent</th>
                    <th>Reply %</th>
                    <th>Bounce %</th>
                    <th>Opps</th>
                </tr>
            </thead>
            <tbody>
"""

        for campaign in campaigns_data:
            # Color code metrics
            reply_class = 'metric-good' if campaign['reply_rate'] >= 2 else 'metric-warning' if campaign['reply_rate'] >= 1 else 'metric-bad'
            bounce_class = 'metric-good' if campaign['bounce_rate'] < 2 else 'metric-warning' if campaign['bounce_rate'] < 5 else 'metric-bad'

            status_badge = f'<span class="status-active">Active</span>' if campaign['status'] == 'Active' else f'<span class="status-paused">Paused</span>'

            html += f"""
                <tr>
                    <td><strong>{campaign['name']}</strong></td>
                    <td>{status_badge}</td>
                    <td>{campaign['health']}</td>
                    <td>{campaign['leads']:,}</td>
                    <td>{campaign['sent']:,}</td>
                    <td class="{reply_class}">{campaign['reply_rate']}%</td>
                    <td class="{bounce_class}">{campaign['bounce_rate']}%</td>
                    <td>{campaign['opportunities']}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <div class="footer">
            <p><strong>Legend:</strong></p>
            <p>🚨 Critical: High bounce rate (>5%) | ⚠️ Warning: Low reply rate (<1%) | 🎉 Excellent: Reply rate >3% | ✅ Healthy: Normal</p>
            <p style="margin-top: 20px;">Generated by Anti-Gravity Workflow Automation • Running on Modal Cloud ☁️</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def get_gmail_service(self):
        """Build Gmail API service from Modal secrets"""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        # Load credentials from Modal secrets
        credentials_json = os.environ.get('GMAIL_CREDENTIALS_JSON')
        token_json = os.environ.get('GMAIL_TOKEN_JSON')

        if not credentials_json or not token_json:
            raise ValueError(
                "Gmail credentials not found in Modal secrets. "
                "Please add GMAIL_CREDENTIALS_JSON and GMAIL_TOKEN_JSON to Modal secrets."
            )

        # Parse credentials
        creds_data = json.loads(credentials_json)
        token_data = json.loads(token_json)

        # Create credentials object
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )

        return build('gmail', 'v1', credentials=creds)

    def send_email(self, html_content, subject):
        """Send email via Gmail API"""
        try:
            if not self.gmail_service:
                print("🔐 Building Gmail API service...")
                self.gmail_service = self.get_gmail_service()

            # Create message
            message = EmailMessage()
            message.set_content("Please view this email in HTML format.", subtype='plain')
            message.add_alternative(html_content, subtype='html')
            message['To'] = self.report_recipient
            message['Subject'] = subject

            # Encode message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            # Send email
            print(f"📨 Sending email to {self.report_recipient}...")
            sent_message = self.gmail_service.users().messages().send(
                userId='me',
                body=create_message
            ).execute()

            print(f"✅ Email sent! Message ID: {sent_message['id']}")
            return True

        except Exception as e:
            print(f"❌ Error sending email: {e}")
            import traceback
            traceback.print_exc()
            return False


# For manual testing
@app.local_entrypoint()
def main():
    """Run manually: modal run modal_workflows/email_campaign_report.py"""
    daily_campaign_report.remote()
