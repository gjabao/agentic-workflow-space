# GitHub Backup - Quick Reference Card

## 🌐 Your Repository
```
https://github.com/gjabao/anti-gravity-workspace
```

---

## ⚡ Quick Actions

### **Download Everything (ZIP)**
1. Open: https://github.com/gjabao/anti-gravity-workspace
2. Click: **"Code"** (green button)
3. Click: **"Download ZIP"**
4. Extract: Double-click the `.zip` file

**Or use this direct link:**
```
https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.zip
```

---

### **Clone with Git**
```bash
# Download to Desktop
cd ~/Desktop
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

---

### **Update Existing Clone**
```bash
cd ~/Desktop/anti-gravity-workspace
git pull origin main
```

---

## 📂 Common Tasks

| Task | How To Do It |
|------|--------------|
| **View files online** | Open: https://github.com/gjabao/anti-gravity-workspace |
| **Download everything** | Click "Code" → "Download ZIP" |
| **See what changed** | Click "Commits" tab |
| **Download old version** | Commits → Find date → Click `<>` → Download ZIP |
| **Download one file** | Navigate to file → Click "Raw" → Save As |
| **Search code** | Press `/` on GitHub page, type search term |

---

## 🔄 Backup Schedule

| Time | What Happens | Where |
|------|--------------|-------|
| **6:00 PM daily** | Auto backup | → GitHub + Local |
| **11:00 PM daily** | Auto backup | → GitHub + Local |
| **Anytime** | Manual | Run `backup_to_github.sh` |

---

## 📍 Backup Locations

```
1. GitHub Cloud:
   https://github.com/gjabao/anti-gravity-workspace

2. Local Archives:
   ~/Anti-Gravity-Backups/

3. Original Workspace:
   /Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace
```

---

## 🚀 Recovery Commands

### **Lost Everything?**
```bash
cd ~/Desktop
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

### **Need Yesterday's Version?**
```bash
cd anti-gravity-workspace
git checkout HEAD@{1.day.ago}
```

### **Need Specific File from Last Week?**
```bash
git checkout HEAD@{1.week.ago} -- path/to/file.py
```

---

## 🔐 What's Backed Up

### ✅ **On GitHub (208 files)**
- All directives (`directives/*.md`)
- All scripts (`execution/*.py`)
- All documentation
- Modal workflows
- Backup scripts
- CSV data files

### ❌ **Not on GitHub (Protected Locally)**
- `.env` (API keys)
- `credentials.json` (Google OAuth)
- `token.json` (OAuth tokens)
- `ONBOARDING_SETUP_STATUS.md` (embedded secrets)

---

## 📚 Documentation

| Guide | Purpose |
|-------|---------|
| **[DOWNLOAD_FROM_GITHUB.md](DOWNLOAD_FROM_GITHUB.md)** | Complete download guide |
| **[BACKUP_SUMMARY.md](BACKUP_SUMMARY.md)** | Backup system overview |
| **[HOW_TO_ACCESS_BACKUPS.md](HOW_TO_ACCESS_BACKUPS.md)** | Local backup access |
| **[GITHUB_BACKUP_QUICKSTART.md](GITHUB_BACKUP_QUICKSTART.md)** | GitHub setup |

---

## 💡 Pro Tips

**View Online (No Download):**
- Just open https://github.com/gjabao/anti-gravity-workspace in browser
- Browse all files, search code, view history

**Access from Phone:**
- Install GitHub Mobile app
- Sign in and navigate to your repo

**Keep Local Copy Synced:**
```bash
cd ~/Documents/anti-gravity-workspace
git pull
```

---

## 🆘 Need Help?

**Can't access GitHub?**
- Use local backup: `~/Anti-Gravity-Backups/`

**Want older version?**
- See: [DOWNLOAD_FROM_GITHUB.md](DOWNLOAD_FROM_GITHUB.md) → "Download Specific Version"

**Lost credentials?**
- `.env`, `credentials.json`, `token.json` stay local
- Recreate from your original sources

---

## ✅ Checklist

- ✅ Repository URL: https://github.com/gjabao/anti-gravity-workspace
- ✅ Auto-backup: Running (6 PM & 11 PM)
- ✅ Manual backup: `bash backup_to_github.sh`
- ✅ Download: "Code" → "Download ZIP"
- ✅ Clone: `git clone https://github.com/gjabao/anti-gravity-workspace.git`

**Your backups are safe and accessible 24/7!** 🚀
