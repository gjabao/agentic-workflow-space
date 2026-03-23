# Multi-Agent Chrome Automation

## Goal
Run parallel browser automation tasks using multiple Chrome instances, each managed by a separate worker. Achieves 10-50x speedup vs sequential execution.

## Architecture
```
Orchestrator (Claude / Python)
├── Worker 1 → Chrome :9301 → Task A
├── Worker 2 → Chrome :9302 → Task B
├── Worker 3 → Chrome :9303 → Task C
├── ...
└── Worker N → Chrome :930N → Task N

Communication: shared JSON task queue + results file
```

## How It Works

### 1. Port Allocation
- Each Chrome instance gets a unique debugging port: 9301, 9302, ..., 930N
- Max 10 concurrent instances recommended (RAM constraint ~500MB/instance)

### 2. Task Queue
- Tasks defined in `.tmp/chrome_tasks/queue.json`
- Each task: `{id, url, actions[], status, result}`

### 3. Execution
```bash
# Run with defaults (5 workers)
python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json

# Run with 10 workers
python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json --workers 10

# Run specific task type
python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json --task-type form_fill
```

### 4. Task Types Supported
| Type | Description | Avg Time |
|------|-------------|----------|
| `navigate` | Go to URL, take snapshot | ~3s |
| `form_fill` | Fill form fields + submit | ~15s |
| `scrape` | Extract data from page | ~5s |
| `screenshot` | Capture page screenshot | ~3s |
| `search` | Search on a site + extract results | ~10s |
| `custom` | Run custom action sequence | varies |

### 5. Task JSON Format
```json
{
  "tasks": [
    {
      "id": "task_001",
      "type": "form_fill",
      "url": "https://example.com/form",
      "actions": [
        {"type": "fill", "selector": "#name", "value": "John Doe"},
        {"type": "fill", "selector": "#email", "value": "john@example.com"},
        {"type": "click", "selector": "#submit"}
      ],
      "wait_after": 2
    }
  ]
}
```

### 6. Results
- Output: `.tmp/chrome_tasks/results.json`
- Each result: `{task_id, status, data, error, duration_ms}`

## Performance Math
```
Sequential:  1 browser × 15s/form × 100 forms = 25 minutes
5 workers:   5 browsers × 15s/form × 20 forms each = 5 minutes  (5x faster)
10 workers: 10 browsers × 15s/form × 10 forms each = 2.5 minutes (10x faster)
```

## Constraints
- Max 10 workers (RAM: each Chrome ~500MB)
- Rate limit aware: add `delay_between` in task config
- Headless mode default (set `--headed` for debugging)
- All Chrome instances killed on exit (cleanup guaranteed)

## Edge Cases & Learnings
- If Chrome fails to start on a port → retry with next port
- If page load timeout → skip task, mark as failed, continue
- If Cloudflare/CAPTCHA detected → pause worker, notify orchestrator
- Always kill Chrome processes on script exit (atexit handler)

## Required
- Python 3.9+
- playwright (`pip install playwright && playwright install chromium`)
- No other dependencies needed
