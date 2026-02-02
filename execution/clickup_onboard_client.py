#!/usr/bin/env python3
"""
ClickUp Client Onboarding - Create client task with subtasks.

Creates ONE parent task for the client with 5-10 subtasks representing the onboarding workflow.

Usage:
    python3 execution/clickup_onboard_client.py \
        --client "Beaumont Exhibits" \
        --website "https://beaumontandco.ca" \
        --contact "Sean Court" \
        --deal-size "$50K-$1M CAD" \
        --list-id "YOUR_LIST_ID"
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

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
# ONBOARDING SUBTASKS - Value-First Nurture Sequence (14-Day Workflow)
# =============================================================================

ONBOARDING_SUBTASKS = [
    # PHASE 0B: AI QUALIFICATION (After Form Submission)
    {
        "name": "🔍 Phase 0B: AI Qualification",
        "description": "Run: python3 execution/qualify_prospect_async.py --form-data .tmp/form_submission_{client}.json | Analyze form data, score 0-10, determine DECLINE/LIGHT_NURTURE/FULL_NURTURE",
        "priority": 1
    },

    # PHASE 1: DEEP RESEARCH (Day 0-1)
    {
        "name": "🔬 Phase 1: Deep Company Research",
        "description": "Run: python3 execution/research_prospect_company.py --company '{client}' --website '{website}' | Scrape website, analyze competitors, identify pain points & opportunities",
        "priority": 1
    },

    # PHASE 2: VALUE-FIRST NURTURE SEQUENCE (Day 1-14)
    {
        "name": "📄 Touch 1 (Day 1): Industry Resource PDF",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 1 | Create & send branded PDF with immediate value | Channels: LinkedIn DM, Email | NO PITCH",
        "priority": 2
    },
    {
        "name": "🎥 Touch 2 (Day 3): Custom Loom Video",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 2 | Record 3-5min custom business breakdown | Channels: WhatsApp, Email | NO PITCH",
        "priority": 2
    },
    {
        "name": "📊 Touch 3 (Day 5): Notion Workspace",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 3 | Share interactive workspace with competitor insights | Channels: Email | NO PITCH",
        "priority": 2
    },
    {
        "name": "📈 Touch 4 (Day 7): Industry Report",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 4 | Send personalized competitor analysis | Channels: Email | NO PITCH",
        "priority": 2
    },
    {
        "name": "💬 Touch 5 (Day 10): LinkedIn Engagement",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 5 | Engage with their content authentically | Channels: LinkedIn | NO PITCH",
        "priority": 3
    },
    {
        "name": "✅ Touch 6 (Day 12): Check-In",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 6 | Ask if resources helped, no call ask yet | Channels: WhatsApp | NO PITCH",
        "priority": 2
    },
    {
        "name": "📞 Touch 7 (Day 14): SOFT Call Invitation",
        "description": "Run: python3 execution/orchestrate_nurture_sequence.py --company '{client}' --touch 7 | Soft invitation framed as help, not sales | Channels: WhatsApp, Email | SOFT ASK ALLOWED",
        "priority": 1
    },

    # PHASE 3: ENGAGEMENT ASSESSMENT (Day 14-16)
    {
        "name": "📊 Phase 3: Engagement Assessment",
        "description": "Evaluate engagement across 7 touches | HIGH: 3+ replies, questions, YES to call → Schedule | MEDIUM: Some engagement → One more touch | LOW: No engagement → STOP",
        "priority": 1
    },

    # PHASE 4: DISCOVERY CALL (Only if HIGH engagement)
    {
        "name": "☎️ Phase 4: Schedule Discovery Call",
        "description": "Only if HIGH engagement | Send calendar link | Prepare discovery call outline | Focus: Learn their world, not pitch",
        "priority": 1
    },

    # PHASE 5: PROPOSAL & CLOSE (Post-Discovery)
    {
        "name": "📋 Phase 5: Custom Proposal",
        "description": "After discovery call | Create tailored proposal | Present solution | Close deal or nurture further",
        "priority": 2
    }
]


class ClickUpClientOnboarder:
    """Creates client task with real subtasks in ClickUp."""

    def __init__(self):
        """Initialize with ClickUp client."""
        self.client = ClickUpClient()
        logger.info("✓ ClickUp Client Onboarder initialized")

    def create_client_with_subtasks(
        self,
        list_id: str,
        client_name: str,
        website: str = "",
        contact: str = "",
        deal_size: str = "",
        notes: str = "",
        priority: int = 2,
        tags: Optional[List[str]] = None
    ) -> Dict:
        """
        Create parent client task with subtasks.

        Args:
            list_id: ClickUp list ID
            client_name: Client company name
            website: Client website URL
            contact: Primary contact name
            deal_size: Estimated deal size
            notes: Additional notes
            priority: 1=Urgent, 2=High, 3=Normal, 4=Low
            tags: List of tags

        Returns:
            Result with parent task and subtasks
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"ONBOARDING CLIENT: {client_name}")
        logger.info(f"{'='*60}\n")

        results = {
            "client_name": client_name,
            "parent_task": None,
            "subtasks": [],
            "success": False
        }

        try:
            # 1. Create parent task
            logger.info("Creating parent task...")

            description = f"""## Client Information

**Company:** {client_name}
**Website:** {website}
**Contact:** {contact}
**Deal Size:** {deal_size}
**Onboarded:** {datetime.now().strftime('%Y-%m-%d')}

---

### Workflow: Value-First Nurture (14 Days)

**Philosophy:** Give MASSIVE value for 14 days BEFORE asking for call
- 7 touches over 14 days (NO pitch until Day 14)
- Engagement-based qualification (if no engagement → STOP)
- Multi-call acceptance (2-3 calls for high-ticket deals)
- Energy protection: Only proceed with engaged prospects

---

### Notes
{notes if notes else 'No additional notes.'}

---

### Deliverables
- Qualification Report: `.tmp/qualification_{client_name.lower().replace(' ', '_')}.md`
- Deep Research: `.tmp/research_{client_name.lower().replace(' ', '_')}.md`
- Nurture Plan: `.tmp/nurture_plan_{client_name.lower().replace(' ', '_')}.md`
- Nurture Touches: `.tmp/nurture_touches_{client_name.lower().replace(' ', '_')}/touch_*.json`
- Engagement Log: `.tmp/nurture_log_{client_name.lower().replace(' ', '_')}.md`
"""

            parent_task = self.client.create_task(
                list_id=list_id,
                name=f"🏢 {client_name}",
                description=description,
                priority=priority,
                tags=tags or ["client", "onboarding"]
            )

            parent_id = parent_task.get("id")
            logger.info(f"✓ Created parent task: {parent_id}")
            results["parent_task"] = parent_task

            # 2. Create subtasks
            logger.info("\nCreating subtasks...")

            for subtask_def in ONBOARDING_SUBTASKS:
                try:
                    subtask = self.client.create_subtask(
                        parent_task_id=parent_id,
                        name=subtask_def["name"],
                        description=subtask_def.get("description", ""),
                        priority=subtask_def.get("priority", 3)
                    )
                    results["subtasks"].append(subtask)
                    logger.info(f"  ✓ {subtask_def['name']}")
                except Exception as e:
                    logger.error(f"  ❌ Failed: {subtask_def['name']} - {e}")

            results["success"] = True

            # Summary
            logger.info(f"\n{'='*60}")
            logger.info("✓ CLIENT ONBOARDING COMPLETE!")
            logger.info(f"{'='*60}")
            logger.info(f"📊 Client: {client_name}")
            logger.info(f"📊 Parent Task ID: {parent_id}")
            logger.info(f"📊 Subtasks Created: {len(results['subtasks'])}")

            task_url = parent_task.get("url", "")
            if task_url:
                logger.info(f"🔗 ClickUp URL: {task_url}")

            return results

        except Exception as e:
            logger.error(f"❌ Onboarding failed: {e}")
            results["error"] = str(e)
            return results

    def delete_tasks(self, task_ids: List[str]) -> Dict:
        """Delete multiple tasks by ID."""
        results = {"deleted": [], "failed": []}
        for task_id in task_ids:
            try:
                self.client.delete_task(task_id)
                results["deleted"].append(task_id)
                logger.info(f"✓ Deleted task: {task_id}")
            except Exception as e:
                results["failed"].append({"id": task_id, "error": str(e)})
                logger.error(f"❌ Failed to delete {task_id}: {e}")
        return results


