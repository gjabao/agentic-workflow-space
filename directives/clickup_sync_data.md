# ClickUp Data Sync Directive

## Objective
Sync data between external sources (CSV, Google Sheets) and ClickUp. Import records as tasks, export tasks for reporting, and bulk update from data sources.

---

## Required Inputs

### For CSV Import
| Input | Required | Description |
|-------|----------|-------------|
| `list_id` | Yes | Target ClickUp list |
| `file_path` | Yes | CSV file path |
| `name_column` | Yes | Column for task name |
| `description_column` | No | Column for description |
| `status_column` | No | Column for status |
| `priority_column` | No | Column for priority |
| `due_date_column` | No | Column for due date |
| `tags_column` | No | Column for tags |

### For Export
| Input | Required | Description |
|-------|----------|-------------|
| `list_id` | Yes | List to export |
| `output_path` | Yes | Output CSV path |

### For Update
| Input | Required | Description |
|-------|----------|-------------|
| `file_path` | Yes | CSV with updates |
| `task_id_column` | Yes | Column with task IDs |
| `update_columns` | No | Columns to update |

---

## Execution Tools

- `execution/clickup_sync.py` - Data synchronization
- `execution/clickup_tasks.py` - Task operations
- `execution/clickup_lists.py` - List discovery

---

## Operations

### 1. Import CSV as Tasks

```bash
# Basic import (name only)
python3 execution/clickup_sync.py import-csv \
    --list-id 901234567 \
    --file data.csv \
    --name-col "Title"

# Full mapping
python3 execution/clickup_sync.py import-csv \
    --list-id 901234567 \
    --file data.csv \
    --name-col "Title" \
    --description-col "Details" \
    --status-col "Stage" \
    --priority-col "Priority" \
    --due-date-col "Deadline" \
    --tags-col "Labels"

# Dry run (preview)
python3 execution/clickup_sync.py import-csv \
    --list-id 901234567 \
    --file data.csv \
    --name-col "Title" \
    --dry-run

# Allow duplicate names
python3 execution/clickup_sync.py import-csv \
    --list-id 901234567 \
    --file data.csv \
    --name-col "Title" \
    --allow-duplicates
```

### 2. Export Tasks to CSV

```bash
# Basic export
python3 execution/clickup_sync.py export \
    --list-id 901234567 \
    --output tasks.csv

# Include closed tasks
python3 execution/clickup_sync.py export \
    --list-id 901234567 \
    --output tasks.csv \
    --include-closed
```

### 3. Update Tasks from CSV

```bash
# Update status
python3 execution/clickup_sync.py update \
    --file updates.csv \
    --id-col "task_id" \
    --status-col "new_status"

# Update multiple fields
python3 execution/clickup_sync.py update \
    --file updates.csv \
    --id-col "task_id" \
    --status-col "status" \
    --priority-col "priority" \
    --due-date-col "due_date"

# Dry run
python3 execution/clickup_sync.py update \
    --file updates.csv \
    --id-col "task_id" \
    --status-col "new_status" \
    --dry-run
```

---

## Programmatic Usage

```python
from execution.clickup_sync import ClickUpDataSync

sync = ClickUpDataSync()

# Import CSV
result = sync.import_csv(
    list_id="901234567",
    file_path="projects.csv",
    name_column="Project Name",
    description_column="Description",
    status_column="Status",
    priority_column="Priority",
    due_date_column="Deadline",
    skip_duplicates=True,
    dry_run=False
)
print(f"Created: {result['created']}, Skipped: {result['skipped']}")

# Export to CSV
result = sync.export_to_csv(
    list_id="901234567",
    output_path=".tmp/export.csv",
    include_closed=True
)
print(f"Exported {result['exported']} tasks")

# Bulk update
result = sync.update_from_csv(
    file_path="updates.csv",
    task_id_column="clickup_id",
    status_column="new_status",
    priority_column="new_priority"
)
print(f"Updated: {result['updated']}, Failed: {result['failed']}")

# Import from Google Sheets
result = sync.import_from_sheets(
    list_id="901234567",
    spreadsheet_id="1abc...xyz",
    sheet_name="Tasks",
    name_column="Task Name",
    status_column="Status"
)
```

---

## CSV Format Examples

### Import CSV
```csv
Title,Details,Stage,Priority,Deadline,Labels
Review docs,Check all specifications,to do,high,2024-01-15,"docs,review"
Send report,Monthly analytics report,in progress,normal,2024-01-20,"reports,monthly"
Fix bug #123,Login timeout issue,to do,urgent,2024-01-12,"bugs,critical"
```

