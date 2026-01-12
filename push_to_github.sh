#!/bin/bash
# Push Anti-Gravity Workspace to GitHub
# This script helps you push your committed changes to GitHub

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Push to GitHub${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Change to workspace directory
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# Check if there are commits to push
if git log origin/main..HEAD &>/dev/null; then
    COMMITS_AHEAD=$(git log origin/main..HEAD --oneline | wc -l | tr -d ' ')

    if [ "$COMMITS_AHEAD" -eq 0 ]; then
        echo -e "${GREEN}✓ Everything is already up to date!${NC}"
        echo ""
        echo -e "Your GitHub repo: ${BLUE}https://github.com/gjabao/anti-gravity-workspace${NC}"
        exit 0
    fi

    echo -e "${YELLOW}You have $COMMITS_AHEAD commit(s) to push:${NC}"
    echo ""
    git log origin/main..HEAD --oneline
    echo ""
fi

echo -e "${BLUE}Repository:${NC} https://github.com/gjabao/anti-gravity-workspace"
echo ""
echo -e "${YELLOW}When prompted, enter your GitHub credentials:${NC}"
echo -e "  Username: ${BLUE}gjabao${NC}"
echo -e "  Password: ${YELLOW}Use a Personal Access Token (not your password)${NC}"
echo ""
echo -e "${YELLOW}Don't have a token? Get one here:${NC}"
echo -e "  ${BLUE}https://github.com/settings/tokens/new${NC}"
echo -e "  (Select 'repo' scope, then generate)"
echo ""
echo -e "${YELLOW}Pushing to GitHub...${NC}"
echo ""

# Try to push
if git push origin main; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ Successfully pushed to GitHub!${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "View your repository:"
    echo -e "  ${BLUE}https://github.com/gjabao/anti-gravity-workspace${NC}"
    echo ""
    echo -e "Files pushed include:"
    echo -e "  ✅ BACKUP_QUICKSTART.md"
    echo -e "  ✅ BACKUP_OPTIONS.md"
    echo -e "  ✅ SETUP_CHEATSHEET.md"
    echo -e "  ✅ VERSION_CONTROL_GUIDE.md"
    echo -e "  ✅ backup_workspace.sh"
    echo -e "  ✅ setup_auto_backup.sh"
    echo -e "  ✅ All your directives and scripts"
    echo ""
else
    echo ""
    echo -e "${RED}✗ Push failed${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo ""
    echo -e "1. ${BLUE}Generate a Personal Access Token:${NC}"
    echo -e "   https://github.com/settings/tokens/new"
    echo -e "   - Select 'repo' scope"
    echo -e "   - Copy the token (starts with ghp_...)"
    echo ""
    echo -e "2. ${BLUE}Try pushing again:${NC}"
    echo -e "   bash push_to_github.sh"
    echo -e "   - Username: gjabao"
    echo -e "   - Password: Paste your token"
    echo ""
    echo -e "3. ${BLUE}Or use SSH instead:${NC}"
    echo -e "   git remote set-url origin git@github.com:gjabao/anti-gravity-workspace.git"
    echo -e "   git push origin main"
    echo ""
    exit 1
fi