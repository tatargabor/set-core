from __future__ import annotations

"""Structured findings storage in shared sentinel directory."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from set_orch.sentinel.set_dir import ensure_set_dir

logger = logging.getLogger(__name__)

FINDINGS_FILE = "findings.json"


def _empty_findings() -> dict:
    return {"run_id": "", "findings": [], "assessments": []}


def _next_finding_id(findings: list[dict]) -> str:
    """Generate next sequential finding ID (F001, F002, ...)."""
    if not findings:
        return "F001"
    max_num = 0
    for f in findings:
        fid = f.get("id", "")
        if fid.startswith("F") and fid[1:].isdigit():
            max_num = max(max_num, int(fid[1:]))
    return f"F{max_num + 1:03d}"


class SentinelFindings:
    """CRUD manager for sentinel findings.

    Findings are stored as a JSON object with:
    - run_id: current run identifier
    - findings: array of finding objects
    - assessments: array of assessment objects
    """

    def __init__(self, project_path: str, event_logger=None):
        """Initialize findings manager.

        Args:
            project_path: Root of the project.
            event_logger: Optional SentinelEventLogger for cross-module event emission.
        """
        self.project_path = os.path.abspath(project_path)
        self.sentinel_dir = ensure_set_dir(self.project_path)
        self.findings_file = os.path.join(self.sentinel_dir, FINDINGS_FILE)
        self._event_logger = event_logger

    def _read(self) -> dict:
        if not os.path.exists(self.findings_file):
            return _empty_findings()
        try:
            with open(self.findings_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return _empty_findings()

    def _write(self, data: dict) -> None:
        tmp = self.findings_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.findings_file)

    def add(
        self,
        severity: str,
        change: str,
        summary: str,
        detail: str = "",
        iteration: Optional[int] = None,
    ) -> dict:
        """Add a new finding. Returns the created finding dict."""
        data = self._read()
        finding_id = _next_finding_id(data["findings"])
        finding = {
            "id": finding_id,
            "severity": severity,
            "change": change,
            "summary": summary,
            "detail": detail,
            "discovered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "open",
            "iteration": iteration,
        }
        data["findings"].append(finding)
        self._write(data)
        logger.info("Finding recorded: %s %s — %s (change=%s)", finding_id, severity, summary, change)

        # Cross-module: emit finding event
        if self._event_logger:
            self._event_logger.finding(
                finding_id=finding_id,
                severity=severity,
                change=change,
                summary=summary,
            )

        return finding

    def update(self, finding_id: str, **kwargs) -> Optional[dict]:
        """Update a finding by ID. Returns updated finding or None if not found."""
        data = self._read()
        for f in data["findings"]:
            if f["id"] == finding_id:
                f.update(kwargs)
                self._write(data)
                logger.info("Finding updated: %s — %s", finding_id, kwargs)
                return f
        logger.warning("Finding not found for update: %s", finding_id)
        return None

    def list(self, status: Optional[str] = None) -> list[dict]:
        """List findings, optionally filtered by status."""
        data = self._read()
        findings = data["findings"]
        if status:
            findings = [f for f in findings if f.get("status") == status]
        return findings

    def assess(
        self,
        scope: str,
        summary: str,
        recommendation: str = "",
    ) -> dict:
        """Add a phase/run-level assessment."""
        data = self._read()
        assessment = {
            "scope": scope,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": summary,
            "recommendation": recommendation,
        }
        data["assessments"].append(assessment)
        self._write(data)
        logger.info("Assessment recorded: scope=%s — %s", scope, summary)

        if self._event_logger:
            self._event_logger.assessment(scope=scope, summary=summary)

        return assessment

    def get_all(self) -> dict:
        """Return the full findings document."""
        return self._read()
