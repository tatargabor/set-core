"""Audit Log — append-only JSONL event logging for issue management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLog:
    """Append-only JSONL audit trail for issue state transitions and actions."""

    def __init__(self, project_path: Path):
        self.audit_path = project_path / ".set" / "issues" / "audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        issue_id: str,
        action: str,
        **detail,
    ):
        """Append an audit entry."""
        entry = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "issue_id": issue_id,
            "action": action,
            **detail,
        }
        with open(self.audit_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_group(
        self,
        group_id: str,
        action: str,
        **detail,
    ):
        """Append an audit entry for a group action."""
        entry = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "group_id": group_id,
            "action": action,
            **detail,
        }
        with open(self.audit_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read(
        self,
        since: Optional[float] = None,
        limit: int = 200,
        issue_id: Optional[str] = None,
    ) -> list[dict]:
        """Read audit entries, newest first.

        Args:
            since: Unix epoch timestamp — only return entries after this time.
            limit: Max entries to return.
            issue_id: Filter to entries for this issue.
        """
        if not self.audit_path.exists():
            return []

        entries = []
        for line in self.audit_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if issue_id and entry.get("issue_id") != issue_id:
                continue

            if since:
                try:
                    ts = datetime.fromisoformat(entry["ts"])
                    if ts.timestamp() <= since:
                        continue
                except (ValueError, KeyError):
                    continue

            entries.append(entry)

        # Newest first, limited
        entries.reverse()
        return entries[:limit]

    def count(self) -> int:
        """Count total audit entries."""
        if not self.audit_path.exists():
            return 0
        return sum(1 for line in self.audit_path.read_text().splitlines() if line.strip())
