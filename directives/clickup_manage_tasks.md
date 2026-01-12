# ClickUp Task Management Directive

## Objective
Manage tasks in ClickUp: create, read, update, delete tasks, add comments, manage tags, and handle bulk operations via API.

---

## Required Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `operation` | Yes | create, list, get, update, delete, comment, tag |
| `list_id` | For create/list | ClickUp list ID |
| `task_id` | For get/update/delete/comment/tag | Task ID |
| `name` | For create | Task name |
| `description` | No | Task description (markdown) |
| `status` | No | Task status (must exist in list) |
| `priority` | No | urgent, high, normal, low |
| `due_date` | No | YYYY-MM-DD format |
| `tags` | No | Comma-separated tag names |
| `comment_text` | For comment | Comment content |

---

## Execution Tools

### Primary Scripts
- `execution/clickup_client.py` - Core API wrapper
- `execution/clickup_tasks.py` - Task CRUD operations
- `execution/clickup_lists.py` - Workspace discovery

### Environment Requirements
```
CLICKUP_API_KEY=pk_xxxxx  # In .env file
```

---

## Operations

### 1. Create Task
```bash
python3 execution/clickup_tasks.py create \
    --list-id 901234567 \
    --name "Review proposal" \
    --description "Check pricing and timeline" \
    --status "to do" \
    --priority high \
    --due-date 2024-01-15 \
    --tags "client,urgent"
```

### 2. List Tasks
```bash
# All tasks in a list
python3 execution/clickup_tasks.py list --list-id 901234567

# Filter by status
python3 execution/clickup_tasks.py list --list-id 901234567 --status "in progress"

# Include closed tasks
python3 execution/clickup_tasks.py list --list-id 901234567 --include-closed

# Search by name
python3 execution/clickup_tasks.py list --list-id 901234567 --search "proposal"

# Verbose output
python3 execution/clickup_tasks.py list --list-id 901234567 -v
```

### 3. Get Task Details
```bash
python3 execution/clickup_tasks.py get --task-id abc123xyz
```

### 4. Update Task
```bash
# Update status
python3 execution/clickup_tasks.py update --task-id abc123xyz --status "complete"

# Update priority
python3 execution/clickup_tasks.py update --task-id abc123xyz --priority urgent

# Update multiple fields
python3 execution/clickup_tasks.py update --task-id abc123xyz \
    --name "Updated name" \
    --status "review" \
    --due-date 2024-02-01
```

### 5. Delete Task
```bash
# With confirmation
python3 execution/clickup_tasks.py delete --task-id abc123xyz

# Force delete (no confirmation)
python3 execution/clickup_tasks.py delete --task-id abc123xyz --force
```

### 6. Add Comment
```bash
python3 execution/clickup_tasks.py comment \
    --task-id abc123xyz \
    --text "Updated the specs. Ready for review."
```

### 7. Manage Tags
```bash
# Add tag
python3 execution/clickup_tasks.py tag --task-id abc123xyz --add "urgent"

# Remove tag
python3 execution/clickup_tasks.py tag --task-id abc123xyz --remove "pending"
```

---

## Programmatic Usage

```python
from execution.clickup_tasks import ClickUpTaskManager

manager = ClickUpTaskManager()

# Create task
task = manager.create_task(
    list_id="901234567",
    name="New feature request",
    description="Details here...",
    status="to do",
    priority="high",
    tags=["feature", "q1"]
)

# List tasks
tasks = manager.list_tasks(list_id="901234567", status="in progress")

# Update task
manager.update_task(task_id="abc123", status="complete")

# Move through pipeline
manager.move_task_status(task_id="abc123", new_status="review")

# Add comment
manager.add_comment(task_id="abc123", text="Done!")

# Bulk create
tasks_to_create = [
    {"name": "Task 1", "priority": "high"},
    {"name": "Task 2", "status": "to do"},
    {"name": "Task 3", "tags": ["urgent"]}
]
results = manager.bulk_create(list_id="901234567", tasks=tasks_to_create)

# Bulk status update
task_ids = ["abc123", "def456", "ghi789"]
results = manager.bulk_update_status(task_ids, new_status="complete")
```

---

## Finding List IDs

Before creating tasks, find the target list ID:

```bash
# 1. Get workspace ID
python3 execution/clickup_lists.py workspaces

# 2. Get spaces in workspace
python3 execution/clickup_lists.py spaces --team-id 9012345678

# 3. Get folders in space
python3 execution/clickup_lists.py folders --space-id 90123456

# 4. Get lists in folder
python3 execution/clickup_lists.py lists --folder-id 90123456

# Or get full hierarchy at once
python3 execution/clickup_lists.py hierarchy --team-id 9012345678

# Or find list by name
python3 execution/clickup_lists.py find-list --team-id 9012345678 --name "My Tasks"
```

---

## Expected Outputs

### Successful Task Creation
```
✓ Task created successfully!
📋 Review proposal
   ID: 86abc123xyz
   Status: to do
   Priority: high
   Due: 2024-01-15
```

### Task List Output
```
📋 Found 5 tasks:

📋 Review proposal
   ID: 86abc123xyz
   Status: to do
   Priority: high

📋 Send invoice
   ID: 86def456abc
   Status: in progress
   Priority: normal
...
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `CLICKUP_API_KEY not found` | Missing API key | Add to .env file |
| `API Error 401` | Invalid API key | Check key in ClickUp settings |
| `API Error 404` | Invalid list/task ID | Verify ID exists |
| `API Error 429` | Rate limited | Script auto-retries with backoff |
| `Status not found` | Invalid status name | Check list statuses first |

---

## Rate Limits

ClickUp API: **100 requests/minute**

The client handles this automatically:
- Thread-safe rate limiting
- Exponential backoff on 429 errors
- Automatic retries (3 attempts)

---

## Quality Checklist

- [ ] Verify list_id exists before creating tasks
- [ ] Check available statuses before setting status
- [ ] Use appropriate priority values (urgent/high/normal/low)
- [ ] Use ISO date format (YYYY-MM-DD) for due dates
- [ ] Handle bulk operations with progress feedback
- [ ] Always confirm before destructive operations

---

## Learnings & Edge Cases

### Statuses Must Exist
ClickUp rejects tasks with non-existent statuses. Check available statuses first:
```bash
python3 execution/clickup_lists.py statuses --list-id 901234567
```

### Custom Fields
To set custom fields, get field IDs first:
```bash
python3 execution/clickup_lists.py custom-fields --list-id 901234567
```

### Tags Must Exist (Sometimes)
Some workspaces require tags to exist before assignment. Create tags in space first:
```python
from execution.clickup_lists import ClickUpWorkspaceManager
manager = ClickUpWorkspaceManager()
manager.create_tag(space_id="90123456", name="urgent", bg_color="#FF0000")
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-28 | Initial directive |
