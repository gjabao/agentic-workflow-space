# ClickUp Lead Pipeline Directive

## Objective
Manage sales leads in ClickUp as a visual pipeline. Import leads, move through stages, track status, and maintain lead information.

---

## Pipeline Concept

Each lead = 1 task in ClickUp. Lead stages map to task statuses:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   New Lead  │ → │  Contacted  │ → │  Qualified  │ → │  Proposal   │ → │    Won      │
│   (to do)   │    │(in progress)│    │  (review)   │    │ (approved)  │    │ (complete)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                              ↓
                                                                        ┌─────────────┐
                                                                        │    Lost     │
                                                                        │  (closed)   │
                                                                        └─────────────┘
```

---

## Required Inputs

### For Lead Import
| Input | Required | Description |
|-------|----------|-------------|
| `list_id` | Yes | ClickUp list for leads |
| `csv_file` | Yes | CSV with lead data |
| `company_col` | Yes | Column for company name |
| `email_col` | No | Column for email |
| `contact_col` | No | Column for contact name |
| `website_col` | No | Column for website |
| `phone_col` | No | Column for phone |

### For Pipeline Movement
| Input | Required | Description |
|-------|----------|-------------|
| `task_id` | Yes | Lead task ID |
| `new_status` | Yes | Target pipeline stage |

---

## Execution Tools

- `execution/clickup_sync.py` - Lead import
- `execution/clickup_tasks.py` - Pipeline operations
- `execution/clickup_lists.py` - Setup and discovery

---

## Operations

### 1. Setup Pipeline List (One-Time)

First, create a list with appropriate statuses:

```bash
# Find your workspace
python3 execution/clickup_lists.py workspaces

# Create list in a folder (or use existing)
python3 execution/clickup_lists.py create-list \
    --folder-id 90123456 \
    --name "Sales Pipeline"
```

Then configure statuses in ClickUp UI:
- `to do` → New Lead
- `in progress` → Contacted
- `review` → Qualified
- `approved` → Proposal Sent
- `complete` → Won
- `closed` → Lost

### 2. Import Leads from CSV

```bash
# Basic import
python3 execution/clickup_sync.py import-leads \
    --list-id 901234567 \
    --file leads.csv \
    --company-col "company" \
    --email-col "email" \
    --contact-col "contact_name"

# Full import with all fields
python3 execution/clickup_sync.py import-leads \
    --list-id 901234567 \
    --file leads.csv \
    --company-col "company" \
    --email-col "email" \
    --contact-col "contact_name" \
    --website-col "website" \
    --phone-col "phone" \
    --notes-col "notes" \
    --status "to do"

# Dry run (preview)
python3 execution/clickup_sync.py import-leads \
    --list-id 901234567 \
    --file leads.csv \
    --dry-run
```

### 3. Move Lead Through Pipeline

```bash
# Move to Contacted
python3 execution/clickup_tasks.py update \
    --task-id abc123xyz \
    --status "in progress"

# Move to Qualified
python3 execution/clickup_tasks.py update \
    --task-id abc123xyz \
    --status "review"

# Move to Proposal
python3 execution/clickup_tasks.py update \
    --task-id abc123xyz \
    --status "approved"

# Mark as Won
python3 execution/clickup_tasks.py update \
    --task-id abc123xyz \
    --status "complete"

# Mark as Lost
python3 execution/clickup_tasks.py update \
    --task-id abc123xyz \
    --status "closed"
```

### 4. Add Activity Note

```bash
python3 execution/clickup_tasks.py comment \
    --task-id abc123xyz \
    --text "Called - interested in Pro plan. Follow up next week."
```

### 5. View Pipeline Status

```bash
# All leads
python3 execution/clickup_tasks.py list --list-id 901234567 -v

# New leads only
python3 execution/clickup_tasks.py list --list-id 901234567 --status "to do"

# Leads in negotiation
python3 execution/clickup_tasks.py list --list-id 901234567 --status "approved"

# Include won/lost
python3 execution/clickup_tasks.py list --list-id 901234567 --include-closed
```

### 6. Bulk Status Update

```bash
# Update multiple leads at once
python3 execution/clickup_sync.py update \
    --file status_updates.csv \
    --id-col "task_id" \
    --status-col "new_status"
