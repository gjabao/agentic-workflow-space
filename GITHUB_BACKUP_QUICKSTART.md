# GitHub Auto-Backup - Quick Start

## ⚡ Super Simple Setup (2 Steps)

### Step 1: Get Your GitHub Token (2 minutes)

1. **Open this link:** https://github.com/settings/tokens/new
2. **Fill in:**
   - Note: `Anti-Gravity Workspace Backup`
   - Expiration: `No expiration`
   - Scopes: ✅ Check **repo** (all repo permissions)
3. **Click:** "Generate token" (green button at bottom)
4. **Copy the token** (starts with `ghp_...`) - you won't see it again!

---

### Step 2: Run Setup Script (1 minute)

Open Terminal and run:

```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_github_auth.sh"
```

When prompted, **paste your token** from Step 1.

**Done!** ✅

---

## 🚀 How to Use

### Automatic Backups (No Work Required)

Your workspace **automatically backs up to GitHub**:
- **6:00 PM** every day
- **11:00 PM** every day

You don't need to do anything!

---

### Manual Backup (Anytime)

Want to backup right now? Just run:

```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_to_github.sh"
```

Or use the full backup (local + GitHub):

```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_workspace.sh"
```

---

## ✅ Verify It's Working

### Check Last Backup

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git log -1
```

### View on GitHub

Open in browser:
```bash
open https://github.com/gjabao/anti-gravity-workspace
```

### Check Auto-Backup Schedule

```bash
launchctl list | grep antigravity
```

Should show: `com.antigravity.backup`

---

## 📍 Your Complete Backup System

After setup, you have **4 layers of protection**:

| Layer | Location | Frequency | Manual Command |
|-------|----------|-----------|----------------|
| **1. GitHub** | Cloud | 6 PM & 11 PM | `bash backup_to_github.sh` |
| **2. Local Archive** | ~/Anti-Gravity-Backups/ | 6 PM & 11 PM | `bash backup_workspace.sh` |
| **3. Time Machine** | External drive | Every hour | (macOS Settings) |
| **4. Cloud Sync** | Google Drive/iCloud | Real-time | (optional) |

---

## 🔧 Common Commands

```bash
# Backup to GitHub now
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_to_github.sh"

# Full backup (local + GitHub)
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_workspace.sh"

# View local backups
open ~/Anti-Gravity-Backups/

# View on GitHub
open https://github.com/gjabao/anti-gravity-workspace

# Check last commit
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" && git log -1 --oneline
```

---

## 🆘 Troubleshooting

### "Authentication failed" when pushing

**Solution:** Run the setup script again:
```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_github_auth.sh"
```

### "No changes to backup"

**Good news!** Everything is already backed up. No action needed.

### Want to force a backup anyway?

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git commit --allow-empty -m "Manual backup checkpoint"
git push origin main
```

---

## 📚 Full Documentation

For detailed guides, see:

- **[GITHUB_BACKUP_QUICKSTART.md](GITHUB_BACKUP_QUICKSTART.md)** ← You are here
- **[GITHUB_AUTO_BACKUP_SETUP.md](GITHUB_AUTO_BACKUP_SETUP.md)** - Detailed setup guide
- **[HOW_TO_ACCESS_BACKUPS.md](HOW_TO_ACCESS_BACKUPS.md)** - How to restore files
- **[BACKUP_QUICKSTART.md](BACKUP_QUICKSTART.md)** - Complete backup overview

---

## 🎯 Quick Decision Tree

**Need to backup RIGHT NOW?**
```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/backup_to_github.sh"
```

**Need to restore a file?**
- See: [HOW_TO_ACCESS_BACKUPS.md](HOW_TO_ACCESS_BACKUPS.md)

**Want to check if backups are working?**
```bash
open https://github.com/gjabao/anti-gravity-workspace
```

**Need to setup authentication?**
```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_github_auth.sh"
```

---

That's it! Your workspace is now backed up automatically to GitHub. 🚀
