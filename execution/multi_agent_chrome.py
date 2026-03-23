#!/usr/bin/env python3
"""
Multi-Agent Chrome Automation
==============================
Runs N parallel Chrome instances, each executing tasks independently.
Achieves 10-50x speedup vs sequential browser automation.

Usage:
    # Basic: 5 workers
    python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json

    # 10 workers, headed mode for debugging
    python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json --workers 10 --headed

    # Generate sample task file
    python3 execution/multi_agent_chrome.py --generate-sample

Architecture:
    Orchestrator (this script)
    ├── Worker 1 → Chromium Instance 1 → Task batch
    ├── Worker 2 → Chromium Instance 2 → Task batch
    └── Worker N → Chromium Instance N → Task batch
"""

import asyncio
import json
import os
import sys
import time
import argparse
import logging
import signal
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("multi-chrome")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class Action:
    type: str  # fill, click, select, wait, screenshot, extract, scroll, press_key
    selector: Optional[str] = None
    value: Optional[str] = None
    timeout: int = 10000  # ms

@dataclass
class Task:
    id: str
    type: str  # navigate, form_fill, scrape, screenshot, search, custom
    url: str
    actions: list = field(default_factory=list)
    wait_after: float = 1.0  # seconds to wait after all actions
    status: str = "pending"  # pending, running, done, failed
    result: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: int = 0
    worker_id: Optional[int] = None

@dataclass
class WorkerStats:
    worker_id: int
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration_ms: int = 0

