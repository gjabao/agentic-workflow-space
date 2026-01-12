#!/usr/bin/env python3
"""
ClickUp Data Sync - Import CSV/Sheets data into ClickUp tasks.

Provides CLI and programmatic interface for:
- Importing CSV files as tasks
- Syncing Google Sheets to ClickUp
- Mapping CSV columns to task fields
- Bulk updating existing tasks from data sources

Usage:
    # Import CSV as tasks
    python3 clickup_sync.py import-csv --list-id 123 --file leads.csv --name-col "Company"

    # Import with field mapping
    python3 clickup_sync.py import-csv --list-id 123 --file leads.csv \\
        --name-col "Company" --description-col "Notes" --status-col "Stage"

    # Dry run (preview without creating)
    python3 clickup_sync.py import-csv --list-id 123 --file leads.csv --dry-run

    # Export tasks to CSV
    python3 clickup_sync.py export --list-id 123 --output tasks.csv
"""

import os
import sys
import csv
import json
import argparse
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.clickup_client import ClickUpClient
from execution.clickup_tasks import ClickUpTaskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClickUpDataSync:
    """
    Data synchronization between external sources and ClickUp.

    Supports:
    - CSV import with column mapping
    - Google Sheets import (requires gspread)
    - Task export to CSV
    - Bulk updates from data sources
    """

    def __init__(self):
        """Initialize with ClickUp client."""
        self.client = ClickUpClient()
        self.task_manager = ClickUpTaskManager()
        logger.info("✓ Data sync initialized")

    # =========================================================================
    # CSV IMPORT
    # =========================================================================

    def read_csv(self, file_path: str) -> List[Dict]:
        """
        Read CSV file into list of dictionaries.

        Args:
            file_path: Path to CSV file

        Returns:
            List of row dictionaries
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        rows = []
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        logger.info(f"✓ Read {len(rows)} rows from {file_path}")
        return rows

    def import_csv(
        self,
        list_id: str,
        file_path: str,
        name_column: str,
        description_column: Optional[str] = None,
        status_column: Optional[str] = None,
        priority_column: Optional[str] = None,
        due_date_column: Optional[str] = None,
        tags_column: Optional[str] = None,
        custom_field_mapping: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
        skip_duplicates: bool = True,
        show_progress: bool = True
    ) -> Dict:
        """
        Import CSV rows as ClickUp tasks.

        Args:
            list_id: Target list ID
            file_path: Path to CSV file
            name_column: Column name for task name (required)
            description_column: Column name for task description
            status_column: Column name for status
            priority_column: Column name for priority
            due_date_column: Column name for due date (YYYY-MM-DD format)
            tags_column: Column name for tags (comma-separated)
            custom_field_mapping: Dict of {clickup_field_name: csv_column_name}
            dry_run: Preview without creating tasks
            skip_duplicates: Skip rows where name already exists as task
            show_progress: Print progress updates

        Returns:
            Summary with counts and results
        """
        rows = self.read_csv(file_path)

        if not rows:
            return {"total": 0, "created": 0, "skipped": 0, "failed": 0}

        # Validate name column exists
        if name_column not in rows[0]:
            raise ValueError(f"Column '{name_column}' not found. Available: {list(rows[0].keys())}")

        # Get existing task names for duplicate detection
        existing_names = set()
        if skip_duplicates:
            existing_tasks = self.client.get_tasks(list_id, include_closed=True)
            existing_names = {t["name"].lower() for t in existing_tasks}
            logger.info(f"Found {len(existing_names)} existing tasks")

        # Get custom field IDs
        field_id_map = {}
        if custom_field_mapping:
            fields = self.client.get_list_custom_fields(list_id)
            for field in fields:
                if field["name"] in custom_field_mapping:
                    field_id_map[custom_field_mapping[field["name"]]] = field["id"]

        results = {
            "total": len(rows),
            "created": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }

        for i, row in enumerate(rows):
            name = row.get(name_column, "").strip()

            if not name:
                results["skipped"] += 1
                results["details"].append({"row": i + 1, "status": "skipped", "reason": "empty name"})
                continue

            if skip_duplicates and name.lower() in existing_names:
                results["skipped"] += 1
                results["details"].append({"row": i + 1, "name": name, "status": "skipped", "reason": "duplicate"})
                continue

            # Build task data
            task_data = {"name": name}

            if description_column and row.get(description_column):
                task_data["description"] = row[description_column]

            if status_column and row.get(status_column):
                task_data["status"] = row[status_column]

            if priority_column and row.get(priority_column):
                priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
                priority_str = row[priority_column].lower()
                if priority_str in priority_map:
                    task_data["priority"] = priority_map[priority_str]

            if due_date_column and row.get(due_date_column):
                try:
                    dt = datetime.strptime(row[due_date_column], "%Y-%m-%d")
                    task_data["due_date"] = int(dt.timestamp() * 1000)
                except ValueError:
                    logger.warning(f"Row {i + 1}: Invalid date format: {row[due_date_column]}")

            if tags_column and row.get(tags_column):
                tags = [t.strip() for t in row[tags_column].split(",") if t.strip()]
                if tags:
                    task_data["tags"] = tags

            # Handle custom fields
            if custom_field_mapping:
                custom_fields = []
                for csv_col, field_id in field_id_map.items():
                    if row.get(csv_col):
                        custom_fields.append({"id": field_id, "value": row[csv_col]})
                if custom_fields:
                    task_data["custom_fields"] = custom_fields

            if dry_run:
                results["created"] += 1
                results["details"].append({"row": i + 1, "name": name, "status": "would_create", "data": task_data})
            else:
                try:
                    result = self.client.create_task(list_id, **task_data)
                    results["created"] += 1
                    results["details"].append({"row": i + 1, "name": name, "status": "created", "task_id": result.get("id")})
                    existing_names.add(name.lower())
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({"row": i + 1, "name": name, "status": "failed", "error": str(e)})

            # Progress update
            if show_progress and (i + 1) % max(1, len(rows) // 10) == 0:
                pct = ((i + 1) / len(rows)) * 100
                print(f"⏳ Progress: {i + 1}/{len(rows)} ({pct:.0f}%)")

        mode = "DRY RUN" if dry_run else "COMPLETE"
        logger.info(f"✓ Import {mode}: {results['created']} created, {results['skipped']} skipped, {results['failed']} failed")
        return results

    # =========================================================================
    # GOOGLE SHEETS IMPORT
    # =========================================================================

    def import_from_sheets(
        self,
        list_id: str,
        spreadsheet_id: str,
        sheet_name: str,
        name_column: str,
        description_column: Optional[str] = None,
        status_column: Optional[str] = None,
        priority_column: Optional[str] = None,
        due_date_column: Optional[str] = None,
        dry_run: bool = False,
        skip_duplicates: bool = True
    ) -> Dict:
        """
        Import data from Google Sheets as ClickUp tasks.

        Requires: gspread, google-auth

        Args:
            list_id: Target list ID
            spreadsheet_id: Google Sheets ID
            sheet_name: Name of the sheet/tab
            name_column: Column name for task name
            (other args same as import_csv)

        Returns:
            Import summary
        """
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError("Install gspread: pip install gspread google-auth")

        # Load credentials
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Google credentials not found: {creds_path}")

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)

        # Fetch data
        logger.info(f"Fetching data from sheet: {sheet_name}")
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        rows = worksheet.get_all_records()

        logger.info(f"✓ Fetched {len(rows)} rows from Google Sheets")

        # Save to temp CSV and use existing import logic
        temp_path = f".tmp/sheets_import_{spreadsheet_id}.csv"
        os.makedirs(".tmp", exist_ok=True)

        if rows:
            with open(temp_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = self.import_csv(
                list_id=list_id,
                file_path=temp_path,
                name_column=name_column,
                description_column=description_column,
                status_column=status_column,
                priority_column=priority_column,
                due_date_column=due_date_column,
                dry_run=dry_run,
                skip_duplicates=skip_duplicates
            )

            # Cleanup temp file
            os.remove(temp_path)
            return result

        return {"total": 0, "created": 0, "skipped": 0, "failed": 0}

    # =========================================================================
    # EXPORT TO CSV
    # =========================================================================

    def export_to_csv(
        self,
        list_id: str,
        output_path: str,
        include_closed: bool = False,
        columns: Optional[List[str]] = None
    ) -> Dict:
        """
        Export tasks from a list to CSV.

        Args:
            list_id: List ID to export from
            output_path: Output CSV file path
            include_closed: Include closed tasks
            columns: Columns to include (default: common fields)

        Returns:
            Export summary
        """
        # Fetch all tasks
        all_tasks = []
        page = 0

        while True:
            tasks = self.client.get_tasks(
                list_id,
                include_closed=include_closed,
                page=page
            )
            if not tasks:
                break
            all_tasks.extend(tasks)
            page += 1

        logger.info(f"Fetched {len(all_tasks)} tasks")

        if not all_tasks:
            return {"exported": 0, "path": output_path}

        # Default columns
        if not columns:
            columns = [
                "id", "name", "description", "status", "priority",
                "due_date", "tags", "assignees", "url"
            ]

        # Prepare rows
        rows = []
        for task in all_tasks:
            row = {}
            for col in columns:
                if col == "status":
                    row[col] = task.get("status", {}).get("status", "")
                elif col == "priority":
                    priority = task.get("priority")
                    row[col] = priority.get("priority", "") if priority else ""
                elif col == "due_date":
                    due = task.get("due_date")
                    if due:
                        row[col] = datetime.fromtimestamp(int(due) / 1000).strftime("%Y-%m-%d")
                    else:
                        row[col] = ""
                elif col == "tags":
                    tags = task.get("tags", [])
                    row[col] = ", ".join([t.get("name", "") for t in tags])
                elif col == "assignees":
                    assignees = task.get("assignees", [])
                    row[col] = ", ".join([a.get("username", a.get("email", "")) for a in assignees])
                else:
                    row[col] = task.get(col, "")

            rows.append(row)

        # Write CSV
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(f"✓ Exported {len(rows)} tasks to {output_path}")
        return {"exported": len(rows), "path": output_path}

    # =========================================================================
    # BULK UPDATE FROM CSV
    # =========================================================================

    def update_from_csv(
        self,
        file_path: str,
        task_id_column: str,
        status_column: Optional[str] = None,
        priority_column: Optional[str] = None,
        due_date_column: Optional[str] = None,
        dry_run: bool = False,
        show_progress: bool = True
    ) -> Dict:
        """
        Update existing tasks from CSV data.

        Args:
            file_path: CSV file with task updates
            task_id_column: Column containing task IDs
            status_column: Column for new status
            priority_column: Column for new priority
            due_date_column: Column for new due date
            dry_run: Preview without updating
            show_progress: Print progress

        Returns:
            Update summary
        """
        rows = self.read_csv(file_path)

        if not rows:
            return {"total": 0, "updated": 0, "failed": 0}

        if task_id_column not in rows[0]:
            raise ValueError(f"Column '{task_id_column}' not found")

        results = {
            "total": len(rows),
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }

        for i, row in enumerate(rows):
            task_id = row.get(task_id_column, "").strip()

            if not task_id:
                results["skipped"] += 1
                continue

            update_data = {}

            if status_column and row.get(status_column):
                update_data["status"] = row[status_column]

            if priority_column and row.get(priority_column):
                priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
                priority_str = row[priority_column].lower()
                if priority_str in priority_map:
                    update_data["priority"] = priority_map[priority_str]

            if due_date_column and row.get(due_date_column):
                try:
                    dt = datetime.strptime(row[due_date_column], "%Y-%m-%d")
                    update_data["due_date"] = int(dt.timestamp() * 1000)
                except ValueError:
                    pass

            if not update_data:
                results["skipped"] += 1
                continue

            if dry_run:
                results["updated"] += 1
                results["details"].append({"task_id": task_id, "status": "would_update", "data": update_data})
            else:
                try:
                    self.client.update_task(task_id, **update_data)
                    results["updated"] += 1
                    results["details"].append({"task_id": task_id, "status": "updated"})
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({"task_id": task_id, "status": "failed", "error": str(e)})

            if show_progress and (i + 1) % max(1, len(rows) // 10) == 0:
                pct = ((i + 1) / len(rows)) * 100
                print(f"⏳ Progress: {i + 1}/{len(rows)} ({pct:.0f}%)")

        mode = "DRY RUN" if dry_run else "COMPLETE"
        logger.info(f"✓ Update {mode}: {results['updated']} updated, {results['skipped']} skipped, {results['failed']} failed")
        return results

    # =========================================================================
    # LEAD PIPELINE IMPORT
    # =========================================================================

    def import_leads_as_pipeline(
        self,
        list_id: str,
        file_path: str,
        company_column: str = "company",
        email_column: Optional[str] = "email",
        contact_column: Optional[str] = "contact_name",
        website_column: Optional[str] = "website",
        phone_column: Optional[str] = "phone",
        notes_column: Optional[str] = "notes",
        initial_status: str = "to do",
        dry_run: bool = False
    ) -> Dict:
        """
        Import leads CSV as pipeline tasks.

        Creates tasks with structured descriptions containing lead info.

        Args:
            list_id: Target pipeline list
            file_path: CSV with lead data
            company_column: Column for company name (task name)
            email_column: Column for email
            contact_column: Column for contact name
            website_column: Column for website
            phone_column: Column for phone
            notes_column: Column for notes
            initial_status: Starting status for leads
            dry_run: Preview without creating

        Returns:
            Import summary
        """
        rows = self.read_csv(file_path)

        if not rows:
            return {"total": 0, "created": 0, "skipped": 0, "failed": 0}

        results = {
            "total": len(rows),
            "created": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }

        for i, row in enumerate(rows):
            company = row.get(company_column, "").strip()

            if not company:
                results["skipped"] += 1
                continue

            # Build structured description
            desc_parts = ["## Lead Information\n"]

            if contact_column and row.get(contact_column):
                desc_parts.append(f"**Contact:** {row[contact_column]}")

            if email_column and row.get(email_column):
                desc_parts.append(f"**Email:** {row[email_column]}")

            if phone_column and row.get(phone_column):
                desc_parts.append(f"**Phone:** {row[phone_column]}")

            if website_column and row.get(website_column):
                desc_parts.append(f"**Website:** {row[website_column]}")

            if notes_column and row.get(notes_column):
                desc_parts.append(f"\n### Notes\n{row[notes_column]}")

            description = "\n".join(desc_parts)

            task_data = {
                "name": company,
                "description": description,
                "status": initial_status
            }

            if dry_run:
                results["created"] += 1
                results["details"].append({"row": i + 1, "company": company, "status": "would_create"})
            else:
                try:
                    result = self.client.create_task(list_id, **task_data)
                    results["created"] += 1
                    results["details"].append({
                        "row": i + 1,
                        "company": company,
                        "status": "created",
                        "task_id": result.get("id")
                    })
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "row": i + 1,
                        "company": company,
                        "status": "failed",
                        "error": str(e)
                    })

            if (i + 1) % max(1, len(rows) // 10) == 0:
                pct = ((i + 1) / len(rows)) * 100
                print(f"⏳ Progress: {i + 1}/{len(rows)} ({pct:.0f}%)")

        mode = "DRY RUN" if dry_run else "COMPLETE"
        logger.info(f"✓ Lead import {mode}: {results['created']} created, {results['skipped']} skipped, {results['failed']} failed")
        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ClickUp Data Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import CSV as tasks
  python3 clickup_sync.py import-csv --list-id 901234567 --file leads.csv --name-col "Company"

  # Import with status mapping
  python3 clickup_sync.py import-csv --list-id 901234567 --file leads.csv \\
      --name-col "Company" --status-col "Stage" --priority-col "Priority"

  # Dry run (preview)
  python3 clickup_sync.py import-csv --list-id 901234567 --file leads.csv --dry-run

  # Import leads as pipeline
  python3 clickup_sync.py import-leads --list-id 901234567 --file leads.csv \\
      --company-col "company" --email-col "email" --contact-col "name"

  # Export tasks to CSV
  python3 clickup_sync.py export --list-id 901234567 --output tasks.csv

  # Update tasks from CSV
  python3 clickup_sync.py update --file updates.csv --id-col "task_id" --status-col "new_status"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # IMPORT-CSV command
    import_parser = subparsers.add_parser("import-csv", help="Import CSV as tasks")
    import_parser.add_argument("--list-id", required=True, help="Target list ID")
    import_parser.add_argument("--file", required=True, help="CSV file path")
    import_parser.add_argument("--name-col", required=True, help="Column for task name")
    import_parser.add_argument("--description-col", help="Column for description")
    import_parser.add_argument("--status-col", help="Column for status")
    import_parser.add_argument("--priority-col", help="Column for priority")
    import_parser.add_argument("--due-date-col", help="Column for due date")
    import_parser.add_argument("--tags-col", help="Column for tags (comma-separated)")
    import_parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    import_parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate names")
    import_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # IMPORT-LEADS command
    leads_parser = subparsers.add_parser("import-leads", help="Import leads as pipeline")
    leads_parser.add_argument("--list-id", required=True, help="Target pipeline list ID")
    leads_parser.add_argument("--file", required=True, help="CSV file path")
    leads_parser.add_argument("--company-col", default="company", help="Column for company name")
    leads_parser.add_argument("--email-col", default="email", help="Column for email")
    leads_parser.add_argument("--contact-col", default="contact_name", help="Column for contact name")
    leads_parser.add_argument("--website-col", default="website", help="Column for website")
    leads_parser.add_argument("--phone-col", default="phone", help="Column for phone")
    leads_parser.add_argument("--notes-col", default="notes", help="Column for notes")
    leads_parser.add_argument("--status", default="to do", help="Initial status")
    leads_parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    leads_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # EXPORT command
    export_parser = subparsers.add_parser("export", help="Export tasks to CSV")
    export_parser.add_argument("--list-id", required=True, help="List ID to export")
    export_parser.add_argument("--output", required=True, help="Output CSV path")
    export_parser.add_argument("--include-closed", action="store_true", help="Include closed tasks")
    export_parser.add_argument("--json", action="store_true", help="Output summary as JSON")

    # UPDATE command
    update_parser = subparsers.add_parser("update", help="Update tasks from CSV")
    update_parser.add_argument("--file", required=True, help="CSV with updates")
    update_parser.add_argument("--id-col", required=True, help="Column with task IDs")
    update_parser.add_argument("--status-col", help="Column for new status")
    update_parser.add_argument("--priority-col", help="Column for new priority")
    update_parser.add_argument("--due-date-col", help="Column for new due date")
    update_parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    update_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    sync = ClickUpDataSync()

    try:
        if args.command == "import-csv":
            result = sync.import_csv(
                list_id=args.list_id,
                file_path=args.file,
                name_column=args.name_col,
                description_column=args.description_col,
                status_column=args.status_col,
                priority_column=args.priority_col,
                due_date_column=args.due_date_col,
                tags_column=args.tags_col,
                dry_run=args.dry_run,
                skip_duplicates=not args.allow_duplicates
            )

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                mode = "DRY RUN" if args.dry_run else "IMPORT"
                print(f"\n✓ {mode} Complete!")
                print(f"  Total: {result['total']}")
                print(f"  Created: {result['created']}")
                print(f"  Skipped: {result['skipped']}")
                print(f"  Failed: {result['failed']}")

        elif args.command == "import-leads":
            result = sync.import_leads_as_pipeline(
                list_id=args.list_id,
                file_path=args.file,
                company_column=args.company_col,
                email_column=args.email_col,
                contact_column=args.contact_col,
                website_column=args.website_col,
                phone_column=args.phone_col,
                notes_column=args.notes_col,
                initial_status=args.status,
                dry_run=args.dry_run
            )

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                mode = "DRY RUN" if args.dry_run else "IMPORT"
                print(f"\n✓ Lead {mode} Complete!")
                print(f"  Total: {result['total']}")
                print(f"  Created: {result['created']}")
                print(f"  Skipped: {result['skipped']}")
                print(f"  Failed: {result['failed']}")

        elif args.command == "export":
            result = sync.export_to_csv(
                list_id=args.list_id,
                output_path=args.output,
                include_closed=args.include_closed
            )

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✓ Exported {result['exported']} tasks to {result['path']}")

        elif args.command == "update":
            result = sync.update_from_csv(
                file_path=args.file,
                task_id_column=args.id_col,
                status_column=args.status_col,
                priority_column=args.priority_col,
                due_date_column=args.due_date_col,
                dry_run=args.dry_run
            )

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                mode = "DRY RUN" if args.dry_run else "UPDATE"
                print(f"\n✓ {mode} Complete!")
                print(f"  Total: {result['total']}")
                print(f"  Updated: {result['updated']}")
                print(f"  Skipped: {result['skipped']}")
                print(f"  Failed: {result['failed']}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
