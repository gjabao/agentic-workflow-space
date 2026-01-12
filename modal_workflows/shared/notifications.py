"""
Notification helpers for Modal workflows
Supports Email (Gmail), Slack, and other channels
"""

import os
import base64
from email.message import EmailMessage
from .google_auth import get_gmail_service


def send_email_via_gmail(to, subject, html_content, plain_text=None):
    """
    Send email via Gmail API

    Args:
        to: Recipient email address
        subject: Email subject
        html_content: HTML email body
        plain_text: Plain text fallback (optional)

    Returns:
        bool: True if sent successfully
    """
    try:
        gmail_service = get_gmail_service()

        # Create message
        message = EmailMessage()

        if plain_text:
            message.set_content(plain_text, subtype='plain')
        else:
            message.set_content("Please view this email in HTML format.", subtype='plain')

        message.add_alternative(html_content, subtype='html')
        message['To'] = to
        message['Subject'] = subject

        # Encode message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        # Send email
        print(f"📨 Sending email to {to}...")
        sent_message = gmail_service.users().messages().send(
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


def send_slack_notification(message, webhook_url=None, channel=None):
    """
    Send notification to Slack

    Args:
        message: Message to send (supports markdown)
        webhook_url: Slack webhook URL (optional, uses SLACK_WEBHOOK_URL from secrets)
        channel: Override channel (optional)

    Returns:
        bool: True if sent successfully
    """
    import requests

    webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')

    if not webhook_url:
        print("⚠️ SLACK_WEBHOOK_URL not found in Modal secrets")
        return False

    try:
        payload = {
            "text": message,
        }

        if channel:
            payload["channel"] = channel

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()

        print("✅ Slack notification sent")
        return True

    except Exception as e:
        print(f"❌ Error sending Slack notification: {e}")
        return False


def send_telegram_notification(message, bot_token=None, chat_id=None):
    """
    Send notification to Telegram

    Args:
        message: Message to send (supports markdown)
        bot_token: Telegram bot token (optional, uses TELEGRAM_BOT_TOKEN from secrets)
        chat_id: Telegram chat ID (optional, uses TELEGRAM_CHAT_ID from secrets)

    Returns:
        bool: True if sent successfully
    """
    import requests

    bot_token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in Modal secrets")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        print("✅ Telegram notification sent")
        return True

    except Exception as e:
        print(f"❌ Error sending Telegram notification: {e}")
        return False


def send_multi_channel_alert(message, subject=None, email_to=None):
    """
    Send alert to multiple channels (Email, Slack, Telegram)

    Args:
        message: Message to send
        subject: Email subject (optional, defaults to message first line)
        email_to: Email recipient (optional, uses REPORT_EMAIL from secrets)

    Returns:
        dict: Results for each channel
    """
    results = {}

    # Email
    if not email_to:
        email_to = os.environ.get('REPORT_EMAIL')

    if email_to:
        if not subject:
            subject = message.split('\n')[0][:100]

        html = f"<html><body><pre>{message}</pre></body></html>"
        results['email'] = send_email_via_gmail(email_to, subject, html, message)

    # Slack
    if os.environ.get('SLACK_WEBHOOK_URL'):
        results['slack'] = send_slack_notification(message)

    # Telegram
    if os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'):
        results['telegram'] = send_telegram_notification(message)

    return results
