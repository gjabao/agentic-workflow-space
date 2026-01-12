# Backup Options: Anti-Gravity Workspace
> Multiple backup strategies for maximum data safety

## Overview: 4-Layer Backup Strategy

| Layer | Method | Frequency | What's Backed Up | Storage Location |
|-------|--------|-----------|------------------|------------------|
| 1️⃣ GitHub | Git push | Real-time/Daily | Code, directives, configs | Cloud (GitHub) |
| 2️⃣ Local Archive | Automated script | Daily (6 PM, 11 PM) | Full workspace snapshot | `~/Anti-Gravity-Backups/` |
| 3️⃣ Time Machine | macOS native | Hourly | Entire Mac | External drive |
| 4️⃣ Cloud Sync | Google Drive/Dropbox | Real-time | Critical files | Cloud storage |

**Result:** Your workspace is backed up to 4 different locations automatically. 🔒

---

## Layer 1: GitHub (Primary - Already Set Up) ✅

### Status
✅ Repository: `https://github.com/gjabao/anti-gravity-workspace`
✅ Configured and working

### Manual Backup
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git add .
git commit -m "Backup: $(date '+%Y-%m-%d %H:%M')"
git push origin main
```

### Quick Alias
Add to `~/.zshrc` or `~/.bash_profile`:
```bash
alias agw-backup='cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" && git add . && git commit -m "Auto-backup: $(date)" && git push origin main && echo "✅ Backed up to GitHub!"'
```

Then just type: `agw-backup`

---

## Layer 2: Automated Local Archive (New!) 🆕

### What This Does
- Creates timestamped `.tar.gz` archives
- Runs automatically 2x daily (6 PM, 11 PM)
- Keeps last 30 days of backups
- Stores in separate location (safe if workspace deleted)

### Setup Instructions

#### Step 1: Create Backup Directory
```bash
mkdir -p ~/Anti-Gravity-Backups
```

#### Step 2: Install Auto-Backup (macOS LaunchAgent)
```bash
# Copy the plist file to LaunchAgents
cp "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/com.antigravity.backup.plist" ~/Library/LaunchAgents/

# Load the backup job
launchctl load ~/Library/LaunchAgents/com.antigravity.backup.plist

# Verify it's running
launchctl list | grep antigravity
```

#### Step 3: Test Backup Manually
```bash
# Run the backup script
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_workspace.sh"

