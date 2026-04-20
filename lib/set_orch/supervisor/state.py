"""SupervisorStatus — persisted state for the set-supervisor daemon.

Lives at LineagePaths.supervisor_status. Contains:

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
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SupervisorStatus:
    """Persisted daemon state. JSON-serializable."""

    daemon_pid: int = 0
    daemon_started_at: str = ""
    orchestrator_pid: int = 0
    orchestrator_started_at: str = ""
    spec: str = ""
    # Section 4c.1: normalised lineage id (project-relative POSIX path of
    # `spec`).  Kept alongside the legacy `spec` field for backwards
    # compatibility with consumers reading raw status.json snapshots.
    spec_lineage_id: str = ""
    poll_cycle: int = 0
    rapid_crashes: int = 0
    rapid_crashes_window_start: float = 0.0
    events_cursor: int = 0  # byte offset into the events stream (LineagePaths.events_file)
    last_canary_at: str = ""
    trigger_counters: dict = field(default_factory=dict)
    last_event_at: str = ""
    status: str = "starting"  # starting|running|stopping|stopped|crashed
    stop_reason: str = ""

    # ── Phase 2: anomaly + canary state ──────────────────
    # Rolling list of recent ephemeral Claude spawn timestamps (epoch seconds)
    # Used by triggers.py for the global hourly rate limit. Pruned on each
    # rate-limit check to bound size.
    ephemeral_spawns_ts: list = field(default_factory=list)

    # Retry budget counters keyed by f"{trigger_type}:{change_name}" (or
    # just trigger_type for change-less triggers). Once a key reaches the
    # configured budget, that (trigger, change) pair stops firing for the
    # remainder of the daemon's lifetime.
    trigger_attempts: dict = field(default_factory=dict)

    # Canary warn rate-limit log: signature → ISO timestamp of last warn.
    # Same signature within 30 min is downgraded to "note".
    canary_warn_log: dict = field(default_factory=dict)

    # Learned event type whitelist — supplements the hardcoded KNOWN_EVENT_TYPES
    # in anomaly.py. The unknown_event_type detector adds to this set on first
    # occurrence so subsequent occurrences are silent.
    known_event_types: list = field(default_factory=list)

    # State stall tracking — last observed state.json mtime + when it changed.
    last_state_mtime: float = 0.0
    last_state_change_at: float = 0.0

    # Log silence + error rate spike tracking — last observed log size + when
    # it grew, plus a rolling baseline used by detect_error_rate_spike.
    last_log_size: int = 0
    last_log_growth_at: float = 0.0
    error_baseline: dict = field(default_factory=dict)

    # Transition-based trigger state — last observed per-change status and
    # orchestration-level status. Detectors fire only when the current value
    # differs from the persisted one, so a stable `failed` state does not
    # re-fire on every poll.
    last_change_statuses: dict = field(default_factory=dict)
    last_orch_status: str = ""
    crossed_token_stall_thresholds: list = field(default_factory=list)
    # Fires exactly once per daemon lifetime. Prevents terminal_state from
    # re-firing after a restart against a pre-existing dead+terminal state.
    terminal_state_fired: bool = False

    # Permanent error surface — populated by _restart_orchestrator() when
    # stderr matches a PERMANENT_ERROR_SIGNALS entry. When set, the daemon
    # halts immediately and the manager API surfaces this to the dashboard.
    permanent_error: Optional[dict] = None

    # Trigger back-off windows — per-tuple suppression of triggers whose
    # retry budget is exhausted. Distinct from `trigger_attempts` (which
    # tracks cumulative attempts for the lifetime budget): this tracks the
    # next time a specific (trigger, change, reason_hash) tuple is allowed
    # to emit again. Key format: f"{trigger}::{change}::{reason_hash}" where
    # `change` is "" for orchestration-scoped triggers (e.g. log_silence).
    # Value shape: {"step": int, "back_off_until": float}. Exponential steps
    # cap at 600s. Cleared for a tuple when the detector's condition no
    # longer holds.
    trigger_backoffs: dict = field(default_factory=dict)


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
    """Atomically write SupervisorStatus to disk (tmpfile + rename).

    Section 4c.1 of run-history-and-phase-continuity: derive
    `spec_lineage_id` from `spec` if the caller didn't set it, so every
    status.json carries the normalised lineage even for legacy callers.
    """
    p = _status_path(project_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if status.spec and not status.spec_lineage_id:
        try:
            from set_orch.types import canonicalise_spec_path
            status.spec_lineage_id = canonicalise_spec_path(
                status.spec, str(project_path),
            )
        except (ValueError, OSError) as exc:
            logger.debug("write_status: cannot canonicalise spec=%r: %s",
                         status.spec, exc)

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


def append_status_history(project_path: str | Path, status: SupervisorStatus) -> None:
    """Append the current status to `status-history.jsonl` (Section 4c.2).

    Called from the sentinel clean-stop path so each session's status
    metadata is retained for later browsing.  Best-effort — logged at
    WARNING on failure, never raises.
    """
    history_path = (
        Path(project_path) / ".set" / "supervisor" / "status-history.jsonl"
    )
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        # Make sure spec_lineage_id is filled in even if write_status was
        # never called for this status object.
        if status.spec and not status.spec_lineage_id:
            try:
                from set_orch.types import canonicalise_spec_path
                status.spec_lineage_id = canonicalise_spec_path(
                    status.spec, str(project_path),
                )
            except (ValueError, OSError):
                pass
        rec = asdict(status)
        rec["rotated_at"] = (
            __import__("datetime")
            .datetime.now()
            .astimezone()
            .isoformat(timespec="milliseconds")
        )
        with open(history_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        logger.info(
            "supervisor_status_history: appended (lineage=%s)",
            status.spec_lineage_id,
        )
    except OSError as exc:
        logger.warning(
            "supervisor_status_history: append failed: %s", exc,
        )
