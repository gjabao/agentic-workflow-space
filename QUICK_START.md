# Quick Start Guide - Client Onboarding

**Last Updated:** 2026-01-14

---

## 🚀 Onboard a New Client (One Command)

```bash
python3 execution/onboard_new_client.py --interactive
```

**That's it!** The system will:
1. ✅ Generate all research
2. ✅ Create 14-day nurture plan
3. ✅ Generate all 7 touch content files (complete, ready-to-use)
4. ✅ Create ClickUp task with 11 subtasks
5. ✅ Update all ClickUp subtasks with content links and instructions

---

## 📋 Example: Onboarding LRO Staffing

### Input
```
Company Name: LRO Staffing
Company Website: https://lrostaffing.com
Primary Contact Name: Sakura Gomi
Contact Email: sgomi@lrostaffing.com
Contact LinkedIn URL: [optional]
Form submission JSON path: [optional]
ClickUp List ID: [press Enter for default: 901807718471]
Estimated Deal Size: $5K-15K
Additional Notes: Specializes in Finance & Accounting placements
```

### Output (Automatically Created)

**1. Content Files** (`.tmp/lro_assets/`):
- `touch_1_hiring_guide.md` - Complete 5-section PDF content
- `touch_2_loom_script.md` - Complete 3-5 min video script
- `touch_3_notion_template.md` - Complete Notion workspace structure
- `touch_4_competitor_analysis.md` - Complete 6-7 page analysis
- `touch_5_linkedin_engagement.md` - Complete LinkedIn scripts
- `touch_6_whatsapp_checkin.md` - Complete WhatsApp messages + guide
- `touch_7_call_invitation.md` - Complete call invitation + agenda

**2. ClickUp Task:** https://app.clickup.com/t/86ew715mw
- Parent task with all content links
- 11 subtasks with step-by-step instructions

**3. Execution Guide:** `LRO_STAFFING_EXECUTION_GUIDE.md`

---

## ✅ Execute Touch 1 (Day 1 - TODAY!)

### Step 1: Open Touch 1 Content
```bash
open .tmp/lro_assets/touch_1_hiring_guide.md
```

### Step 2: Export to PDF
- Copy content into Google Docs
- Add branding (logo, colors)
- Export as PDF
- Or use Canva for professional design

### Step 3: Send to Client
**Email:**
- **To:** sgomi@lrostaffing.com
- **Subject:** "Boost Your Hiring Strategy: Exclusive Resource Inside"
- **Body:** (Use template from Touch 1 file)
- **Attach:** PDF

**LinkedIn DM:**
- Find Sakura Gomi on LinkedIn
- Send same message + PDF link

### Step 4: Mark Complete
- ✅ Check off "Touch 1" in ClickUp
- Log delivery in `.tmp/nurture_log_lro_staffing.md`

---

## 📅 14-Day Execution Schedule

| Day | Touch | Action | Channel | Pitch? |
|-----|-------|--------|---------|--------|
| 1 | Touch 1 | Send hiring guide PDF | Email + LinkedIn | ❌ NO |
| 3 | Touch 2 | Send Loom video (3-5 min) | WhatsApp + Email | ❌ NO |
| 5 | Touch 3 | Share Notion workspace | Email | ❌ NO |
| 7 | Touch 4 | Send competitor analysis PDF | Email | ❌ NO |
| 10 | Touch 5 | LinkedIn engagement + DM | LinkedIn | ❌ NO |
| 12 | Touch 6 | Check-in message + guide | WhatsApp | ❌ NO |
| 14 | Touch 7 | Call invitation | WhatsApp + Email | ✅ SOFT ASK |

**After Day 14:** Assess engagement (HIGH/MEDIUM/LOW) → Schedule discovery call if HIGH

---

## 🎯 Service Positioning

When Touch 7 arrives, frame your service as:

> **"I help recruitment agencies like yours connect with new clients and strategic partners to drive growth."**

**Offer includes:**
- Strategic partnership development (CPA firms, CFO networks)
- Client acquisition strategies
- Content-driven lead generation
- Differentiated outreach playbooks

**Free intro offer:**
> "I'd love to offer you a free introductory partnership analysis—I'll map out 5-10 strategic partners that would be a perfect fit for your expansion, and share exactly how to approach them."

---

## 📊 Engagement Tracking

After each touch, log in `.tmp/nurture_log_lro_staffing.md`:

```markdown
## Touch 1 (2026-01-14)
- Sent: Email + LinkedIn DM
- Response: [None yet / Opened / Replied]
- Engagement: [Low / Medium / High]
- Notes: [Any observations]
```

**Engagement Signals:**
- ✅ **HIGH:** Opens emails, replies, asks questions, engages on LinkedIn
- ⚠️ **MEDIUM:** Opens emails, no reply, passive engagement
- ❌ **LOW:** No opens, no replies, no engagement

**Decision Rule:**
- HIGH engagement → Proceed to discovery call
- MEDIUM engagement → One more touch, then reassess
- LOW engagement → STOP (protect your energy)

---

## 🔄 For Next Client

Just run the same command:

```bash
python3 execution/onboard_new_client.py --interactive
```

The system automatically:
- Creates new asset directory: `.tmp/[new_company]_assets/`
- Generates all content specific to new company
- Creates new ClickUp task
- Updates all subtasks with new content links

**No manual work. No code editing. Just run and execute.**

---

## 🛠️ Troubleshooting

### "ClickUp task creation failed"
**Fix:** Check API key in `.env`:
```bash
cat .env | grep CLICKUP_API_KEY
```

### "Content generation failed"
**Fix:** Check Azure OpenAI key in `.env`:
```bash
cat .env | grep AZURE_OPENAI_KEY
```

### "ClickUp update failed"
**Fix:** Run update manually:
```bash
python3 execution/update_client_clickup.py --task-id TASK_ID --company "Company Name"
```

---

## 📚 Reference Documents

- **Full Setup:** [CLICKUP_SETUP.md](CLICKUP_SETUP.md)
- **System Update:** [SYSTEM_UPDATE_2026-01-14.md](SYSTEM_UPDATE_2026-01-14.md)
- **Workflow Guide:** [NURTURE_WORKFLOW_GUIDE.md](NURTURE_WORKFLOW_GUIDE.md)
- **Example Execution:** [LRO_STAFFING_EXECUTION_GUIDE.md](LRO_STAFFING_EXECUTION_GUIDE.md)

---

## ⚡ Quick Commands

**Onboard new client:**
```bash
python3 execution/onboard_new_client.py --interactive
```

**View ClickUp workspaces:**
```bash
python3 execution/clickup_onboard_client.py --list-workspaces
```

**Update ClickUp manually:**
```bash
python3 execution/update_client_clickup.py --task-id TASK_ID --company "Company Name"
```

**Check LRO Staffing task:**
```bash
open https://app.clickup.com/t/86ew715mw
```

---

**Ready to scale!** 🚀

You can now onboard 10+ clients per day with zero manual content generation.
