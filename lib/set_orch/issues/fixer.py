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


def _is_pid_alive(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class FixRunner:
    """Runs opsx workflow in set-core directory. Max 1 at a time."""

    def __init__(self, set_core_path: Path, audit: AuditLog):
        self.set_core_path = set_core_path
        self.audit = audit
        self._processes: dict[str, subprocess.Popen] = {}
        self._verify_processes: dict[str, subprocess.Popen] = {}
        self._stdout_files: dict[str, object] = {}

    def _resolve_fix_target(self, issue: Issue) -> tuple[str, str]:
        """Determine where to run the fix and which prompt to use.

        Returns (cwd, prompt) tuple.
        Framework bugs → set-core (openspec + redeploy).
        Consumer issues → consumer project.
        """
        change_name = issue.change_name or ""
        diag_json = ""
        if issue.diagnosis:
            diag_json = json.dumps(issue.diagnosis.to_dict(), indent=2, ensure_ascii=False)

        fix_target = getattr(issue.diagnosis, "fix_target", "consumer") if issue.diagnosis else "consumer"

        from ..paths import LineagePaths
        _lp_fixer = LineagePaths(issue.environment_path or str(self.set_core_path))
        state_basename = os.path.basename(_lp_fixer.state_file)
        config_yaml_rel = os.path.relpath(
            _lp_fixer.config_yaml,
            issue.environment_path or str(self.set_core_path),
        )

        if fix_target in ("framework", "both"):
            cwd = str(self.set_core_path)
            prompt = FRAMEWORK_FIX_PROMPT.format(
                issue_id=issue.id,
                change_name=change_name,
                diagnosis=diag_json,
                environment=issue.environment,
                error_summary=issue.error_summary,
                consumer_project=issue.environment_path or "unknown",
                state_basename=state_basename,
                config_yaml=config_yaml_rel,
            )
        else:
            cwd = issue.environment_path or str(self.set_core_path)
            prompt = FIX_PROMPT.format(
                issue_id=issue.id,
                change_name=change_name,
                diagnosis=diag_json,
                environment=issue.environment,
                error_summary=issue.error_summary,
                state_basename=state_basename,
                config_yaml=config_yaml_rel,
            )

        return cwd, prompt

    def spawn(self, issue: Issue):
        """Start opsx fix agent — in set-core for framework bugs, consumer for app issues."""
        change_name = f"fix-{issue.id.lower()}-{_slugify(issue.error_summary)}"
        issue.change_name = change_name

        project_cwd, prompt = self._resolve_fix_target(issue)

        cmd = [
            "claude", "-p", "--max-turns", "50",
            "--dangerously-skip-permissions",
            "--verbose", "--output-format", "stream-json",
            prompt,
        ]

        # Capture output to file for debugging
        fix_output_dir = Path(project_cwd) / ".set" / "issues" / "fixes"
        fix_output_dir.mkdir(parents=True, exist_ok=True)
        fix_output_file = fix_output_dir / f"{issue.id}.md"
        stdout_fh = open(fix_output_file, "w")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=project_cwd,
                stdout=stdout_fh,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._stdout_files[issue.id] = stdout_fh
            self._processes[issue.id] = proc
            issue.fix_agent_pid = proc.pid
            logger.info(f"Fix agent spawned for {issue.id}, PID={proc.pid}, change={change_name}")
        except FileNotFoundError:
            logger.error("claude CLI not found — cannot spawn fix agent")
            self.audit.log(issue.id, "fix_spawn_failed", error="claude not found")

    def is_done(self, issue: Issue) -> bool:
        proc = self._processes.get(issue.id)
        if proc is None:
            # Process reference lost (restart?) — check PID liveness
            if issue.fix_agent_pid:
                return not _is_pid_alive(issue.fix_agent_pid)
            return True  # No PID, no process — must be done
        return proc.poll() is not None

    def _check_archived(self, issue: Issue) -> bool:
        """Check if the fix change was archived on disk."""
        # Framework/both fixes check set-core, consumer fixes check the consumer project
        fix_target = getattr(issue.diagnosis, "fix_target", "consumer") if issue.diagnosis else "consumer"
        project_path = self.set_core_path if fix_target in ("framework", "both") else (
            Path(issue.environment_path) if issue.environment_path else self.set_core_path
        )
        change_name = issue.change_name or ""
        if not change_name:
            return False
        change_dir = project_path / "openspec" / "changes" / change_name
        if change_dir.exists():
            return False  # Still active, not archived
        # Check archive dir for matching entry
        archive_dir = project_path / "openspec" / "changes" / "archive"
        if archive_dir.is_dir():
            for d in archive_dir.iterdir():
                if d.name.endswith(change_name):
                    return True
        return True  # Change dir gone = archived or cleaned up

    def collect(self, issue: Issue) -> dict:
        """Collect fix result. Returns dict with 'success' key."""
        proc = self._processes.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass

        archived = self._check_archived(issue)

        if proc is None:
            # Process reference lost — rely on filesystem
            return {
                "success": archived,
                "returncode": None,
                "archived": archived,
                "change_name": issue.change_name,
                "note": "process_reference_lost_checked_filesystem",
            }

        returncode = proc.returncode
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
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
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


FIX_PROMPT = """Implement the fix for issue {issue_id}.

The investigation agent already created the change artifacts with /opsx:ff.
The proposal, design, specs, and tasks are in `openspec/changes/{change_name}/`.

## Issue
**Summary:** {error_summary}
**Environment:** {environment}

## Instructions

1. Run `/opsx:apply {change_name}` — implement the tasks defined in tasks.md.

2. After apply completes, verify the fix works by running the command that was failing.

3. **Deploy the fix to all active worktrees:**
   ```bash
   for wt in $(git worktree list --porcelain | grep '^worktree ' | awk '{{print $2}}' | tail -n +2); do
     cp vitest.config.ts "$wt/vitest.config.ts" 2>/dev/null
     cp {config_yaml} "$wt/{config_yaml}" 2>/dev/null
     cp playwright.config.ts "$wt/playwright.config.ts" 2>/dev/null
   done
   ```

4. **Reset blocked changes** so the orchestrator retries (keep merge_retry_count to prevent infinite loops):
   ```bash
   python3 -c "
   import json; f='{state_basename}'; s=json.load(open(f))
   for c in s['changes']:
       if c['status'] in ('integration-failed', 'merge-blocked'):
           c['status']='done'
           c.setdefault('extras',{{}})['ff_retry_count']=0
           print(f'Reset {{c[\"name\"]}} → done (merge_retry={{c.get(\"extras\",{{}}).get(\"merge_retry_count\",0)}})')
   json.dump(s, open(f,'w'), indent=2)
   "
   ```

5. Run `/opsx:archive {change_name}` — archive the completed change.

Focus on a minimal, correct fix — do not refactor unrelated code.
"""


FRAMEWORK_FIX_PROMPT = """Fix framework bug for issue {issue_id}.

You are working in the **set-core** repository (the framework), NOT the consumer project.
The bug was detected in consumer project: {consumer_project}

## Issue
**Summary:** {error_summary}
**Environment:** {environment}

## Diagnosis
```json
{diagnosis}
```

## Instructions

1. Run `/opsx:ff {change_name}` — create a structured fix plan in set-core's openspec.
   The proposal should describe the framework bug and the fix.

2. Run `/opsx:apply {change_name}` — implement the fix in set-core's codebase.
   Fix files under `lib/set_orch/`, `modules/`, or other framework code as needed.

3. Commit the fix on set-core's main branch.

4. **Redeploy to the consumer project** so the fix takes effect:
   ```bash
   set-project init --name {environment}
   ```

5. **Reset blocked changes** in the consumer project so the orchestrator retries:
   ```bash
   python3 -c "
   import json, os
   f = os.path.join('{consumer_project}', '{state_basename}')
   if os.path.exists(f):
       s = json.load(open(f))
       for c in s['changes']:
           if c['status'] in ('integration-failed', 'merge-blocked'):
               c['status'] = 'done'
               c.setdefault('extras', {{}})['ff_retry_count'] = 0
               print(f'Reset {{c[\"name\"]}} → done (merge_retry={{c.get(\"extras\",{{}}).get(\"merge_retry_count\",0)}})')
       json.dump(s, open(f, 'w'), indent=2)
   "
   ```

6. Run `/opsx:archive {change_name}` — archive the completed change in set-core.

Focus on a minimal, correct framework fix — do not modify consumer project code directly.
"""
