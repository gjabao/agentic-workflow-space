#!/bin/bash
# Cron Jobs Setup Script
# Automatically configures cron jobs for Instantly workflow automation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Instantly Workflow - Cron Jobs Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get workspace directory (absolute path)
WORKSPACE_DIR="$(cd "$(dirname "$0")" && pwd)"
echo -e "${GREEN}✓${NC} Workspace: ${WORKSPACE_DIR}"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check if .env exists
if [ ! -f "$WORKSPACE_DIR/.env" ]; then
    echo -e "${RED}✗${NC} .env file not found"
    exit 1
fi
echo -e "${GREEN}✓${NC} .env file found"

# Create logs directory
mkdir -p "$WORKSPACE_DIR/.tmp/cron_logs"
echo -e "${GREEN}✓${NC} Logs directory created: .tmp/cron_logs"

# Generate cron jobs
CRON_TEMP_FILE=$(mktemp)

cat > "$CRON_TEMP_FILE" << EOF
# Instantly Workflow Automation - Cron Jobs
# Generated on $(date)
# DO NOT EDIT MANUALLY - Use setup_cron.sh to update

# PATH for cron environment
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# Daily Email Report (7 AM Hanoi time = 12 AM UTC)
0 0 * * * cd "$WORKSPACE_DIR" && /usr/bin/python3 execution/email_campaign_report.py >> .tmp/cron_logs/email_report.log 2>&1

# Hourly Quick Check (Every hour during business hours Hanoi time: 9 AM - 7 PM = 2 AM - 12 PM UTC)
0 2-12 * * * cd "$WORKSPACE_DIR" && /usr/bin/python3 execution/monitor_campaigns.py >> .tmp/cron_logs/hourly_check.log 2>&1

# Weekly Optimization Report (Every Monday 9 AM Dubai time)
# 0 5 * * 1 cd "$WORKSPACE_DIR" && /usr/bin/python3 execution/weekly_optimization.py >> .tmp/cron_logs/weekly_report.log 2>&1

# Cleanup old logs (Every Sunday midnight)
0 0 * * 0 find "$WORKSPACE_DIR/.tmp/cron_logs" -name "*.log" -mtime +30 -delete

# End of Instantly Workflow Automation cron jobs
EOF

echo ""
echo -e "${BLUE}Cron Jobs to be installed:${NC}"
echo -e "${YELLOW}-------------------------------------------${NC}"
cat "$CRON_TEMP_FILE" | grep -v "^#" | grep -v "^$"
echo -e "${YELLOW}-------------------------------------------${NC}"
echo ""

# Ask for confirmation
read -p "$(echo -e ${GREEN}Install these cron jobs? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠${NC} Installation cancelled"
    rm "$CRON_TEMP_FILE"
    exit 0
fi

# Backup existing crontab
echo -e "${BLUE}→${NC} Backing up existing crontab..."
crontab -l > "$WORKSPACE_DIR/.tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || true
echo -e "${GREEN}✓${NC} Backup created"

# Remove old Instantly cron jobs if they exist
echo -e "${BLUE}→${NC} Removing old Instantly cron jobs..."
(crontab -l 2>/dev/null | grep -v "Instantly Workflow Automation" || true) | crontab - 2>/dev/null || true

# Install new cron jobs
echo -e "${BLUE}→${NC} Installing new cron jobs..."
(crontab -l 2>/dev/null; cat "$CRON_TEMP_FILE") | crontab -

# Verify installation
echo ""
echo -e "${BLUE}→${NC} Verifying installation..."
if crontab -l | grep -q "Instantly Workflow Automation"; then
    echo -e "${GREEN}✓✓✓ Cron jobs installed successfully!${NC}"
else
    echo -e "${RED}✗${NC} Installation failed"
    rm "$CRON_TEMP_FILE"
    exit 1
fi

# Cleanup
rm "$CRON_TEMP_FILE"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Cron jobs are now active"
echo -e "  2. Monitor logs in: ${WORKSPACE_DIR}/.tmp/cron_logs/"
echo -e "  3. Daily reports in: ${WORKSPACE_DIR}/.tmp/reports/"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  View cron jobs:     ${GREEN}crontab -l${NC}"
echo -e "  Edit cron jobs:     ${GREEN}crontab -e${NC}"
echo -e "  Remove cron jobs:   ${GREEN}crontab -r${NC}"
echo -e "  View daily log:     ${GREEN}tail -f .tmp/cron_logs/daily_monitor.log${NC}"
echo -e "  Test monitor now:   ${GREEN}python3 execution/monitor_campaigns.py${NC}"
echo ""
echo -e "${BLUE}Schedule:${NC}"
echo -e "  📧 Email Report:    Every day at 7 AM Hanoi time → ${GREEN}giabaongb0305@gmail.com${NC}"
echo -e "  🔍 Hourly Check:    Every hour (9 AM - 7 PM Hanoi time)"
echo -e "  🗑️  Log Cleanup:     Every Sunday at midnight"
echo ""
