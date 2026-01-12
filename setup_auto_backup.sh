#!/bin/bash
# Anti-Gravity Workspace - Complete Backup Setup Script
# Run this once to install all backup automation

set -e  # Exit on error

echo "🚀 Anti-Gravity Workspace - Backup Setup"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

WORKSPACE_DIR="/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
BACKUP_DIR="$HOME/Anti-Gravity-Backups"
PLIST_NAME="com.antigravity.backup.plist"
PLIST_SOURCE="$WORKSPACE_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Step 1: Create backup directory
echo -e "${BLUE}[1/6]${NC} Creating backup directory..."
mkdir -p "$BACKUP_DIR"
echo -e "${GREEN}✓${NC} Created: $BACKUP_DIR"
echo ""

# Step 2: Make backup script executable
echo -e "${BLUE}[2/6]${NC} Making backup script executable..."
chmod +x "$WORKSPACE_DIR/backup_workspace.sh"
echo -e "${GREEN}✓${NC} backup_workspace.sh is now executable"
echo ""

# Step 3: Install LaunchAgent (auto-backup at 6 PM & 11 PM)
echo -e "${BLUE}[3/6]${NC} Installing automated backup scheduler..."

# Check if already installed
if [ -f "$PLIST_DEST" ]; then
    echo -e "${YELLOW}⚠${NC}  LaunchAgent already exists. Unloading old version..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm "$PLIST_DEST"
fi

# Copy plist file
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load the LaunchAgent
launchctl load "$PLIST_DEST"

echo -e "${GREEN}✓${NC} Auto-backup installed (runs at 6 PM & 11 PM daily)"
echo ""

# Step 4: Add git backup alias
echo -e "${BLUE}[4/6]${NC} Installing git backup shortcut..."

SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    # Check if alias already exists
    if grep -q "alias agw-backup=" "$SHELL_RC"; then
        echo -e "${YELLOW}⚠${NC}  Alias 'agw-backup' already exists in $SHELL_RC"
    else
        echo "" >> "$SHELL_RC"
        echo "# Anti-Gravity Workspace - Quick backup to GitHub" >> "$SHELL_RC"
        echo "alias agw-backup='cd \"$WORKSPACE_DIR\" && git add . && git commit -m \"Auto-backup: \$(date)\" && git push origin main && echo \"✅ Backed up to GitHub!\"'" >> "$SHELL_RC"
        echo -e "${GREEN}✓${NC} Added 'agw-backup' alias to $SHELL_RC"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Could not find shell config file. Skipping alias setup."
fi
echo ""

# Step 5: Test backup script
echo -e "${BLUE}[5/6]${NC} Running test backup..."
bash "$WORKSPACE_DIR/backup_workspace.sh"
echo -e "${GREEN}✓${NC} Test backup complete"
echo ""

# Step 6: Verify installation
echo -e "${BLUE}[6/6]${NC} Verifying installation..."

# Check LaunchAgent is loaded
if launchctl list | grep -q "com.antigravity.backup"; then
    echo -e "${GREEN}✓${NC} LaunchAgent is running"
else
    echo -e "${YELLOW}⚠${NC}  LaunchAgent not found (may need manual load)"
fi

# Check backup files exist
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.tar.gz" 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $BACKUP_COUNT backup archive(s)"
else
    echo -e "${YELLOW}⚠${NC}  No backup archives found yet"
fi

# Check git remote
cd "$WORKSPACE_DIR"
if git remote -v | grep -q "github.com"; then
    echo -e "${GREEN}✓${NC} GitHub remote configured"
else
    echo -e "${YELLOW}⚠${NC}  GitHub remote not found"
fi

echo ""
echo "========================================"
echo -e "${GREEN}✅ Backup Setup Complete!${NC}"
echo "========================================"
echo ""
echo "Your workspace is now backed up to:"
echo ""
echo "  🟢 GitHub:         https://github.com/gjabao/anti-gravity-workspace"
echo "  🟢 Local Archives: $BACKUP_DIR"
echo "  🟢 Auto-backup:    6 PM & 11 PM daily"
echo ""
echo "Usage:"
echo ""
echo "  agw-backup              → Push to GitHub immediately"
echo "  ls ~/Anti-Gravity-Backups  → View local archives"
echo "  tail ~/Anti-Gravity-Backups/backup.log  → Check backup logs"
echo ""
echo "Next steps:"
echo ""
echo "  1. Restart terminal (to enable 'agw-backup' command)"
echo "  2. Enable Time Machine (System Settings → General → Time Machine)"
echo "  3. Optional: Install Google Drive Desktop for cloud sync"
echo ""
echo "Documentation:"
echo "  - BACKUP_OPTIONS.md (comprehensive guide)"
echo "  - VERSION_CONTROL_GUIDE.md (git workflow)"
echo ""
echo "🎉 You're all set! Your workspace will auto-backup twice daily."
echo ""