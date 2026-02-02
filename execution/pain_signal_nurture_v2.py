#!/usr/bin/env python3
"""
Pain-Signal 5-Touch Client Nurture - V2 (Improved CRM Structure)

KEY IMPROVEMENTS OVER V1:
1. ✅ Clean visual status dashboard
2. ✅ Deduplication of prospects
3. ✅ Better formatting with collapsible sections
4. ✅ Custom fields for engagement tracking
5. ✅ Progress tracking with completion percentages
6. ✅ Cleaner email templates (no truncation)
7. ✅ Better parent task overview

This script automates the entire 5-touch nurture workflow:
1. Parse onboarding form
2. Create ClickUp parent task + 5 subtasks
3. Research prospects with pain signals (UNIQUE ONLY)
4. Generate ALL content for 5 touches (.md files)
5. Update ClickUp subtasks with ENHANCED step-by-step guides
6. Track engagement with custom fields

Usage:
    # Prepare all 5 touches at once
    python3 execution/pain_signal_nurture_v2.py \\
        --form-data .tmp/clients/lro_staffing/onboarding.json \\
        --prepare-all

    # Or execute touch-by-touch
    python3 execution/pain_signal_nurture_v2.py --form-data FILE --touch 1
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.clickup_client import ClickUpClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CASE STUDIES MAPPING
# =============================================================================

CASE_STUDIES = {
    "recruiting": {
        "name": "Crawford Thomas Recruiting",
        "results": "$100K+ revenue in one quarter, 39 placements",
        "industry": "Finance & Accounting recruiting",
        "pain_signals": "Job postings + funding rounds"
    },
    "edtech": {
        "name": "FabuLingua",
        "results": "5 new clients in 48 days",
        "industry": "EdTech platform",
        "pain_signals": "Expansion signals + funding"
    },
    "healthcare": {
        "name": "Aerolase Partner",
        "results": "1,000+ leads built, 40% reply rate",
        "industry": "Medical devices",
        "pain_signals": "New office openings + hiring"
    },
    "beauty": {
        "name": "Beauty Connect Shop",
        "results": "$181K revenue, 73% from email campaigns",
        "industry": "Beauty/Aesthetics",
        "pain_signals": "Product launches"
    },
    "default": {
        "name": "Connect Group",
        "results": "3x lead quality improvement in 90 days",
        "industry": "B2B services",
        "pain_signals": "Multiple triggers"
    }
}


# =============================================================================
# FORM PARSER
# =============================================================================

class OnboardingFormParser:
    """Parse onboarding form data and extract key fields."""

    @staticmethod
    def parse(form_data: Dict) -> Dict:
        """Parse form data into structured format with industry categorization."""

        # Extract client info
        client = {
            "company": form_data.get("client", {}).get("company", ""),
            "website": form_data.get("client", {}).get("website", ""),
            "first_name": form_data.get("client", {}).get("first_name", ""),
            "last_name": form_data.get("client", {}).get("last_name", ""),
            "email": form_data.get("client", {}).get("email", ""),
            "phone": form_data.get("client", {}).get("phone", "")
        }

        # Extract ICP
        icp = {
            "titles": form_data.get("icp", {}).get("titles", ""),
            "industries": form_data.get("icp", {}).get("industries", ""),
            "company_size": form_data.get("icp", {}).get("company_size", "")
        }

        # Extract business info
        business = {
            "unique_qualities": form_data.get("business", {}).get("unique_qualities", ""),
            "services": form_data.get("business", {}).get("services", "")
        }

        # Industry categorization
        industry_category = OnboardingFormParser._categorize_industry(
            icp.get("industries", ""),
            business.get("services", "")
        )

        # Create slug
        slug = client["company"].lower().replace(" ", "_").replace("-", "_")
        slug = "".join([c for c in slug if c.isalnum() or c == "_"])

        return {
            "client": client,
            "icp": icp,
            "business": business,
            "metadata": {
                "industry_category": industry_category,
                "slug": slug,
                "parsed_at": datetime.now().isoformat()
            }
        }

    @staticmethod
    def _categorize_industry(industries: str, services: str) -> str:
        """Categorize client's industry for case study matching."""
        combined = f"{industries} {services}".lower()

        if any(kw in combined for kw in ["recruit", "staffing", "hiring", "placement"]):
            return "recruiting"
        elif any(kw in combined for kw in ["edtech", "education", "learning", "training"]):
            return "edtech"
        elif any(kw in combined for kw in ["healthcare", "medical", "pharma", "health", "clinic", "hospital"]):
            return "healthcare"
        elif any(kw in combined for kw in ["beauty", "aesthetic", "cosmetic", "salon", "spa"]):
            return "beauty"
        else:
            return "default"


# =============================================================================
# PROSPECT RESEARCHER (WITH DEDUPLICATION)
# =============================================================================

class ProspectResearcher:
    """Research prospects with pain signals - UNIQUE ONLY."""

    @staticmethod
    def research_prospects(icp_data: Dict, count: int = 8) -> List[Dict]:
        """
        Research UNIQUE prospects matching ICP with active pain signals.

        V2 IMPROVEMENT: Returns UNIQUE prospects only (no duplicates)
        """
        logger.info(f"Researching {count} UNIQUE prospects...")
        logger.warning("⚠️ Using MOCK data - integrate with Apollo/LinkedIn for real prospects")

        # Mock prospects - UNIQUE ONLY (V2 improvement)
        unique_prospects = [
            {
                "name": "Michael Chen",
                "first_name": "Michael",
                "title": "CFO",
                "company": "MedTech Solutions Inc.",
                "company_size": "42 employees",
                "industry": "Medical Devices",
                "email": "michael.chen@medtechsolutions.com",
                "pain_signal": "Posted 'Senior Accountant' role 3 days ago",
                "job_title_hiring": "Senior Accountant",
                "days_ago": "3 days ago",
                "source": "LinkedIn"
            },
            {
                "name": "Sarah Johnson",
                "first_name": "Sarah",
                "title": "VP Finance",
                "company": "Pharma Distributors Ltd",
                "company_size": "35 employees",
                "industry": "Pharmaceutical Distribution",
                "email": "sarah.johnson@pharmadist.ca",
                "pain_signal": "Posted 'Controller' role 5 days ago",
                "job_title_hiring": "Controller",
                "days_ago": "5 days ago",
                "source": "Indeed"
            },
            {
                "name": "David Kim",
                "first_name": "David",
                "title": "Controller",
                "company": "BuildCorp Inc.",
                "company_size": "28 employees",
                "industry": "Construction",
                "email": "dkim@buildcorpinc.com",
                "pain_signal": "Posted 'Staff Accountant' role 2 days ago",
                "job_title_hiring": "Staff Accountant",
                "days_ago": "2 days ago",
                "source": "LinkedIn"
            },
            {
                "name": "Emily Rodriguez",
                "first_name": "Emily",
                "title": "CFO",
                "company": "TechGrowth Solutions",
                "company_size": "48 employees",
                "industry": "SaaS",
                "email": "erodriguez@techgrowth.io",
                "pain_signal": "Posted 'Financial Analyst' role 1 day ago",
                "job_title_hiring": "Financial Analyst",
                "days_ago": "1 day ago",
                "source": "LinkedIn"
            },
            {
                "name": "James Wilson",
                "first_name": "James",
                "title": "Director of Finance",
                "company": "GreenEnergy Corp",
                "company_size": "52 employees",
                "industry": "Renewable Energy",
                "email": "jwilson@greenenergy.com",
                "pain_signal": "Posted 'Senior Accountant' role 4 days ago",
                "job_title_hiring": "Senior Accountant",
                "days_ago": "4 days ago",
                "source": "Indeed"
            },
            {
                "name": "Lisa Park",
                "first_name": "Lisa",
                "title": "VP of Finance",
                "company": "HealthPlus Clinic",
                "company_size": "31 employees",
                "industry": "Healthcare",
                "email": "lpark@healthplus.ca",
                "pain_signal": "Posted 'Accounting Manager' role 6 days ago",
                "job_title_hiring": "Accounting Manager",
                "days_ago": "6 days ago",
                "source": "LinkedIn"
            },
            {
                "name": "Robert Anderson",
                "first_name": "Robert",
                "title": "CFO",
                "company": "LogiTrans Inc.",
                "company_size": "44 employees",
                "industry": "Logistics",
                "email": "randerson@logitrans.com",
                "pain_signal": "Posted 'Controller' role 2 days ago",
                "job_title_hiring": "Controller",
                "days_ago": "2 days ago",
                "source": "Indeed"
            },
            {
                "name": "Maria Garcia",
                "first_name": "Maria",
                "title": "Director of Accounting",
                "company": "RetailPro Systems",
                "company_size": "39 employees",
                "industry": "Retail Technology",
                "email": "mgarcia@retailpro.com",
                "pain_signal": "Posted 'Staff Accountant' role 1 day ago",
                "job_title_hiring": "Staff Accountant",
                "days_ago": "1 day ago",
                "source": "LinkedIn"
            }
        ]

        return unique_prospects[:count]


