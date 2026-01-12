#!/bin/bash
# Interactive workflow trigger script

export PATH="/Users/nguyengiabao/Library/Python/3.9/bin:$PATH"
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

echo "🚀 Modal Workflow Trigger"
echo "========================="
echo ""
echo "Select workflow to run:"
echo "1. Daily Campaign Report"
echo "2. Scrape Leads (custom query)"
echo "3. Generate Email Copy"
echo "4. View Logs"
echo "5. Exit"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "Running daily campaign report..."
        python3 -m modal run modal_workflows/email_campaign_report.py
        ;;
    2)
        echo ""
        read -p "Enter search query (e.g., 'dentists in New York'): " query
        read -p "Enter limit (default: 100): " limit
        limit=${limit:-100}
        echo ""
        echo "🔍 Scraping leads: '$query' (limit: $limit)"
        python3 -m modal run modal_workflows/scrape_on_demand.py --query "$query" --limit "$limit"
        ;;
    3)
        echo ""
        read -p "Enter company name: " company
        read -p "Enter industry (default: general): " industry
        industry=${industry:-general}
        read -p "Enter location (default: USA): " location
        location=${location:-USA}
        echo ""
        echo "✍️  Generating copy for: $company ($industry, $location)"
        python3 -m modal run modal_workflows/generate_copy_on_demand.py \
            --company-name "$company" \
            --industry "$industry" \
            --location "$location"
        ;;
    4)
        echo ""
        echo "📊 Opening live logs (Ctrl+C to exit)..."
        python3 -m modal app logs anti-gravity-workflows --follow
        ;;
    5)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
