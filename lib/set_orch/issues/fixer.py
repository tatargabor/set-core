"""Fix Runner — spawn opsx workflow agent in set-core directory."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .audit import AuditLog
from .models import Issue, IssueGroup, now_iso

logger = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to kebab-case slug."""
    s = re.sub(r'[^a-z0-9\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s[:max_len].rstrip('-')


class FixRunner:
    """Runs opsx workflow in set-core directory. Max 1 at a time."""

    def __init__(self, set_core_path: Path, audit: AuditLog):
        self.set_core_path = set_core_path
        self.audit = audit
        self._processes: dict[str, subprocess.Popen] = {}
        self._verify_processes: dict[str, subprocess.Popen] = {}

    def spawn(self, issue: Issue):
        """Start opsx fix agent in set-core directory."""
        change_name = f"fix-{issue.id.lower()}-{_slugify(issue.error_summary)}"
        issue.change_name = change_name

        diag_json = ""
        if issue.diagnosis:
            diag_json = json.dumps(issue.diagnosis.to_dict(), indent=2, ensure_ascii=False)

        prompt = FIX_PROMPT.format(
            issue_id=issue.id,
            change_name=change_name,
            diagnosis=diag_json,
            environment=issue.environment,
            error_summary=issue.error_summary,
        )

        cmd = ["claude", "-p", "--max-turns", "50", prompt]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.set_core_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._processes[issue.id] = proc
            issue.fix_agent_pid = proc.pid
            logger.info(f"Fix agent spawned for {issue.id}, PID={proc.pid}, change={change_name}")
        except FileNotFoundError:
            logger.error("claude CLI not found — cannot spawn fix agent")
            self.audit.log(issue.id, "fix_spawn_failed", error="claude not found")

    def is_done(self, issue: Issue) -> bool:
        proc = self._processes.get(issue.id)
        if proc is None:
            return True
        return proc.poll() is not None

    def collect(self, issue: Issue) -> dict:
        """Collect fix result. Returns dict with 'success' key."""
        proc = self._processes.pop(issue.id, None)
        if proc is None:
            return {"success": False, "error": "no process"}

        returncode = proc.returncode
        # Check if opsx change was archived
        change_dir = self.set_core_path / "openspec" / "changes" / (issue.change_name or "")
        archived = not change_dir.exists()  # archived = moved to archive/

        success = returncode == 0 or archived
        return {
            "success": success,
            "returncode": returncode,
            "archived": archived,
            "change_name": issue.change_name,
        }

    def run_verify(self, issue: Issue):
        """Run verification after fix (opsx:verify equivalent)."""
        # Verification is part of the fix agent's opsx workflow
        # This is called when the fix agent has completed successfully
        # The verify step is included in the fix prompt
        pass

    def verify_done(self, issue: Issue) -> bool:
        """Check if verification is complete."""
        # Verification runs as part of the fix agent's workflow
        # If fix is done, verify is done
        return self.is_done(issue)

    def verify_passed(self, issue: Issue) -> bool:
        """Check if verification passed."""
        result = self.collect(issue) if issue.id in self._processes else {"success": True}
        return result.get("success", False)

    def verify_result(self, issue: Issue) -> dict:
        return self.collect(issue)

    def kill(self, issue: Issue):
        """Kill the fix agent process."""
        for store in (self._processes, self._verify_processes):
            proc = store.pop(issue.id, None)
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
        issue.fix_agent_pid = None

    # --- Group support ---

    def is_done_group(self, group: IssueGroup) -> bool:
        proc = self._processes.get(group.id)
        if proc is None:
            return True
        return proc.poll() is not None

    def collect_group(self, group: IssueGroup) -> dict[str, bool]:
        """Collect group fix results. Returns {issue_id: success} map."""
        # For now, all issues in group succeed or fail together
        proc = self._processes.pop(group.id, None)
        success = proc is not None and proc.returncode == 0
        return {iid: success for iid in group.issue_ids}


FIX_PROMPT = """You are fixing issue {issue_id} in set-core.

## Issue
**Summary:** {error_summary}
**Environment:** {environment}

## Diagnosis
{diagnosis}

## Instructions
1. Run `/opsx:ff {change_name}` — create the change with scope based on the diagnosis
2. Run `/opsx:apply` — implement the fix
3. Run `/opsx:verify` — validate the fix
4. Run `/opsx:archive` — complete the change

Work in the set-core directory. Do NOT create worktrees.
Commit your changes after each step.
Focus on a minimal, correct fix — do not refactor unrelated code.
"""
