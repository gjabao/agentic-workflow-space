#!/bin/bash
# Anti-Gravity Workspace - Automated Backup Script
# Backs up to: GitHub + Local timestamped archive + Optional cloud storage

set -e  # Exit on error

# Configuration
WORKSPACE_DIR="/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
BACKUP_DIR="$HOME/Anti-Gravity-Backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_LABEL=$(date +"%Y-%m-%d %H:%M:%S")

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Anti-Gravity Workspace Backup${NC}"
echo -e "${BLUE}  Started: ${DATE_LABEL}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Change to workspace directory
cd "$WORKSPACE_DIR"

# ============================================
# STEP 1: Git Backup (Primary)
# ============================================
echo -e "${YELLOW}[1/4]${NC} Backing up to GitHub..."

# Check if there are changes
if [[ -n $(git status -s) ]]; then
    # Add all changes
    git add .

    # Commit with timestamp
    git commit -m "Auto-backup: $DATE_LABEL" || {
        echo -e "${YELLOW}⚠️  No changes to commit${NC}"
    }

    # Push to GitHub
    if git push origin main; then
        echo -e "${GREEN}✓ Pushed to GitHub successfully${NC}"
    else
        echo -e "${RED}✗ Failed to push to GitHub (check internet connection)${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ No changes to backup${NC}"
fi

# ============================================
# STEP 2: Local Archive Backup
# ============================================
echo
echo -e "${YELLOW}[2/4]${NC} Creating local archive backup..."

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create archive (excluding .tmp, .git, and large files)
ARCHIVE_NAME="anti-gravity-workspace_$TIMESTAMP.tar.gz"
tar -czf "$BACKUP_DIR/$ARCHIVE_NAME" \
    --exclude='.git' \
    --exclude='.tmp' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='venv' \
    --exclude='node_modules' \
    .

ARCHIVE_SIZE=$(du -h "$BACKUP_DIR/$ARCHIVE_NAME" | cut -f1)
echo -e "${GREEN}✓ Archive created: $ARCHIVE_NAME ($ARCHIVE_SIZE)${NC}"

# ============================================
# STEP 3: Cleanup Old Local Backups
# ============================================
echo
echo -e "${YELLOW}[3/4]${NC} Cleaning up old backups (keeping last 30 days)..."

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "anti-gravity-workspace_*.tar.gz" -mtime +30 -delete 2>/dev/null || true

BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/anti-gravity-workspace_*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
echo -e "${GREEN}✓ Local backups: $BACKUP_COUNT archives${NC}"

# ============================================
# STEP 4: Optional Cloud Sync (Google Drive, Dropbox, iCloud)
# ============================================
echo
echo -e "${YELLOW}[4/4]${NC} Checking for cloud sync locations..."

# Check for common cloud storage locations
CLOUD_SYNCED=false

# Google Drive
if [ -d "$HOME/Google Drive/Anti-Gravity-Backups" ]; then
    cp "$BACKUP_DIR/$ARCHIVE_NAME" "$HOME/Google Drive/Anti-Gravity-Backups/"
    echo -e "${GREEN}✓ Synced to Google Drive${NC}"
    CLOUD_SYNCED=true
fi

# Dropbox
if [ -d "$HOME/Dropbox/Anti-Gravity-Backups" ]; then
    cp "$BACKUP_DIR/$ARCHIVE_NAME" "$HOME/Dropbox/Anti-Gravity-Backups/"
    echo -e "${GREEN}✓ Synced to Dropbox${NC}"
    CLOUD_SYNCED=true
fi

# iCloud Drive
if [ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Anti-Gravity-Backups" ]; then
    cp "$BACKUP_DIR/$ARCHIVE_NAME" "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Anti-Gravity-Backups/"
    echo -e "${GREEN}✓ Synced to iCloud Drive${NC}"
    CLOUD_SYNCED=true
fi

if [ "$CLOUD_SYNCED" = false ]; then
    echo -e "${BLUE}ℹ  No cloud storage detected (optional)${NC}"
fi

# ============================================
# Summary
# ============================================
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Backup Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "📍 Backup Locations:"
echo -e "   1. GitHub: https://github.com/gjabao/anti-gravity-workspace"
echo -e "   2. Local: $BACKUP_DIR"
if [ "$CLOUD_SYNCED" = true ]; then
    echo -e "   3. Cloud: Synced to your cloud storage"
fi
echo
echo -e "📊 Statistics:"
echo -e "   • Archive Size: $ARCHIVE_SIZE"
echo -e "   • Total Backups: $BACKUP_COUNT"
echo -e "   • Timestamp: $TIMESTAMP"
echo
