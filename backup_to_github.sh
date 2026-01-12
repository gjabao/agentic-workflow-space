#!/bin/bash
# Quick GitHub Backup Script
# Usage: bash backup_to_github.sh

WORKSPACE_DIR="/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
cd "$WORKSPACE_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔄 Backing up to GitHub..."

# Check if there are changes
if [[ -z $(git status -s) ]]; then
    echo -e "${GREEN}✅ No changes to backup${NC}"
    echo ""
    echo "Your workspace is already up to date on GitHub!"
    echo "Last commit:"
    git log -1 --pretty=format:"  %s (%ar)"
    echo ""
    exit 0
fi

# Add all changes
git add .

# Commit with timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Backup: $TIMESTAMP"

# Push to GitHub
if git push origin main; then
    echo ""
    echo -e "${GREEN}✅ Successfully backed up to GitHub!${NC}"
    echo ""
    echo "View online: https://github.com/gjabao/anti-gravity-workspace"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Failed to push to GitHub${NC}"
    echo ""
    echo "This usually means you need to authenticate first."
    echo "Run the setup script:"
    echo "  bash setup_github_auth.sh"
    echo ""
    exit 1
fi
