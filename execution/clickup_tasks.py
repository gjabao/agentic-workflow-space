#!/usr/bin/env python3
"""
ClickUp Task Management - Full CRUD operations for tasks.

Provides CLI and programmatic interface for:
- Creating tasks (single or bulk)
- Reading/searching tasks
- Updating tasks (status, assignee, priority, etc.)
- Deleting tasks
- Adding comments

Usage:
    # Create a task
    python3 clickup_tasks.py create --list-id 123 --name "New Task" --description "Details"

    # List tasks
    python3 clickup_tasks.py list --list-id 123

    # Update task status
    python3 clickup_tasks.py update --task-id abc --status "in progress"

    # Delete task
    python3 clickup_tasks.py delete --task-id abc

    # Add comment
    python3 clickup_tasks.py comment --task-id abc --text "Updated the specs"
"""

import os
import sys
import json
import argparse
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.clickup_client import ClickUpClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClickUpTaskManager:
    """
    High-level task management operations.

    Wraps ClickUpClient with convenience methods and validation.
    """

    PRIORITY_MAP = {
        "urgent": 1,
        "high": 2,
        "normal": 3,
        "low": 4
    }

    def __init__(self):
        """Initialize with ClickUp client."""
        self.client = ClickUpClient()
        logger.info("✓ Task manager initialized")

    def create_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignees: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        due_date: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Create a new task with validation.

        Args:
            list_id: Target list ID
            name: Task name (required)
            description: Task description (markdown supported)
            status: Status name (must exist in list)
            priority: urgent, high, normal, or low
            assignees: List of user IDs
            tags: List of tag names
            due_date: Date string (YYYY-MM-DD) or timestamp
            custom_fields: Dict of {field_name: value}

        Returns:
            Created task data
        """
        if not name.strip():
            raise ValueError("Task name cannot be empty")

        # Convert priority string to number
        priority_num = None
        if priority:
            priority_lower = priority.lower()
            if priority_lower not in self.PRIORITY_MAP:
                raise ValueError(f"Invalid priority: {priority}. Use: urgent, high, normal, low")
            priority_num = self.PRIORITY_MAP[priority_lower]

        # Convert date string to timestamp
        due_timestamp = None
        if due_date:
            if isinstance(due_date, str):
                try:
                    dt = datetime.strptime(due_date, "%Y-%m-%d")
                    due_timestamp = int(dt.timestamp() * 1000)
                except ValueError:
                    # Try parsing as timestamp
                    due_timestamp = int(due_date)
            else:
                due_timestamp = int(due_date)

        # Handle custom fields
        custom_field_list = None
        if custom_fields:
            # Get available fields for the list
            available_fields = self.client.get_list_custom_fields(list_id)
            field_map = {f["name"]: f["id"] for f in available_fields}

            custom_field_list = []
            for field_name, value in custom_fields.items():
                if field_name in field_map:
                    custom_field_list.append({
                        "id": field_map[field_name],
                        "value": value
                    })
                else:
                    logger.warning(f"⚠️ Custom field '{field_name}' not found, skipping")

        logger.info(f"Creating task: {name}")
        result = self.client.create_task(
            list_id=list_id,
            name=name,
            description=description,
            status=status,
            priority=priority_num,
            assignees=assignees,
            tags=tags,
            due_date=due_timestamp,
            custom_fields=custom_field_list
        )

        logger.info(f"✓ Task created: {result.get('id')}")
        return result

    def get_task(self, task_id: str, include_subtasks: bool = False) -> Dict:
        """Get a single task by ID."""
        return self.client.get_task(task_id, include_subtasks)

    def list_tasks(
        self,
        list_id: str,
        status: Optional[str] = None,
        assignee: Optional[int] = None,
        include_closed: bool = False,
        page: int = 0
    ) -> List[Dict]:
        """
        List tasks from a list with optional filters.

        Args:
            list_id: List to fetch from
            status: Filter by status name
            assignee: Filter by assignee ID
            include_closed: Include closed tasks
            page: Page number (100 per page)

        Returns:
            List of tasks
        """
        statuses = [status] if status else None
        assignees = [assignee] if assignee else None

        tasks = self.client.get_tasks(
            list_id=list_id,
            include_closed=include_closed,
            page=page,
            statuses=statuses,
            assignees=assignees
        )

        logger.info(f"✓ Found {len(tasks)} tasks")
        return tasks

    def search_tasks(
        self,
        list_id: str,
        query: str,
        include_closed: bool = False
    ) -> List[Dict]:
        """
        Search tasks by name/description.

        Note: Client-side filtering as ClickUp API doesn't have search endpoint.
        """
        all_tasks = []
        page = 0

        while True:
            tasks = self.client.get_tasks(
                list_id=list_id,
                include_closed=include_closed,
                page=page
            )
            if not tasks:
                break
            all_tasks.extend(tasks)
            page += 1

        # Filter by query (case-insensitive)
        query_lower = query.lower()
        matches = [
            t for t in all_tasks
            if query_lower in t.get("name", "").lower()
            or query_lower in t.get("description", "").lower()
        ]

        logger.info(f"✓ Found {len(matches)} tasks matching '{query}'")
        return matches

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[str] = None,
        archived: Optional[bool] = None
    ) -> Dict:
        """
        Update task fields.

        Only provided fields will be updated.
        """
        update_data = {}

        if name:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if status:
            update_data["status"] = status
        if priority:
            priority_lower = priority.lower()
            if priority_lower not in self.PRIORITY_MAP:
                raise ValueError(f"Invalid priority: {priority}")
            update_data["priority"] = self.PRIORITY_MAP[priority_lower]
        if due_date:
            if isinstance(due_date, str):
                dt = datetime.strptime(due_date, "%Y-%m-%d")
                update_data["due_date"] = int(dt.timestamp() * 1000)
            else:
                update_data["due_date"] = int(due_date)
        if archived is not None:
            update_data["archived"] = archived

        if not update_data:
            logger.warning("No updates provided")
            return self.get_task(task_id)

        logger.info(f"Updating task {task_id}: {list(update_data.keys())}")
        result = self.client.update_task(task_id, **update_data)
        logger.info(f"✓ Task updated")
        return result

    def delete_task(self, task_id: str) -> Dict:
        """Delete a task."""
        logger.info(f"Deleting task {task_id}")
        result = self.client.delete_task(task_id)
        logger.info(f"✓ Task deleted")
        return result

    def add_comment(
        self,
        task_id: str,
        text: str,
        assignee: Optional[int] = None
    ) -> Dict:
        """Add a comment to a task."""
        logger.info(f"Adding comment to task {task_id}")
        result = self.client.add_task_comment(task_id, text, assignee)
        logger.info(f"✓ Comment added")
        return result

    def get_comments(self, task_id: str) -> List[Dict]:
        """Get all comments on a task."""
        comments = self.client.get_task_comments(task_id)
        logger.info(f"✓ Found {len(comments)} comments")
        return comments

    def move_task_status(self, task_id: str, new_status: str) -> Dict:
        """
        Move task to a new status.

        Common statuses: "to do", "in progress", "review", "complete"
        """
        return self.update_task(task_id, status=new_status)

    def assign_task(self, task_id: str, assignee_ids: List[int]) -> Dict:
        """Assign users to a task."""
        return self.client.update_task(task_id, assignees={"add": assignee_ids})

    def unassign_task(self, task_id: str, assignee_ids: List[int]) -> Dict:
        """Remove users from a task."""
        return self.client.update_task(task_id, assignees={"rem": assignee_ids})

    def add_tag(self, task_id: str, tag_name: str) -> Dict:
        """Add a tag to a task."""
        return self.client.add_tag_to_task(task_id, tag_name)

    def remove_tag(self, task_id: str, tag_name: str) -> Dict:
        """Remove a tag from a task."""
        return self.client.remove_tag_from_task(task_id, tag_name)

    def bulk_create(
        self,
        list_id: str,
        tasks: List[Dict],
        show_progress: bool = True
    ) -> Dict:
        """
        Create multiple tasks.

        Args:
            list_id: Target list
            tasks: List of task dicts with at minimum 'name' key
            show_progress: Print progress updates

        Returns:
            Summary with success/failure counts
        """
        def progress_callback(completed, total):
            if show_progress:
                pct = (completed / total) * 100
                print(f"⏳ Progress: {completed}/{total} ({pct:.0f}%)")

        logger.info(f"Creating {len(tasks)} tasks in list {list_id}")
        results = self.client.bulk_create_tasks(list_id, tasks, progress_callback)

        success = sum(1 for r in results if r.get("success"))
        failed = len(results) - success

        summary = {
            "total": len(tasks),
            "success": success,
            "failed": failed,
            "results": results
        }

        logger.info(f"✓ Bulk create complete: {success} success, {failed} failed")
        return summary

    def bulk_update_status(
        self,
        task_ids: List[str],
        new_status: str,
        show_progress: bool = True
    ) -> Dict:
        """
        Update status for multiple tasks.

        Args:
            task_ids: List of task IDs
            new_status: New status to set
            show_progress: Print progress updates

        Returns:
            Summary with success/failure counts
        """
        updates = [{"task_id": tid, "status": new_status} for tid in task_ids]

        def progress_callback(completed, total):
            if show_progress:
                pct = (completed / total) * 100
                print(f"⏳ Progress: {completed}/{total} ({pct:.0f}%)")

        logger.info(f"Updating {len(task_ids)} tasks to status: {new_status}")
        results = self.client.bulk_update_tasks(updates, progress_callback)

        success = sum(1 for r in results if r.get("success"))
        failed = len(results) - success

        summary = {
            "total": len(task_ids),
            "success": success,
            "failed": failed,
            "results": results
        }

        logger.info(f"✓ Bulk update complete: {success} success, {failed} failed")
        return summary


def format_task(task: Dict, verbose: bool = False) -> str:
    """Format task for display."""
    lines = []

    status = task.get("status", {}).get("status", "unknown")
    priority = task.get("priority", {})
    priority_str = priority.get("priority", "none") if priority else "none"

    lines.append(f"📋 {task.get('name', 'Untitled')}")
    lines.append(f"   ID: {task.get('id')}")
    lines.append(f"   Status: {status}")
    lines.append(f"   Priority: {priority_str}")

    if verbose:
        if task.get("description"):
            desc = task["description"][:100] + "..." if len(task.get("description", "")) > 100 else task.get("description", "")
            lines.append(f"   Description: {desc}")

        assignees = task.get("assignees", [])
        if assignees:
            names = [a.get("username", a.get("email", "unknown")) for a in assignees]
            lines.append(f"   Assignees: {', '.join(names)}")

        tags = task.get("tags", [])
        if tags:
            tag_names = [t.get("name") for t in tags]
            lines.append(f"   Tags: {', '.join(tag_names)}")

        if task.get("due_date"):
            due = datetime.fromtimestamp(int(task["due_date"]) / 1000)
            lines.append(f"   Due: {due.strftime('%Y-%m-%d')}")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ClickUp Task Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a task
  python3 clickup_tasks.py create --list-id 901234567 --name "Review PR" --priority high

  # List all tasks
  python3 clickup_tasks.py list --list-id 901234567

  # List tasks with status filter
  python3 clickup_tasks.py list --list-id 901234567 --status "in progress"

  # Update task status
  python3 clickup_tasks.py update --task-id abc123 --status "complete"

  # Add comment
  python3 clickup_tasks.py comment --task-id abc123 --text "Done!"

  # Delete task
  python3 clickup_tasks.py delete --task-id abc123
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # CREATE command
    create_parser = subparsers.add_parser("create", help="Create a new task")
    create_parser.add_argument("--list-id", required=True, help="Target list ID")
    create_parser.add_argument("--name", required=True, help="Task name")
    create_parser.add_argument("--description", default="", help="Task description")
    create_parser.add_argument("--status", help="Initial status")
    create_parser.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="Task priority")
    create_parser.add_argument("--due-date", help="Due date (YYYY-MM-DD)")
    create_parser.add_argument("--tags", nargs="+", help="Tags to add")
    create_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # LIST command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--list-id", required=True, help="List ID to fetch from")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--include-closed", action="store_true", help="Include closed tasks")
    list_parser.add_argument("--search", help="Search by name/description")
    list_parser.add_argument("--verbose", "-v", action="store_true", help="Show more details")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # GET command
    get_parser = subparsers.add_parser("get", help="Get a specific task")
    get_parser.add_argument("--task-id", required=True, help="Task ID")
    get_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # UPDATE command
    update_parser = subparsers.add_parser("update", help="Update a task")
    update_parser.add_argument("--task-id", required=True, help="Task ID to update")
    update_parser.add_argument("--name", help="New name")
    update_parser.add_argument("--description", help="New description")
    update_parser.add_argument("--status", help="New status")
    update_parser.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="New priority")
    update_parser.add_argument("--due-date", help="New due date (YYYY-MM-DD)")
    update_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # DELETE command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("--task-id", required=True, help="Task ID to delete")
    delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # COMMENT command
    comment_parser = subparsers.add_parser("comment", help="Add comment to task")
    comment_parser.add_argument("--task-id", required=True, help="Task ID")
    comment_parser.add_argument("--text", required=True, help="Comment text")
    comment_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # TAG commands
    tag_parser = subparsers.add_parser("tag", help="Manage task tags")
    tag_parser.add_argument("--task-id", required=True, help="Task ID")
    tag_parser.add_argument("--add", help="Tag name to add")
    tag_parser.add_argument("--remove", help="Tag name to remove")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = ClickUpTaskManager()

    try:
        if args.command == "create":
            result = manager.create_task(
                list_id=args.list_id,
                name=args.name,
                description=args.description,
                status=args.status,
                priority=args.priority,
                due_date=args.due_date,
                tags=args.tags
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Task created successfully!")
                print(format_task(result, verbose=True))

        elif args.command == "list":
            if args.search:
                tasks = manager.search_tasks(
                    list_id=args.list_id,
                    query=args.search,
                    include_closed=args.include_closed
                )
            else:
                tasks = manager.list_tasks(
                    list_id=args.list_id,
                    status=args.status,
                    include_closed=args.include_closed
                )

            if args.json:
                print(json.dumps(tasks, indent=2))
            else:
                print(f"\n📋 Found {len(tasks)} tasks:\n")
                for task in tasks:
                    print(format_task(task, verbose=args.verbose))
                    print()

        elif args.command == "get":
            task = manager.get_task(args.task_id)
            if args.json:
                print(json.dumps(task, indent=2))
            else:
                print(format_task(task, verbose=True))

        elif args.command == "update":
            result = manager.update_task(
                task_id=args.task_id,
                name=args.name,
                description=args.description,
                status=args.status,
                priority=args.priority,
                due_date=args.due_date
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Task updated!")
                print(format_task(result, verbose=True))

        elif args.command == "delete":
            if not args.force:
                confirm = input(f"Delete task {args.task_id}? (y/N): ")
                if confirm.lower() != "y":
                    print("Cancelled")
                    return

            manager.delete_task(args.task_id)
            print(f"\n✓ Task {args.task_id} deleted")

        elif args.command == "comment":
            result = manager.add_comment(args.task_id, args.text)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Comment added to task {args.task_id}")

        elif args.command == "tag":
            if args.add:
                manager.add_tag(args.task_id, args.add)
                print(f"\n✓ Tag '{args.add}' added")
            elif args.remove:
                manager.remove_tag(args.task_id, args.remove)
                print(f"\n✓ Tag '{args.remove}' removed")
            else:
                print("Specify --add or --remove")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
