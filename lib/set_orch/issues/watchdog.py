"""Diagnosed-state timeout watchdog.

Emits `ISSUE_DIAGNOSED_TIMEOUT` events when an issue has been stuck in
`DIAGNOSED` state longer than `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS`.
This is a safety net: the normal flow is that a diagnosed issue is
promoted by the auto-fix policy to FIXING within seconds. If that path
stalls (agent crash, missing fix policy, operator inattention) the
watchdog surfaces it so the supervisor can raise an alert.

The watchdog is invoked from the engine's periodic maintenance path.
It reads the issues registry (LineagePaths.issues_registry) directly — there is no global
issue manager singleton in every execution context, so this module
reuses `IssueRegistry` for file access but does NOT transition state.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .models import DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS, IssueState
from .registry import IssueRegistry

logger = logging.getLogger(__name__)


# Process-local dedup state keyed by project path. Callers that pass
# state=None automatically share this cache, so the engine's monitor
# loop gets cross-poll dedup without having to thread a dict through.
_WATCHDOG_STATE: dict[str, dict] = {}


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def check_diagnosed_timeouts(
    project_path: Path,
    *,
    timeout_secs: int = DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS,
    event_bus: Any = None,
    state: Optional[dict] = None,
) -> list[dict]:
    """Scan the issue registry for issues stuck in `diagnosed` beyond the timeout.

    For each hit, emit an `ISSUE_DIAGNOSED_TIMEOUT` event with
    `{issue_id, change, age_seconds}` and log a WARNING. Returns the
    list of timed-out issue descriptors for caller inspection.

    Non-blocking: any exception reading the registry is swallowed with
    a WARNING so the engine's maintenance loop keeps running.

    Dedup: when `state` is None, the function uses a process-local
    cache keyed by `project_path` so cross-poll dedup works without
    the caller threading any state. Tests that need isolated dedup
    per call should pass an explicit dict.
    """
    hits: list[dict] = []
    try:
        registry = IssueRegistry(project_path)
    except Exception as exc:
        logger.warning(
            "Issue watchdog: could not open registry at %s: %s",
            project_path,
            exc,
        )
        return hits

    if state is None:
        state = _WATCHDOG_STATE.setdefault(str(project_path), {})

    now = datetime.now(timezone.utc)
    recorded_seen = set(state.get("diagnosed_timeout_seen", []))
    new_seen = set(recorded_seen)

    for issue in registry.all_issues():
        if issue.state != IssueState.DIAGNOSED:
            continue
        diagnosed_at = _parse_iso(issue.diagnosed_at or "")
        if diagnosed_at is None:
            # Backfill from updated_at when the field was missing (older
            # issues created before this feature landed).
            diagnosed_at = _parse_iso(issue.updated_at or "")
        if diagnosed_at is None:
            continue
        age = (now - diagnosed_at).total_seconds()
        if age < timeout_secs:
            continue
        # Dedup — only emit once per issue until it leaves diagnosed state.
        if issue.id in recorded_seen:
            continue

        hit = {
            "issue_id": issue.id,
            "change": issue.affected_change or "",
            "age_seconds": int(age),
        }
        hits.append(hit)
        new_seen.add(issue.id)
        logger.warning(
            "ISSUE_DIAGNOSED_TIMEOUT: %s stuck in diagnosed for %ds "
            "(limit %ds, change=%s)",
            issue.id, int(age), timeout_secs, issue.affected_change or "-",
        )
        if event_bus is not None:
            try:
                event_bus.emit(
                    "ISSUE_DIAGNOSED_TIMEOUT",
                    change=issue.affected_change or "",
                    data=hit,
                )
            except Exception:
                logger.debug("event_bus.emit failed for ISSUE_DIAGNOSED_TIMEOUT", exc_info=True)

    # Purge dedup entries for issues that have since left diagnosed.
    current_diagnosed_ids = {
        i.id for i in registry.all_issues() if i.state == IssueState.DIAGNOSED
    }
    new_seen = new_seen & current_diagnosed_ids
    state["diagnosed_timeout_seen"] = sorted(new_seen)
    return hits


def _reset_watchdog_state_for_tests() -> None:
    """Clear the process-local dedup cache. For unit tests only."""
    _WATCHDOG_STATE.clear()
