# Version Control Guide: Anti-Gravity Workspace

## Current Setup Status

✅ **Git repository initialized**
✅ **Remote configured:** `https://github.com/gjabao/anti-gravity-workspace.git`
✅ **`.gitignore` configured** for DO Architecture

---

## Daily Workflow: Keep Your Workspace Updated

### 1. Before Starting Work (Pull Latest Changes)
```bash
# Fetch and merge latest changes from GitHub
git pull origin main
```

**When to use:** Start of each work session, before making changes.

---

### 2. During Work (Save Changes Locally)

#### Option A: Commit Specific Changes
```bash
# Check what changed
git status

# Add specific files
git add directives/new_workflow.md
git add execution/new_script.py

# Commit with descriptive message
git commit -m "Add lead enrichment workflow"
```

#### Option B: Commit All Changes (Quick)
```bash
# Add all changed files
git add .

# Commit everything
git commit -m "Update scraping workflows and fix email validation"
```

---

### 3. After Work (Backup to GitHub)
```bash
# Push changes to GitHub
git push origin main
```

**Result:** Your work is now safely stored in the cloud ☁️

---

## Complete Update Cycle (One Command)

For quick updates when you've made changes:

```bash
# Stage all changes, commit, and push
git add . && git commit -m "Daily update: $(date +%Y-%m-%d)" && git push origin main
```

---

## Best Practices

### ✅ DO Commit These Files
- **Directives:** `directives/*.md` (your SOPs)
- **Scripts:** `execution/*.py` (your tools)
- **Documentation:** `*.md` files
- **Configuration:** `.env` (already in your repo for private sharing)
- **Credentials:** `credentials.json`, `token.json` (already committed)

### ❌ DON'T Commit These Files
- **Temp data:** `.tmp/` folder (auto-ignored)
- **Logs:** `*.log` files (auto-ignored)
- **Python cache:** `__pycache__/` (auto-ignored)
- **CSV exports:** Large data files (store in Google Sheets instead)

---

## Common Scenarios

### Scenario 1: Made Changes, Want to Save
```bash
git add .
git commit -m "Improved Google Maps scraper rate limiting"
git push origin main
```

### Scenario 2: Working on Multiple Machines
```bash
# On Machine A (laptop)
git push origin main

# On Machine B (desktop)
git pull origin main  # Get latest changes
# ... make changes ...
git push origin main

# Back on Machine A
git pull origin main  # Sync changes from Machine B
```

### Scenario 3: Undo Last Commit (Before Pushing)
```bash
# Keep changes, undo commit
git reset --soft HEAD~1

# Discard changes, undo commit
git reset --hard HEAD~1
```

### Scenario 4: See What Changed
```bash
# View changes not yet committed
git diff

# View commit history
git log --oneline -10

# View changes in last commit
git show HEAD
```

---

## Automated Backup Script

Create a quick backup alias:

```bash
# Add to your ~/.bashrc or ~/.zshrc
alias agw-save='cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" && git add . && git commit -m "Auto-save: $(date)" && git push origin main && echo "✅ Workspace backed up to GitHub!"'
```

**Usage:** Just type `agw-save` in terminal to backup everything.

---

## Branch Strategy (Optional - For Experimentation)

### Create a Test Branch
```bash
# Create and switch to experiment branch
git checkout -b experiment-new-feature

# Make changes...
# Test...

# If successful, merge back to main
git checkout main
git merge experiment-new-feature
git push origin main

# If failed, just switch back (changes stay in branch)
git checkout main
```

**Use case:** Testing risky changes without affecting main workflow.

---

## Recovery & History

### View File History
```bash
# See all changes to a specific file
git log --follow -- execution/scrape_google_maps.py
```

### Restore Old Version of File
```bash
# Restore file from 3 commits ago
git checkout HEAD~3 -- execution/scrape_google_maps.py
```

### See What Changed in a Commit
```bash
# Show changes in specific commit
git show 6fc8e36
```

---

## GitHub Web Interface

**Access your code anywhere:**
🌐 `https://github.com/gjabao/anti-gravity-workspace`

**Features:**
- ✅ Browse files online
- ✅ Edit files directly (auto-commits)
- ✅ View commit history
- ✅ Clone to new machines
- ✅ Share with collaborators

---

## Clone to New Machine

```bash
# On new machine
git clone https://github.com/gjabao/anti-gravity-workspace.git
cd anti-gravity-workspace

# Install dependencies
pip3 install -r requirements.txt

# Setup .env (copy from GitHub or re-enter keys)
# Already committed, so it should be there!
```

---

## Collaboration Setup (If Working with Others)

### Add Collaborator
1. Go to: `https://github.com/gjabao/anti-gravity-workspace/settings/access`
2. Click "Add people"
3. Enter their GitHub username
4. They can now clone, push, and pull

### Their Setup
```bash
# Clone repo
git clone https://github.com/gjabao/anti-gravity-workspace.git

# Before making changes
git pull origin main

# After making changes
git add .
git commit -m "Description of changes"
git push origin main
```

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Get latest | `git pull origin main` |
| Save changes | `git add . && git commit -m "message"` |
| Backup to cloud | `git push origin main` |
| Check status | `git status` |
| View history | `git log --oneline -10` |
| Undo changes | `git checkout -- filename` |
| Full sync | `git pull && git add . && git commit -m "update" && git push` |

---

## Recommended Schedule

**Daily:**
```bash
# Morning: Pull latest
git pull origin main

# Evening: Push changes
git add . && git commit -m "Daily update" && git push origin main
```

**Weekly:**
```bash
# Review what changed
git log --oneline --since="1 week ago"

# Clean up temp files
rm -rf .tmp/*
```

**Monthly:**
```bash
# Create backup branch
git checkout -b backup-2026-01
git push origin backup-2026-01
git checkout main
```

---

## TL;DR: Simplest Workflow

```bash
# Start of day
git pull origin main

# End of day (or after significant changes)
git add .
git commit -m "What I changed today"
git push origin main
```

**That's it!** Your workspace is now version-controlled and backed up. 🚀

---

## Current Repository Status

Your repo is already set up correctly:
- ✅ 2 commits in history
- ✅ `.gitignore` configured properly
- ✅ Connected to GitHub
- ✅ `.env` and credentials committed (private repo)

**You're ready to go!** Just use the workflow above to keep it updated.