# GitHub Auto-Backup Setup Guide

## Quick Setup (5 Minutes)

Follow these steps to enable automatic GitHub backups.

---

## Step 1: Generate GitHub Personal Access Token

1. **Go to GitHub Settings:**
   - Visit: https://github.com/settings/tokens
   - Or: GitHub.com → Click your profile (top right) → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate new token:**
   - Click **"Generate new token"** → **"Generate new token (classic)"**
   - Note: `Anti-Gravity Workspace Auto-Backup`
   - Expiration: **No expiration** (or 1 year if you prefer)
   - Select scopes: ✅ **repo** (all repo permissions)
   - Click **"Generate token"** at bottom

3. **Copy the token immediately!**
   - It looks like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **Save it** - you won't see it again!

---

## Step 2: Configure GitHub Authentication

### Option A: Use GitHub CLI (Easiest)

```bash
# Install GitHub CLI (if not installed)
brew install gh

# Login with your token
gh auth login
# Choose: GitHub.com
# Choose: HTTPS
# Choose: Paste an authentication token
# Paste your token from Step 1

# Test it works
gh auth status
```

### Option B: Use Token Directly

```bash
# Configure git to use your token
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# Update remote URL to use token (replace YOUR_TOKEN)
git remote set-url origin https://YOUR_TOKEN@github.com/gjabao/anti-gravity-workspace.git

# Test it works
git push origin main
```

### Option C: Use Credential Helper (Recommended)

This stores your credentials securely in macOS Keychain:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"

# The credential helper is already configured (osxkeychain)
# Just try to push - it will prompt for credentials
git push origin main

# When prompted:
# Username: gjabao
# Password: [paste your token from Step 1]

# Credentials will be saved in macOS Keychain for future use
```

---

## Step 3: Test Automatic Backup

Once authenticated, test the backup system:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
bash backup_workspace.sh
```

You should see:
```
✓ Pushed to GitHub successfully
✓ Archive created: anti-gravity-workspace_20260112_XXXXXX.tar.gz
✓ Backup Complete!
```

---

## Step 4: Enable Auto-Push (Already Configured!)

Your system is already set to auto-backup at:
- **6:00 PM** daily
- **11:00 PM** daily

The LaunchAgent will automatically push to GitHub if authentication is working.

Verify it's running:
```bash
launchctl list | grep antigravity
# Should show: com.antigravity.backup
```

---

## Manual Backup Command

### Simple One-Liner

Add this to your shell config for easy backups:

```bash
# Open your shell config
nano ~/.zshrc
# (or ~/.bash_profile if using bash)

# Add this alias at the end:
alias agw-backup='cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace" && git add . && git commit -m "Backup: $(date +"%Y-%m-%d %H:%M")" && git push origin main && echo "✅ Backed up to GitHub!"'

# Save and exit (Ctrl+X, then Y, then Enter)

# Reload your shell
source ~/.zshrc
```

Now you can backup anytime with:
```bash
agw-backup
```

---

## Troubleshooting

### "Authentication failed" when pushing

**Solution:** Your token expired or wasn't saved. Redo Step 2.

### "remote: Support for password authentication was removed"

**Problem:** You used your GitHub password instead of a token.

**Solution:** Use the Personal Access Token from Step 1, NOT your password.

### "Permission denied (publickey)"

**Problem:** Trying to use SSH but not configured.

**Solution:** Use HTTPS method (Option C in Step 2).

### Check what authentication method you're using:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git remote -v
```

Should show:
```
origin  https://github.com/gjabao/anti-gravity-workspace.git (fetch)
origin  https://github.com/gjabao/anti-gravity-workspace.git (push)
```

---

## Security Notes

1. **Never share your token** - treat it like a password
2. **Token in URL** (Option B) is convenient but less secure
3. **Credential Helper** (Option C) is most secure - stores in macOS Keychain
4. **GitHub CLI** (Option A) is easiest and secure

---

## What Happens After Setup

Once configured, your workspace automatically:

1. **Commits changes** to git
2. **Pushes to GitHub** cloud storage
3. **Creates local archive** in ~/Anti-Gravity-Backups/
4. **Runs twice daily** (6 PM & 11 PM)

**Plus you can manually backup anytime:**
```bash
agw-backup
```

---

## Verify It's Working

Check your GitHub repository:
```bash
# Open in browser
open https://github.com/gjabao/anti-gravity-workspace

# Or check latest commit
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git log --oneline -5
```

You should see your recent commits!

---

## Recovery from GitHub

If you ever need to restore from GitHub:

```bash
# Clone to Desktop
cd ~/Desktop
git clone https://github.com/gjabao/anti-gravity-workspace.git

# Or download as ZIP
open https://github.com/gjabao/anti-gravity-workspace/archive/refs/heads/main.zip
```

---

## Next Steps

1. ✅ Generate GitHub token (Step 1)
2. ✅ Configure authentication (Step 2 - choose one option)
3. ✅ Test backup (Step 3)
4. ✅ Set up `agw-backup` alias (Step 4)
5. ✅ Verify auto-backup works (check at 6 PM or 11 PM)

---

## Quick Command Summary

```bash
# One-time setup
gh auth login    # OR use credential helper when you git push

# Daily usage (after alias is set)
agw-backup

# Check backup status
launchctl list | grep antigravity
git log --oneline -5
open https://github.com/gjabao/anti-gravity-workspace
```

Your workspace will be automatically backed up to GitHub! 🚀
