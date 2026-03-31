#!/bin/bash
# Test script for Apify leads scraping webhook

echo "🧪 Testing Apify Lead Scraping Webhook..."
echo ""

# Webhook URL (adjust if running on a different host/port)
WEBHOOK_URL="http://localhost:5000/webhook/scrape-apify-leads"

# Test payload
PAYLOAD='{
  "industry": "Marketing Agency",
  "fetch_count": 5,
  "location": "united states",
  "company_keywords": ["digital marketing", "PPC agency"],
  "job_title": ["CEO", "Founder"],
  "company_industry": ["marketing & advertising"],
  "skip_test": true,
  "valid_only": true,
  "sender_context": "We help marketing agencies scale their PPC campaigns"
}'

echo "📤 Sending webhook request to: $WEBHOOK_URL"
echo ""
echo "📦 Payload:"
echo "$PAYLOAD" | jq '.'
echo ""

# Send webhook request
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${INSTANTLY_WEBHOOK_SECRET:-}" \
  -d "$PAYLOAD" \
  -w "\n\n📊 HTTP Status: %{http_code}\n" \
  -s | jq '.'

echo ""
echo "✅ Webhook request sent!"
echo "Check the webhook server logs to see if the workflow was triggered."