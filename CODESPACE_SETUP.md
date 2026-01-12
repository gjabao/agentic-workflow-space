# GitHub Codespace Setup Guide

## Quick Start for Collaborators

This repository is configured as a GitHub Codespace with everything pre-installed.

### What's Included

- **Python 3.11** runtime
- **Claude Code extension** (AI coding assistant)
- **All dependencies** auto-installed via requirements.txt
- **API keys & credentials** (already in .env, credentials.json, token.json)

### How to Launch

1. **Get access** - Repository owner must invite you (see below)
2. **Open Codespace**:
   - Go to: `https://github.com/[USERNAME]/[REPO-NAME]`
   - Click green **Code** button → **Codespaces** tab → **Create codespace on main**
3. **Wait 2-3 minutes** for setup to complete
4. **Start coding!** - All tools are ready to use

### Direct Codespace Link (After Repo Creation)

```
https://codespaces.new/[USERNAME]/[REPO-NAME]
```

## For Repository Owner: How to Invite Collaborators

### Option 1: Via GitHub Web UI

1. Go to your repo: `https://github.com/[USERNAME]/[REPO-NAME]`
2. Click **Settings** (tab)
3. Click **Collaborators** (left sidebar)
4. Click **Add people** button
5. Enter their GitHub username (e.g., `octocat`)
6. Select **Write** or **Admin** access
7. Click **Add [username] to this repository**

They'll receive an email invitation.

### Option 2: Via GitHub CLI (Faster)

```bash
# Install GitHub CLI if not already installed
# brew install gh  (macOS)
# sudo apt install gh  (Linux)

# Authenticate
gh auth login

# Add collaborator
gh repo add-collaborator [USERNAME]/[REPO-NAME] GITHUB_USERNAME --permission push
```

**Access levels:**
- `pull` - Read only
- `push` - Read + Write (recommended for collaborators)
- `admin` - Full control

### Example

```bash
gh repo add-collaborator nguyengiabao/anti-gravity-workspace johndoe --permission push
```

## What Collaborators Can Do

Once invited, collaborators can:

✅ Launch Codespaces instantly (no local setup)
✅ Access all API keys (from committed .env)
✅ Run all Python scripts
✅ Use Claude Code extension for AI assistance
✅ Push changes to the repo

## Troubleshooting

**"Codespace won't start"**
- Check if repo is private (Codespaces work on private repos)
- Ensure collaborator accepted invitation

**"Missing API keys"**
- Verify .env file is committed (it should be)
- Check .gitignore doesn't exclude .env

**"Python dependencies not installed"**
- Wait for postCreateCommand to finish (shows in terminal)
- Manually run: `pip install -r requirements.txt`

## Cost Notes

- **Codespaces billing** goes to repository owner
- Free tier: 120 core-hours/month (60 hours on 2-core machine)
- Stop/delete unused Codespaces to save quota

---

**Questions?** Contact the repository owner.