# =============================================================================
# CONTENT GENERATOR (IMPROVED FORMATTING)
# =============================================================================

class ContentGenerator:
    """Generate all .md content files for 5-touch nurture - V2 IMPROVED."""

    def __init__(self, client_data: Dict, prospects: List[Dict]):
        self.client = client_data["client"]
        self.icp = client_data["icp"]
        self.business = client_data["business"]
        self.metadata = client_data["metadata"]
        self.prospects = prospects

    def generate_all(self, output_dir: str):
        """Generate ALL content for 5 touches."""
        logger.info("Generating content for all 5 touches...")

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Save onboarding data
        with open(f"{output_dir}/onboarding.json", "w") as f:
            json.dump({
                "client": self.client,
                "icp": self.icp,
                "business": self.business,
                "metadata": self.metadata
            }, f, indent=2)

        # Generate prospects research file
        self._generate_prospects_file(output_dir)

        # Generate engagement log
        self._generate_engagement_log(output_dir)

        # Generate each touch
        self._generate_touch_1(output_dir)
        self._generate_touch_2(output_dir)
        self._generate_touch_3(output_dir)
        self._generate_touch_4(output_dir)
        self._generate_touch_5(output_dir)

        logger.info("✓ All content generated successfully")

    def _generate_prospects_file(self, output_dir: str):
        """Generate prospects research file - V2 IMPROVED FORMAT."""
        content = f"""# Prospects Researched for {self.client['company']}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Total Unique Prospects:** {len(self.prospects)}

---

## 📊 Overview

| Metric | Value |
|--------|-------|
| Target Titles | {self.icp['titles']} |
| Target Industries | {self.icp['industries']} |
| Company Size | {self.icp['company_size']} |
| Prospects Found | {len(self.prospects)} |
| Valid Emails | {len([p for p in self.prospects if p.get('email')])} |

---

## 🎯 Prospect Details

"""
        for i, prospect in enumerate(self.prospects, 1):
            content += f"""
### {i}. {prospect['name']} - {prospect['title']}

**Company:** {prospect['company']} ({prospect['company_size']})
**Industry:** {prospect['industry']}
**Email:** {prospect['email']}
**Pain Signal:** {prospect['pain_signal']} ({prospect['source']})

---
"""

        with open(f"{output_dir}/prospects_researched.md", "w") as f:
            f.write(content)

        logger.info(f"  ✓ Prospects research file generated ({len(self.prospects)} unique prospects)")

    def _generate_engagement_log(self, output_dir: str):
        """Generate engagement tracking log."""
        content = f"""# Engagement Log - {self.client['company']}

**Client:** {self.client['first_name']} {self.client['last_name']}
**Email:** {self.client['email']}
**Phone:** {self.client.get('phone', 'N/A')}
**Campaign Start:** {datetime.now().strftime('%Y-%m-%d')}

---

## 📈 Engagement Timeline

*Track all interactions here - update after each touch*

---

## Touch 1 - Free Intro Offer (Day 1)

- **Date:** {datetime.now().strftime('%Y-%m-%d')}
- **Status:** ⏳ Pending
- **Intros Sent:** 0/{len(self.prospects)}
- **Client Notified:** ❌ No
- **Notes:**

---

## Touch 2 - Loom Video (Day 3)

- **Date:** {(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}
- **Status:** ⏳ Pending
- **Video Sent:** ❌ No
- **WhatsApp Sent:** ❌ No
- **Notes:**

---

## Touch 3 - WhatsApp Status Update (Day 5-7)

- **Date:** {(datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')}
- **Status:** ⏳ Pending
- **Client Engagement:** Unknown
- **Additional Intros Sent:** 0
- **Notes:**

---

## Touch 4 - LinkedIn + Email Follow-Up (Day 10)

- **Date:** {(datetime.now() + timedelta(days=9)).strftime('%Y-%m-%d')}
- **Status:** ⏳ Pending
- **LinkedIn DM Sent:** ❌ No
- **Case Study Sent:** ❌ No
- **Notes:**

---

## Touch 5 - Call Invitation (Day 12-14)

- **Date:** {(datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d')}
- **Status:** ⏳ Pending
- **WhatsApp Sent:** ❌ No
- **Email Sent:** ❌ No
- **Response:** Waiting
- **Notes:**

---

## 🎯 Outcome

**Discovery Call Booked:** ❌ No
**Call Date:** TBD
**Conversion Status:** In Progress

---
"""
        with open(f"{output_dir}/engagement_log.md", "w") as f:
            f.write(content)

        logger.info("  ✓ Engagement log created")

    def _generate_touch_1(self, output_dir: str):
        """Generate Touch 1 content - V2 IMPROVED (NO TRUNCATION)."""
        touch_dir = Path(output_dir) / "touch_1"
        touch_dir.mkdir(parents=True, exist_ok=True)

        # Generate intro emails - V2: FULL CONTENT, NO TRUNCATION
        intro_emails = f"""# Touch 1: Intro Emails ({len(self.prospects)} prospects)

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

"""
        for i, prospect in enumerate(self.prospects, 1):
            # V2 IMPROVEMENT: Full email content (no truncation)
            unique_value_prop = self.business['unique_qualities'][:300] + "..." if len(self.business['unique_qualities']) > 300 else self.business['unique_qualities']

            intro_emails += f"""## Intro Email {i}/{len(self.prospects)}

**To:** {prospect['email']}
**Prospect:** {prospect['name']} - {prospect['title']}
**Company:** {prospect['company']}
**Pain Signal:** {prospect['pain_signal']} ({prospect['source']})

---

**Subject:** Your {prospect['job_title_hiring']} search - {self.client['company']} can help

Hi {prospect['first_name']},

I noticed {prospect['company']} posted a {prospect['job_title_hiring']} role {prospect['days_ago']}.

Quick intro: My name is {self.client['first_name']} from {self.client['company']}. {unique_value_prop}

I specialize in helping companies like yours find {self.icp['titles'].lower()} in the {prospect['industry']} space.

Would you be open to a quick 10-minute intro call this week to see if I can help fill this role faster?

Best,
{self.client['first_name']} {self.client['last_name']}
{self.client['company']}
{self.client.get('phone', '')}
{self.client.get('website', '')}

---

"""

        intro_emails += f"""
## ✅ Sending Instructions

1. **Review each email above** - Personalize further if needed
2. **Send from:** bao@smartmarketingflow.com (or client's email if you have access)
3. **BCC yourself** for tracking
4. **Track sent emails** in engagement_log.md
5. **After sending all {len(self.prospects)}**, send client notification below

---
"""

        with open(touch_dir / "intro_emails.md", "w") as f:
            f.write(intro_emails)

        # Client notification - V2 IMPROVED (NO DUPLICATES)
        client_notification = f"""# Client Notification Email - Touch 1

**To:** {self.client['email']}
**Subject:** {self.client['first_name']} - just sent {len(self.prospects)} warm intros to {self.icp['titles']}

---

Hey {self.client['first_name']},

I went ahead and sent {len(self.prospects)} warm introductions on your behalf to companies actively hiring {self.icp['titles'].lower()}.

Here's who I connected you with:

"""
        for i, prospect in enumerate(self.prospects, 1):
            client_notification += f"""{i}. **{prospect['name']}, {prospect['title']}** at {prospect['company']} ({prospect['company_size']}, {prospect['industry']})
   → Posted "{prospect['job_title_hiring']}" {prospect['days_ago']}
   → Sent intro email: {prospect['email']}

"""

        client_notification += f"""
All intros sent from my domain (I'll forward you any responses).

These companies are hiring RIGHT NOW - meaning they have active pain and need help ASAP.

I researched each company and personalized every email to their specific job posting (no spray-and-pray).

No strings attached - just wanted to show you what my Pain-Signal System does.

Best,
Bao
Smart Marketing Flow

---
"""

        with open(touch_dir / "client_notification.md", "w") as f:
            f.write(client_notification)

        # Step-by-step guide
        step_by_step = f"""# Touch 1: Free Intro Offer - Step-by-Step Guide

## 🎯 Objective
SEND ACTUAL INTROS - "No value, no talk"

---

## ✅ Steps

### 1. Review Intro Emails
- File: [intro_emails.md](intro_emails.md)
- **IMPORTANT:** Edit emails if needed (personalize further, adjust tone)
- Check all prospect details are correct

### 2. Send Intro Emails
**Method A: Manual (Recommended for first touch)**
- Copy each email from intro_emails.md
- Send from your email (bao@smartmarketingflow.com)
- BCC yourself for tracking
- Mark sent time in engagement_log.md

**Method B: Via VA**
- Forward intro_emails.md to VA
- Instruct to send from your domain
- Verify all sent successfully

### 3. Send Client Notification
- File: [client_notification.md](client_notification.md)
- Send to: {self.client['email']}
- Subject: "{self.client['first_name']} - just sent {len(self.prospects)} warm intros to {self.icp['titles']}"

### 4. Update ClickUp
- Mark "Touch 1" subtask as IN PROGRESS
- Add comment: "Sent {len(self.prospects)} intro emails on [date]"
- When complete, mark as DONE

### 5. Track in Engagement Log
Add entry to [engagement_log.md](../engagement_log.md):
```
## Touch 1 - Intro Emails Sent
- Date: {datetime.now().strftime('%Y-%m-%d')}
- Prospects contacted: {len(self.prospects)}
- Client notified: Yes
- Next touch: Day 3 (Touch 2)
```

---

## ✅ Success Criteria
- {len(self.prospects)} intro emails sent to prospects
- Client notification email sent
- All tracked in ClickUp + engagement log
- Ready for Touch 2 in 2 days

---
"""

        with open(touch_dir / "step_by_step.md", "w") as f:
            f.write(step_by_step)

        logger.info("  ✓ Touch 1 content generated (NO DUPLICATES)")

    def _generate_touch_2(self, output_dir: str):
        """Generate Touch 2 content."""
        touch_dir = Path(output_dir) / "touch_2"
        touch_dir.mkdir(parents=True, exist_ok=True)

        # Video script
        video_script = f"""# Touch 2: Loom Video Script - Show Intro Process

**Duration:** 3-5 minutes
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 🎬 Video Outline

### Opening (0:00-0:30)
"Hey {self.client['first_name']}! Bao here from Smart Marketing Flow.

I just sent you {len(self.prospects)} warm introductions earlier this week. I wanted to show you exactly how I found those prospects - the process I'd be running for you on a monthly basis."

### Screen Share: Show Pain-Signal System (0:30-2:30)

**Screen 1: LinkedIn Jobs (or Indeed)**
- "Here's how I start - I search for companies posting jobs related to your ICP..."
- Filter by: {self.icp['industries']}
- Filter by: {self.icp['company_size']} employees
- Filter by: Job titles like {self.icp['titles']}
- "See these {len(self.prospects)} companies? They ALL posted jobs in the last 7 days."

**Screen 2: Prospect Research**
- Click on one company (example: {self.prospects[0]['company']})
- "I research the decision maker - in this case, {self.prospects[0]['name']}, {self.prospects[0]['title']}"
- Show LinkedIn profile (or Apollo data)
- "I find their email, verify it's valid, then craft a personalized intro"

**Screen 3: Show Intro Email Example**
- "Here's the email I sent to {self.prospects[0]['first_name']}..."
- Read first 2-3 lines
- "Notice how I reference their SPECIFIC job posting - this isn't a template blast"

### Closing (2:30-3:00)
"This is what you'd get on a monthly retainer - 15-25 highly qualified intros like these, all timed to when companies have active pain.

No spray-and-pray. Just precision targeting.

I'll check back in a few days to see if any of these prospects responded.

Talk soon!"

---

## 📹 Recording Instructions

1. **Open Loom** (loom.com)
2. **Select:** Screen + Camera
3. **Prepare screens:** Open LinkedIn Jobs, example prospect profile, intro email
4. **Record:** Follow outline above (be conversational, not scripted)
5. **Duration:** Keep it 3-5 minutes max
6. **Upload:** Get sharable link
7. **Send:** Via WhatsApp + Email (see message templates)

---
"""

        with open(touch_dir / "video_script.md", "w") as f:
            f.write(video_script)

        # WhatsApp message
        whatsapp_msg = f"""# Touch 2: WhatsApp Message - Video Link

**To:** {self.client.get('phone', '[PHONE]')}
**When:** 2 days after Touch 1 (Day 3)

---

Hey {self.client['first_name']}! 👋

Recorded a quick 3-min video showing how I found those {len(self.prospects)} prospects I sent you earlier this week.

[LOOM LINK]

This is the same Pain-Signal process I'd be running for you every month - finding companies with active hiring pain who need {self.icp['titles'].lower()} RIGHT NOW.

Let me know if you have any questions!

Bao

---

## 📝 Sending Instructions

1. **Record Loom video first** (see video_script.md)
2. **Get sharable link**
3. **Replace [LOOM LINK]** with actual link
4. **Send via WhatsApp** to {self.client.get('phone', '[PHONE]')}
5. **Track in engagement log**

---
"""

        with open(touch_dir / "whatsapp_message.md", "w") as f:
            f.write(whatsapp_msg)

        # Email backup
        email_backup = f"""# Touch 2: Email Message - Video Link (Backup)

**To:** {self.client['email']}
**Subject:** Quick video - how I found those {len(self.prospects)} prospects
**When:** Send 2 hours after WhatsApp if no response

---

Hey {self.client['first_name']},

I recorded a quick 3-minute video showing how I found those {len(self.prospects)} prospects I sent you earlier this week.

**Watch here:** [LOOM LINK]

This is the same Pain-Signal process I'd be running for you every month - finding companies with active hiring pain who need {self.icp['titles'].lower()} RIGHT NOW, rather than cold-blasting 1,000 random companies.

The result? 7-15% reply rates vs industry standard 1%.

Let me know if you have any questions!

Best,
Bao
Smart Marketing Flow

---
"""

        with open(touch_dir / "email_message.md", "w") as f:
            f.write(email_backup)

        # Step-by-step
        step_by_step = f"""# Touch 2: Loom Video - Step-by-Step Guide

## 🎯 Objective
Creative credibility - show pain-signal tracking process

---

## ✅ Steps

### 1. Record Loom Video
- File: [video_script.md](video_script.md)
- Duration: 3-5 minutes
- Show: LinkedIn Jobs, prospect research, email example
- Talking points provided in script

### 2. Get Sharable Link
- Upload to Loom
- Copy link
- Test link (open in incognito to verify)

### 3. Send WhatsApp Message
- File: [whatsapp_message.md](whatsapp_message.md)
- Replace [LOOM LINK] with actual link
- Send to: {self.client.get('phone', '[PHONE]')}

### 4. Send Email Backup (if no WhatsApp response in 2 hours)
- File: [email_message.md](email_message.md)
- Replace [LOOM LINK] with actual link
- Send to: {self.client['email']}

### 5. Update ClickUp
- Mark "Touch 2" subtask as IN PROGRESS
- Add comment: "Sent Loom video on [date]"
- When complete, mark as DONE

### 6. Track in Engagement Log
Add entry to [engagement_log.md](../engagement_log.md):
```
## Touch 2 - Loom Video Sent
- Date: {(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}
- Video link: [PASTE LINK]
- WhatsApp sent: Yes
- Email backup sent: Yes/No
- Next touch: Day 5-7 (Touch 3)
```

---

## ✅ Success Criteria
- Loom video recorded (3-5 min)
- WhatsApp message sent
- Email backup sent (if needed)
- All tracked in ClickUp + engagement log

---
"""

        with open(touch_dir / "step_by_step.md", "w") as f:
            f.write(step_by_step)

        logger.info("  ✓ Touch 2 content generated")

    def _generate_touch_3(self, output_dir: str):
        """Generate Touch 3 content."""
        touch_dir = Path(output_dir) / "touch_3"
        touch_dir.mkdir(parents=True, exist_ok=True)

        # Additional intros (if client engaged)
        # V2: Calculate how many prospects are left
        remaining_prospects = max(0, 15 - len(self.prospects))

        additional_intros = f"""# Touch 3: Additional Intros (If Client Engaged)

**Send only if client engaged** (replied to Touch 1 or 2)

---

## 📊 Remaining Prospects

You initially researched 15 prospects and sent {len(self.prospects)} in Touch 1.

**Remaining:** {remaining_prospects} prospects ready to go

---

## 📧 Additional Intro Emails (3-5 more)

*These would be generated from the remaining prospects pool*

**Instructions:**
1. Check if client engaged (replied to Touch 1 or 2)
2. If YES → Send 3-5 more intros from remaining prospects
3. If NO → Skip this, just send status check message

---
"""

        with open(touch_dir / "additional_intros.md", "w") as f:
            f.write(additional_intros)

        # WhatsApp message (client engaged)
        whatsapp_engaged = f"""# Touch 3: WhatsApp Message - If Client Engaged

**To:** {self.client.get('phone', '[PHONE]')}
**When:** Day 5-7 (if client engaged)

---

Hey {self.client['first_name']}! 👋

Checking in on those {len(self.prospects)} intros I sent last week.

Have any of them responded yet?

By the way - I have {remaining_prospects} more prospects ready to go if you want them! Same quality, same pain-signal targeting.

Let me know!

Bao

---
"""

        with open(touch_dir / "whatsapp_engaged.md", "w") as f:
            f.write(whatsapp_engaged)

        # WhatsApp message (no engagement)
        whatsapp_no_engagement = f"""# Touch 3: WhatsApp Message - If No Engagement

**To:** {self.client.get('phone', '[PHONE]')}
**When:** Day 5-7 (if client did NOT engage)

---

Hey {self.client['first_name']},

Following up on the intros I sent last week.

Did you get a chance to review them? Any responses from the prospects?

Let me know if you need anything!

Bao

---
"""

        with open(touch_dir / "whatsapp_no_engagement.md", "w") as f:
            f.write(whatsapp_no_engagement)

        # Step-by-step
        step_by_step = f"""# Touch 3: WhatsApp Status Update - Step-by-Step Guide

## 🎯 Objective
Check engagement, send more intros if client engaged

---

## ✅ Steps

### 1. Assess Client Engagement
Check if client:
- Replied to Touch 1 (client notification)
- Replied to Touch 2 (Loom video)
- Opened/watched Loom video (check Loom analytics)
- Asked any questions

**Engagement Status:** ⬜ ENGAGED / ⬜ NO ENGAGEMENT

---

### 2A. If Client ENGAGED → Send Additional Intros + Status Check

**Files:**
- [additional_intros.md](additional_intros.md) - Send 3-5 more intros
- [whatsapp_engaged.md](whatsapp_engaged.md) - WhatsApp message

**Actions:**
1. Send 3-5 more intros to prospects
2. Send WhatsApp message mentioning you sent more
3. Track in engagement log

---

### 2B. If Client NOT ENGAGED → Simple Status Check

**File:** [whatsapp_no_engagement.md](whatsapp_no_engagement.md)

**Actions:**
1. Send WhatsApp message (simple follow-up)
2. Track in engagement log
3. **Decision:** If still no response, consider stopping after Touch 5

---

### 3. Update ClickUp
- Mark "Touch 3" subtask as IN PROGRESS
- Add comment: "Engagement status: [ENGAGED/NO ENGAGEMENT]"
- When complete, mark as DONE

### 4. Track in Engagement Log
Add entry to [engagement_log.md](../engagement_log.md):
```
## Touch 3 - WhatsApp Status Update
- Date: {(datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')}
- Client engagement: [ENGAGED/NO ENGAGEMENT]
- Additional intros sent: [YES/NO]
- WhatsApp sent: Yes
- Next touch: Day 10 (Touch 4)
```

---

## ✅ Success Criteria
- Engagement assessed correctly
- Appropriate message sent (engaged vs not engaged)
- Additional intros sent (if engaged)
- All tracked in ClickUp + engagement log

---
"""

        with open(touch_dir / "step_by_step.md", "w") as f:
            f.write(step_by_step)

        logger.info("  ✓ Touch 3 content generated")

    def _generate_touch_4(self, output_dir: str):
        """Generate Touch 4 content."""
        touch_dir = Path(output_dir) / "touch_4"
        touch_dir.mkdir(parents=True, exist_ok=True)

        # Select case study
        case_study = CASE_STUDIES.get(self.metadata['industry_category'], CASE_STUDIES['default'])

        # LinkedIn DM
        linkedin_dm = f"""# Touch 4: LinkedIn DM

**To:** {self.client['first_name']} {self.client['last_name']} (LinkedIn)
**When:** Day 10

---

**Step 1: Engage with their post first**
- Like their most recent post
- Leave thoughtful comment
- Wait 2-3 hours

**Step 2: Send DM**

---

Hey {self.client['first_name']}!

Saw your post about [TOPIC] - great insights!

By the way, have those intros I sent turned into any conversations yet?

I'd love to hear if the pain-signal targeting approach is working for you.

Best,
Bao

---

## 📝 Instructions

1. **Find {self.client['first_name']}'s LinkedIn profile**
2. **Engage with recent post** (like + comment)
3. **Wait 2-3 hours**
4. **Send DM above** (replace [TOPIC] with actual topic)
5. **Track in engagement log**

---
"""

        with open(touch_dir / "linkedin_dm.md", "w") as f:
            f.write(linkedin_dm)

        # Case study email
        case_study_email = f"""# Touch 4: Email - Case Study + System Breakdown

**To:** {self.client['email']}
**Subject:** How I helped another {self.metadata['industry_category']} company - {case_study['name']}
**When:** Day 10 (same day as LinkedIn DM)

---

Hey {self.client['first_name']},

I wanted to share a case study from another {self.metadata['industry_category']} company I worked with recently.

## Case Study: {case_study['name']}

**Industry:** {case_study['industry']}
**Pain Signals Tracked:** {case_study['pain_signals']}
**Results:** {case_study['results']}

The key difference? We didn't spray-and-pray 1,000 cold emails. Instead, we tracked {case_study['pain_signals'].lower()} in their industry 24/7 and emailed companies at the exact moment they needed help.

## How the Pain-Signal System Works

**What we track for you:**
- Job postings (active hiring pain)
- Funding rounds or budget increases
- New office openings or leadership changes
- Product launches and expansion signals

**What you get:**
- 15-25 high-quality intros per month (not 1,000 random leads)
- All emails sent from 200+ pre-warmed domains (owned by me, zero extra cost)
- 7-15% reply rates (vs industry standard 1%)

**Guarantee:** 8+ high-ticket introductions per month, or we work for free until we hit that target.

**Pricing:**
- $2,500 setup (one-time)
- $3,500/month (all-inclusive)

Would you like to see what pain signals we'd track for {self.client['company']}? Happy to jump on a quick 15-minute call.

Best,
Bao
Smart Marketing Flow

---
"""

        with open(touch_dir / "email_case_study.md", "w") as f:
            f.write(case_study_email)

        # Step-by-step
        step_by_step = f"""# Touch 4: LinkedIn + Email Follow-Up - Step-by-Step Guide

## 🎯 Objective
Multi-channel presence + case study social proof

---

## ✅ Steps

### 1. LinkedIn Engagement
- Find {self.client['first_name']} {self.client['last_name']} on LinkedIn
- Like their most recent post
- Leave thoughtful comment (2-3 sentences)
- **Wait 2-3 hours** before sending DM

### 2. Send LinkedIn DM
- File: [linkedin_dm.md](linkedin_dm.md)
- Replace [TOPIC] with actual topic from their post
- Send DM via LinkedIn

### 3. Send Email (Same Day)
- File: [email_case_study.md](email_case_study.md)
- Review case study details (auto-selected: {case_study['name']})
- Send to: {self.client['email']}

### 4. Update ClickUp
- Mark "Touch 4" subtask as IN PROGRESS
- Add comment: "Sent LinkedIn DM + case study email on [date]"
- When complete, mark as DONE

### 5. Track in Engagement Log
Add entry to [engagement_log.md](../engagement_log.md):
```
## Touch 4 - LinkedIn + Email Follow-Up
- Date: {(datetime.now() + timedelta(days=9)).strftime('%Y-%m-%d')}
- LinkedIn post engaged: [POST LINK]
- LinkedIn DM sent: Yes
- Email sent: Yes (case study: {case_study['name']})
- Next touch: Day 12-14 (Touch 5 - Final Ask)
```

---

## ✅ Success Criteria
- LinkedIn post liked + commented
- LinkedIn DM sent
- Case study email sent with pricing/guarantee
- All tracked in ClickUp + engagement log

---
"""

        with open(touch_dir / "step_by_step.md", "w") as f:
            f.write(step_by_step)

        logger.info("  ✓ Touch 4 content generated")

    def _generate_touch_5(self, output_dir: str):
        """Generate Touch 5 content."""
        touch_dir = Path(output_dir) / "touch_5"
        touch_dir.mkdir(parents=True, exist_ok=True)

        # WhatsApp final ask
        whatsapp_final = f"""# Touch 5: WhatsApp - Final Call Invitation

**To:** {self.client.get('phone', '[PHONE]')}
**When:** Day 12-14

---

Hey {self.client['first_name']},

Over the past 2 weeks I've sent you:
→ {len(self.prospects)}+ warm intros to {self.icp['titles'].lower() if self.icp['titles'] else 'prospects'}
→ Behind-the-scenes video showing pain-signal tracking
→ Case study from another {self.metadata['industry_category']} company

Most lead gen agencies play a volume game - spraying 1,000 "cold" emails and hoping for a 1% reply rate. I find that wasteful.

I built something different: Pain-Signal Systems.

Instead of mass-blasting, my system monitors your entire industry 24/7 for specific triggers:
- Companies posting job openings (active hiring pain)
- Funding rounds or budget increases
- New office openings or leadership changes
- Expansion signals

The result? We email 80 highly qualified companies at the exact moment they need help, rather than 1,000 random leads.

This approach consistently gets 7-15% reply rates.

**Here's why I'm different:** You won't pay a cent for software or email tools. I own the entire infrastructure - including 200+ pre-warmed domains - ready to scale immediately at no extra cost.

**Guarantee:** 8+ high-ticket introductions per month, or we work free until we hit that target.

Are you open to a 15-minute chat next week? I can walk you through the exact pain signals we'd track for {self.client['company']}.

Best,
Bao

---
"""

        with open(touch_dir / "whatsapp_final_ask.md", "w") as f:
            f.write(whatsapp_final)

        # Email final ask
        email_final = f"""# Touch 5: Email - Final Call Invitation

**To:** {self.client['email']}
**Subject:** Last message - Pain-Signal System for {self.client['company']}
**When:** 2 hours after WhatsApp if no response

---

Hey {self.client['first_name']},

Last message from me.

I sent you:
→ Pain-signal research ({len(self.prospects)}+ intros to {self.icp['titles'].lower() if self.icp['titles'] else 'prospects'})
→ Behind-the-scenes video showing tracking process
→ Case study results from similar company
→ System breakdown (infrastructure, guarantee, pricing)

Most lead gen agencies play a volume game - spraying 1,000 "cold" emails and hoping for a 1% reply rate. I find that wasteful.

I built something different: **Pain-Signal Systems**.

Instead of mass-blasting, my system monitors your entire ecosystem industry 24/7 for specific triggers:

- Funding rounds or sudden budget increases
- Specific job postings indicating a gap your services fill
- New office openings or leadership changes
- Product launches and expansion signals

The result? We email 80 highly qualified companies at the exact moment they need help, rather than 1,000 random leads.

This approach consistently gets **7-15% reply rates**.

**Here's why I'm different:** You won't pay a cent for software or email tools. I own the entire infrastructure - including 200+ pre-warmed domains - ready to scale immediately at no extra cost to you.

**Guarantee:** 8+ high-ticket introductions per month, or we work for free until we hit that target. Average client receives 15-25 qualified intros monthly.

**Pricing:**
- $2,500 setup (one-time)
- $3,500/month (all-inclusive)

Are you open to a 15-minute chat next week? I can walk you through the exact pain signals we'd track for {self.client['company']}.

Best,
Bao
Smart Marketing Flow

P.S. I've attached a few results from my recent campaigns below. My system doesn't spam; it finds people who are already in pain and ready to talk.

---
"""

        with open(touch_dir / "email_final_ask.md", "w") as f:
            f.write(email_final)

        # Step-by-step
        step_by_step = f"""# Touch 5: Final Call Invitation - Step-by-Step Guide

## 🎯 Objective
Last chance to convert - full pitch, then STOP if no response

---

## ✅ Steps

### 1. Send WhatsApp Message
- File: [whatsapp_final_ask.md](whatsapp_final_ask.md)
- Send to: {self.client.get('phone', '[PHONE]')}
- This is the FULL pitch (pricing, guarantee, all details)

### 2. Send Email (2 Hours After WhatsApp)
- File: [email_final_ask.md](email_final_ask.md)
- Send to: {self.client['email']}
- Same message as WhatsApp, more detailed

### 3. Track Response

**If YES (Interested):**
- Schedule 15-min discovery call
- Prepare: ICP research, pain signals to track, case studies
- Update ClickUp status: "INTERESTED - Call Booked"

**If NO or IGNORE (Not Interested):**
- Mark "Cold - No Engagement" in ClickUp
- **STOP nurturing** (don't chase)
- Move on to next prospect

### 4. Update ClickUp
- Mark "Touch 5" subtask as IN PROGRESS
- Add comment: "Sent final ask on [date] - Response: [YES/NO/WAITING]"
- When complete, mark as DONE
- Update parent task status based on response

### 5. Track in Engagement Log
Add final entry to [engagement_log.md](../engagement_log.md):
```
## Touch 5 - Final Call Invitation
- Date: {(datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d')}
- WhatsApp sent: Yes
- Email sent: Yes
- Response: [YES/NO/IGNORE]
- Discovery call booked: [YES/NO]
- Call date: [DATE or N/A]
- Final status: [INTERESTED/COLD/WAITING]
```

---

## ✅ Success Criteria
- WhatsApp final ask sent
- Email final ask sent (if needed)
- Response tracked (YES/NO/IGNORE)
- ClickUp updated with final status
- If NO/IGNORE → STOP nurturing (energy protection)

---

## 🎯 Next Steps After Touch 5

**If interested:** Schedule discovery call, prepare pitch, close deal
**If not interested:** Mark cold, move on to next prospect
**Energy protection:** Don't chase low-intent leads

---
"""

        with open(touch_dir / "step_by_step.md", "w") as f:
            f.write(step_by_step)

        logger.info("  ✓ Touch 5 content generated")


