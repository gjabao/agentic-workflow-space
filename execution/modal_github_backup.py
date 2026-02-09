#!/usr/bin/env python3
"""
Modal Cloud Backup for Anti-Gravity Workspace
Runs automatically in the cloud - no need to keep Mac awake

Schedule: Every 6 hours (4x daily)
"""

import modal
import subprocess
import os
from datetime import datetime

app = modal.App("anti-gravity-backup")

# Create image with git installed
image = modal.Image.debian_slim().apt_install("git")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("github-backup-token")],
    schedule=modal.Cron("0 */6 * * *"),  # Every 6 hours
    timeout=300,
)
def backup_to_github():
    """
    Clone repo, check for local changes marker, and verify backup status.
    Since Modal can't access your local files, this function:
    1. Clones the repo to verify it's accessible
    2. Logs the last commit info
    3. Can be triggered manually to verify connectivity

    For actual backups, your local LaunchAgent pushes changes.
    This Modal function serves as a health check and backup trigger reminder.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Anti-Gravity Backup Health Check")
    print(f"  Time: {timestamp}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Get GitHub token from Modal secrets
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("❌ ERROR: GITHUB_TOKEN not found in secrets")
        return {"status": "error", "message": "Missing GITHUB_TOKEN"}

    repo_url = f"https://{github_token}@github.com/gjabao/anti-gravity-workspace.git"

    try:
        # Clone repo (shallow) to check status
        print("\n[1/3] Checking repository access...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, "/tmp/backup-check"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"❌ Clone failed: {result.stderr}")
            return {"status": "error", "message": result.stderr}

        print("✓ Repository accessible")

        # Get last commit info
        print("\n[2/3] Checking last backup...")
        os.chdir("/tmp/backup-check")

        commit_result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%H|%s|%ai"],
            capture_output=True,
            text=True
        )

        if commit_result.returncode == 0:
            parts = commit_result.stdout.split("|")
            commit_hash = parts[0][:8] if parts else "unknown"
            commit_msg = parts[1] if len(parts) > 1 else "unknown"
            commit_date = parts[2] if len(parts) > 2 else "unknown"

            print(f"✓ Last commit: {commit_hash}")
            print(f"  Message: {commit_msg}")
            print(f"  Date: {commit_date}")

        # Count files
        print("\n[3/3] Repository statistics...")
        file_count = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True
        )
        num_files = len(file_count.stdout.strip().split("\n")) if file_count.stdout else 0
        print(f"✓ Total files tracked: {num_files}")

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✓ Backup Health Check Complete!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return {
            "status": "success",
            "timestamp": timestamp,
            "last_commit": commit_hash,
            "last_message": commit_msg,
            "files_tracked": num_files
        }

    except subprocess.TimeoutExpired:
        print("❌ ERROR: Operation timed out")
        return {"status": "error", "message": "Timeout"}
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.local_entrypoint()
def main():
    """Run backup check manually"""
    result = backup_to_github.remote()
    print(f"\nResult: {result}")
