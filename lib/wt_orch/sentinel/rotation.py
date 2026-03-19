"""Run rotation — archive old events and findings for a new run."""

import os
import shutil
from datetime import datetime, timezone

from wt_orch.sentinel.wt_dir import ensure_wt_dir

EVENTS_FILE = "events.jsonl"
FINDINGS_FILE = "findings.json"
ARCHIVE_DIR = "archive"


def rotate(project_path: str) -> dict:
    """Archive current events.jsonl and findings.json, start fresh.

    Returns dict with archived file paths (empty strings if nothing to archive).
    """
    sentinel_dir = ensure_wt_dir(project_path)
    archive_dir = os.path.join(sentinel_dir, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    result = {"events_archived": "", "findings_archived": ""}

    # Archive events
    events_path = os.path.join(sentinel_dir, EVENTS_FILE)
    if os.path.exists(events_path) and os.path.getsize(events_path) > 0:
        dest = os.path.join(archive_dir, f"events-{timestamp}.jsonl")
        shutil.move(events_path, dest)
        result["events_archived"] = dest

    # Archive findings
    findings_path = os.path.join(sentinel_dir, FINDINGS_FILE)
    if os.path.exists(findings_path) and os.path.getsize(findings_path) > 0:
        dest = os.path.join(archive_dir, f"findings-{timestamp}.json")
        shutil.move(findings_path, dest)
        result["findings_archived"] = dest

    # Create fresh empty files
    open(events_path, "w").close()

    return result
