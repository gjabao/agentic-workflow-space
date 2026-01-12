# Backup Setup Cheat Sheet

## 🚀 Quick Setup (Copy & Paste This)

```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_auto_backup.sh"
```

Then restart your terminal and you're done! ✅

---

## What This Does

The setup script automatically:

1. ✅ Creates backup directory (`~/Anti-Gravity-Backups`)
2. ✅ Installs automated backup (runs at 6 PM & 11 PM daily)
3. ✅ Adds `agw-backup` command to your terminal
4. ✅ Runs a test backup to verify everything works
5. ✅ Shows you a summary of what was installed

**Total time:** 30 seconds

---

## After Setup

### Daily Usage

Just type this once per day (end of workday):
```bash
agw-backup
```

That's it! This backs up your workspace to GitHub.

Local archives happen automatically at 6 PM & 11 PM (you don't have to do anything).

---

## Commands You Now Have

| Command | What It Does |
|---------|--------------|
| `agw-backup` | Push workspace to GitHub immediately |
| `ls ~/Anti-Gravity-Backups` | View local backup archives |
| `tail ~/Anti-Gravity-Backups/backup.log` | Check backup logs |

---

## Optional: Enable Cloud Sync

### Option 1: Google Drive (Recommended)
1. Install [Google Drive Desktop](https://www.google.com/drive/download/)
2. Create folder: `~/Google Drive/Anti-Gravity-Backups`
3. Backups will auto-sync to cloud!

### Option 2: iCloud Drive (macOS Native)
```bash
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/Anti-Gravity-Backups
```

### Option 3: Dropbox
```bash
mkdir -p ~/Dropbox/Anti-Gravity-Backups
```

The backup script automatically detects and syncs to these locations if they exist.

---

## How to Check Everything is Working

```bash
# 1. Check auto-backup is running
launchctl list | grep antigravity

# 2. Check recent backups
ls -lh ~/Anti-Gravity-Backups/ | tail -5

# 3. Check GitHub connection
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git remote -v

# 4. View backup logs
tail ~/Anti-Gravity-Backups/backup.log
```

---

## Pause/Resume Auto-Backup

**Pause (temporarily stop):**
```bash
launchctl unload ~/Library/LaunchAgents/com.antigravity.backup.plist
```

**Resume:**
```bash
launchctl load ~/Library/LaunchAgents/com.antigravity.backup.plist
```

---

## Restore from Backup

### From GitHub (Most Common)
```bash
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

### From Local Archive
```bash
cd ~/Anti-Gravity-Backups
ls -lh  # Find the backup you want
tar -xzf anti-gravity-workspace_TIMESTAMP.tar.gz
```

### From Time Machine (macOS)
1. Right-click workspace folder
2. Select "Restore from Time Machine"
3. Choose date/time

---

## Complete Backup Coverage

After setup, your workspace is backed up to:

| Location | Frequency | Storage |
|----------|-----------|---------|
| 🟢 GitHub | Manual (`agw-backup`) | Cloud |
| 🟢 Local Archives | Auto (6 PM, 11 PM) | `~/Anti-Gravity-Backups/` |
| 🟢 Time Machine | Hourly (macOS) | External drive |
| 🟢 Cloud Sync | Real-time (optional) | Google Drive/Dropbox/iCloud |

**You're protected against:**
- ✅ Accidental deletion
- ✅ Computer crash
- ✅ Hard drive failure
- ✅ Ransomware
- ✅ Lost/stolen laptop

---

## TL;DR

**Setup once:**
```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_auto_backup.sh"
```

**Use daily:**
```bash
agw-backup
```

**Everything else is automatic.** 🎉

---

## Need More Details?

- **Comprehensive guide:** [BACKUP_OPTIONS.md](BACKUP_OPTIONS.md)
- **Git workflow:** [VERSION_CONTROL_GUIDE.md](VERSION_CONTROL_GUIDE.md)
- **Scripts:**
  - `setup_auto_backup.sh` - One-time setup
  - `backup_workspace.sh` - Backup logic (runs automatically)
  - `com.antigravity.backup.plist` - macOS scheduler config
