# How to Download Backup from GitHub

## 🎯 Quick Methods

### **Method 1: Download Entire Repository as ZIP (Easiest)**

**Step 1:** Open your repository in browser:
```
https://github.com/gjabao/anti-gravity-workspace
```

**Step 2:** Click the green **"Code"** button (top right)

**Step 3:** Click **"Download ZIP"**

**Step 4:** Extract the ZIP file
- Double-click the downloaded `.zip` file
- macOS will automatically extract it to a folder

**Done!** You now have all your files in: `anti-gravity-workspace-main/`

---

### **Method 2: Clone with Git (Recommended)**

This gives you full version history and ability to sync updates.

**Open Terminal and run:**
```bash
# Download to Desktop
cd ~/Desktop
git clone https://github.com/gjabao/anti-gravity-workspace.git

# Or download to a specific location
cd ~/Documents
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

**Result:** Creates folder `anti-gravity-workspace/` with all your files

---

### **Method 3: Using GitHub CLI**

If you have `gh` installed:

```bash
cd ~/Desktop
gh repo clone gjabao/anti-gravity-workspace
```

---

## 📦 What You'll Get

After downloading, you'll have:

```
anti-gravity-workspace/
├── directives/           # Your SOPs
├── execution/            # Your Python scripts
├── modal_workflows/      # Cloud automation
├── BACKUP_SUMMARY.md     # Documentation
├── README.md
└── ... (all 208 files)
```

**Note:** These files will NOT be included (they're in `.gitignore`):
- `.env` (you have this locally)
- `credentials.json` (you have this locally)
- `token.json` (you have this locally)
- `ONBOARDING_SETUP_STATUS.md` (protected)

---

## 🔄 Download Specific Version (Time Travel)

### **View All Versions:**

**In browser:**
1. Go to: https://github.com/gjabao/anti-gravity-workspace/commits/main
2. Browse all commits (backup snapshots)
3. Click any commit to see what changed

### **Download a Specific Past Version:**

**Using Browser:**
1. Go to commits: https://github.com/gjabao/anti-gravity-workspace/commits/main
2. Find the date you want
3. Click the **`<>`** icon (Browse files at this point in time)
4. Click **"Code"** → **"Download ZIP"**

**Using Git:**
```bash
# Clone the repo
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace

# See all versions
git log --oneline

# Go back to a specific date (example: Jan 10, 2026)
git checkout `git rev-list -n 1 --before="2026-01-10" main`

# Or go to a specific commit
git checkout 47417e4
```

---

## 📂 Download Individual Files

### **Download One File:**

**Method A: Browser**
1. Navigate to file on GitHub
2. Click **"Raw"** button
3. Right-click → **"Save As..."**

**Method B: Direct Download URL**
```
https://raw.githubusercontent.com/gjabao/anti-gravity-workspace/main/path/to/file.py
```

Example:
```bash
# Download a specific script
curl -O https://raw.githubusercontent.com/gjabao/anti-gravity-workspace/main/execution/scrape_google_maps.py
```

---

## 🚀 Recovery Scenarios

### **Scenario 1: Lost Everything, Need Full Restore**

```bash
# Download everything
cd ~/Desktop
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace

# Restore your secrets (you'll need to recreate these)
# 1. Copy your .env file back
# 2. Copy your credentials.json back
# 3. Copy your token.json back
```

### **Scenario 2: Need Yesterday's Version of One File**

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# See file history
git log --oneline execution/scrape_google_maps.py

# Restore from a specific commit
git checkout 47417e4 execution/scrape_google_maps.py
```

### **Scenario 3: New Computer Setup**

```bash
# 1. Clone from GitHub
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your credentials
# - Create .env file with your API keys
# - Add credentials.json (Google OAuth)
# - Run scripts to generate token.json

# 4. You're ready to go!
```

---

## 🌐 Access from Any Device

### **View Files Online (No Download)**

Just open in browser:
```
https://github.com/gjabao/anti-gravity-workspace
```

You can:
- ✅ Browse all files
- ✅ View file contents
- ✅ Search code
- ✅ See full history
- ✅ Download individual files

### **Access from Phone/Tablet**

1. Install **GitHub Mobile App**
2. Sign in to your account
3. Navigate to `gjabao/anti-gravity-workspace`
4. View files, search, browse history

---

## 💡 Pro Tips

### **Keep a Local Clone Synced**

```bash
# First time
cd ~/Documents
git clone https://github.com/gjabao/anti-gravity-workspace.git

# Later, to update with latest changes
cd ~/Documents/anti-gravity-workspace
git pull origin main
```

### **Download as Different Formats**

**TAR.GZ:**
```
https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.tar.gz
```

**ZIP:**
```
https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.zip
```

**Direct download command:**
```bash
# Download as ZIP
curl -L -o backup.zip https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.zip

# Download as TAR.GZ
curl -L -o backup.tar.gz https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.tar.gz
```

---

## 🔐 Private Repository Access

Your repository is currently **private**, which means:

- ✅ Only you can access it
- ✅ Need GitHub login to download
- ✅ Protected from public view

**To download on a new computer:**
1. Sign in to GitHub first
2. Then clone or download

---

## 📊 Compare Versions

**See what changed between versions:**

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# Compare current version with yesterday
git diff HEAD@{1.day.ago}

# Compare two specific commits
git diff 47417e4 eb47a71

# See just the file names that changed
git diff --name-only HEAD@{1.day.ago}
```

---

## 🆘 Common Questions

### **Q: Can I download just the directives folder?**

**A:** Using git sparse-checkout:
```bash
git clone --no-checkout https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace
git sparse-checkout init --cone
git sparse-checkout set directives
git checkout main
```

### **Q: How do I download the version from last week?**

**A:**
```bash
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace
git checkout `git rev-list -n 1 --before="1 week ago" main`
```

### **Q: Can I download from GitHub on a computer without git?**

**A:** Yes! Just use the ZIP download method:
1. Visit: https://github.com/gjabao/anti-gravity-workspace
2. Click "Code" → "Download ZIP"
3. No git needed!

---

## 🎯 Quick Reference

| What You Need | Command/Link |
|---------------|--------------|
| **Everything (ZIP)** | https://github.com/gjabao/anti-gravity-workspace → "Code" → "Download ZIP" |
| **Everything (Git)** | `git clone https://github.com/gjabao/anti-gravity-workspace.git` |
| **View Online** | https://github.com/gjabao/anti-gravity-workspace |
| **See All Versions** | https://github.com/gjabao/anti-gravity-workspace/commits/main |
| **Download One File** | Click file → "Raw" → Save As |
| **Update Existing Clone** | `git pull origin main` |

---

## ✅ Summary

**Easiest way:**
1. Go to https://github.com/gjabao/anti-gravity-workspace
2. Click green "Code" button
3. Click "Download ZIP"
4. Double-click to extract

**Best way for ongoing use:**
```bash
git clone https://github.com/gjabao/anti-gravity-workspace.git
```

Your files are safe on GitHub and can be downloaded anytime from anywhere! 🚀
