#!/usr/bin/env python3
"""
Single Campaign Analytics Report
Analyzes and sends report for one specific campaign
"""

import os
import sys
import json
import requests
import base64
from email.message import EmailMessage
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

class SingleCampaignReporter:
    """Sends report for a single campaign"""

    def __init__(self, campaign_identifier):
        self.campaign_identifier = campaign_identifier
        self.campaign_id = None
        self.api_key = os.getenv('INSTANTLY_API_KEY')
        self.report_recipient = os.getenv('REPORT_EMAIL', os.getenv('GMAIL_USER', 'giabaongb0305@gmail.com'))

        if not self.api_key:
            raise ValueError("INSTANTLY_API_KEY not found in .env")

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        self.gmail_service = None

    def get_campaign_analytics(self):
        """Fetch analytics for specific campaign by ID or name"""
        try:
            # Get all campaigns analytics
            response = requests.get(
                'https://api.instantly.ai/api/v2/campaigns/analytics',
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            campaigns = response.json()

            # Find our campaign by ID or name (case-insensitive partial match)
            campaign = None
            matched_campaigns = []

            for c in campaigns:
                # Exact ID match
                if c.get('campaign_id') == self.campaign_identifier:
                    campaign = c
                    break
                # Partial name match (case-insensitive)
                campaign_name = c.get('campaign_name', '').lower()
                search_term = self.campaign_identifier.lower()
                if search_term in campaign_name:
                    matched_campaigns.append(c)

            # If no exact ID match, use name matches
            if not campaign:
                if len(matched_campaigns) == 0:
                    print(f"❌ No campaign found matching: {self.campaign_identifier}")
                    print(f"\n💡 Available campaigns:")
                    for c in campaigns[:10]:  # Show first 10
                        print(f"   - {c.get('campaign_name')} (ID: {c.get('campaign_id')})")
                    return None
                elif len(matched_campaigns) == 1:
                    campaign = matched_campaigns[0]
                    print(f"✓ Found campaign by name: {campaign.get('campaign_name')}")
                else:
                    print(f"❌ Multiple campaigns match '{self.campaign_identifier}':")
                    for c in matched_campaigns:
                        print(f"   - {c.get('campaign_name')} (ID: {c.get('campaign_id')})")
                    print(f"\n💡 Please use the exact campaign ID or a more specific name")
                    return None

            # Store the campaign ID for later use
            self.campaign_id = campaign.get('campaign_id')

            if not campaign:
                print(f"❌ Campaign '{self.campaign_identifier}' not found")
                return None

            # Get campaign details
            detail_response = requests.get(
                f'https://api.instantly.ai/api/v2/campaigns/{self.campaign_id}',
                headers=self.headers,
                timeout=10
            )

            if detail_response.status_code == 200:
                details = detail_response.json()
                campaign['status'] = details.get('status')
                campaign['status_text'] = 'Active' if details.get('status') == 1 else 'Paused' if details.get('status') == 2 else 'Stopped'
                campaign['created_at'] = details.get('created_at', '')
            else:
                campaign['status'] = None
                campaign['status_text'] = 'Unknown'

            return campaign

        except Exception as e:
            print(f"❌ Error fetching campaign: {e}")
            return None

    def analyze_campaign(self, campaign):
        """Analyze campaign and return detailed summary"""
        campaign_name = campaign.get('campaign_name', 'Unknown')
        status_text = campaign.get('status_text', 'Unknown')
        leads_count = campaign.get('leads_count', 0)
        emails_sent = campaign.get('emails_sent_count', 0)
        replies_unique = campaign.get('reply_count_unique', 0)
        replies_auto = campaign.get('reply_count_automatic_unique', 0)
        bounced = campaign.get('bounced_count', 0)
        opportunities = campaign.get('total_opportunities', 0)
        opened = campaign.get('opened_count', 0)
        clicked = campaign.get('clicked_count', 0)

        # Calculate metrics
        real_replies = replies_unique - replies_auto
        real_reply_rate = (real_replies / leads_count * 100) if leads_count > 0 else 0
        bounce_rate = (bounced / emails_sent * 100) if emails_sent > 0 else 0
        opp_rate = (opportunities / leads_count * 100) if leads_count > 0 else 0
        open_rate = (opened / emails_sent * 100) if emails_sent > 0 else 0
        click_rate = (clicked / emails_sent * 100) if emails_sent > 0 else 0

        # Determine health
        if bounce_rate > 5:
            health = '🚨 Critical'
            health_desc = 'High bounce rate indicates deliverability issues'
        elif real_reply_rate < 1 and emails_sent > 100:
            health = '⚠️ Warning'
            health_desc = 'Low engagement - consider revising copy or targeting'
        elif real_reply_rate >= 3:
            health = '🎉 Excellent'
            health_desc = 'Strong performance - keep it up!'
        else:
            health = '✅ Healthy'
            health_desc = 'Normal performance'

        return {
            'name': campaign_name,
            'id': campaign.get('campaign_id'),
            'status': status_text,
            'health': health,
            'health_desc': health_desc,
            'leads': leads_count,
            'sent': emails_sent,
            'replies_total': replies_unique,
            'replies_real': real_replies,
            'replies_auto': replies_auto,
            'reply_rate': round(real_reply_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'bounced': bounced,
            'opportunities': opportunities,
            'opp_rate': round(opp_rate, 2),
            'opened': opened,
            'open_rate': round(open_rate, 2),
            'clicked': clicked,
            'click_rate': round(click_rate, 2),
            'created_at': campaign.get('created_at', '')
        }

    def generate_html_email(self, data):
        """Generate detailed HTML email for single campaign"""
        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')

        # Color classes for metrics
        reply_class = 'metric-good' if data['reply_rate'] >= 2 else 'metric-warning' if data['reply_rate'] >= 1 else 'metric-bad'
        bounce_class = 'metric-good' if data['bounce_rate'] < 2 else 'metric-warning' if data['bounce_rate'] < 5 else 'metric-bad'
        open_class = 'metric-good' if data['open_rate'] >= 20 else 'metric-warning' if data['open_rate'] >= 10 else 'metric-bad'

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
            max-width: 700px;
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
            margin-bottom: 5px;
            font-size: 26px;
        }}
        .campaign-id {{
            color: #7f8c8d;
            font-size: 12px;
            font-family: monospace;
            margin-bottom: 10px;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .health-banner {{
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .health-banner.critical {{ background-color: #fee; border: 2px solid #e74c3c; }}
        .health-banner.warning {{ background-color: #fff3cd; border: 2px solid #f39c12; }}
        .health-banner.excellent {{ background-color: #d4edda; border: 2px solid #27ae60; }}
        .health-banner.healthy {{ background-color: #e8f4f8; border: 2px solid #3498db; }}
        .health-banner h2 {{
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        .health-banner p {{
            margin: 0;
            font-size: 14px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        .status-active {{ background-color: #d4edda; color: #155724; }}
        .status-paused {{ background-color: #fff3cd; color: #856404; }}
        .status-stopped {{ background-color: #f8d7da; color: #721c24; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        .metric-card .value {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .metric-card .subvalue {{
            font-size: 14px;
            color: #7f8c8d;
        }}
        .metric-good {{ color: #27ae60; }}
        .metric-warning {{ color: #f39c12; }}
        .metric-bad {{ color: #e74c3c; }}
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
            font-size: 14px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }}
        @media (max-width: 600px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Campaign Performance Report</h1>
        <div class="campaign-id">Campaign ID: {data['id']}</div>
        <div class="timestamp">{timestamp}</div>

        <h2 style="margin-bottom: 10px;">{data['name']}</h2>
        <span class="status-badge status-{data['status'].lower()}">{data['status']}</span>

        <div class="health-banner {data['health'].split()[1].lower() if len(data['health'].split()) > 1 else 'healthy'}">
            <h2>{data['health']}</h2>
            <p>{data['health_desc']}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>📧 Emails Sent</h3>
                <div class="value">{data['sent']:,}</div>
                <div class="subvalue">out of {data['leads']:,} leads</div>
            </div>

            <div class="metric-card">
                <h3>💬 Reply Rate</h3>
                <div class="value {reply_class}">{data['reply_rate']}%</div>
                <div class="subvalue">{data['replies_real']} real replies ({data['replies_total']} total - {data['replies_auto']} auto)</div>
            </div>

            <div class="metric-card">
                <h3>📊 Open Rate</h3>
                <div class="value {open_class}">{data['open_rate']}%</div>
                <div class="subvalue">{data['opened']:,} opens</div>
            </div>

            <div class="metric-card">
                <h3>⚡ Bounce Rate</h3>
                <div class="value {bounce_class}">{data['bounce_rate']}%</div>
                <div class="subvalue">{data['bounced']} bounced</div>
            </div>

            <div class="metric-card">
                <h3>🎯 Opportunities</h3>
                <div class="value">{data['opportunities']}</div>
                <div class="subvalue">{data['opp_rate']}% conversion</div>
            </div>

            <div class="metric-card">
                <h3>🖱️ Click Rate</h3>
                <div class="value">{data['click_rate']}%</div>
                <div class="subvalue">{data['clicked']} clicks</div>
            </div>
        </div>

        <h3>📈 Detailed Breakdown</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Percentage</th>
            </tr>
            <tr>
                <td><strong>Total Leads</strong></td>
                <td>{data['leads']:,}</td>
                <td>100%</td>
            </tr>
            <tr>
                <td>Emails Sent</td>
                <td>{data['sent']:,}</td>
                <td>{(data['sent']/data['leads']*100) if data['leads'] > 0 else 0:.1f}%</td>
            </tr>
            <tr>
                <td>Opened</td>
                <td>{data['opened']:,}</td>
                <td class="{open_class}">{data['open_rate']}%</td>
            </tr>
            <tr>
                <td>Clicked</td>
                <td>{data['clicked']}</td>
                <td>{data['click_rate']}%</td>
            </tr>
            <tr>
                <td>Replied (Real)</td>
                <td>{data['replies_real']}</td>
                <td class="{reply_class}">{data['reply_rate']}%</td>
            </tr>
            <tr>
                <td>Replied (Auto-detected)</td>
                <td>{data['replies_auto']}</td>
                <td>{(data['replies_auto']/data['leads']*100) if data['leads'] > 0 else 0:.2f}%</td>
            </tr>
            <tr>
                <td>Opportunities</td>
                <td>{data['opportunities']}</td>
                <td>{data['opp_rate']}%</td>
            </tr>
            <tr>
                <td style="color: #e74c3c;">Bounced</td>
                <td>{data['bounced']}</td>
                <td class="{bounce_class}">{data['bounce_rate']}%</td>
            </tr>
        </table>

        <div class="footer">
            <p><strong>Benchmarks:</strong></p>
            <p>Reply Rate: <span class="metric-good">Good ≥2%</span> | <span class="metric-warning">Warning 1-2%</span> | <span class="metric-bad">Poor &lt;1%</span></p>
            <p>Bounce Rate: <span class="metric-good">Good &lt;2%</span> | <span class="metric-warning">Warning 2-5%</span> | <span class="metric-bad">Critical &gt;5%</span></p>
            <p style="margin-top: 20px;">Generated by Instantly Workflow Automation</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def get_gmail_credentials(self):
        """Get Google OAuth credentials"""
        creds = None
        if os.path.exists('token.json'):
            try:
                with open('token.json', 'r') as f:
                    token_data = json.load(f)
                current_scopes = token_data.get('scopes', [])
                if 'https://www.googleapis.com/auth/gmail.compose' not in current_scopes:
                    creds = None
                else:
                    creds = Credentials(
                        token=token_data.get('token'),
                        refresh_token=token_data.get('refresh_token'),
                        token_uri=token_data.get('token_uri'),
                        client_id=token_data.get('client_id'),
                        client_secret=token_data.get('client_secret'),
                        scopes=token_data.get('scopes')
                    )
            except Exception as e:
                print(f"⚠️  Error loading token: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not os.path.exists('credentials.json'):
                    print("❌ credentials.json not found")
                    sys.exit(1)
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return creds

    def send_email(self, html_content, subject):
        """Send email via Gmail API"""
        try:
            if not self.gmail_service:
                print(f"🔐 Authenticating with Gmail...")
                creds = self.get_gmail_credentials()
                self.gmail_service = build('gmail', 'v1', credentials=creds)

            message = EmailMessage()
            message.set_content("Please view this email in HTML format.", subtype='plain')
            message.add_alternative(html_content, subtype='html')
            message['To'] = self.report_recipient
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            print(f"📨 Sending to {self.report_recipient}...")
            sent_message = self.gmail_service.users().messages().send(
                userId='me',
                body=create_message
            ).execute()

            print(f"✅ Email sent! Message ID: {sent_message['id']}")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Generate and send report"""
        print(f"\n🔍 Searching for campaign: {self.campaign_identifier}...\n")

        campaign = self.get_campaign_analytics()
        if not campaign:
            return False

        print(f"✓ Found campaign: {campaign.get('campaign_name')}\n")

        data = self.analyze_campaign(campaign)
        html_content = self.generate_html_email(data)

        subject = f"{data['health']} Campaign Report: {data['name']} - {datetime.now().strftime('%b %d')}"

        success = self.send_email(html_content, subject)

        if success:
            os.makedirs('.tmp/email_reports', exist_ok=True)
            filename = f".tmp/email_reports/single_report_{self.campaign_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(filename, 'w') as f:
                f.write(html_content)
            print(f"✓ Copy saved: {filename}\n")

        return success

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 single_campaign_report.py <campaign_id_or_name>")
        print("\nExamples:")
        print("  python3 single_campaign_report.py ef76771a-880c-426e-abc8-f6c30e70dde2")
        print("  python3 single_campaign_report.py 'IT Recruitment'")
        print("  python3 single_campaign_report.py healthcare")
        sys.exit(1)

    # Join all arguments to support campaign names with spaces
    campaign_identifier = ' '.join(sys.argv[1:])

    try:
        reporter = SingleCampaignReporter(campaign_identifier)
        success = reporter.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
