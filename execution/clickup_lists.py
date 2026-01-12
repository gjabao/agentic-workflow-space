#!/usr/bin/env python3
"""
ClickUp List & Folder Management - Workspace structure operations.

Provides CLI and programmatic interface for:
- Listing workspaces, spaces, folders, lists
- Creating/updating/deleting folders and lists
- Getting list custom fields
- Managing list statuses

Usage:
    # List all workspaces
    python3 clickup_lists.py workspaces

    # List spaces in a workspace
    python3 clickup_lists.py spaces --team-id 123

    # List folders in a space
    python3 clickup_lists.py folders --space-id 456

    # List lists in a folder
    python3 clickup_lists.py lists --folder-id 789

    # Create a new list
    python3 clickup_lists.py create-list --folder-id 789 --name "New List"

    # Get list details
    python3 clickup_lists.py list-info --list-id 901
"""

import os
import sys
import json
import argparse
import logging
from typing import Optional, List, Dict

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.clickup_client import ClickUpClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClickUpWorkspaceManager:
    """
    High-level workspace/list management operations.

    Wraps ClickUpClient with convenience methods for navigating
    and managing ClickUp workspace hierarchy.
    """

    def __init__(self):
        """Initialize with ClickUp client."""
        self.client = ClickUpClient()
        logger.info("✓ Workspace manager initialized")

    # =========================================================================
    # DISCOVERY METHODS
    # =========================================================================

    def get_workspaces(self) -> List[Dict]:
        """Get all accessible workspaces (teams)."""
        teams = self.client.get_teams()
        logger.info(f"✓ Found {len(teams)} workspace(s)")
        return teams

    def get_spaces(self, team_id: str, include_archived: bool = False) -> List[Dict]:
        """Get all spaces in a workspace."""
        spaces = self.client.get_spaces(team_id, archived=include_archived)
        logger.info(f"✓ Found {len(spaces)} space(s)")
        return spaces

    def get_folders(self, space_id: str, include_archived: bool = False) -> List[Dict]:
        """Get all folders in a space."""
        folders = self.client.get_folders(space_id, archived=include_archived)
        logger.info(f"✓ Found {len(folders)} folder(s)")
        return folders

    def get_lists(self, folder_id: str, include_archived: bool = False) -> List[Dict]:
        """Get all lists in a folder."""
        lists = self.client.get_lists(folder_id, archived=include_archived)
        logger.info(f"✓ Found {len(lists)} list(s)")
        return lists

    def get_folderless_lists(self, space_id: str, include_archived: bool = False) -> List[Dict]:
        """Get lists directly under a space (not in folders)."""
        lists = self.client.get_folderless_lists(space_id, archived=include_archived)
        logger.info(f"✓ Found {len(lists)} folderless list(s)")
        return lists

    def get_list_info(self, list_id: str) -> Dict:
        """Get detailed information about a list."""
        return self.client.get_list(list_id)

    def get_full_hierarchy(self, team_id: str) -> Dict:
        """
        Get full workspace hierarchy.

        Returns nested structure:
        {
            "team": {...},
            "spaces": [
                {
                    "space": {...},
                    "folders": [
                        {
                            "folder": {...},
                            "lists": [...]
                        }
                    ],
                    "folderless_lists": [...]
                }
            ]
        }
        """
        logger.info(f"Fetching full hierarchy for workspace {team_id}...")

        result = {
            "team_id": team_id,
            "spaces": []
        }

        spaces = self.client.get_spaces(team_id)
        for space in spaces:
            space_data = {
                "space": space,
                "folders": [],
                "folderless_lists": []
            }

            # Get folders
            folders = self.client.get_folders(space["id"])
            for folder in folders:
                folder_data = {
                    "folder": folder,
                    "lists": self.client.get_lists(folder["id"])
                }
                space_data["folders"].append(folder_data)

            # Get folderless lists
            space_data["folderless_lists"] = self.client.get_folderless_lists(space["id"])

            result["spaces"].append(space_data)

        logger.info(f"✓ Hierarchy fetched: {len(spaces)} spaces")
        return result

    # =========================================================================
    # FOLDER OPERATIONS
    # =========================================================================

    def create_folder(self, space_id: str, name: str) -> Dict:
        """Create a new folder in a space."""
        if not name.strip():
            raise ValueError("Folder name cannot be empty")

        logger.info(f"Creating folder: {name}")
        result = self.client.create_folder(space_id, name)
        logger.info(f"✓ Folder created: {result.get('id')}")
        return result

    def update_folder(self, folder_id: str, name: str) -> Dict:
        """Rename a folder."""
        if not name.strip():
            raise ValueError("Folder name cannot be empty")

        logger.info(f"Renaming folder {folder_id} to: {name}")
        result = self.client.update_folder(folder_id, name)
        logger.info(f"✓ Folder updated")
        return result

    def delete_folder(self, folder_id: str) -> Dict:
        """Delete a folder (and all contents)."""
        logger.info(f"Deleting folder {folder_id}")
        result = self.client.delete_folder(folder_id)
        logger.info(f"✓ Folder deleted")
        return result

    # =========================================================================
    # LIST OPERATIONS
    # =========================================================================

    def create_list(
        self,
        folder_id: str,
        name: str,
        content: str = "",
        due_date: Optional[int] = None
    ) -> Dict:
        """Create a new list in a folder."""
        if not name.strip():
            raise ValueError("List name cannot be empty")

        logger.info(f"Creating list: {name}")
        result = self.client.create_list(
            folder_id=folder_id,
            name=name,
            content=content,
            due_date=due_date
        )
        logger.info(f"✓ List created: {result.get('id')}")
        return result

    def create_folderless_list(
        self,
        space_id: str,
        name: str,
        content: str = ""
    ) -> Dict:
        """Create a list directly in a space (no folder)."""
        if not name.strip():
            raise ValueError("List name cannot be empty")

        logger.info(f"Creating folderless list: {name}")
        result = self.client.create_folderless_list(space_id, name, content=content)
        logger.info(f"✓ List created: {result.get('id')}")
        return result

    def update_list(
        self,
        list_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
        due_date: Optional[int] = None,
        unset_status: bool = False
    ) -> Dict:
        """Update list properties."""
        update_data = {}
        if name:
            update_data["name"] = name
        if content is not None:
            update_data["content"] = content
        if due_date:
            update_data["due_date"] = due_date
        if unset_status:
            update_data["unset_status"] = True

        if not update_data:
            logger.warning("No updates provided")
            return self.get_list_info(list_id)

        logger.info(f"Updating list {list_id}")
        result = self.client.update_list(list_id, **update_data)
        logger.info(f"✓ List updated")
        return result

    def delete_list(self, list_id: str) -> Dict:
        """Delete a list."""
        logger.info(f"Deleting list {list_id}")
        result = self.client.delete_list(list_id)
        logger.info(f"✓ List deleted")
        return result

    # =========================================================================
    # SPACE OPERATIONS
    # =========================================================================

    def create_space(
        self,
        team_id: str,
        name: str,
        multiple_assignees: bool = True,
        features: Optional[Dict] = None
    ) -> Dict:
        """Create a new space in a workspace."""
        if not name.strip():
            raise ValueError("Space name cannot be empty")

        kwargs = {"multiple_assignees": multiple_assignees}
        if features:
            kwargs["features"] = features

        logger.info(f"Creating space: {name}")
        result = self.client.create_space(team_id, name, **kwargs)
        logger.info(f"✓ Space created: {result.get('id')}")
        return result

    def update_space(
        self,
        space_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        private: Optional[bool] = None,
        multiple_assignees: Optional[bool] = None
    ) -> Dict:
        """Update space settings."""
        update_data = {}
        if name:
            update_data["name"] = name
        if color:
            update_data["color"] = color
        if private is not None:
            update_data["private"] = private
        if multiple_assignees is not None:
            update_data["multiple_assignees"] = multiple_assignees

        if not update_data:
            logger.warning("No updates provided")
            return self.client.get_space(space_id)

        logger.info(f"Updating space {space_id}")
        result = self.client.update_space(space_id, **update_data)
        logger.info(f"✓ Space updated")
        return result

    def delete_space(self, space_id: str) -> Dict:
        """Delete a space (and all contents)."""
        logger.info(f"Deleting space {space_id}")
        result = self.client.delete_space(space_id)
        logger.info(f"✓ Space deleted")
        return result

    # =========================================================================
    # CUSTOM FIELDS
    # =========================================================================

    def get_custom_fields(self, list_id: str) -> List[Dict]:
        """Get available custom fields for a list."""
        fields = self.client.get_list_custom_fields(list_id)
        logger.info(f"✓ Found {len(fields)} custom field(s)")
        return fields

    # =========================================================================
    # TAGS
    # =========================================================================

    def get_tags(self, space_id: str) -> List[Dict]:
        """Get all tags in a space."""
        tags = self.client.get_space_tags(space_id)
        logger.info(f"✓ Found {len(tags)} tag(s)")
        return tags

    def create_tag(
        self,
        space_id: str,
        name: str,
        bg_color: str = "#7C4DFF",
        fg_color: str = "#FFFFFF"
    ) -> Dict:
        """Create a new tag in a space."""
        logger.info(f"Creating tag: {name}")
        result = self.client.create_space_tag(space_id, name, bg_color, fg_color)
        logger.info(f"✓ Tag created")
        return result

    # =========================================================================
    # MEMBERS
    # =========================================================================

    def get_list_members(self, list_id: str) -> List[Dict]:
        """Get members with access to a list."""
        members = self.client.get_list_members(list_id)
        logger.info(f"✓ Found {len(members)} member(s)")
        return members

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def find_list_by_name(
        self,
        team_id: str,
        list_name: str,
        space_name: Optional[str] = None,
        folder_name: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find a list by name across the workspace.

        Args:
            team_id: Workspace ID to search in
            list_name: Name of list to find
            space_name: Optional space name filter
            folder_name: Optional folder name filter

        Returns:
            List data if found, None otherwise
        """
        logger.info(f"Searching for list: {list_name}")

        spaces = self.client.get_spaces(team_id)

        for space in spaces:
            if space_name and space["name"].lower() != space_name.lower():
                continue

            # Check folders
            folders = self.client.get_folders(space["id"])
            for folder in folders:
                if folder_name and folder["name"].lower() != folder_name.lower():
                    continue

                lists = self.client.get_lists(folder["id"])
                for lst in lists:
                    if lst["name"].lower() == list_name.lower():
                        logger.info(f"✓ Found list: {lst['id']}")
                        return lst

            # Check folderless lists
            if not folder_name:
                lists = self.client.get_folderless_lists(space["id"])
                for lst in lists:
                    if lst["name"].lower() == list_name.lower():
                        logger.info(f"✓ Found list: {lst['id']}")
                        return lst

        logger.warning(f"List not found: {list_name}")
        return None

    def get_list_statuses(self, list_id: str) -> List[Dict]:
        """Get available statuses for a list."""
        list_info = self.client.get_list(list_id)
        statuses = list_info.get("statuses", [])
        logger.info(f"✓ Found {len(statuses)} status(es)")
        return statuses


def format_workspace(workspace: Dict) -> str:
    """Format workspace for display."""
    return f"🏢 {workspace['name']} (ID: {workspace['id']})"


def format_space(space: Dict) -> str:
    """Format space for display."""
    return f"📁 {space['name']} (ID: {space['id']})"


def format_folder(folder: Dict) -> str:
    """Format folder for display."""
    return f"📂 {folder['name']} (ID: {folder['id']})"


def format_list(lst: Dict, verbose: bool = False) -> str:
    """Format list for display."""
    lines = [f"📋 {lst['name']} (ID: {lst['id']})"]

    if verbose:
        if lst.get("content"):
            lines.append(f"   Description: {lst['content'][:100]}")
        if lst.get("statuses"):
            status_names = [s["status"] for s in lst["statuses"]]
            lines.append(f"   Statuses: {', '.join(status_names)}")
        task_count = lst.get("task_count", 0)
        lines.append(f"   Tasks: {task_count}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ClickUp Workspace & List Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all workspaces
  python3 clickup_lists.py workspaces

  # List spaces in workspace
  python3 clickup_lists.py spaces --team-id 9012345678

  # List folders in space
  python3 clickup_lists.py folders --space-id 90123456

  # List lists in folder
  python3 clickup_lists.py lists --folder-id 90123456

  # Get full workspace hierarchy
  python3 clickup_lists.py hierarchy --team-id 9012345678

  # Create a folder
  python3 clickup_lists.py create-folder --space-id 90123456 --name "New Folder"

  # Create a list
  python3 clickup_lists.py create-list --folder-id 90123456 --name "New List"

  # Get list details
  python3 clickup_lists.py list-info --list-id 901234567

  # Find list by name
  python3 clickup_lists.py find-list --team-id 9012345678 --name "My List"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # WORKSPACES command
    subparsers.add_parser("workspaces", help="List all workspaces")

    # SPACES command
    spaces_parser = subparsers.add_parser("spaces", help="List spaces in workspace")
    spaces_parser.add_argument("--team-id", required=True, help="Workspace ID")
    spaces_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # FOLDERS command
    folders_parser = subparsers.add_parser("folders", help="List folders in space")
    folders_parser.add_argument("--space-id", required=True, help="Space ID")
    folders_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # LISTS command
    lists_parser = subparsers.add_parser("lists", help="List lists in folder")
    lists_parser.add_argument("--folder-id", help="Folder ID")
    lists_parser.add_argument("--space-id", help="Space ID (for folderless lists)")
    lists_parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    lists_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # HIERARCHY command
    hierarchy_parser = subparsers.add_parser("hierarchy", help="Get full workspace hierarchy")
    hierarchy_parser.add_argument("--team-id", required=True, help="Workspace ID")
    hierarchy_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # LIST-INFO command
    info_parser = subparsers.add_parser("list-info", help="Get list details")
    info_parser.add_argument("--list-id", required=True, help="List ID")
    info_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # CREATE-SPACE command
    create_space_parser = subparsers.add_parser("create-space", help="Create a space")
    create_space_parser.add_argument("--team-id", required=True, help="Workspace ID")
    create_space_parser.add_argument("--name", required=True, help="Space name")
    create_space_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # CREATE-FOLDER command
    create_folder_parser = subparsers.add_parser("create-folder", help="Create a folder")
    create_folder_parser.add_argument("--space-id", required=True, help="Space ID")
    create_folder_parser.add_argument("--name", required=True, help="Folder name")
    create_folder_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # CREATE-LIST command
    create_list_parser = subparsers.add_parser("create-list", help="Create a list")
    create_list_parser.add_argument("--folder-id", help="Folder ID")
    create_list_parser.add_argument("--space-id", help="Space ID (for folderless list)")
    create_list_parser.add_argument("--name", required=True, help="List name")
    create_list_parser.add_argument("--description", default="", help="List description")
    create_list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # DELETE commands
    delete_folder_parser = subparsers.add_parser("delete-folder", help="Delete a folder")
    delete_folder_parser.add_argument("--folder-id", required=True, help="Folder ID")
    delete_folder_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    delete_list_parser = subparsers.add_parser("delete-list", help="Delete a list")
    delete_list_parser.add_argument("--list-id", required=True, help="List ID")
    delete_list_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # FIND-LIST command
    find_parser = subparsers.add_parser("find-list", help="Find list by name")
    find_parser.add_argument("--team-id", required=True, help="Workspace ID")
    find_parser.add_argument("--name", required=True, help="List name to find")
    find_parser.add_argument("--space", help="Filter by space name")
    find_parser.add_argument("--folder", help="Filter by folder name")
    find_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # CUSTOM-FIELDS command
    fields_parser = subparsers.add_parser("custom-fields", help="Get list custom fields")
    fields_parser.add_argument("--list-id", required=True, help="List ID")
    fields_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # STATUSES command
    statuses_parser = subparsers.add_parser("statuses", help="Get list statuses")
    statuses_parser.add_argument("--list-id", required=True, help="List ID")
    statuses_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # TAGS command
    tags_parser = subparsers.add_parser("tags", help="Get space tags")
    tags_parser.add_argument("--space-id", required=True, help="Space ID")
    tags_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = ClickUpWorkspaceManager()

    try:
        if args.command == "workspaces":
            workspaces = manager.get_workspaces()
            print(f"\n🏢 Found {len(workspaces)} workspace(s):\n")
            for ws in workspaces:
                print(format_workspace(ws))

        elif args.command == "spaces":
            spaces = manager.get_spaces(args.team_id)
            if args.json:
                print(json.dumps(spaces, indent=2))
            else:
                print(f"\n📁 Found {len(spaces)} space(s):\n")
                for space in spaces:
                    print(format_space(space))

        elif args.command == "folders":
            folders = manager.get_folders(args.space_id)
            if args.json:
                print(json.dumps(folders, indent=2))
            else:
                print(f"\n📂 Found {len(folders)} folder(s):\n")
                for folder in folders:
                    print(format_folder(folder))

        elif args.command == "lists":
            if args.folder_id:
                lists = manager.get_lists(args.folder_id)
            elif args.space_id:
                lists = manager.get_folderless_lists(args.space_id)
            else:
                print("Error: Provide --folder-id or --space-id")
                return

            if args.json:
                print(json.dumps(lists, indent=2))
            else:
                print(f"\n📋 Found {len(lists)} list(s):\n")
                for lst in lists:
                    print(format_list(lst, verbose=args.verbose))
                    print()

        elif args.command == "hierarchy":
            hierarchy = manager.get_full_hierarchy(args.team_id)
            if args.json:
                print(json.dumps(hierarchy, indent=2))
            else:
                print(f"\n🏢 Workspace: {args.team_id}\n")
                for space_data in hierarchy["spaces"]:
                    space = space_data["space"]
                    print(f"  📁 {space['name']} ({space['id']})")

                    for folder_data in space_data["folders"]:
                        folder = folder_data["folder"]
                        print(f"    📂 {folder['name']} ({folder['id']})")
                        for lst in folder_data["lists"]:
                            print(f"      📋 {lst['name']} ({lst['id']})")

                    if space_data["folderless_lists"]:
                        print(f"    📋 (No folder):")
                        for lst in space_data["folderless_lists"]:
                            print(f"      📋 {lst['name']} ({lst['id']})")

        elif args.command == "list-info":
            list_info = manager.get_list_info(args.list_id)
            if args.json:
                print(json.dumps(list_info, indent=2))
            else:
                print(format_list(list_info, verbose=True))

        elif args.command == "create-space":
            result = manager.create_space(args.team_id, args.name)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Space created: {format_space(result)}")

        elif args.command == "create-folder":
            result = manager.create_folder(args.space_id, args.name)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Folder created: {format_folder(result)}")

        elif args.command == "create-list":
            if args.folder_id:
                result = manager.create_list(args.folder_id, args.name, args.description)
            elif args.space_id:
                result = manager.create_folderless_list(args.space_id, args.name, args.description)
            else:
                print("Error: Provide --folder-id or --space-id")
                return

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ List created: {format_list(result)}")

        elif args.command == "delete-folder":
            if not args.force:
                confirm = input(f"Delete folder {args.folder_id} and ALL contents? (y/N): ")
                if confirm.lower() != "y":
                    print("Cancelled")
                    return
            manager.delete_folder(args.folder_id)
            print(f"\n✓ Folder {args.folder_id} deleted")

        elif args.command == "delete-list":
            if not args.force:
                confirm = input(f"Delete list {args.list_id}? (y/N): ")
                if confirm.lower() != "y":
                    print("Cancelled")
                    return
            manager.delete_list(args.list_id)
            print(f"\n✓ List {args.list_id} deleted")

        elif args.command == "find-list":
            result = manager.find_list_by_name(
                team_id=args.team_id,
                list_name=args.name,
                space_name=args.space,
                folder_name=args.folder
            )
            if result:
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(f"\n✓ Found: {format_list(result, verbose=True)}")
            else:
                print(f"\n❌ List '{args.name}' not found")

        elif args.command == "custom-fields":
            fields = manager.get_custom_fields(args.list_id)
            if args.json:
                print(json.dumps(fields, indent=2))
            else:
                print(f"\n🔧 Custom fields ({len(fields)}):\n")
                for field in fields:
                    print(f"  • {field['name']} (ID: {field['id']}, Type: {field['type']})")

        elif args.command == "statuses":
            statuses = manager.get_list_statuses(args.list_id)
            if args.json:
                print(json.dumps(statuses, indent=2))
            else:
                print(f"\n📊 Statuses ({len(statuses)}):\n")
                for status in statuses:
                    color = status.get("color", "none")
                    print(f"  • {status['status']} (color: {color})")

        elif args.command == "tags":
            tags = manager.get_tags(args.space_id)
            if args.json:
                print(json.dumps(tags, indent=2))
            else:
                print(f"\n🏷️ Tags ({len(tags)}):\n")
                for tag in tags:
                    print(f"  • {tag['name']}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
