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
# ONBOARDING SUBTASKS (5-10 key tasks)
# =============================================================================

ONBOARDING_SUBTASKS = [
    {
        "name": "📋 ICP Research & Apollo URLs",
        "description": "Extract target audiences from client profile, generate Apollo search URLs",
        "priority": 2
    },
    {
        "name": "🎯 Scrape Leads (Audience 1)",
        "description": "Run lead scraper for primary audience, verify emails, generate icebreakers",
        "priority": 2
    },
    {
        "name": "🎯 Scrape Leads (Audience 2)",
        "description": "Run lead scraper for secondary audience if applicable",
        "priority": 3
    },
    {
        "name": "📧 Generate Cold Email Copy",
        "description": "Analyze website, research competitors, generate 3+ email variants with Connector Angle",
        "priority": 2
    },
    {
        "name": "✅ Quality Check: ≥50 Valid Emails",
        "description": "Ensure at least 50 valid emails before proceeding to campaign",
        "priority": 2
    },
    {
        "name": "🚀 Setup Instantly Campaign",
        "description": "Import leads, create campaign, set up follow-up sequence",
        "priority": 1
    },
    {
        "name": "📤 Launch Campaign",
        "description": "Test deliverability, launch campaign, notify client",
        "priority": 1
    },
    {
        "name": "📊 Monitor & Report (48h check)",
        "description": "Check opens/replies after 48h, handle positive responses",
        "priority": 3
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

### Notes
{notes if notes else 'No additional notes.'}

---

### Deliverables
- ICP Research: `.tmp/icp_research_{client_name.lower().replace(' ', '_')}.md`
- Leads CSV: `.tmp/leads_*.csv`
- Cold Email Copy: `.tmp/custom_copy_{client_name.lower().replace(' ', '_')}.md`
- Campaign Summary: `.tmp/{client_name.lower().replace(' ', '_')}_campaign_summary.md`
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
