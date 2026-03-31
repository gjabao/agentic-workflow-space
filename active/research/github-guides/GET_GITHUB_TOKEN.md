# Get Your GitHub Token (2 Minutes)

The token you provided appears to be invalid or expired. Let's get a fresh one!

---

## 🎯 Step-by-Step Instructions

### 1. Open GitHub Token Page

**Click this link (or copy/paste into browser):**
```
https://github.com/settings/tokens/new
```

This will open GitHub's "New personal access token" page.

---

### 2. Fill Out the Form

**Token name (Note):**
```
Anti-Gravity Workspace Auto-Backup
```

**Expiration:**
- Select: **No expiration**
- (Or choose "1 year" if you prefer)

**Select scopes:**
- ✅ Check **`repo`** (this will check all sub-boxes under it)
  - ✅ repo:status
  - ✅ repo_deployment
  - ✅ public_repo
  - ✅ repo:invite
  - ✅ security_events

**Scroll to bottom and click:**
- 🟢 **"Generate token"** button

---

### 3. Copy Your Token

After clicking "Generate token", you'll see a **green box** with your token.

**IMPORTANT:**
- The token starts with `ghp_`
- It's about 40 characters long
- Example: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **You can only see it ONCE** - GitHub won't show it again!

**Click the copy button** (📋 icon next to the token)

---

### 4. Save It Temporarily

**Paste the token somewhere safe temporarily:**
- Notes app
- TextEdit
- Or just keep the GitHub tab open

You'll need to paste it in the terminal in the next step.

---

### 5. Run the Setup Command

Open Terminal and run this command:

```bash
bash "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace/setup_github_auth.sh"
```

When it asks for your token, **paste the token you just copied**.

---

## ✅ Verification

After the setup script runs, verify it worked:

```bash
cd "/Users/nguyengiabao/Downloads/Claude skill/Anti-Gravity Workspace"
git push origin main
```

You should see:
```
✅ Successfully pushed to GitHub!
```

---

## 🆘 Troubleshooting

### "Token is invalid"

**Possible reasons:**
1. Token was copied with extra spaces - try copying again
2. Token expired - create a new one
3. Didn't select "repo" scope - recreate with repo checked

### "Permission denied"

Make sure you checked the **`repo`** scope when creating the token.

### "Repository not found"

Your token needs access to the `gjabao/anti-gravity-workspace` repository.

---

## 🔐 Security Notes

1. **Keep your token secret** - treat it like a password
2. **Don't share it** with anyone
3. **Don't commit it** to git (our scripts handle it securely)
4. If you accidentally expose it, revoke it at: https://github.com/settings/tokens

---

## Quick Links

- **Generate token:** https://github.com/settings/tokens/new
- **View existing tokens:** https://github.com/settings/tokens
- **Your repository:** https://github.com/gjabao/anti-gravity-workspace

---

Ready? Let's get that token! 🚀
