# How to Access Your Backup Files

## Quick Reference

**Your backups are stored here:**
```
~/Anti-Gravity-Backups/
```

**Full path:**
```
/Users/nguyengiabao/Anti-Gravity-Backups/
```

---

## View Your Backups

### Option 1: Using Finder (GUI)
1. Open **Finder**
2. Press `Cmd + Shift + G` (Go to Folder)
3. Type: `~/Anti-Gravity-Backups`
4. Press Enter

You'll see files like:
```
anti-gravity-workspace_20260112_182138.tar.gz (3.1 MB)
anti-gravity-workspace_20260113_180000.tar.gz
anti-gravity-workspace_20260114_230000.tar.gz
```

### Option 2: Using Terminal
```bash
# List all backups
ls -lh ~/Anti-Gravity-Backups/

# See how many backups you have
ls ~/Anti-Gravity-Backups/*.tar.gz | wc -l
```

---

## Open/Extract a Backup File

### Method 1: Double-Click (Easiest)
1. Open Finder → Go to `~/Anti-Gravity-Backups/`
2. **Double-click** the `.tar.gz` file
3. macOS will automatically extract it to a folder
4. Browse the extracted folder to find your files

### Method 2: Extract to Specific Location (Terminal)
```bash
# Go to where you want to extract
cd ~/Desktop

# Extract the backup (replace with actual filename)
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260112_182138.tar.gz

# This creates a folder with all your files
```

### Method 3: Extract Specific File Only
```bash
# List what's inside the backup (without extracting)
tar -tzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260112_182138.tar.gz | head -20

# Extract just one file (example: .env)
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260112_182138.tar.gz .env

# Extract just one folder (example: directives/)
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260112_182138.tar.gz directives/
```

---

## Common Tasks

### Find Latest Backup
```bash
# Shows most recent backup at bottom
ls -lt ~/Anti-Gravity-Backups/

# Or get the exact filename
ls -t ~/Anti-Gravity-Backups/*.tar.gz | head -1
```

### Find Backup from Specific Date
```bash
# Example: Find backups from January 12, 2026
ls ~/Anti-Gravity-Backups/*20260112*.tar.gz
```

### Check Backup Size
```bash
# Human-readable sizes
du -h ~/Anti-Gravity-Backups/
```

### Extract to Desktop for Easy Access
```bash
# Creates a folder on your desktop
cd ~/Desktop
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260112_182138.tar.gz
mv Anti-Gravity\ Workspace ~/Desktop/Restored-Backup
```

---

## What's Inside a Backup?

Each backup contains:
```
anti-gravity-workspace/
├── directives/          # Your SOPs
├── execution/           # Your Python scripts
├── modal_workflows/     # Cloud automation
├── .env                 # API keys & secrets
├── credentials.json     # Google OAuth
├── token.json          # Google tokens
├── Claude.md           # Instructions
└── *.md files          # All documentation
```

**Not included (by design):**
- `.tmp/` folder (temporary files)
- `__pycache__/` (Python cache)
- `*.log` files (logs)
- `.git/` folder (use GitHub for version history)

---

## Recovery Scenarios

### Scenario 1: "I deleted a file by accident today"
**Solution:** Use Git
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git checkout HEAD -- path/to/file.py
```

### Scenario 2: "I need yesterday's version of a script"
**Solution:** Extract from backup
```bash
cd ~/Desktop
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260111_*.tar.gz execution/my_script.py
```

### Scenario 3: "I need to restore everything from 3 days ago"
**Solution:** Extract full backup
```bash
cd ~/Desktop
tar -xzf ~/Anti-Gravity-Backups/anti-gravity-workspace_20260109_*.tar.gz
mv Anti-Gravity\ Workspace ~/Desktop/Restored-Jan-9
```

### Scenario 4: "My computer crashed, restore from cloud"
**Solution:** Clone from GitHub
```bash
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace
# Add your .env and credentials.json back
```

---

## Backup Schedule

Your backups run **automatically** at:
- **6:00 PM** every day
- **11:00 PM** every day

**Manual backup anytime:**
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
bash backup_workspace.sh
```

---

## Verification Commands

### Check if auto-backup is running
```bash
launchctl list | grep antigravity
# Should show: com.antigravity.backup
```

### Check backup logs
```bash
tail ~/Anti-Gravity-Backups/backup.log
```

### Count your backups
```bash
ls ~/Anti-Gravity-Backups/*.tar.gz | wc -l
```

---

## Tips

1. **Backups older than 30 days are auto-deleted** (saves space)
2. **Each backup is ~3-5 MB** (very small!)
3. **Backups are timestamped** so you can find specific dates easily
4. **GitHub has unlimited history** for long-term version control
5. **Double-clicking .tar.gz works!** macOS auto-extracts

---

## Need Help?

**View all backup documentation:**
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
ls -l | grep BACKUP
```

**Key files:**
- [BACKUP_QUICKSTART.md](BACKUP_QUICKSTART.md) - Overview
- [BACKUP_OPTIONS.md](BACKUP_OPTIONS.md) - Full guide
- [VERSION_CONTROL_GUIDE.md](VERSION_CONTROL_GUIDE.md) - Git workflow
- **HOW_TO_ACCESS_BACKUPS.md** (this file) - How to open backups

---

## Quick Copy-Paste Commands

**Open backup folder in Finder:**
```bash
open ~/Anti-Gravity-Backups/
```

**Extract latest backup to Desktop:**
```bash
cd ~/Desktop && tar -xzf ~/Anti-Gravity-Backups/$(ls -t ~/Anti-Gravity-Backups/*.tar.gz | head -1)
```

**Create manual backup right now:**
```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" && bash backup_workspace.sh
```

**See backup file contents without extracting:**
```bash
tar -tzf ~/Anti-Gravity-Backups/$(ls -t ~/Anti-Gravity-Backups/*.tar.gz | head -1) | less
```

---

You're all set! Your workspace is backed up automatically twice daily. 🚀
