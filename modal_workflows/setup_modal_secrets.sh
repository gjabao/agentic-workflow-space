#!/bin/bash
# Setup Modal Secrets for Anti-Gravity Workflows
# Run this after: modal token new

set -e

echo "🔧 Modal Secrets Setup for Anti-Gravity Workflows"
echo "=================================================="
echo ""

# Check if modal is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Install with: pip install modal"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create it first."
    exit 1
fi

echo "📋 Loading secrets from .env file..."
echo ""

# Source .env to get variables
set -a
source .env
set +a

# Check required secrets
REQUIRED_SECRETS=("INSTANTLY_API_KEY" "APOLLO_API_KEY" "OPENAI_API_KEY")
MISSING_SECRETS=()

for secret in "${REQUIRED_SECRETS[@]}"; do
    if [ -z "${!secret}" ]; then
        MISSING_SECRETS+=("$secret")
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo "⚠️  Missing required secrets in .env:"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "   - $secret"
    done
    echo ""
    echo "Please add these to your .env file first."
    exit 1
fi

echo "✓ All required secrets found in .env"
echo ""

# Prepare Gmail credentials
GMAIL_CREDS=""
GMAIL_TOKEN=""

if [ -f "credentials.json" ]; then
    GMAIL_CREDS=$(cat credentials.json | tr -d '\n')
    echo "✓ Found credentials.json"
else
    echo "⚠️  credentials.json not found (needed for Gmail)"
fi

if [ -f "token.json" ]; then
    GMAIL_TOKEN=$(cat token.json | tr -d '\n')
    echo "✓ Found token.json"
else
    echo "⚠️  token.json not found (needed for Gmail)"
    echo "   Run: python execution/email_campaign_report.py first to generate token.json"
fi

echo ""
echo "🚀 Creating Modal secret: anti-gravity-secrets"
echo ""

# Create the secret
modal secret create anti-gravity-secrets \
    INSTANTLY_API_KEY="$INSTANTLY_API_KEY" \
    APOLLO_API_KEY="$APOLLO_API_KEY" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    REPORT_EMAIL="${GMAIL_USER:-giabaongb0305@gmail.com}" \
    ${GMAIL_CREDS:+GMAIL_CREDENTIALS_JSON="$GMAIL_CREDS"} \
    ${GMAIL_TOKEN:+GMAIL_TOKEN_JSON="$GMAIL_TOKEN"} \
    2>/dev/null || {
        echo ""
        echo "ℹ️  Secret might already exist. Updating instead..."
        echo ""
        echo "To update manually, go to: https://modal.com/secrets"
        echo "Or delete existing: modal secret delete anti-gravity-secrets"
    }

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Deploy workflow: modal deploy modal_workflows/email_campaign_report.py"
echo "   2. Test manually: modal run modal_workflows/email_campaign_report.py"
echo "   3. View logs: modal app logs anti-gravity-workflows"
echo ""
echo "🔗 View secrets at: https://modal.com/secrets"
echo ""
