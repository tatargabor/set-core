from __future__ import annotations

"""Sentinel status/identity management in shared sentinel directory."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from set_orch.archive import archive_and_write
from set_orch.sentinel.set_dir import ensure_set_dir

logger = logging.getLogger(__name__)

STATUS_FILE = "status.json"


class SentinelStatus:
    """Manages sentinel identity and heartbeat."""

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.sentinel_dir = ensure_set_dir(self.project_path)
        self.status_file = os.path.join(self.sentinel_dir, STATUS_FILE)

    def _write_direct(self, data: dict) -> None:
        tmp = self.status_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.status_file)

    def _write(self, data: dict) -> None:
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        archive_dir = os.path.join(self.sentinel_dir, "archive", "status")
        try:
            archive_and_write(
                self.status_file,
                content,
                archive_dir=archive_dir,
                reason="status-update",
                max_archives=20,
            )
        except OSError as exc:
            logger.warning(
                "archive_and_write failed for status, falling back to direct: %s",
                exc,
            )
            self._write_direct(data)

    def register(
        self,
        member: str,
        orchestrator_pid: Optional[int] = None,
        poll_interval_s: int = 15,
        session_id: str = "",
    ) -> dict:
        """Register sentinel identity on startup."""
        data = {
            "active": True,
            "member": member,
            "session_id": session_id,
            "started_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "last_event_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "poll_interval_s": poll_interval_s,
            "orchestrator_pid": orchestrator_pid,
        }
        self._write(data)
        logger.info("Sentinel registered: member=%s, session=%s, pid=%s", member, session_id, orchestrator_pid)
        return data

    def heartbeat(self) -> None:
        """Update last_event_at timestamp."""
        data = self.get()
        data["last_event_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self._write(data)
        logger.debug("Sentinel heartbeat: session=%s", data.get("session_id", "?"))

    def deactivate(self) -> None:
        """Mark sentinel as inactive (best-effort on exit)."""
        try:
            data = self.get()
            data["active"] = False
            data["last_event_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            self._write(data)
            logger.info("Sentinel deactivated: session=%s", data.get("session_id", "?"))
        except Exception:
            pass  # Best-effort during cleanup

    def get(self) -> dict:
        """Read current status. Returns inactive default if file missing."""
        if not os.path.exists(self.status_file):
            return {"active": False}
        try:
            with open(self.status_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"active": False}

    def is_active(self, staleness_threshold_s: int = 60) -> bool:
        """Check if sentinel is active and recently heard from."""
        data = self.get()
        if not data.get("active"):
            return False
        last = data.get("last_event_at", "")
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last_dt).total_seconds()
            return age < staleness_threshold_s
        except (ValueError, TypeError):
            return False