```

Where `status_updates.csv`:
```csv
task_id,new_status
abc123xyz,in progress
def456abc,complete
ghi789def,closed
```

---

## Programmatic Usage

```python
from execution.clickup_sync import ClickUpDataSync
from execution.clickup_tasks import ClickUpTaskManager

sync = ClickUpDataSync()
tasks = ClickUpTaskManager()

# Import leads
result = sync.import_leads_as_pipeline(
    list_id="901234567",
    file_path="leads.csv",
    company_column="company",
    email_column="email",
    contact_column="contact_name",
    initial_status="to do"
)
print(f"Imported {result['created']} leads")

# Move lead through pipeline
tasks.move_task_status("abc123xyz", "in progress")  # Contacted
tasks.add_comment("abc123xyz", "Left voicemail")

tasks.move_task_status("abc123xyz", "review")  # Qualified
tasks.add_comment("abc123xyz", "Demo scheduled for Thursday")

tasks.move_task_status("abc123xyz", "approved")  # Proposal
tasks.add_comment("abc123xyz", "Sent proposal: $5,000/mo")

tasks.move_task_status("abc123xyz", "complete")  # Won!
tasks.add_comment("abc123xyz", "Signed! Start date: Feb 1")

# Get pipeline stats
all_leads = tasks.list_tasks("901234567", include_closed=True)
by_status = {}
for lead in all_leads:
    status = lead.get("status", {}).get("status", "unknown")
    by_status[status] = by_status.get(status, 0) + 1

print("Pipeline Stats:")
for status, count in by_status.items():
    print(f"  {status}: {count}")
```

---

## Lead Task Structure

When imported, each lead task has this format:

**Task Name:** Company Name

**Description:**
```markdown
## Lead Information

**Contact:** John Smith
**Email:** john@company.com
**Phone:** +1-555-0123
**Website:** https://company.com

### Notes
Initial inquiry about Pro plan.
```

---

## CSV Format Example

Input CSV (`leads.csv`):
```csv
company,contact_name,email,phone,website,notes
Acme Corp,John Smith,john@acme.com,555-0101,https://acme.com,Inbound from website
Tech Solutions,Jane Doe,jane@techsol.com,555-0102,https://techsol.io,Referral from client
StartupXYZ,Bob Wilson,bob@startupxyz.com,555-0103,https://startupxyz.co,Met at conference
```

---

## Expected Output

### Successful Import
```
⏳ Progress: 10/100 (10%)
⏳ Progress: 50/100 (50%)
⏳ Progress: 100/100 (100%)

✓ Lead IMPORT Complete!
  Total: 100
  Created: 98
  Skipped: 2
  Failed: 0
```

### Pipeline View
```
📋 Found 50 leads:

📋 Acme Corp
   ID: 86abc123xyz
   Status: in progress
   Priority: high

📋 Tech Solutions
   ID: 86def456abc
   Status: review
   Priority: normal
...
```

---

## Quality Checklist

- [ ] Clean company names (no extra whitespace)
- [ ] Validate email format before import
- [ ] Deduplicate leads (skip existing companies)
- [ ] Set appropriate initial status
- [ ] Add source/channel as tag for tracking
- [ ] Document all status changes with comments

---

## Workflow Integration

### After Lead Scraping
```bash
# 1. Scrape leads
python3 execution/scrape_apify_leads.py --query "saas companies" --limit 50

# 2. Import to ClickUp pipeline
python3 execution/clickup_sync.py import-leads \
    --list-id 901234567 \
    --file .tmp/leads_saas_20241228.csv \
    --company-col "company" \
    --email-col "email"
```

### After Email Campaign
```bash
# Update leads who replied
python3 execution/clickup_sync.py update \
    --file replied_leads.csv \
    --id-col "clickup_task_id" \
    --status-col "new_status"
```

---

## Learnings & Edge Cases

### Duplicate Handling
By default, import skips companies that already exist as tasks. Use `--allow-duplicates` to override.

### Status Mapping
Map your CSV stages to ClickUp statuses:
```python
STATUS_MAP = {
    "new": "to do",
    "contacted": "in progress",
    "qualified": "review",
    "proposal": "approved",
    "won": "complete",
    "lost": "closed"
}
```

### Priority Assignment
High-value leads can be auto-tagged:
```python
if lead["company_size"] == "enterprise":
    task_data["priority"] = "urgent"
    task_data["tags"] = ["enterprise", "high-value"]
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-28 | Initial directive |