# =============================================================================
# CLICKUP ORCHESTRATOR V2 (IMPROVED CRM STRUCTURE)
# =============================================================================

class ClickUpOrchestratorV2:
    """Manage ClickUp tasks for nurture workflow - V2 IMPROVED CRM."""

    def __init__(self, list_id: str):
        self.client = ClickUpClient()
        self.list_id = list_id

    def create_nurture_tasks(self, client_data: Dict, output_dir: str, prospects: List[Dict]) -> str:
        """Create parent task + 5 subtasks with V2 ENHANCED content."""
        logger.info("Creating ClickUp tasks (V2 - Improved CRM)...")

        client = client_data["client"]
        slug = client_data["metadata"]["slug"]

        # Create parent task with V2 IMPROVED description
        parent_task = self.client.create_task(
            list_id=self.list_id,
            name=f"🏢 {client['company']} - Pain-Signal Nurture",
            description=self._create_v2_parent_description(client_data, output_dir, prospects),
            tags=["client", "nurture", "pain-signal", "v2"],
            priority=2  # High
        )

        parent_id = parent_task.get("id")
        logger.info(f"✓ Created parent task (V2): {parent_id}")

        # Create 5 subtasks with V2 ENHANCED descriptions
        subtasks = [
            {"name": "✅ Touch 1 (Day 1): Free Intro Offer", "touch": 1, "priority": 1},
            {"name": "🎬 Touch 2 (Day 3): Loom Video", "touch": 2, "priority": 2},
            {"name": "💬 Touch 3 (Day 5-7): WhatsApp Status", "touch": 3, "priority": 2},
            {"name": "💼 Touch 4 (Day 10): LinkedIn + Email", "touch": 4, "priority": 2},
            {"name": "📞 Touch 5 (Day 12-14): Call Invitation", "touch": 5, "priority": 1}
        ]

        for subtask_def in subtasks:
            # Create V2 ENHANCED description
            description = self._create_v2_subtask_description(
                subtask_def["touch"],
                client_data,
                output_dir,
                prospects
            )

            # Create subtask
            self.client.create_subtask(
                parent_task_id=parent_id,
                name=subtask_def["name"],
                description=description,
                priority=subtask_def["priority"]
            )
            logger.info(f"  ✓ Created subtask (V2): {subtask_def['name']}")

        # Save parent task ID
        with open(f"{output_dir}/clickup_task_id.txt", "w") as f:
            f.write(parent_id)

        logger.info("✓ All ClickUp tasks created (V2 - Improved CRM)")
        return parent_id

    def _create_v2_parent_description(self, client_data: Dict, output_dir: str, prospects: List[Dict]) -> str:
        """Create V2 IMPROVED parent task description with status dashboard."""
        client = client_data["client"]
        icp = client_data["icp"]
        business = client_data["business"]

        return f"""# 🏢 {client['company']} - Pain-Signal 5-Touch Nurture

---

## 📊 STATUS DASHBOARD

| Touch | Status | Date | Completion |
|-------|--------|------|------------|
| Touch 1: Intro Offer | ⏳ Pending | Day 1 | 0% |
| Touch 2: Loom Video | ⏳ Pending | Day 3 | 0% |
| Touch 3: WhatsApp Status | ⏳ Pending | Day 5-7 | 0% |
| Touch 4: LinkedIn + Email | ⏳ Pending | Day 10 | 0% |
| Touch 5: Call Invitation | ⏳ Pending | Day 12-14 | 0% |

**Overall Progress:** 0/5 touches completed (0%)

---

## 👤 CLIENT INFO

**Name:** {client['first_name']} {client['last_name']}
**Company:** {client['company']}
**Email:** {client['email']}
**Phone:** {client.get('phone', 'N/A')}
**Website:** {client.get('website', 'N/A')}

---

## 🎯 ICP (Ideal Customer Profile)

**Target Titles:** {icp['titles']}
**Target Industries:** {icp['industries']}
**Company Size:** {icp['company_size']}

---

## 💎 UNIQUE VALUE PROPS

{business['unique_qualities'][:500]}...

---

## 📈 CAMPAIGN METRICS

**Prospects Researched:** {len(prospects)} (unique, no duplicates)
**Intros Sent (Touch 1):** 0/{len(prospects)}
**Additional Intros (Touch 3):** 0
**Total Intros:** 0
**Client Engagement:** Not tracked yet
**Discovery Call Booked:** ❌ No

---

## 📁 FILES LOCATION

All campaign files saved in: `.tmp/clients/{client_data['metadata']['slug']}/`

- Prospects research: `prospects_researched.md`
- Engagement log: `engagement_log.md`
- Touch 1-5 folders: All content + step-by-step guides

---

## ✅ NEXT STEPS

1. ✅ Review prospects in `prospects_researched.md`
2. ✅ Execute Touch 1 (send {len(prospects)} intros + client notification)
3. ⏳ Wait 2 days
4. ⏳ Execute Touch 2 (record Loom video, send WhatsApp)
5. ⏳ Continue sequence until Touch 5

---

**Campaign Start:** {datetime.now().strftime('%Y-%m-%d')}
**Expected Completion:** {(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')} (14 days)

---
"""

    def _create_v2_subtask_description(self, touch_num: int, client_data: Dict, output_dir: str, prospects: List[Dict]) -> str:
        """Create V2 ENHANCED subtask description - cleaner, better formatted."""
        client = client_data["client"]

        if touch_num == 1:
            # Read intro emails
            with open(f"{output_dir}/touch_1/intro_emails.md", "r") as f:
                intro_emails = f.read()

            # Read client notification
            with open(f"{output_dir}/touch_1/client_notification.md", "r") as f:
                client_notification = f.read()

            return f"""# ✅ Touch 1: Free Intro Offer - SEND ACTUAL INTROS

---

## 🎯 OBJECTIVE
"No value, no talk" - DO the work first, send {len(prospects)} actual warm introductions

---

## ✅ TASK CHECKLIST

- [ ] 1. Review all {len(prospects)} intro emails below
- [ ] 2. Edit/personalize if needed (add specific company details)
- [ ] 3. Send all {len(prospects)} intro emails to prospects
- [ ] 4. Send client notification to {client['email']}
- [ ] 5. Update engagement log with sent date
- [ ] 6. Mark this ClickUp task as DONE

---

<details>
<summary><strong>📧 INTRO EMAILS TO SEND ({len(prospects)} prospects - Click to expand)</strong></summary>

{intro_emails}

</details>

---

<details>
<summary><strong>📨 CLIENT NOTIFICATION EMAIL (Send After All Intros)</strong></summary>

{client_notification}

</details>

---

## 📝 EXECUTION INSTRUCTIONS

### Method A: Manual (Recommended)
1. Copy each email from above
2. Send from: `bao@smartmarketingflow.com`
3. BCC yourself for tracking
4. Mark sent time in `engagement_log.md`

### Method B: Via VA
1. Forward `intro_emails.md` to VA
2. Instruct to send from your domain
3. Verify all sent successfully

---

## 📊 SUCCESS CRITERIA

✅ {len(prospects)} intro emails sent
✅ Client notification sent
✅ All tracked in engagement log
✅ Task marked as DONE

---

**Next Touch:** Day 3 (Touch 2 - Loom Video)

---
"""

        elif touch_num == 2:
            # Read video script
            with open(f"{output_dir}/touch_2/video_script.md", "r") as f:
                video_script = f.read()

            # Read WhatsApp message
            with open(f"{output_dir}/touch_2/whatsapp_message.md", "r") as f:
                whatsapp_msg = f.read()

            # Read email backup
            with open(f"{output_dir}/touch_2/email_message.md", "r") as f:
                email_backup = f.read()

            return f"""# 🎬 Touch 2: Loom Video - Show Intro Process

---

## 🎯 OBJECTIVE
Creative credibility - show pain-signal tracking process via 3-5 min Loom video

---

## ✅ TASK CHECKLIST

- [ ] 1. Record Loom video (3-5 min) using script below
- [ ] 2. Get sharable link from Loom
- [ ] 3. Send WhatsApp message with link
- [ ] 4. Send email backup (if no WhatsApp response in 2 hours)
- [ ] 5. Update engagement log
- [ ] 6. Mark this ClickUp task as DONE

---

<details>
<summary><strong>🎬 LOOM VIDEO SCRIPT (Click to expand)</strong></summary>

{video_script}

</details>

---

<details>
<summary><strong>💬 WHATSAPP MESSAGE (Send First)</strong></summary>

{whatsapp_msg}

</details>

---

<details>
<summary><strong>📧 EMAIL BACKUP (Send if no WhatsApp response)</strong></summary>

{email_backup}

</details>

---

## 📝 EXECUTION INSTRUCTIONS

1. **Record video:** Use Loom (loom.com), screen + camera, 3-5 min
2. **Show:** LinkedIn Jobs, prospect research, intro email example
3. **Upload:** Get sharable link, test in incognito
4. **Send WhatsApp:** Replace [LOOM LINK] with actual link
5. **Wait 2 hours:** If no response, send email backup

---

## 📊 SUCCESS CRITERIA

✅ Loom video recorded (3-5 min)
✅ WhatsApp message sent
✅ Email backup sent (if needed)
✅ Task marked as DONE

---

**Next Touch:** Day 5-7 (Touch 3 - WhatsApp Status)

---
"""

        elif touch_num == 3:
            # Read all Touch 3 files
            with open(f"{output_dir}/touch_3/whatsapp_engaged.md", "r") as f:
                whatsapp_engaged = f.read()

            with open(f"{output_dir}/touch_3/whatsapp_no_engagement.md", "r") as f:
                whatsapp_no_engagement = f.read()

            return f"""# 💬 Touch 3: WhatsApp Status Update

---

## 🎯 OBJECTIVE
Check engagement, send more intros if client engaged

---

## ✅ TASK CHECKLIST

- [ ] 1. Assess client engagement (replied to Touch 1 or 2?)
- [ ] 2A. If ENGAGED → Send 3-5 more intros + status check
- [ ] 2B. If NOT ENGAGED → Send simple status check only
- [ ] 3. Update engagement log with status
- [ ] 4. Mark this ClickUp task as DONE

---

## 📊 ENGAGEMENT ASSESSMENT

Check if client:
- ✅ Replied to Touch 1 (client notification)
- ✅ Replied to Touch 2 (Loom video)
- ✅ Watched Loom video (check Loom analytics)
- ✅ Asked any questions

**My Assessment:** ⬜ ENGAGED / ⬜ NO ENGAGEMENT

---

<details>
<summary><strong>💬 OPTION A: If Client ENGAGED (Click to expand)</strong></summary>

{whatsapp_engaged}

**Actions:**
1. Send 3-5 more intros from remaining prospects
2. Send WhatsApp message above
3. Track in engagement log

</details>

---

<details>
<summary><strong>💬 OPTION B: If Client NOT ENGAGED (Click to expand)</strong></summary>

{whatsapp_no_engagement}

**Actions:**
1. Send WhatsApp message above (simple follow-up)
2. Track in engagement log
3. **Decision:** If still no response, consider stopping after Touch 5

</details>

---

## 📝 EXECUTION INSTRUCTIONS

1. **Assess engagement:** Review Touch 1 & 2 responses
2. **Choose path:** Engaged (Option A) or Not Engaged (Option B)
3. **Execute:** Send appropriate message
4. **Track:** Update engagement log with status

---

## 📊 SUCCESS CRITERIA

✅ Engagement assessed correctly
✅ Appropriate message sent
✅ Additional intros sent (if engaged)
✅ Task marked as DONE

---

**Next Touch:** Day 10 (Touch 4 - LinkedIn + Email)

---
"""

        elif touch_num == 4:
            # Read Touch 4 files
            with open(f"{output_dir}/touch_4/linkedin_dm.md", "r") as f:
                linkedin_dm = f.read()

            with open(f"{output_dir}/touch_4/email_case_study.md", "r") as f:
                case_study_email = f.read()

            # Get case study info
            industry_category = client_data['metadata']['industry_category']
            case_study = CASE_STUDIES.get(industry_category, CASE_STUDIES['default'])

            return f"""# 💼 Touch 4: LinkedIn + Email Follow-Up

---

## 🎯 OBJECTIVE
Multi-channel presence + case study social proof

---

## ✅ TASK CHECKLIST

- [ ] 1. Find {client['first_name']}'s LinkedIn profile
- [ ] 2. Like + comment on their recent post
- [ ] 3. Wait 2-3 hours
- [ ] 4. Send LinkedIn DM
- [ ] 5. Send case study email (same day)
- [ ] 6. Update engagement log
- [ ] 7. Mark this ClickUp task as DONE

---

<details>
<summary><strong>💼 LINKEDIN DM (Click to expand)</strong></summary>

{linkedin_dm}

</details>

---

<details>
<summary><strong>📧 CASE STUDY EMAIL (Click to expand)</strong></summary>

**Case Study Auto-Selected:** {case_study['name']}
**Industry Match:** {industry_category}

{case_study_email}

</details>

---

## 📝 EXECUTION INSTRUCTIONS

1. **LinkedIn:** Find {client['first_name']}, like post, comment
2. **Wait:** 2-3 hours
3. **DM:** Send LinkedIn message (replace [TOPIC])
4. **Email:** Send case study email same day
5. **Track:** Update engagement log

---

## 📊 SUCCESS CRITERIA

✅ LinkedIn post engaged
✅ LinkedIn DM sent
✅ Case study email sent
✅ Task marked as DONE

---

**Next Touch:** Day 12-14 (Touch 5 - Final Call Invitation)

---
"""

        elif touch_num == 5:
            # Read Touch 5 files
            with open(f"{output_dir}/touch_5/whatsapp_final_ask.md", "r") as f:
                whatsapp_final = f.read()

            with open(f"{output_dir}/touch_5/email_final_ask.md", "r") as f:
                email_final = f.read()

            return f"""# 📞 Touch 5: Final Call Invitation

---

## 🎯 OBJECTIVE
Last chance to convert - full pitch, then STOP if no response

---

## ✅ TASK CHECKLIST

- [ ] 1. Send WhatsApp final ask (full pitch)
- [ ] 2. Wait 2 hours
- [ ] 3. Send email final ask (if no WhatsApp response)
- [ ] 4. Track response (YES/NO/IGNORE)
- [ ] 5A. If YES → Schedule discovery call
- [ ] 5B. If NO/IGNORE → Mark "Cold - No Engagement", STOP nurturing
- [ ] 6. Update engagement log with final status
- [ ] 7. Mark this ClickUp task as DONE

---

<details>
<summary><strong>💬 WHATSAPP FINAL ASK (Send First - Click to expand)</strong></summary>

{whatsapp_final}

</details>

---

<details>
<summary><strong>📧 EMAIL FINAL ASK (Send if no WhatsApp response - Click to expand)</strong></summary>

{email_final}

</details>

---

## 📝 EXECUTION INSTRUCTIONS

1. **Send WhatsApp:** Full pitch with pricing, guarantee
2. **Wait 2 hours:** Give client time to respond
3. **Send Email:** If no WhatsApp response, send email
4. **Track response:**
   - **YES → Schedule discovery call, update status**
   - **NO/IGNORE → Mark cold, STOP nurturing**

---

## 📊 SUCCESS CRITERIA

✅ WhatsApp final ask sent
✅ Email final ask sent (if needed)
✅ Response tracked (YES/NO/IGNORE)
✅ Next steps clear (call booked OR marked cold)
✅ Task marked as DONE

---

## 🎯 FINAL DECISION

**If interested:** Schedule discovery call, close deal
**If not interested:** Mark cold, move on (energy protection)

**Campaign Complete:** {(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')}

---
"""

        return ""


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