def main():
    parser = argparse.ArgumentParser(
        description="Create client task with subtasks in ClickUp"
    )

    # Client info
    parser.add_argument("--client", default="", help="Client company name")
    parser.add_argument("--list-id", default="", help="ClickUp list ID")
    parser.add_argument("--website", default="", help="Client website URL")
    parser.add_argument("--contact", default="", help="Primary contact name")
    parser.add_argument("--deal-size", default="", help="Estimated deal size")
    parser.add_argument("--notes", default="", help="Additional notes")
    parser.add_argument("--tags", nargs="+", default=["client", "onboarding"], help="Tags")

    # Discovery commands
    parser.add_argument("--list-workspaces", action="store_true", help="List workspaces")
    parser.add_argument("--list-spaces", type=str, metavar="TEAM_ID", help="List spaces")
    parser.add_argument("--list-folders", type=str, metavar="SPACE_ID", help="List folders")
    parser.add_argument("--list-lists", type=str, metavar="FOLDER_ID", help="List lists")

    # Delete command
    parser.add_argument("--delete", nargs="+", metavar="TASK_ID", help="Delete task(s) by ID")

    args = parser.parse_args()

    # Initialize
    onboarder = ClickUpClientOnboarder()

    # Handle discovery commands
    if args.list_workspaces:
        teams = onboarder.client.get_teams()
        print("\n📋 Workspaces:")
        for team in teams:
            print(f"  • {team['name']} (ID: {team['id']})")
        return

    if args.list_spaces:
        spaces = onboarder.client.get_spaces(args.list_spaces)
        print(f"\n📁 Spaces in workspace {args.list_spaces}:")
        for space in spaces:
            print(f"  • {space['name']} (ID: {space['id']})")
        return

    if args.list_folders:
        folders = onboarder.client.get_folders(args.list_folders)
        print(f"\n📂 Folders in space {args.list_folders}:")
        for folder in folders:
            print(f"  • {folder['name']} (ID: {folder['id']})")
        return

    if args.list_lists:
        lists = onboarder.client.get_lists(args.list_lists)
        print(f"\n📝 Lists in folder {args.list_lists}:")
        for lst in lists:
            print(f"  • {lst['name']} (ID: {lst['id']})")
        return

    # Handle delete command
    if args.delete:
        result = onboarder.delete_tasks(args.delete)
        print(f"\n✓ Deleted: {len(result['deleted'])} tasks")
        if result['failed']:
            print(f"❌ Failed: {len(result['failed'])} tasks")
        return

    # Validate required args for onboarding
    if not args.client or not args.list_id:
        print("❌ Error: --client and --list-id are required for onboarding")
        print("\nUsage:")
        print("  python3 clickup_onboard_client.py --client 'Company Name' --list-id 'LIST_ID'")
        print("\nDiscovery:")
        print("  --list-workspaces       List all workspaces")
        print("  --list-spaces TEAM_ID   List spaces in workspace")
        print("  --list-folders SPACE_ID List folders in space")
        print("  --list-lists FOLDER_ID  List lists in folder")
        print("\nDelete:")
        print("  --delete TASK_ID [...]  Delete task(s) by ID")
        return

    # Run onboarding
    result = onboarder.create_client_with_subtasks(
        list_id=args.list_id,
        client_name=args.client,
        website=args.website,
        contact=args.contact,
        deal_size=args.deal_size,
        notes=args.notes,
        tags=args.tags
    )

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
