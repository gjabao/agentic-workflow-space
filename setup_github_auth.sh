#!/bin/bash
# GitHub Authentication Setup for Auto-Backup
# This script helps you authenticate with GitHub for automatic backups

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  GitHub Auto-Backup Authentication Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

WORKSPACE_DIR="/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
cd "$WORKSPACE_DIR"

# Step 1: Check current status
echo -e "${YELLOW}[Step 1/3]${NC} Checking current GitHub connection..."
echo ""

REMOTE_URL=$(git remote get-url origin)
echo -e "Repository: ${BLUE}$REMOTE_URL${NC}"

# Try to push (will fail if not authenticated)
echo ""
echo -e "${YELLOW}Testing GitHub access...${NC}"
if git ls-remote origin &>/dev/null; then
    echo -e "${GREEN}✅ Already authenticated! You're all set.${NC}"
    echo ""
    echo "You can now use automatic backups:"
    echo "  • Auto-backup runs at 6 PM & 11 PM daily"
    echo "  • Manual backup: cd \"$WORKSPACE_DIR\" && bash backup_workspace.sh"
    echo ""
    exit 0
else
    echo -e "${YELLOW}⚠️  Not authenticated yet. Let's fix that!${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 2: Get GitHub token
echo -e "${YELLOW}[Step 2/3]${NC} GitHub Personal Access Token Required"
echo ""
echo "To enable automatic backups, you need a GitHub Personal Access Token."
echo ""
echo -e "${GREEN}📝 How to get your token:${NC}"
echo ""
echo "  1. Open this URL in your browser:"
echo -e "     ${BLUE}https://github.com/settings/tokens/new${NC}"
echo ""
echo "  2. Fill in:"
echo "     • Note: Anti-Gravity Workspace Auto-Backup"
echo "     • Expiration: No expiration (or 1 year)"
echo "     • Select scopes: ✅ repo (check all repo boxes)"
echo ""
echo "  3. Click 'Generate token' at the bottom"
echo ""
echo "  4. Copy the token (starts with 'ghp_')"
echo "     ⚠️  Save it - you won't see it again!"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Prompt for token
echo -e "${GREEN}Paste your GitHub token here:${NC}"
echo -n "Token: "
read -s GITHUB_TOKEN
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}❌ No token provided. Exiting.${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[Step 3/3]${NC} Testing token and saving credentials..."
echo ""

# Test the token by trying to push
export GIT_ASKPASS_TOKEN="$GITHUB_TOKEN"

# Create a helper script for git credentials
HELPER_SCRIPT=$(mktemp)
cat > "$HELPER_SCRIPT" << 'EOF'
#!/bin/bash
echo "username=gjabao"
echo "password=$GIT_ASKPASS_TOKEN"
EOF
chmod +x "$HELPER_SCRIPT"

# Try to access the repo with the token
if git ls-remote "https://$GITHUB_TOKEN@github.com/gjabao/anti-gravity-workspace.git" &>/dev/null; then
    echo -e "${GREEN}✅ Token is valid!${NC}"

    # Save credentials to macOS Keychain
    echo ""
    echo "Saving credentials to macOS Keychain..."

    # Use git credential helper to store the token
    printf "protocol=https\nhost=github.com\nusername=gjabao\npassword=$GITHUB_TOKEN\n" | git credential-osxkeychain store

    echo -e "${GREEN}✅ Credentials saved to macOS Keychain${NC}"
    echo ""

    # Test automatic push
    echo "Testing automatic push..."
    if git add . && git commit -m "Setup: GitHub auto-backup authentication" && git push origin main; then
        echo ""
        echo -e "${GREEN}✅ Successfully pushed to GitHub!${NC}"
    else
        echo -e "${YELLOW}ℹ️  No changes to push (that's okay)${NC}"
    fi

else
    echo -e "${RED}❌ Token authentication failed.${NC}"
    echo ""
    echo "Please check:"
    echo "  • Token was copied correctly (no extra spaces)"
    echo "  • Token has 'repo' scope enabled"
    echo "  • Token hasn't expired"
    echo ""
    rm "$HELPER_SCRIPT"
    exit 1
fi

# Cleanup
rm "$HELPER_SCRIPT"
unset GITHUB_TOKEN
unset GIT_ASKPASS_TOKEN

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ GitHub Auto-Backup Setup Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Your workspace is now configured for automatic GitHub backups!"
echo ""
echo -e "${GREEN}📅 Automatic Schedule:${NC}"
echo "  • 6:00 PM daily"
echo "  • 11:00 PM daily"
echo ""
echo -e "${GREEN}🔧 Manual Backup:${NC}"
echo "  cd \"$WORKSPACE_DIR\""
echo "  bash backup_workspace.sh"
echo ""
echo -e "${GREEN}📊 Check Status:${NC}"
echo "  • View backups: open ~/Anti-Gravity-Backups/"
echo "  • View on GitHub: open https://github.com/gjabao/anti-gravity-workspace"
echo "  • Check scheduler: launchctl list | grep antigravity"
echo ""
echo -e "${GREEN}📚 Documentation:${NC}"
echo "  • GITHUB_AUTO_BACKUP_SETUP.md - Full guide"
echo "  • HOW_TO_ACCESS_BACKUPS.md - How to restore"
echo "  • BACKUP_QUICKSTART.md - Quick reference"
echo ""
echo "🎉 You're all set!"
echo ""
