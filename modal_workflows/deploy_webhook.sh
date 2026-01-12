#!/bin/bash
# Quick deployment script for Modal webhook

echo "🚀 Deploying Apify Lead Scraping Webhook to Modal..."
echo ""

# Check if Modal CLI is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Installing..."
    pip install modal
fi

# Check if user is authenticated
if ! modal token current &> /dev/null; then
    echo "❌ Not authenticated with Modal."
    echo "   Run: modal token new"
    exit 1
fi

# Check if secrets are configured
if ! modal secret list 2>/dev/null | grep -q "anti-gravity-secrets"; then
    echo "⚠️  Modal secret 'anti-gravity-secrets' not found."
    echo ""
    echo "   Creating secret now..."
    echo ""

    # Prompt for API keys
    read -p "Enter APIFY_API_KEY: " APIFY_KEY
    read -p "Enter WEBHOOK_SECRET (optional, press Enter to skip): " WEBHOOK_SECRET

    if [ -z "$WEBHOOK_SECRET" ]; then
        modal secret create anti-gravity-secrets \
            APIFY_API_KEY="$APIFY_KEY"
    else
        modal secret create anti-gravity-secrets \
            APIFY_API_KEY="$APIFY_KEY" \
            WEBHOOK_SECRET="$WEBHOOK_SECRET"
    fi

    echo "✅ Secret created!"
    echo ""
fi

# Deploy the webhook
echo "📦 Deploying webhook to Modal..."
echo ""

modal deploy modal_workflows/webhook_scrape_apify.py

if [ $? -eq 0 ]; then
    echo ""
    echo "="*60
    echo "✅ Webhook deployed successfully!"
    echo "="*60
    echo ""
    echo "📋 Next steps:"
    echo ""
    echo "1️⃣  Get your webhook URL:"
    echo "   modal app list | grep anti-gravity-webhook"
    echo ""
    echo "2️⃣  Test the webhook:"
    echo "   ./modal_workflows/test_modal_webhook.sh"
    echo ""
    echo "3️⃣  Monitor logs:"
    echo "   modal app logs anti-gravity-webhook"
    echo ""
    echo "4️⃣  View interactive API docs:"
    echo "   https://your-workspace--anti-gravity-webhook-fastapi-app.modal.run/docs"
    echo ""
    echo "🎉 You're all set!"
else
    echo ""
    echo "❌ Deployment failed. Check the error above."
    echo ""
    echo "💡 Common fixes:"
    echo "   - Verify Modal authentication: modal token current"
    echo "   - Check secrets: modal secret list"
    echo "   - View logs: modal app logs anti-gravity-webhook"
fi
