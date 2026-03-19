"""Sentinel status/identity management in shared sentinel directory."""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from wt_orch.sentinel.wt_dir import ensure_wt_dir

STATUS_FILE = "status.json"


class SentinelStatus:
    """Manages sentinel identity and heartbeat."""

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.sentinel_dir = ensure_wt_dir(self.project_path)
        self.status_file = os.path.join(self.sentinel_dir, STATUS_FILE)

    def _write(self, data: dict) -> None:
        tmp = self.status_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.status_file)

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
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_event_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "poll_interval_s": poll_interval_s,
            "orchestrator_pid": orchestrator_pid,
        }
        self._write(data)
        return data

    def heartbeat(self) -> None:
        """Update last_event_at timestamp."""
        data = self.get()
        data["last_event_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write(data)

    def deactivate(self) -> None:
        """Mark sentinel as inactive (best-effort on exit)."""
        try:
            data = self.get()
            data["active"] = False
            data["last_event_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._write(data)
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
