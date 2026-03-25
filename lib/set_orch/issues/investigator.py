"""Investigation Runner — spawn claude CLI for read-only issue investigation."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .audit import AuditLog
from .models import Diagnosis, Issue, now_iso
from .policy import IssuesPolicyConfig

logger = logging.getLogger(__name__)


class InvestigationRunner:
    """Spawns claude CLI for investigation. Runs in set-core directory."""

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

    def spawn(self, issue: Issue):
        """Start investigation agent as a claude CLI subprocess."""
        template = self._get_template(issue)
        prompt = self._render_template(template, issue)
        output_file = self._investigation_path(issue)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "claude", "-p",
            "--max-turns", "20",
            "--verbose", "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            prompt,
        ]

        # Run in the consumer project directory so the agent can read
        # config.yaml, package.json, etc. Falls back to set-core path.
        project_cwd = issue.environment_path or str(self.set_core_path)

        # Write stdout to file for collect() to parse later
        stdout_file = open(output_file, "w")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=project_cwd,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._stdout_files[issue.id] = stdout_file
            self._processes[issue.id] = proc
            self._started_at[issue.id] = datetime.now(timezone.utc)
            issue.fix_agent_pid = proc.pid
            logger.info(f"Investigation spawned for {issue.id}, PID={proc.pid}")
        except FileNotFoundError:
            logger.error("claude CLI not found — cannot spawn investigation")
            self.audit.log(issue.id, "investigation_spawn_failed", error="claude not found")

    def is_done(self, issue: Issue) -> bool:
        """Check if investigation agent has completed."""
        proc = self._processes.get(issue.id)
        if proc is None:
            return True  # No process = treat as done
        return proc.poll() is not None

    def is_timed_out(self, issue: Issue) -> bool:
        """Check if investigation has exceeded timeout."""
        started = self._started_at.get(issue.id)
        if not started:
            return False
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return elapsed > self.config.investigation.timeout_seconds

    def kill(self, issue: Issue):
        """Kill the investigation agent process."""
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
        """Parse investigation output into Diagnosis."""
        self._processes.pop(issue.id, None)
        self._started_at.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass

        output_file = self._investigation_path(issue)
        if not output_file.exists():
            raw_output = ""
        else:
            # Output is stream-json — extract assistant text blocks
            raw_stream = output_file.read_text()
            texts = []
            for line in raw_stream.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "assistant":
                    for block in obj.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text"):
                            texts.append(block["text"])
            raw_output = "\n".join(texts)

        if not raw_output:
            self.audit.log(issue.id, "investigation_no_output")
            return None

        # Try DIAGNOSIS_START/END markers first
        match = re.search(
            r'DIAGNOSIS_START\s*(\{.*?\})\s*DIAGNOSIS_END',
            raw_output, re.DOTALL
        )
        if not match:
            # Fallback: JSON in markdown code fence at end
            match = re.search(
                r'```json\s*(\{.*?\})\s*```\s*$',
                raw_output, re.DOTALL
            )

        if not match:
            self.audit.log(issue.id, "diagnosis_parse_failed",
                           raw_length=len(raw_output))
            return Diagnosis(
                root_cause="Investigation completed but diagnosis could not be parsed",
                impact=issue.severity if issue.severity != "unknown" else "medium",
                confidence=0.0,
                fix_scope="unknown",
                suggested_fix="Manual review required — see raw investigation output",
                raw_output=raw_output,
            )

        try:
            data = json.loads(match.group(1))
            # Build Diagnosis from parsed data
            return Diagnosis(
                root_cause=data.get("root_cause", ""),
                impact=data.get("impact", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                fix_scope=data.get("fix_scope", "unknown"),
                suggested_fix=data.get("suggested_fix", ""),
                affected_files=data.get("affected_files", []),
                related_issues=data.get("related_issues", []),
                suggested_group=data.get("suggested_group"),
                group_reason=data.get("group_reason"),
                tags=data.get("tags", []),
                raw_output=raw_output,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            self.audit.log(issue.id, "diagnosis_parse_error", error=str(e))
            return Diagnosis(
                root_cause=f"Diagnosis JSON parse error: {e}",
                confidence=0.0,
                fix_scope="unknown",
                raw_output=raw_output,
            )

    def _investigation_path(self, issue: Issue) -> Path:
        """Path to investigation output file."""
        project_path = Path(issue.environment_path) if issue.environment_path else self.set_core_path
        return project_path / ".set" / "issues" / "investigations" / f"{issue.id}.md"

    def _get_template(self, issue: Issue) -> str:
        """Resolve template: profile-specific > config > default."""
        if self.profile and hasattr(self.profile, 'investigation_template'):
            custom = self.profile.investigation_template(issue)
            if custom:
                return custom

        template_name = self.config.investigation.template
        template_path = Path(__file__).parent / "templates" / f"{template_name}.md"
        if template_path.exists():
            return template_path.read_text()

        # Inline default if no file
        return DEFAULT_TEMPLATE

    def _render_template(self, template: str, issue: Issue) -> str:
        """Render template with issue context."""
        # Build open issues summary
        open_summary = "No other open issues."
        # Use error_detail if available, fall back to error_summary
        error_text = issue.error_detail or issue.error_summary or "No error details available"
        return template.format(
            issue_id=issue.id,
            environment=issue.environment,
            source=issue.source,
            affected_change=issue.affected_change or "N/A",
            severity=issue.severity,
            detected_at=issue.detected_at,
            occurrence_count=issue.occurrence_count,
            error_detail=error_text,
            open_issues_summary=open_summary,
        )


DEFAULT_TEMPLATE = """# Issue Investigation: {issue_id}

