# ClickUp Setup & Configuration

**Last Updated:** 2026-01-14

## ⚡ Quick Start - Fully Automated Onboarding

The system now **automatically generates all content AND updates ClickUp** when you onboard a new client.

**One command does everything:**

```bash
python3 execution/onboard_new_client.py --interactive
```

**What happens automatically:**
1. ✅ AI qualification (if form data provided)
2. ✅ Deep company research
3. ✅ 14-day nurture plan creation
4. ✅ **All 7 touch content files generated** (complete, ready-to-use)
5. ✅ ClickUp task created with 11 subtasks
6. ✅ **All ClickUp subtasks updated with content links and instructions**

**Result:** Everything is ready to execute Touch 1 immediately.

---

## Default Configuration

The system is now configured to automatically use your **"Clients"** list in the **CRM** folder for all client onboarding.

### Default List Details

- **List Name:** Clients
- **Folder:** CRM
- **List ID:** `901807718471`
- **URL:** https://app.clickup.com/9018921308/v/li/901807718471

This default is stored in: `.env.clickup`

---

## Quick Commands

### Onboard New Client (Uses Default List Automatically)

**Interactive Mode (Recommended):**
```bash
python3 execution/onboard_new_client.py --interactive
```

**Direct Command:**
```bash
python3 execution/onboard_new_client.py \
    --company "Company Name" \
    --website "https://example.com" \
    --contact "Contact Name" \
    --email "email@example.com" \
    --deal-size "$5K-15K"
```

The `--clickup-list-id` parameter is now **optional** - it will use `901807718471` by default.

### Override Default (Use Different List)

If you need to use a different list for a specific client:

```bash
python3 execution/onboard_new_client.py \
    --company "Special Client" \
    --website "https://special.com" \
    --contact "Name" \
    --email "email@example.com" \
    --clickup-list-id "DIFFERENT_LIST_ID"
```

---

## What Gets Created During Onboarding

When you onboard a client, the system automatically:

### 1. Generates All Content (7 Touches)
Creates `.tmp/[company]_assets/` directory with:
- `touch_1_hiring_guide.md` - Complete PDF content ready to export
- `touch_2_loom_script.md` - Complete 3-5 minute video script
- `touch_3_notion_template.md` - Complete Notion workspace structure
- `touch_4_competitor_analysis.md` - Complete competitor analysis PDF content
- `touch_5_linkedin_engagement.md` - Complete LinkedIn engagement scripts
- `touch_6_whatsapp_checkin.md` - Complete WhatsApp messages + talent guide
- `touch_7_call_invitation.md` - Complete call invitation + session agenda

### 2. Creates ClickUp Task: 🏢 [Company Name]

Parent task contains:
- Client information (website, contact, deal size, onboarding date)
- Workflow philosophy (value-first nurture, 14 days, no pitch until Day 14)
- Links to all 7 content files
- Quick start instructions

### 3. Creates 11 Subtasks (Automatically Updated with Content Links):

1. **🔍 Phase 0B: AI Qualification** - Analyze form data, score 0-10
2. **🔬 Phase 1: Deep Company Research** - Scrape website, competitors, pain points
3. **📄 Touch 1 (Day 1): Industry Resource PDF** - LinkedIn/Email, NO PITCH
4. **🎥 Touch 2 (Day 3): Custom Loom Video** - WhatsApp/Email, NO PITCH
5. **📊 Touch 3 (Day 5): Notion Workspace** - Email, NO PITCH
6. **📈 Touch 4 (Day 7): Industry Report** - Email, NO PITCH
7. **💬 Touch 5 (Day 10): LinkedIn Engagement** - LinkedIn, NO PITCH
8. **✅ Touch 6 (Day 12): Check-In** - WhatsApp, NO PITCH
9. **📞 Touch 7 (Day 14): SOFT Call Invitation** - WhatsApp/Email, SOFT ASK
10. **📊 Phase 3: Engagement Assessment** - Evaluate HIGH/MEDIUM/LOW engagement
11. **☎️ Phase 4: Schedule Discovery Call** - Only if HIGH engagement

Each subtask includes:
- Exact command to run
- Expected deliverables
- Channel guidance
- Pitch restrictions

---

## Changing the Default List

To use a different list as the default:

1. **Find your desired list ID:**
   ```bash
   python3 execution/clickup_onboard_client.py --list-workspaces
   python3 execution/clickup_onboard_client.py --list-spaces TEAM_ID
   python3 execution/clickup_onboard_client.py --list-folders SPACE_ID
   python3 execution/clickup_onboard_client.py --list-lists FOLDER_ID
   ```

2. **Update `.env.clickup`:**
   ```bash
   CLICKUP_DEFAULT_LIST_ID=YOUR_NEW_LIST_ID
   ```

3. **Test it:**
   ```bash
   python3 execution/onboard_new_client.py --interactive
   ```

---

## Troubleshooting

### "ClickUp task creation failed"

**Check API key:**
```bash
# Verify CLICKUP_API_KEY exists in .env
cat .env | grep CLICKUP_API_KEY
```

**Test connection:**
```bash
python3 execution/clickup_onboard_client.py --list-workspaces
```

### "List not found"

The list ID in `.env.clickup` may be incorrect. Run the discovery commands above to find the correct list ID.

### "Subtasks not appearing"

This usually means the parent task was created but subtask creation failed. Check:
1. ClickUp API rate limits (wait 60 seconds, try again)
2. Parent task permissions (ensure you have edit access)

---

## ClickUp Workspace Structure

```
Gia Bảo's Workspace (9018921308)
└── Team Space (90183208544)
    └── CRM Folder
        └── Clients List (901807718471) ← DEFAULT
```

---

## Related Files

- **Default Config:** `.env.clickup`
- **API Key:** `.env` (CLICKUP_API_KEY)
- **Master Script:** `execution/onboard_new_client.py`
- **ClickUp Client:** `execution/clickup_client.py`
- **ClickUp Onboarder:** `execution/clickup_onboard_client.py`

---

## Next Steps

1. **Test the setup** with a real client using `--interactive` mode
2. **Verify tasks appear** in ClickUp at https://app.clickup.com/9018921308/v/li/901807718471
3. **Execute Touch 1** for your first client to test the full workflow

---

**Need help?** Check [NURTURE_WORKFLOW_GUIDE.md](NURTURE_WORKFLOW_GUIDE.md) for complete workflow documentation.
