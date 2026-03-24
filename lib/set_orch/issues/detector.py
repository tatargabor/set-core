"""Detection Bridge — reads sentinel findings and converts to issues."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .models import now_iso

logger = logging.getLogger(__name__)


class DetectionBridge:
    """Scans sentinel findings from all supervised projects and registers as issues."""

    def __init__(self, issue_manager, projects: Optional[dict] = None):
        """
        Args:
            issue_manager: IssueManager instance (for register() calls)
            projects: dict of {name: ProjectSupervisor} or {name: {"path": Path}}
        """
        self.issue_manager = issue_manager
        self.projects = projects or {}
        self._processed_findings: set[str] = set()  # "project:finding_id"

    def scan_all_projects(self):
        """Called from manager tick(). Reads new findings from all projects."""
        for name, proj in self.projects.items():
            path = self._get_project_path(proj)
            if path:
                self._scan_project(name, path)

    def _scan_project(self, project_name: str, project_path: Path):
        """Read findings.json from a project and register new ones as issues."""
        findings_path = project_path / ".set" / "sentinel" / "findings.json"
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

            if status != "open":
                continue

            key = f"{project_name}:{finding_id}"
            if key in self._processed_findings:
                continue

            self._processed_findings.add(key)

            severity_hint = finding.get("severity", "info")

            self.issue_manager.register(
                source="sentinel",
                error_summary=finding.get("summary", ""),
                error_detail=finding.get("detail", ""),
                affected_change=finding.get("change"),
                environment=project_name,
                environment_path=str(project_path),
                source_finding_id=finding_id,
            )

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