### Update CSV
```csv
task_id,new_status,new_priority
86abc123xyz,complete,
86def456abc,in progress,high
86ghi789def,review,normal
```

### Export Output
```csv
id,name,description,status,priority,due_date,tags,assignees,url
86abc123xyz,Review docs,Check all specs,complete,high,2024-01-15,"docs,review",john@company.com,https://app.clickup.com/t/abc123
```

---

## Column Mapping Guide

### Status Values
Map your CSV values to ClickUp statuses:

| CSV Value | ClickUp Status |
|-----------|----------------|
| new / pending | to do |
| active / working | in progress |
| waiting / blocked | review |
| approved | approved |
| done / finished | complete |
| cancelled | closed |

### Priority Values
| CSV Value | ClickUp Priority |
|-----------|------------------|
| critical / p0 | urgent |
| high / p1 | high |
| medium / normal / p2 | normal |
| low / p3 | low |

### Date Format
Use ISO format: `YYYY-MM-DD`
- Valid: `2024-01-15`
- Invalid: `01/15/2024`, `Jan 15, 2024`

### Tags Format
Comma-separated: `tag1, tag2, tag3`

---

## Custom Field Mapping

For custom fields, pass a mapping dictionary:

```python
from execution.clickup_sync import ClickUpDataSync

sync = ClickUpDataSync()

# Map CSV columns to ClickUp custom fields
custom_mapping = {
    "Deal Value": "deal_value_csv_column",  # ClickUp field name : CSV column
    "Industry": "industry_column",
    "Source": "lead_source"
}

result = sync.import_csv(
    list_id="901234567",
    file_path="deals.csv",
    name_column="Company",
    custom_field_mapping=custom_mapping
)
```

---

## Expected Output

### Successful Import
```
2024-12-28 10:30:15 - INFO - ✓ Read 100 rows from data.csv
2024-12-28 10:30:16 - INFO - Found 5 existing tasks
⏳ Progress: 10/100 (10%)
⏳ Progress: 50/100 (50%)
⏳ Progress: 100/100 (100%)
2024-12-28 10:32:45 - INFO - ✓ Import COMPLETE: 95 created, 5 skipped, 0 failed

✓ IMPORT Complete!
  Total: 100
  Created: 95
  Skipped: 5
  Failed: 0
```

### Dry Run Output
```
✓ DRY RUN Complete!
  Total: 100
  Would create: 95
  Would skip: 5
  Would fail: 0
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Column 'X' not found` | Typo in column name | Check CSV headers |
| `File not found` | Wrong path | Verify file exists |
| `Invalid date format` | Date not YYYY-MM-DD | Reformat dates |
| `Status not found` | Status doesn't exist | Check list statuses |
| `API Error 429` | Rate limited | Auto-handled with backoff |

---

## Quality Checklist

- [ ] Verify CSV encoding (UTF-8)
- [ ] Check for empty rows
- [ ] Validate required columns exist
- [ ] Test with dry-run first
- [ ] Confirm status values match ClickUp
- [ ] Use consistent date format
- [ ] Handle special characters in names

---

## Workflow Integration

### After Lead Generation
```bash
# 1. Generate leads
python3 execution/scrape_apify_leads.py --query "marketing agencies" --limit 100

# 2. Sync to ClickUp
python3 execution/clickup_sync.py import-csv \
    --list-id 901234567 \
    --file .tmp/leads_marketing_agencies_20241228.csv \
    --name-col "company" \
    --description-col "description"
```

### Weekly Export for Reports
```bash
# Export all tasks
python3 execution/clickup_sync.py export \
    --list-id 901234567 \
    --output .tmp/weekly_report_$(date +%Y%m%d).csv \
    --include-closed
```

### Batch Status Updates
```bash
# Prepare update file
echo "task_id,new_status" > updates.csv
echo "abc123,complete" >> updates.csv
echo "def456,complete" >> updates.csv

# Apply updates
python3 execution/clickup_sync.py update \
    --file updates.csv \
    --id-col "task_id" \
    --status-col "new_status"
```

---

## Performance Notes

### Rate Limits
- ClickUp: 100 requests/minute
- Import 100 tasks: ~2 minutes
- Export 500 tasks: ~30 seconds

### Optimization Tips
1. Use `--dry-run` first to catch errors
2. Enable `--skip-duplicates` (default) to avoid redundant work
3. Batch updates using CSV instead of individual calls
4. Export includes pagination automatically

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-28 | Initial directive |