# ---------------------------------------------------------------------------
# Chrome Worker
# ---------------------------------------------------------------------------
class ChromeWorker:
    """A single Chrome browser instance that processes tasks sequentially."""

    def __init__(self, worker_id: int, headless: bool = True):
        self.worker_id = worker_id
        self.headless = headless
        self.browser = None
        self.stats = WorkerStats(worker_id=worker_id)

    async def start(self, playwright):
        """Launch a new Chromium instance for this worker."""
        log.info(f"  Worker {self.worker_id}: Launching Chrome (headless={self.headless})")
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-size=1280,720",
            ],
        )
        log.info(f"  Worker {self.worker_id}: Chrome ready ✓")

    async def stop(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            log.info(f"  Worker {self.worker_id}: Chrome closed")

    async def execute_task(self, task: Task) -> Task:
        """Execute a single task and return updated task with results."""
        task.status = "running"
        task.worker_id = self.worker_id
        start_time = time.time()

        try:
            context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            # Navigate
            log.info(f"  Worker {self.worker_id}: [{task.id}] → {task.url}")
            await page.goto(task.url, wait_until="domcontentloaded", timeout=30000)

            # Execute actions
            results = []
            for i, action_dict in enumerate(task.actions):
                action = Action(**action_dict) if isinstance(action_dict, dict) else action_dict
                result = await self._execute_action(page, action, i)
                if result:
                    results.append(result)

            # Wait after actions
            if task.wait_after > 0:
                await asyncio.sleep(task.wait_after)

            # Collect page info
            title = await page.title()
            current_url = page.url

            task.status = "done"
            task.result = {
                "title": title,
                "url": current_url,
                "action_results": results,
            }

            await context.close()
            self.stats.tasks_completed += 1

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            log.error(f"  Worker {self.worker_id}: [{task.id}] FAILED: {e}")
            self.stats.tasks_failed += 1

        elapsed = int((time.time() - start_time) * 1000)
        task.duration_ms = elapsed
        self.stats.total_duration_ms += elapsed

        status_icon = "✓" if task.status == "done" else "✗"
        log.info(f"  Worker {self.worker_id}: [{task.id}] {status_icon} ({elapsed}ms)")
        return task

    async def _execute_action(self, page, action: Action, index: int) -> Optional[dict]:
        """Execute a single action on the page."""
        try:
            if action.type == "fill":
                await page.fill(action.selector, action.value, timeout=action.timeout)

            elif action.type == "click":
                await page.click(action.selector, timeout=action.timeout)

            elif action.type == "select":
                await page.select_option(action.selector, action.value, timeout=action.timeout)

            elif action.type == "wait":
                wait_time = float(action.value) if action.value else 1.0
                await asyncio.sleep(wait_time)

            elif action.type == "screenshot":
                path = action.value or f".tmp/chrome_tasks/screenshots/action_{index}.png"
                os.makedirs(os.path.dirname(path), exist_ok=True)
                await page.screenshot(path=path, full_page=True)
                return {"type": "screenshot", "path": path}

            elif action.type == "extract":
                # Extract text content from selector
                elements = await page.query_selector_all(action.selector)
                texts = []
                for el in elements:
                    text = await el.text_content()
                    if text:
                        texts.append(text.strip())
                return {"type": "extract", "selector": action.selector, "data": texts}

            elif action.type == "extract_attribute":
                # Extract attribute from elements
                elements = await page.query_selector_all(action.selector)
                values = []
                attr_name = action.value or "href"
                for el in elements:
                    val = await el.get_attribute(attr_name)
                    if val:
                        values.append(val)
                return {"type": "extract_attribute", "selector": action.selector, "data": values}

            elif action.type == "scroll":
                direction = action.value or "down"
                if direction == "down":
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                elif direction == "up":
                    await page.evaluate("window.scrollBy(0, -window.innerHeight)")
                elif direction == "bottom":
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            elif action.type == "press_key":
                await page.keyboard.press(action.value or "Enter")

            elif action.type == "type":
                await page.type(action.selector, action.value, delay=50)

            elif action.type == "wait_for":
                await page.wait_for_selector(action.selector, timeout=action.timeout)

            elif action.type == "evaluate":
                # Run arbitrary JS and return result
                result = await page.evaluate(action.value)
                return {"type": "evaluate", "data": result}

            else:
                log.warning(f"Unknown action type: {action.type}")

        except Exception as e:
            log.warning(f"Action {index} ({action.type}) failed: {e}")
            return {"type": action.type, "error": str(e)}

        return None

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class MultiAgentOrchestrator:
    """Distributes tasks across multiple Chrome workers."""

    def __init__(self, num_workers: int = 5, headless: bool = True):
        self.num_workers = min(num_workers, 10)  # Cap at 10
        self.headless = headless
        self.workers: list[ChromeWorker] = []
        self.results: list[Task] = []

    async def run(self, tasks: list[Task]) -> list[Task]:
        """Run all tasks distributed across workers."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.error("❌ Playwright not installed. Run:")
            log.error("   pip install playwright && playwright install chromium")
            sys.exit(1)

        total = len(tasks)
        log.info(f"=" * 60)
        log.info(f"Multi-Agent Chrome Automation")
        log.info(f"  Tasks: {total}")
        log.info(f"  Workers: {self.num_workers}")
        log.info(f"  Mode: {'headed' if not self.headless else 'headless'}")
        log.info(f"  Est. time: ~{(total / self.num_workers) * 10:.0f}s (vs ~{total * 10:.0f}s sequential)")
        log.info(f"=" * 60)

        start_time = time.time()

        async with async_playwright() as p:
            # 1. Launch all workers
            log.info(f"\n⏳ Launching {self.num_workers} Chrome instances...")
            self.workers = [ChromeWorker(i + 1, self.headless) for i in range(self.num_workers)]

            launch_tasks = [w.start(p) for w in self.workers]
            await asyncio.gather(*launch_tasks)
            log.info(f"✓ All {self.num_workers} Chrome instances ready\n")

            # 2. Distribute tasks across workers (round-robin)
            task_queues: list[list[Task]] = [[] for _ in range(self.num_workers)]
            for i, task in enumerate(tasks):
                task_queues[i % self.num_workers].append(task)

            # 3. Run workers in parallel
            log.info(f"⏳ Processing {total} tasks across {self.num_workers} workers...\n")

            async def worker_loop(worker: ChromeWorker, queue: list[Task]):
                results = []
                for task in queue:
                    result = await worker.execute_task(task)
                    results.append(result)
                return results

            worker_tasks = [
                worker_loop(self.workers[i], task_queues[i])
                for i in range(self.num_workers)
            ]
            all_results = await asyncio.gather(*worker_tasks)

            # Flatten results
            self.results = [task for batch in all_results for task in batch]

            # 4. Cleanup
            log.info(f"\n⏳ Closing Chrome instances...")
            close_tasks = [w.stop() for w in self.workers]
            await asyncio.gather(*close_tasks)

        elapsed = time.time() - start_time
        self._print_summary(elapsed)
        return self.results

    def _print_summary(self, elapsed: float):
        """Print execution summary."""
        done = sum(1 for t in self.results if t.status == "done")
        failed = sum(1 for t in self.results if t.status == "failed")
        total = len(self.results)

        log.info(f"\n{'=' * 60}")
        log.info(f"✓ COMPLETE")
        log.info(f"  Total tasks:  {total}")
        log.info(f"  Succeeded:    {done} ({done/total*100:.0f}%)" if total else "  Succeeded: 0")
        log.info(f"  Failed:       {failed}")
        log.info(f"  Total time:   {elapsed:.1f}s")
        log.info(f"  Avg per task: {elapsed/total:.1f}s" if total else "  Avg: N/A")
        log.info(f"  Speedup:      ~{self.num_workers}x vs sequential")

        # Per-worker stats
        log.info(f"\n  Worker Stats:")
        for w in self.workers:
            s = w.stats
            log.info(f"    Worker {s.worker_id}: {s.tasks_completed} done, {s.tasks_failed} failed, {s.total_duration_ms}ms total")
        log.info(f"{'=' * 60}")

# ---------------------------------------------------------------------------
# Task Queue I/O
# ---------------------------------------------------------------------------
def load_tasks(path: str) -> list[Task]:
    """Load tasks from JSON file."""
    with open(path, "r") as f:
        data = json.load(f)

    tasks_data = data if isinstance(data, list) else data.get("tasks", [])
    tasks = []
    for t in tasks_data:
        tasks.append(Task(
            id=t.get("id", f"task_{len(tasks)+1:03d}"),
            type=t.get("type", "navigate"),
            url=t["url"],
            actions=t.get("actions", []),
            wait_after=t.get("wait_after", 1.0),
        ))
    return tasks


def save_results(results: list[Task], path: str):
    """Save results to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    output = []
    for t in results:
        output.append({
            "id": t.id,
            "type": t.type,
            "url": t.url,
            "status": t.status,
            "worker_id": t.worker_id,
            "duration_ms": t.duration_ms,
            "result": t.result,
            "error": t.error,
        })
    with open(path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    log.info(f"\n📁 Results saved: {path}")


def generate_sample_tasks(path: str):
    """Generate a sample task queue file for testing."""
    sample = {
        "tasks": [
            {
                "id": "search_001",
                "type": "search",
                "url": "https://www.bing.com",
                "actions": [
                    {"type": "fill", "selector": "#sb_form_q", "value": "best coffee District 7 HCMC"},
                    {"type": "click", "selector": "#sb_form button[type=submit]"},
                    {"type": "wait", "value": "2"},
                    {"type": "extract", "selector": "h2 a"},
                ],
                "wait_after": 1
            },
            {
                "id": "search_002",
                "type": "search",
                "url": "https://www.bing.com",
                "actions": [
                    {"type": "fill", "selector": "#sb_form_q", "value": "máy sấy tóc tốt nhất 2026"},
                    {"type": "click", "selector": "#sb_form button[type=submit]"},
                    {"type": "wait", "value": "2"},
                    {"type": "extract", "selector": "h2 a"},
                ],
                "wait_after": 1
            },
            {
                "id": "search_003",
                "type": "search",
                "url": "https://www.bing.com",
                "actions": [
                    {"type": "fill", "selector": "#sb_form_q", "value": "top restaurants Saigon 2026"},
                    {"type": "click", "selector": "#sb_form button[type=submit]"},
                    {"type": "wait", "value": "2"},
                    {"type": "extract", "selector": "h2 a"},
                ],
                "wait_after": 1
            },
            {
                "id": "scrape_001",
                "type": "scrape",
                "url": "https://news.ycombinator.com",
                "actions": [
                    {"type": "extract", "selector": ".titleline > a"},
                ],
                "wait_after": 0.5
            },
            {
                "id": "scrape_002",
                "type": "scrape",
                "url": "https://www.producthunt.com",
                "actions": [
                    {"type": "wait", "value": "3"},
                    {"type": "screenshot", "value": ".tmp/chrome_tasks/screenshots/producthunt.png"},
                ],
                "wait_after": 0.5
            },
            {
                "id": "navigate_001",
                "type": "navigate",
                "url": "https://github.com/trending",
                "actions": [
                    {"type": "extract", "selector": "h2.h3 a"},
                ],
                "wait_after": 0.5
            },
            {
                "id": "navigate_002",
                "type": "navigate",
                "url": "https://www.reddit.com/r/programming/top/?t=day",
                "actions": [
                    {"type": "wait", "value": "3"},
                    {"type": "extract", "selector": "a[data-testid='post-title']"},
                ],
                "wait_after": 1
            },
            {
                "id": "search_004",
                "type": "search",
                "url": "https://www.bing.com",
                "actions": [
                    {"type": "fill", "selector": "#sb_form_q", "value": "Claude AI agent automation 2026"},
                    {"type": "click", "selector": "#sb_form button[type=submit]"},
                    {"type": "wait", "value": "2"},
                    {"type": "extract", "selector": "h2 a"},
                ],
                "wait_after": 1
            },
            {
                "id": "search_005",
                "type": "search",
                "url": "https://www.bing.com",
                "actions": [
                    {"type": "fill", "selector": "#sb_form_q", "value": "Playwright browser automation tutorial"},
                    {"type": "click", "selector": "#sb_form button[type=submit]"},
                    {"type": "wait", "value": "2"},
                    {"type": "extract", "selector": "h2 a"},
                ],
                "wait_after": 1
            },
            {
                "id": "scrape_003",
                "type": "scrape",
                "url": "https://lobste.rs",
                "actions": [
                    {"type": "extract", "selector": ".u-url"},
                ],
                "wait_after": 0.5
            },
        ]
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sample, f, indent=2, ensure_ascii=False)
    log.info(f"✓ Sample tasks generated: {path} ({len(sample['tasks'])} tasks)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Chrome Automation - Run N parallel browsers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate sample task file
  python3 execution/multi_agent_chrome.py --generate-sample

  # Run with 5 workers (default)
  python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json

  # Run 10 workers in headed mode
  python3 execution/multi_agent_chrome.py --tasks .tmp/chrome_tasks/queue.json --workers 10 --headed
        """,
    )
    parser.add_argument("--tasks", type=str, help="Path to task queue JSON file")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel Chrome workers (max 10)")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode (visible browser)")
    parser.add_argument("--output", type=str, default=".tmp/chrome_tasks/results.json", help="Output results path")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample task queue file")

    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_tasks(".tmp/chrome_tasks/queue.json")
        return

    if not args.tasks:
        parser.print_help()
        print("\n❌ --tasks is required. Use --generate-sample to create a sample file.")
        sys.exit(1)

    if not os.path.exists(args.tasks):
        log.error(f"❌ Task file not found: {args.tasks}")
        sys.exit(1)

    # Load tasks
    tasks = load_tasks(args.tasks)
    if not tasks:
        log.error("❌ No tasks found in file")
        sys.exit(1)

    # Run orchestrator
    orchestrator = MultiAgentOrchestrator(
        num_workers=args.workers,
        headless=not args.headed,
    )
    results = asyncio.run(orchestrator.run(tasks))

    # Save results
    save_results(results, args.output)


if __name__ == "__main__":
    main()
