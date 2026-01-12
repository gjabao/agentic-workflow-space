#!/bin/bash
# Test Modal webhook for Apify lead scraping

echo "🧪 Testing Modal Webhook for Apify Lead Scraping..."
echo ""

# Get Modal app URL
echo "📋 Getting Modal app URL..."
WEBHOOK_URL=$(modal app list 2>/dev/null | grep "anti-gravity-webhook" | awk '{print $NF}')

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ Modal app 'anti-gravity-webhook' not found."
    echo "   Deploy it first with: modal deploy modal_workflows/webhook_scrape_apify.py"
    exit 1
fi

# Append endpoint path
WEBHOOK_URL="${WEBHOOK_URL}/webhook/scrape-apify-leads"

echo "✅ Found webhook URL: $WEBHOOK_URL"
echo ""

# Test payload
PAYLOAD='{
  "industry": "Marketing Agency",
  "fetch_count": 5,
  "location": "united states",
  "company_keywords": ["digital marketing", "PPC"],
  "skip_test": true,
  "valid_only": true
}'

echo "📤 Sending test request..."
echo ""
echo "📦 Payload:"
echo "$PAYLOAD" | jq '.' 2>/dev/null || echo "$PAYLOAD"
echo ""

# Send request
RESPONSE=$(curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${WEBHOOK_SECRET:-}" \
  -d "$PAYLOAD" \
  -w "\nHTTP_STATUS:%{http_code}")

# Extract HTTP status
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

echo "📊 Response (HTTP $HTTP_STATUS):"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_STATUS" = "202" ] || [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Webhook triggered successfully!"
    echo ""
    echo "🔍 Monitor progress:"
    echo "   modal app logs anti-gravity-webhook"
    echo ""
    echo "📊 View results:"
    echo "   modal volume ls anti-gravity-data /data/scraped_data"
else
    echo "❌ Webhook request failed with HTTP $HTTP_STATUS"
    echo ""
    echo "💡 Troubleshooting:"
    echo "   1. Check if webhook is deployed: modal app list"
    echo "   2. Check Modal secrets: modal secret list"
    echo "   3. View logs: modal app logs anti-gravity-webhook"
fi