#!/bin/bash
# One-command Modal webhook setup script

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Modal Webhook Setup - Apify Lead Scraping              ║"
echo "║   Automated Setup Script                                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Check Python
echo -e "${BLUE}[1/6]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} Found: $PYTHON_VERSION"
echo ""

# Step 2: Install Modal
echo -e "${BLUE}[2/6]${NC} Installing Modal CLI..."
if ! command -v modal &> /dev/null; then
    echo "   Installing modal package..."
    pip install modal -q
    echo -e "${GREEN}✓${NC} Modal CLI installed"
else
    echo -e "${GREEN}✓${NC} Modal CLI already installed"
fi
echo ""

# Step 3: Check authentication
echo -e "${BLUE}[3/6]${NC} Checking Modal authentication..."
if modal token current &> /dev/null; then
    CURRENT_TOKEN=$(modal token current 2>&1)
    echo -e "${GREEN}✓${NC} Already authenticated with Modal"
    echo "   User: ${CURRENT_TOKEN}"
else
    echo -e "${YELLOW}⚠${NC}  Not authenticated with Modal"
    echo ""
    echo "   Opening browser for authentication..."
    echo "   ${YELLOW}Please log in or create a free account at modal.com${NC}"
    echo ""
    modal token new
    echo -e "${GREEN}✓${NC} Authentication successful"
fi
echo ""

# Step 4: Setup secrets
echo -e "${BLUE}[4/6]${NC} Setting up Modal secrets..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo ""
    echo "Please create .env file with your API keys:"
    echo "   APIFY_API_KEY=your_key_here"
    echo ""
    exit 1
fi

# Load environment variables
source .env

# Check if secret already exists
if modal secret list 2>/dev/null | grep -q "anti-gravity-secrets"; then
    echo -e "${GREEN}✓${NC} Secret 'anti-gravity-secrets' already exists"

    read -p "   Do you want to update it? (y/N): " UPDATE_SECRET
    if [[ $UPDATE_SECRET =~ ^[Yy]$ ]]; then
        echo "   Deleting old secret..."
        modal secret delete anti-gravity-secrets -y 2>/dev/null || true
    else
        echo "   Keeping existing secret"
    fi
fi

# Create secret if it doesn't exist or was deleted
if ! modal secret list 2>/dev/null | grep -q "anti-gravity-secrets"; then
    echo "   Creating Modal secret with API keys from .env..."

    # Build secret creation command using array (safe — no eval)
    SECRET_ARGS=()
    [ -n "$APIFY_API_KEY" ] && SECRET_ARGS+=("APIFY_API_KEY=$APIFY_API_KEY")
    [ -n "$SSMASTERS_API_KEY" ] && SECRET_ARGS+=("SSMASTERS_API_KEY=$SSMASTERS_API_KEY")
    [ -n "$AZURE_OPENAI_ENDPOINT" ] && SECRET_ARGS+=("AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT")
    [ -n "$AZURE_OPENAI_API_KEY" ] && SECRET_ARGS+=("AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY")
    [ -n "$AZURE_OPENAI_DEPLOYMENT" ] && SECRET_ARGS+=("AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT")

    # Execute secret creation (array form prevents injection)
    modal secret create anti-gravity-secrets "${SECRET_ARGS[@]}"

    echo -e "${GREEN}✓${NC} Secrets uploaded to Modal"
fi
echo ""

# Step 5: Deploy webhook
echo -e "${BLUE}[5/6]${NC} Deploying webhook to Modal..."
echo ""
modal deploy modal_workflows/webhook_scrape_apify.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓${NC} Webhook deployed successfully!"
else
    echo ""
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi
echo ""

# Step 6: Get webhook URL
echo -e "${BLUE}[6/6]${NC} Getting your webhook URL..."
echo ""

WEBHOOK_INFO=$(modal app list 2>/dev/null | grep "anti-gravity-webhook")

if [ -z "$WEBHOOK_INFO" ]; then
    echo -e "${YELLOW}⚠${NC}  Could not find webhook URL automatically"
    echo "   Run: modal app list | grep anti-gravity-webhook"
else
    WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | awk '{print $NF}')
    FULL_URL="${WEBHOOK_URL}/webhook/scrape-apify-leads"

    echo -e "${GREEN}✓${NC} Your webhook is live at:"
    echo ""
    echo -e "   ${GREEN}${FULL_URL}${NC}"
    echo ""

    # Save URL to file
    echo "$FULL_URL" > .modal_webhook_url
    echo "   (Saved to .modal_webhook_url)"
fi
echo ""

# Success summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    🎉 SETUP COMPLETE! 🎉                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 What was created:"
echo "   ✓ Modal CLI installed"
echo "   ✓ Authenticated with Modal"
echo "   ✓ Secrets uploaded (APIFY_API_KEY, etc.)"
echo "   ✓ Webhook deployed and live"
echo ""
echo "🚀 Quick Test:"
echo ""
echo "   curl -X POST $FULL_URL \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"industry\": \"Marketing Agency\", \"fetch_count\": 5}'"
echo ""
echo "📊 Monitor logs:"
echo "   modal app logs anti-gravity-webhook"
echo ""
echo "📚 Full documentation:"
echo "   cat MODAL_WEBHOOK_HOWTO.md"
echo ""
echo "🎯 Next steps:"
echo "   1. Test your webhook (use command above)"
echo "   2. Integrate with Make.com/Zapier/n8n"
echo "   3. Build automation workflows"
echo ""
echo -e "${GREEN}You're all set! Happy scraping! 🚀${NC}"
echo ""