## Context
- **Environment:** {environment}
- **Source:** {source}
- **Affected change:** {affected_change}
- **Severity (initial):** {severity}
- **Detected at:** {detected_at}
- **Occurrence count:** {occurrence_count}

## Error Details
```
{error_detail}
```

## Other Open Issues
{open_issues_summary}

## Framework Knowledge

This project runs on the **set-core orchestration framework**. Key facts for investigation:

- **Orchestration config:** `set/orchestration/config.yaml` — overrides for test_command, e2e_command, build_command. These take priority over auto-detected commands.
- **Integration gates:** The merger runs build → test → e2e gates before merging. Gate commands come from: 1) config.yaml directives, 2) profile auto-detection (WebProjectType).
- **Profile:** `set/plugins/project-type.yaml` defines the project type (web, base). The web profile auto-detects test/build/e2e commands from package.json.
- **Common gate failures:**
  - `test=fail` with vitest: vitest exits 1 when no test files found. Fix: set `test_command: "npx vitest run --passWithNoTests"` in config.yaml
  - `build=fail`: usually missing deps or type errors. Check if `pnpm install` ran before build.
  - `e2e=fail`: playwright needs `pnpm exec playwright install` and a dev server.
- **Config override pattern:** To fix a gate command, edit `set/orchestration/config.yaml` and set the specific command. The orchestrator will pick it up on next merge attempt.

## Instructions

Investigate this issue thoroughly. You may read files in both the project directory AND the set-core framework code to understand the root cause.

1. **Read the error output** — identify the exact failure point (file, line, function)
2. **Read the affected code** — understand the context around the failure
3. **Check the config** — read `set/orchestration/config.yaml` and `set/plugins/project-type.yaml`
4. **Check git history** — `git log --oneline -20 -- <affected_files>` to see recent changes
5. **Trace the root cause** — follow the chain from symptom to underlying bug
6. **Propose a fix** — either a config change (config.yaml override) or a code change
7. **Assess impact** — what breaks if this isn't fixed? Is it blocking?

## Output Format

End your response with a JSON diagnosis block:

DIAGNOSIS_START
{{
  "root_cause": "Clear description of the actual underlying bug",
  "impact": "low|medium|high|critical",
  "confidence": 0.85,
  "fix_scope": "config_override|single_file|multi_file|cross_module",
  "suggested_fix": "What needs to change and why — include exact file path and content if config_override",
  "affected_files": ["path/to/file.py:42"],
  "related_issues": [],
  "suggested_group": null,
  "group_reason": null,
  "tags": ["relevant", "tags"]
}}
DIAGNOSIS_END
"""
