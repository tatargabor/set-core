"""Detection Bridge — reads sentinel findings and converts to issues."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from .models import now_iso
from ..paths import SetRuntime

logger = logging.getLogger(__name__)


class DetectionBridge:
    """Scans sentinel findings from all supervised projects and registers as issues."""

    def __init__(self, issue_manager, projects: Optional[dict] = None,
                 state_dir: Optional[Path] = None):
        """
        Args:
            issue_manager: IssueManager instance (for register() calls)
            projects: dict of {name: ProjectSupervisor} or {name: {"path": Path}}
            state_dir: directory to persist processed findings (survives restarts)
        """
        self.issue_manager = issue_manager
        self.projects = projects or {}
        self._state_dir = state_dir
        self._processed_findings: set[str] = set()  # "project:finding_id"
        self._load_processed()

    def scan_all_projects(self):
        """Called from manager tick(). Reads new findings from all projects."""
        for name, proj in self.projects.items():
            path = self._get_project_path(proj)
            if path:
                self._scan_project(name, path)

    def _scan_project(self, project_name: str, project_path: Path):
        """Read findings.json from a project and register new ones as issues."""
        rt = SetRuntime(str(project_path))
        findings_path = Path(rt.sentinel_dir) / "findings.json"
        if not findings_path.exists():
            return

        try:
            data = json.loads(findings_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not read findings for {project_name}: {e}")
            return

        for finding in data.get("findings", []):
            finding_id = finding.get("id", "")
            status = finding.get("status", "open")

            if status not in ("open",):
                continue  # Skip "pipeline", "fixed", etc.

            key = f"{project_name}:{finding_id}"
            if key in self._processed_findings:
                continue

            self._processed_findings.add(key)

            severity_hint = finding.get("severity", "unknown")

            issue = self.issue_manager.register(
                source="sentinel",
                severity_hint=severity_hint,
                error_summary=finding.get("summary", ""),
                error_detail=finding.get("detail", ""),
                affected_change=finding.get("change"),
                environment=project_name,
                environment_path=str(project_path),
                source_finding_id=finding_id,
            )

            # Mark finding as pipeline-owned so sentinel doesn't double-fix
            if issue:
                self._mark_finding_status(project_path, finding_id, "pipeline")

        self._save_processed()

    def mark_finding_resolved(self, project_path: str, finding_id: str):
        """Mark a finding as fixed when the issue is resolved."""
        if finding_id:
            self._mark_finding_status(Path(project_path), finding_id, "fixed")

    def _mark_finding_status(self, project_path: Path, finding_id: str, status: str):
        """Update a finding's status in findings.json."""
        try:
            rt = SetRuntime(str(project_path))
            findings_path = Path(rt.sentinel_dir) / "findings.json"
            if not findings_path.exists():
                return
            data = json.loads(findings_path.read_text())
            for f in data.get("findings", []):
                if f.get("id") == finding_id:
                    f["status"] = status
                    break
            tmp = str(findings_path) + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, str(findings_path))
            logger.debug("Marked finding %s as %s in %s", finding_id, status, project_path)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Could not mark finding %s: %s", finding_id, e)

    def _save_processed(self):
        """Persist processed findings set to disk."""
        if not self._state_dir:
            return
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            path = self._state_dir / "processed_findings.json"
            tmp = str(path) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(sorted(self._processed_findings), f)
            os.replace(tmp, str(path))
        except OSError as e:
            logger.debug("Could not save processed findings: %s", e)

    def _load_processed(self):
        """Load processed findings set from disk."""
        if not self._state_dir:
            return
        path = self._state_dir / "processed_findings.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._processed_findings = set(data)
                logger.debug("Loaded %d processed findings from disk", len(self._processed_findings))
            except (json.JSONDecodeError, OSError) as e:
                logger.debug("Could not load processed findings: %s", e)

    def _get_project_path(self, proj) -> Optional[Path]:
        """Extract path from project config or supervisor."""
        if isinstance(proj, dict):
            p = proj.get("path")
            return Path(p) if p else None
        if hasattr(proj, "config"):
            return proj.config.path
        if hasattr(proj, "path"):
            return proj.path
        return None

    def reset(self):
        """Reset processed findings tracking (e.g., after restart)."""
        self._processed_findings.clear()
