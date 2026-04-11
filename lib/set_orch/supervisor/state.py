"""SupervisorStatus — persisted state for the set-supervisor daemon.

Lives at `<project>/.set/supervisor/status.json`. Contains:

- daemon PID + start time
- orchestrator PID (the subprocess the daemon wraps)
- rapid_crashes counter + window
- cursor into events.jsonl (byte offset so we pick up where we left off)
- counters for trigger fires (Phase 2 — reserved)
- last_canary_at timestamp (Phase 2 — reserved)

The status file is the single source of truth for daemon restart. If the
daemon crashes and a manager-level watchdog restarts it, the new daemon
reads this file and resumes from the same cursor + counters.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SupervisorStatus:
    """Persisted daemon state. JSON-serializable."""

    daemon_pid: int = 0
    daemon_started_at: str = ""
    orchestrator_pid: int = 0
    orchestrator_started_at: str = ""
    spec: str = ""
    poll_cycle: int = 0
    rapid_crashes: int = 0
    rapid_crashes_window_start: float = 0.0
    events_cursor: int = 0  # byte offset into orchestration-events.jsonl
    last_canary_at: str = ""
    trigger_counters: dict = field(default_factory=dict)
    last_event_at: str = ""
    status: str = "starting"  # starting|running|stopping|stopped|crashed
    stop_reason: str = ""


def _status_path(project_path: str | Path) -> Path:
    return Path(project_path) / ".set" / "supervisor" / "status.json"


def read_status(project_path: str | Path) -> SupervisorStatus:
    """Read SupervisorStatus from disk; return default if missing."""
    p = _status_path(project_path)
    if not p.is_file():
        return SupervisorStatus()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read supervisor status at %s: %s — returning default", p, exc)
        return SupervisorStatus()
    # Drop unknown keys to tolerate schema evolution
    known = {f for f in SupervisorStatus.__dataclass_fields__}
    clean = {k: v for k, v in data.items() if k in known}
    return SupervisorStatus(**clean)


def write_status(project_path: str | Path, status: SupervisorStatus) -> None:
    """Atomically write SupervisorStatus to disk (tmpfile + rename)."""
    p = _status_path(project_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(status)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp, p)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        logger.warning("Could not write supervisor status to %s: %s", p, exc)