# Check results
ls -lh ~/Anti-Gravity-Backups/
```

### Backup Schedule
- **6:00 PM daily** - End of workday backup
- **11:00 PM daily** - Before bed backup

### What Gets Backed Up
✅ All directives (`directives/*.md`)
✅ All scripts (`execution/*.py`)
✅ Configuration files (`.env`, `credentials.json`)
✅ Documentation (`*.md`)
✅ Git history (`.git/`)

❌ Temporary files (`.tmp/`)
❌ Python cache (`__pycache__/`)
❌ Log files (`*.log`)

### Restore from Archive
```bash
# List available backups
ls -lh ~/Anti-Gravity-Backups/

# Extract a specific backup
cd ~/Anti-Gravity-Backups
tar -xzf anti-gravity-workspace-2026-01-10-18-00.tar.gz

# Files extracted to: anti-gravity-workspace/
```

### Manage Auto-Backup

**Pause backups:**
```bash
launchctl unload ~/Library/LaunchAgents/com.antigravity.backup.plist
```

**Resume backups:**
```bash
launchctl load ~/Library/LaunchAgents/com.antigravity.backup.plist
```

**Remove auto-backup:**
```bash
launchctl unload ~/Library/LaunchAgents/com.antigravity.backup.plist
rm ~/Library/LaunchAgents/com.antigravity.backup.plist
```

**Check backup logs:**
```bash
tail -f ~/Anti-Gravity-Backups/backup.log
```

---

## Layer 3: macOS Time Machine

### Setup (If Not Already Done)

1. **Connect External Drive**
   - USB hard drive (500 GB+ recommended)
   - Format as "Mac OS Extended (Journaled)"

2. **Enable Time Machine**
   ```
   System Settings → General → Time Machine → Add Backup Disk
   ```

3. **Verify Workspace is Included**
   - Time Machine backs up entire Mac by default
   - Your workspace is in `~/Downloads/Claude skill/`
   - ✅ Automatically included

### Restore from Time Machine
1. Right-click workspace folder
2. Select "Restore from Time Machine"
3. Browse hourly snapshots
4. Select version to restore

**Backup frequency:** Every hour (automatic)

---

## Layer 4: Cloud Sync (Optional)

### Option A: Google Drive Desktop

**Setup:**
1. Install [Google Drive Desktop](https://www.google.com/drive/download/)
2. Sign in with Google account
3. Choose "Mirror files" option
4. Add workspace folder to sync

**Location:** `~/Google Drive/My Drive/Anti-Gravity-Workspace`

**Sync frequency:** Real-time (automatic)

### Option B: Dropbox

**Setup:**
1. Install [Dropbox](https://www.dropbox.com/install)
2. Sign in
3. Move workspace to `~/Dropbox/`
   ```bash
   mv "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" ~/Dropbox/
   cd ~/Dropbox/Anti-Gravity\ Workspace
   ```

**Sync frequency:** Real-time (automatic)

### Option C: iCloud Drive (macOS Native)

**Setup:**
```bash
# Create symlink to iCloud
ln -s "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" ~/Library/Mobile\ Documents/com~apple~CloudDocs/Anti-Gravity-Workspace
```

**Access from:**
- Mac: iCloud Drive folder
- iPhone/iPad: Files app
- Web: icloud.com

**Sync frequency:** Real-time (automatic)

---

## Backup Verification Checklist

Run this weekly to ensure all backups are working:

```bash
# 1. Check GitHub (should show recent commits)
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git log --oneline -5

# 2. Check local archives (should have recent backups)
ls -lh ~/Anti-Gravity-Backups/ | tail -5

# 3. Check Time Machine status
tmutil latestbackup

# 4. Check cloud sync (if using Google Drive/Dropbox)
# Verify last sync time in app
```

---

## Recovery Scenarios

### Scenario 1: Accidentally Deleted File
**Best option:** Git recovery
```bash
git checkout HEAD -- path/to/file.py
```

### Scenario 2: Computer Crash/Lost
**Best option:** Clone from GitHub
```bash
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

### Scenario 3: Corrupted Workspace
**Best option:** Local archive
```bash
cd ~/Anti-Gravity-Backups
tar -xzf anti-gravity-workspace-LATEST.tar.gz
```

### Scenario 4: Need Version from 3 Days Ago
**Best option:** Time Machine
- Browse Time Machine snapshots
- Restore specific files/folders

---

## Storage Requirements

| Backup Method | Disk Space Needed | Notes |
|---------------|-------------------|-------|
| GitHub | Free (1 GB limit) | Current repo: ~50 MB |
| Local Archives | ~2 GB (30 days) | 60 MB × 60 backups |
| Time Machine | 500 GB+ drive | Backs up entire Mac |
| Cloud Sync | ~50 MB | Real-time mirror |

**Total workspace size:** ~50 MB (without `.tmp/` folder)

---

## Automated Backup Summary

Once set up, this happens automatically:

```
Every hour:
└─ Time Machine backup (macOS)

Daily at 6 PM:
├─ Local archive created (LaunchAgent)
└─ You should: git push (GitHub)

Daily at 11 PM:
└─ Local archive created (LaunchAgent)

Real-time:
└─ Cloud sync (if using Google Drive/Dropbox)
```

**You don't have to do anything!** Just push to GitHub occasionally.

---

## Quick Setup Script

Run this to set up everything:

```bash
#!/bin/bash
# Complete backup setup

# 1. Create backup directory
mkdir -p ~/Anti-Gravity-Backups

# 2. Install auto-backup
cp "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/com.antigravity.backup.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.antigravity.backup.plist

# 3. Add git alias
echo 'alias agw-backup="cd \"/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace\" && git add . && git commit -m \"Auto-backup: \$(date)\" && git push origin main && echo \"✅ Backed up to GitHub!\""' >> ~/.zshrc

# 4. Test backup
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_workspace.sh"

# 5. Verify
echo ""
echo "✅ Backup setup complete!"
echo ""
echo "Backups installed:"
echo "  🟢 GitHub: https://github.com/gjabao/anti-gravity-workspace"
echo "  🟢 Local Archives: ~/Anti-Gravity-Backups/"
echo "  🟢 Auto-backup: 6 PM & 11 PM daily"
echo ""
echo "Next steps:"
echo "  1. Type 'agw-backup' to backup to GitHub anytime"
echo "  2. Enable Time Machine (System Settings)"
echo "  3. Optional: Install Google Drive Desktop for cloud sync"
```

---

## Backup Best Practices

### Daily (10 seconds)
```bash
# End of day
agw-backup
```

### Weekly (1 minute)
```bash
# Verify all backups working
ls ~/Anti-Gravity-Backups/ | tail -5
git log --oneline -5
tmutil latestbackup
```

### Monthly (5 minutes)
```bash
# Clean old local archives (keep last 30 days)
cd ~/Anti-Gravity-Backups
find . -name "*.tar.gz" -mtime +30 -delete

# Verify GitHub connection
git remote -v
git pull origin main
```

---

## TL;DR: Quickstart

**1. Install auto-backup:**
```bash
mkdir -p ~/Anti-Gravity-Backups
cp "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/com.antigravity.backup.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.antigravity.backup.plist
```

**2. Add git shortcut:**
```bash
echo 'alias agw-backup="cd \"/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace\" && git add . && git commit -m \"Auto-backup: \$(date)\" && git push origin main && echo \"✅ Backed up!\""' >> ~/.zshrc
source ~/.zshrc
```

**3. Daily usage:**
```bash
agw-backup  # Push to GitHub
```

**That's it!** Local archives happen automatically at 6 PM & 11 PM. 🎉

---

## Support

**Check backup status anytime:**
```bash
# GitHub
git status

# Local archives
ls -lh ~/Anti-Gravity-Backups/ | tail -5

# Auto-backup job
launchctl list | grep antigravity

# Logs
tail ~/Anti-Gravity-Backups/backup.log
```

**Need help?** All scripts are in the workspace root directory.