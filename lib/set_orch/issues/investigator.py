"""Investigation Runner — spawn /opsx:ff to diagnose and plan fix."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .audit import AuditLog
from .models import Diagnosis, Issue, now_iso
from .policy import IssuesPolicyConfig

logger = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to kebab-case slug."""
    s = re.sub(r'[^a-z0-9\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s[:max_len].rstrip('-')


class InvestigationRunner:
    """Spawns /opsx:ff to investigate and create fix artifacts."""

    def __init__(
        self,
        set_core_path: Path,
        config: IssuesPolicyConfig,
        audit: AuditLog,
        profile=None,
    ):
        self.set_core_path = set_core_path
        self.config = config
        self.audit = audit
        self.profile = profile
        self._processes: dict[str, subprocess.Popen] = {}
        self._started_at: dict[str, datetime] = {}
        self._stdout_files: dict[str, object] = {}
        self._change_names: dict[str, str] = {}

    def spawn(self, issue: Issue):
        """Start investigation via /opsx:ff — creates proposal + design + tasks."""
        change_name = f"fix-{issue.id.lower()}-{_slugify(issue.error_summary)}"
        self._change_names[issue.id] = change_name
        issue.change_name = change_name

        error_text = issue.error_detail or issue.error_summary or "No error details"

        prompt = INVESTIGATION_PROMPT.format(
            issue_id=issue.id,
            change_name=change_name,
            environment=issue.environment,
            error_detail=error_text,
            affected_change=issue.affected_change or "N/A",
        )

        output_file = self._investigation_path(issue)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        stdout_fh = open(output_file, "w")

        cmd = [
            "claude", "-p",
            "--max-turns", "20",
            "--verbose", "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            prompt,
        ]

        project_cwd = issue.environment_path or str(self.set_core_path)

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
            self._started_at[issue.id] = datetime.now(timezone.utc)
            issue.fix_agent_pid = proc.pid
            logger.info(f"Investigation /opsx:ff spawned for {issue.id}, PID={proc.pid}, change={change_name}")
        except FileNotFoundError:
            logger.error("claude CLI not found — cannot spawn investigation")
            self.audit.log(issue.id, "investigation_spawn_failed", error="claude not found")

    def is_done(self, issue: Issue) -> bool:
        proc = self._processes.get(issue.id)
        if proc is None:
            return True
        return proc.poll() is not None

    def is_timed_out(self, issue: Issue) -> bool:
        started = self._started_at.get(issue.id)
        if not started:
            return False
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return elapsed > self.config.investigation.timeout_seconds

    def kill(self, issue: Issue):
        proc = self._processes.pop(issue.id, None)
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        self._started_at.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass
        issue.fix_agent_pid = None

    def collect(self, issue: Issue) -> Optional[Diagnosis]:
        """Parse diagnosis from /opsx:ff artifacts (proposal.md)."""
        self._processes.pop(issue.id, None)
        self._started_at.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass

        change_name = self._change_names.pop(issue.id, issue.change_name or "")
        project_path = Path(issue.environment_path) if issue.environment_path else self.set_core_path

        # Read proposal.md — this IS the diagnosis
        proposal_path = project_path / "openspec" / "changes" / change_name / "proposal.md"
        if not proposal_path.exists():
            self.audit.log(issue.id, "investigation_no_proposal", change=change_name)
            return None

        proposal = proposal_path.read_text()

        # Check tasks.md exists (confirms /opsx:ff completed)
        tasks_path = project_path / "openspec" / "changes" / change_name / "tasks.md"
        tasks_exist = tasks_path.exists()

        # Extract diagnosis from proposal content
        diagnosis = self._parse_proposal(proposal, tasks_exist)
        diagnosis.raw_output = proposal
        return diagnosis

    def _parse_proposal(self, proposal: str, has_tasks: bool) -> Diagnosis:
        """Extract diagnosis fields from proposal.md content."""
        lines = proposal.lower()

        # Detect impact/severity from content
        impact = "medium"
        if any(w in lines for w in ["critical", "blocker", "permanently block", "pipeline blocked"]):
            impact = "high"
        elif any(w in lines for w in ["minor", "cosmetic", "warning"]):
            impact = "low"

        # Detect scope from content
        fix_scope = "single_file"
        if any(w in lines for w in ["config.yaml", "config override", "vitest.config", "playwright.config"]):
            fix_scope = "config_override"
        elif any(w in lines for w in ["multiple files", "cross-module", "several files"]):
            fix_scope = "multi_file"

        # Extract root cause — first paragraph after "## Problem" or "## Why"
        root_cause = ""
        for header in [r"##\s*(?:Problem|Why|Root Cause|Background)", r"##\s*\w+"]:
            match = re.search(header + r"\s*\n\s*(.+?)(?:\n\n|\n##)", proposal, re.DOTALL | re.IGNORECASE)
            if match:
                root_cause = match.group(1).strip()[:500]
                break
        if not root_cause:
            # Fallback: first non-header paragraph
            for line in proposal.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-") and len(line) > 20:
                    root_cause = line[:500]
                    break

        # Extract suggested fix — from "## What" or "## Solution" section
        suggested_fix = ""
        for header in [r"##\s*(?:What|Solution|Fix|Scope)", r"##\s*\w+"]:
            match = re.search(header + r"\s*\n\s*(.+?)(?:\n\n|\n##)", proposal, re.DOTALL | re.IGNORECASE)
            if match and match.group(1).strip() != root_cause:
                suggested_fix = match.group(1).strip()[:500]
                break

        # Confidence based on completeness
        confidence = 0.5
        if root_cause and suggested_fix:
            confidence = 0.8
        if has_tasks:
            confidence = 0.95  # /opsx:ff completed fully

        return Diagnosis(
            root_cause=root_cause or "See proposal.md for details",
            impact=impact,
            confidence=confidence,
            fix_scope=fix_scope,
            suggested_fix=suggested_fix or "See tasks.md for implementation plan",
            affected_files=[],
            related_issues=[],
            tags=[],
        )

    def _investigation_path(self, issue: Issue) -> Path:
        project_path = Path(issue.environment_path) if issue.environment_path else self.set_core_path
        return project_path / ".set" / "issues" / "investigations" / f"{issue.id}.md"


INVESTIGATION_PROMPT = """Investigate and plan a fix for issue {issue_id}.

## Issue
**Environment:** {environment}
**Affected change:** {affected_change}

**Error:**
```
{error_detail}
```

## Framework Knowledge

This project uses **set-core orchestration**:
- Config: `set/orchestration/config.yaml` — overrides for test/e2e/build commands
- Gates: merger runs build → test → e2e before merging
- Profile: `set/plugins/project-type.yaml` → web profile auto-detects commands
- Common fixes:
  - vitest "no test files" → add `passWithNoTests: true` to vitest.config.ts
  - build fail → check deps installed, type errors
  - e2e fail → playwright needs install + dev server

## Instructions

Run `/opsx:ff {change_name}` to create a structured fix plan. The proposal should describe:
- What is broken and why (root cause)
- What needs to change (exact files and content)
- Impact if not fixed

The /opsx:ff command will create proposal.md, design.md, specs, and tasks.md — everything needed for the fix agent to implement with /opsx:apply.
"""
