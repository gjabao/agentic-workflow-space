#!/usr/bin/env python3
"""
ClickUp API Client - Core wrapper with rate limiting and error handling.

This is the base client used by all ClickUp execution scripts.
Implements secure credential handling and production-grade patterns.

Usage:
    from clickup_client import ClickUpClient

    client = ClickUpClient()
    teams = client.get_teams()
"""

import os
import sys
import time
import json
import logging
from typing import Optional, Dict, Any, List
from threading import Lock
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import requests
try:
    import requests
except ImportError:
    logger.error("❌ requests not installed. Run: pip install requests")
    sys.exit(1)


class ClickUpClient:
    """
    Production-grade ClickUp API client.

    Features:
    - Secure credential handling (Load → Use → Delete pattern)
    - Thread-safe rate limiting (100 req/min for ClickUp)
    - Exponential backoff on 429 errors
    - Comprehensive error handling
    - Request/response logging
    """

    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(self):
        """Initialize client with secure credential loading."""
        self._rate_limit_lock = Lock()
        self._last_call_time = 0
        self._min_delay = 0.6  # 100 req/min = ~1.67 req/sec, use 0.6s for safety

        # Secure credential loading
        api_key = self._load_secret("CLICKUP_API_KEY", required=True)
        self._headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        del api_key  # Clear from memory

        logger.info("✓ ClickUp client initialized")

    def _load_secret(self, key_name: str, required: bool = False) -> str:
        """Load secret from environment with validation."""
        value = os.getenv(key_name)
        if required and not value:
            raise ValueError(f"❌ {key_name} not found in .env file")
        if value:
            logger.info(f"✓ {key_name} loaded")
        return value

    def __repr__(self):
        """Prevent credential exposure in debugging."""
        return "<ClickUpClient initialized>"

    def _rate_limit(self):
        """Thread-safe rate limiting."""
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_call_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)
            self._last_call_time = time.time()

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body for POST/PUT
            params: Query parameters
            max_retries: Maximum retry attempts on failure

        Returns:
            API response as dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(max_retries):
            self._rate_limit()

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    json=data,
                    params=params,
                    timeout=30
                )

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = 2 ** attempt * 2  # 2, 4, 8 seconds
                    logger.warning(f"⚠️ Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Handle success
                if response.status_code in [200, 201]:
                    return response.json()

                # Handle no content (DELETE success)
                if response.status_code == 204:
                    return {"success": True, "message": "Deleted successfully"}

                # Handle errors
                error_msg = f"API Error {response.status_code}: {response.text}"
                logger.error(f"❌ {error_msg}")

                # Don't retry on client errors (4xx except 429)
                if 400 <= response.status_code < 500:
                    raise Exception(error_msg)

                # Retry on server errors (5xx)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                raise Exception(error_msg)

            except requests.Timeout:
                logger.warning(f"⚠️ Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise Exception("Request timed out after all retries")

            except requests.RequestException as e:
                logger.error(f"❌ Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise Exception("Max retries exceeded")

    # =========================================================================
    # WORKSPACE & TEAM METHODS
    # =========================================================================

    def get_teams(self) -> List[Dict]:
        """Get all workspaces (teams) accessible to the user."""
        response = self._request("GET", "/team")
        return response.get("teams", [])

    def get_team(self, team_id: str) -> Dict:
        """Get a specific workspace by ID."""
        return self._request("GET", f"/team/{team_id}")

    # =========================================================================
    # SPACE METHODS
    # =========================================================================

    def get_spaces(self, team_id: str, archived: bool = False) -> List[Dict]:
        """Get all spaces in a workspace."""
        params = {"archived": str(archived).lower()}
        response = self._request("GET", f"/team/{team_id}/space", params=params)
        return response.get("spaces", [])

    def get_space(self, space_id: str) -> Dict:
        """Get a specific space by ID."""
        return self._request("GET", f"/space/{space_id}")

    def create_space(self, team_id: str, name: str, **kwargs) -> Dict:
        """
        Create a new space.

        Args:
            team_id: Workspace ID
            name: Space name
            **kwargs: Optional settings (multiple_assignees, features, etc.)
        """
        data = {"name": name, **kwargs}
        return self._request("POST", f"/team/{team_id}/space", data=data)

    def update_space(self, space_id: str, **kwargs) -> Dict:
        """Update space settings."""
        return self._request("PUT", f"/space/{space_id}", data=kwargs)

    def delete_space(self, space_id: str) -> Dict:
        """Delete a space."""
        return self._request("DELETE", f"/space/{space_id}")

    # =========================================================================
    # FOLDER METHODS
    # =========================================================================

    def get_folders(self, space_id: str, archived: bool = False) -> List[Dict]:
        """Get all folders in a space."""
        params = {"archived": str(archived).lower()}
        response = self._request("GET", f"/space/{space_id}/folder", params=params)
        return response.get("folders", [])

    def get_folder(self, folder_id: str) -> Dict:
        """Get a specific folder by ID."""
        return self._request("GET", f"/folder/{folder_id}")

    def create_folder(self, space_id: str, name: str) -> Dict:
        """Create a new folder in a space."""
        return self._request("POST", f"/space/{space_id}/folder", data={"name": name})

    def update_folder(self, folder_id: str, name: str) -> Dict:
        """Rename a folder."""
        return self._request("PUT", f"/folder/{folder_id}", data={"name": name})

    def delete_folder(self, folder_id: str) -> Dict:
        """Delete a folder."""
        return self._request("DELETE", f"/folder/{folder_id}")

    # =========================================================================
    # LIST METHODS
    # =========================================================================

    def get_lists(self, folder_id: str, archived: bool = False) -> List[Dict]:
        """Get all lists in a folder."""
        params = {"archived": str(archived).lower()}
        response = self._request("GET", f"/folder/{folder_id}/list", params=params)
        return response.get("lists", [])

    def get_folderless_lists(self, space_id: str, archived: bool = False) -> List[Dict]:
        """Get lists not in any folder."""
        params = {"archived": str(archived).lower()}
        response = self._request("GET", f"/space/{space_id}/list", params=params)
        return response.get("lists", [])

    def get_list(self, list_id: str) -> Dict:
        """Get a specific list by ID."""
        return self._request("GET", f"/list/{list_id}")

    def create_list(
        self,
        folder_id: str,
        name: str,
        content: str = "",
        due_date: Optional[int] = None,
        priority: Optional[int] = None,
        assignee: Optional[int] = None,
        status: Optional[str] = None
    ) -> Dict:
        """
        Create a new list in a folder.

        Args:
            folder_id: Parent folder ID
            name: List name
            content: List description
            due_date: Unix timestamp in milliseconds
            priority: 1 (urgent) to 4 (low)
            assignee: User ID to assign
            status: Status name
        """
        data = {"name": name}
        if content:
            data["content"] = content
        if due_date:
            data["due_date"] = due_date
        if priority:
            data["priority"] = priority
        if assignee:
            data["assignee"] = assignee
        if status:
            data["status"] = status

        return self._request("POST", f"/folder/{folder_id}/list", data=data)

    def create_folderless_list(self, space_id: str, name: str, **kwargs) -> Dict:
        """Create a list directly in a space (no folder)."""
        data = {"name": name, **kwargs}
        return self._request("POST", f"/space/{space_id}/list", data=data)

    def update_list(self, list_id: str, **kwargs) -> Dict:
        """Update list properties."""
        return self._request("PUT", f"/list/{list_id}", data=kwargs)

    def delete_list(self, list_id: str) -> Dict:
        """Delete a list."""
        return self._request("DELETE", f"/list/{list_id}")

    # =========================================================================
    # TASK METHODS
    # =========================================================================

    def get_tasks(
        self,
        list_id: str,
        archived: bool = False,
        page: int = 0,
        include_closed: bool = False,
        subtasks: bool = False,
        statuses: Optional[List[str]] = None,
        assignees: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Get tasks from a list.

        Args:
            list_id: List ID to fetch tasks from
            archived: Include archived tasks
            page: Page number (100 tasks per page)
            include_closed: Include closed tasks
            subtasks: Include subtasks
            statuses: Filter by status names
            assignees: Filter by assignee IDs
        """
        params = {
            "archived": str(archived).lower(),
            "page": page,
            "include_closed": str(include_closed).lower(),
            "subtasks": str(subtasks).lower()
        }
        if statuses:
            params["statuses[]"] = statuses
        if assignees:
            params["assignees[]"] = assignees

        response = self._request("GET", f"/list/{list_id}/task", params=params)
        return response.get("tasks", [])

    def get_task(self, task_id: str, include_subtasks: bool = False) -> Dict:
        """Get a specific task by ID."""
        params = {"include_subtasks": str(include_subtasks).lower()}
        return self._request("GET", f"/task/{task_id}", params=params)

    def create_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        assignees: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[int] = None,
        start_date: Optional[int] = None,
        notify_all: bool = True,
        custom_fields: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Create a new task.

        Args:
            list_id: List to create task in
            name: Task name
            description: Task description (supports markdown)
            assignees: List of user IDs
            tags: List of tag names
            status: Status name
            priority: 1 (urgent), 2 (high), 3 (normal), 4 (low)
            due_date: Unix timestamp in milliseconds
            start_date: Unix timestamp in milliseconds
            notify_all: Notify all assignees
            custom_fields: List of {"id": field_id, "value": value}
        """
        data = {
            "name": name,
            "notify_all": notify_all
        }

        if description:
            data["description"] = description
        if assignees:
            data["assignees"] = assignees
        if tags:
            data["tags"] = tags
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        if due_date:
            data["due_date"] = due_date
        if start_date:
            data["start_date"] = start_date
        if custom_fields:
            data["custom_fields"] = custom_fields

        return self._request("POST", f"/list/{list_id}/task", data=data)

    def update_task(self, task_id: str, **kwargs) -> Dict:
        """
        Update a task.

        Common kwargs:
            name, description, status, priority, due_date, start_date,
            assignees (list to add), archived
        """
        return self._request("PUT", f"/task/{task_id}", data=kwargs)

    def delete_task(self, task_id: str) -> Dict:
        """Delete a task."""
        return self._request("DELETE", f"/task/{task_id}")

    def create_subtask(
        self,
        parent_task_id: str,
        name: str,
        description: str = "",
        priority: Optional[int] = None,
        assignees: Optional[List[int]] = None,
        status: Optional[str] = None
    ) -> Dict:
        """
        Create a subtask under a parent task.

        Args:
            parent_task_id: Parent task ID
            name: Subtask name
            description: Subtask description
            priority: 1 (urgent), 2 (high), 3 (normal), 4 (low)
            assignees: List of user IDs
            status: Status name

        Returns:
            Created subtask response
        """
        data = {
            "name": name,
            "parent": parent_task_id
        }

        if description:
            data["description"] = description
        if priority:
            data["priority"] = priority
        if assignees:
            data["assignees"] = assignees
        if status:
            data["status"] = status

        # Get list_id from parent task first
        parent = self.get_task(parent_task_id)
        list_id = parent.get("list", {}).get("id")

        if not list_id:
            raise ValueError(f"Could not get list_id from parent task {parent_task_id}")

        return self._request("POST", f"/list/{list_id}/task", data=data)

    # =========================================================================
    # TASK COMMENT METHODS
    # =========================================================================

    def get_task_comments(self, task_id: str) -> List[Dict]:
        """Get all comments on a task."""
        response = self._request("GET", f"/task/{task_id}/comment")
        return response.get("comments", [])

    def add_task_comment(
        self,
        task_id: str,
        comment_text: str,
        assignee: Optional[int] = None,
        notify_all: bool = True
    ) -> Dict:
        """
        Add a comment to a task.

        Args:
            task_id: Task to comment on
            comment_text: Comment content (supports markdown)
            assignee: User ID to assign in comment
            notify_all: Notify all assignees
        """
        data = {
            "comment_text": comment_text,
            "notify_all": notify_all
        }
        if assignee:
            data["assignee"] = assignee

        return self._request("POST", f"/task/{task_id}/comment", data=data)

    # =========================================================================
    # CUSTOM FIELD METHODS
    # =========================================================================

    def get_list_custom_fields(self, list_id: str) -> List[Dict]:
        """Get custom fields available for a list."""
        response = self._request("GET", f"/list/{list_id}/field")
        return response.get("fields", [])

    def set_custom_field_value(
        self,
        task_id: str,
        field_id: str,
        value: Any
    ) -> Dict:
        """
        Set a custom field value on a task.

        Args:
            task_id: Task ID
            field_id: Custom field ID
            value: Field value (type depends on field type)
        """
        return self._request(
            "POST",
            f"/task/{task_id}/field/{field_id}",
            data={"value": value}
        )

    # =========================================================================
    # MEMBER METHODS
    # =========================================================================

    def get_list_members(self, list_id: str) -> List[Dict]:
        """Get members who have access to a list."""
        response = self._request("GET", f"/list/{list_id}/member")
        return response.get("members", [])

    def get_task_members(self, task_id: str) -> List[Dict]:
        """Get members assigned to a task."""
        response = self._request("GET", f"/task/{task_id}/member")
        return response.get("members", [])

    # =========================================================================
    # TAG METHODS
    # =========================================================================

    def get_space_tags(self, space_id: str) -> List[Dict]:
        """Get all tags in a space."""
        response = self._request("GET", f"/space/{space_id}/tag")
        return response.get("tags", [])

    def create_space_tag(
        self,
        space_id: str,
        name: str,
        tag_bg: str = "#7C4DFF",
        tag_fg: str = "#FFFFFF"
    ) -> Dict:
        """
        Create a new tag in a space.

        Args:
            space_id: Space ID
            name: Tag name
            tag_bg: Background color (hex)
            tag_fg: Foreground color (hex)
        """
        data = {
            "tag": {
                "name": name,
                "tag_bg": tag_bg,
                "tag_fg": tag_fg
            }
        }
        return self._request("POST", f"/space/{space_id}/tag", data=data)

    def add_tag_to_task(self, task_id: str, tag_name: str) -> Dict:
        """Add an existing tag to a task."""
        return self._request("POST", f"/task/{task_id}/tag/{tag_name}")

    def remove_tag_from_task(self, task_id: str, tag_name: str) -> Dict:
        """Remove a tag from a task."""
        return self._request("DELETE", f"/task/{task_id}/tag/{tag_name}")

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def bulk_create_tasks(
        self,
        list_id: str,
        tasks: List[Dict],
        progress_callback=None
    ) -> List[Dict]:
        """
        Create multiple tasks with progress tracking.

        Args:
            list_id: List to create tasks in
            tasks: List of task dicts (each with 'name' and optional fields)
            progress_callback: Optional function(completed, total) for updates

        Returns:
            List of created task responses
        """
        results = []
        total = len(tasks)

        for i, task_data in enumerate(tasks):
            try:
                name = task_data.pop("name")
                result = self.create_task(list_id, name, **task_data)
                results.append({"success": True, "task": result})
            except Exception as e:
                results.append({"success": False, "error": str(e), "task_data": task_data})

            if progress_callback and (i + 1) % max(1, total // 10) == 0:
                progress_callback(i + 1, total)

        return results

    def bulk_update_tasks(
        self,
        updates: List[Dict],
        progress_callback=None
    ) -> List[Dict]:
        """
        Update multiple tasks.

        Args:
            updates: List of {"task_id": id, **update_fields}
            progress_callback: Optional function(completed, total) for updates

        Returns:
            List of update results
        """
        results = []
        total = len(updates)

        for i, update in enumerate(updates):
            try:
                task_id = update.pop("task_id")
                result = self.update_task(task_id, **update)
                results.append({"success": True, "task": result})
            except Exception as e:
                results.append({"success": False, "error": str(e), "update": update})

            if progress_callback and (i + 1) % max(1, total // 10) == 0:
                progress_callback(i + 1, total)

        return results


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ClickUp API Client Test")
    parser.add_argument("--test", action="store_true", help="Run connection test")
    parser.add_argument("--list-teams", action="store_true", help="List all workspaces")
    parser.add_argument("--list-spaces", type=str, help="List spaces in workspace (team_id)")

    args = parser.parse_args()

    if args.test or args.list_teams or args.list_spaces:
        client = ClickUpClient()

        if args.test or args.list_teams:
            print("\n📋 Fetching workspaces...")
            teams = client.get_teams()
            for team in teams:
                print(f"  • {team['name']} (ID: {team['id']})")
            print(f"\n✓ Connection successful! Found {len(teams)} workspace(s)")

        if args.list_spaces:
            print(f"\n📁 Fetching spaces for workspace {args.list_spaces}...")
            spaces = client.get_spaces(args.list_spaces)
            for space in spaces:
                print(f"  • {space['name']} (ID: {space['id']})")
            print(f"\n✓ Found {len(spaces)} space(s)")
    else:
        parser.print_help()