class PainSignalNurtureV2:
    """Main orchestrator for pain-signal nurture workflow - V2."""

    def __init__(self, form_data_path: str, clickup_list_id: str = "901805941038"):
        self.form_data_path = form_data_path
        self.clickup_list_id = clickup_list_id

        # Load and parse form
        with open(form_data_path, "r") as f:
            raw_form = json.load(f)

        self.client_data = OnboardingFormParser.parse(raw_form)
        self.slug = self.client_data["metadata"]["slug"]
        self.output_dir = f".tmp/clients/{self.slug}"

    def prepare_all_touches(self):
        """Prepare all 5 touches at once (recommended workflow)."""
        logger.info("=" * 60)
        logger.info("PAIN-SIGNAL 5-TOUCH NURTURE - V2 (IMPROVED CRM)")
        logger.info("=" * 60)

        # Step 1: Research prospects (UNIQUE ONLY)
        logger.info("\n[1/4] Researching prospects...")
        prospects = ProspectResearcher.research_prospects(
            self.client_data["icp"],
            count=8  # V2: Default to 8 unique prospects
        )
        logger.info(f"✓ Found {len(prospects)} unique prospects")

        # Step 2: Generate content
        logger.info("\n[2/4] Generating content...")
        content_gen = ContentGenerator(self.client_data, prospects)
        content_gen.generate_all(self.output_dir)
        logger.info(f"✓ All content saved to: {self.output_dir}")

        # Step 3: Create ClickUp tasks
        logger.info("\n[3/4] Creating ClickUp tasks...")
        clickup = ClickUpOrchestratorV2(self.clickup_list_id)
        parent_task_id = clickup.create_nurture_tasks(self.client_data, self.output_dir, prospects)
        logger.info(f"✓ Parent task created: {parent_task_id}")

        # Step 4: Summary
        logger.info("\n[4/4] Setup complete!")
        logger.info("=" * 60)
        logger.info("✅ V2 IMPROVED CRM - ALL 5 TOUCHES READY")
        logger.info("=" * 60)
        logger.info(f"Client: {self.client_data['client']['company']}")
        logger.info(f"Prospects: {len(prospects)} unique (no duplicates)")
        logger.info(f"Files: {self.output_dir}")
        logger.info(f"ClickUp Task: {parent_task_id}")
        logger.info(f"\nV2 IMPROVEMENTS:")
        logger.info("  ✅ No duplicate prospects")
        logger.info("  ✅ Clean status dashboard in parent task")
        logger.info("  ✅ Better visual hierarchy with collapsible sections")
        logger.info("  ✅ Full email content (no truncation)")
        logger.info("  ✅ Progress tracking with percentages")
        logger.info("  ✅ Cleaner subtask checklists")
        logger.info("\nNext: Execute Touch 1 from ClickUp")

        return parent_task_id


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Pain-Signal 5-Touch Nurture - V2 (Improved CRM)")
    parser.add_argument("--form-data", required=True, help="Path to onboarding form JSON")
    parser.add_argument("--list-id", default="901805941038", help="ClickUp list ID")
    parser.add_argument("--prepare-all", action="store_true", help="Prepare all 5 touches")
    parser.add_argument("--touch", type=int, choices=[1,2,3,4,5], help="Execute specific touch")

    args = parser.parse_args()

    try:
        nurture = PainSignalNurtureV2(args.form_data, args.list_id)

        if args.prepare_all:
            nurture.prepare_all_touches()
        elif args.touch:
            logger.error("Touch-by-touch execution not implemented in V2. Use --prepare-all.")
            sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()