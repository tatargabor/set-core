"""The desk — the one session that answers for a project (capability `project-desk`).

Layer 1 (abstract). Measured 2026-11-23: 58 % of two weeks' bus traffic was addressed to a
project NAME, which the bus delivers to every live session of that project — whoever happens
to be open there, in the middle of unrelated work, or nobody at all. A request needs one
session that is there *for* it.

## What the desk is

The live, framework-held agent whose open mandate has kind `desk` for the project. Resolution
asks that one question and never looks at what any other session is doing: a `work` agent is
not picked because it is idle, and it is not picked because it is the only one.

Its label is `<project>-desk`. The label is not the definition, but it buys two things that
already exist: the owner refuses a second agent under a held label, so "one desk per project"
is an enforced invariant and a concurrent second start resolves to "the desk exists"; and the
bus already resolves a fleet label as an address.

## Why every dependency is passed in

Resolution joins the mandate store, the owner, the project registry, the bus and the
runtime's trust record. Each is a callable here, so the decision can be tested without any of
them — and so this module holds no knowledge of where those facts come from.

## Refusals come before the start, and say why

Unknown project, archived, a root that fails the start-location check, not enrolled on the
bus, never trusted by the runtime. "Could not be measured" is its own refusal: starting a
desk on a guess leaves a silent agent behind (measured: a folder the runtime was never
trusted in stops at a prompt and waits for a key).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config
from . import mandate
from .mandate import MandateStore

logger = logging.getLogger(__name__)

#: Seconds to wait for a started desk's bus seat. Measured 2026-11-23: ten starts obtained a
#: seat in 6.9-8.8 s; the bound is about seven times the slowest (measurements.md M4).
READY_TIMEOUT_SECONDS = 60.0
POLL_SECONDS = 1.0

CONFIG_QUIET_MINUTES = "fleet_desk_quiet_minutes"
#: Lowered from 30 on 2026-11-24 at the owner's request: a desk that has answered everything
#: should not hold a seat for half an hour. The window still lets a follow-up request reach
#: the same session, and the listing's close forecast shows the countdown meanwhile.
DEFAULT_QUIET_MINUTES = 5.0

REFUSALS = (
    "unknown-project", "archived", "start-location", "not-on-bus", "not-trusted",
    "unmeasured", "start-refused", "owner-unavailable", "desk-not-ready",
)

SAC = "sac"

__all__ = [
    "READY_TIMEOUT_SECONDS", "REFUSALS", "DeskRefused", "LabelHeld", "StartFailed", "Desk",
    "DeskResolver", "desk_goal", "enrolled_on_bus", "trusted_by_runtime", "quiet_seconds",
    "sweep_decision", "KEEP", "STOP",
]


class DeskRefused(Exception):
    """Resolution did not produce a desk. `reason` is one of `REFUSALS`."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


class LabelHeld(Exception):
    """The owner refused the start because the desk label is already held."""


class StartFailed(Exception):
    """The start did not happen. `reason` is `start-refused` or `owner-unavailable`."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


@dataclass
class Desk:
    project: str
    label: str
    seat: str
    mandate_id: Optional[str]
    started: bool
    pid: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"project": self.project, "label": self.label, "seat": self.seat,
                "mandate_id": self.mandate_id, "started": self.started, "pid": self.pid}


def desk_goal(project: str) -> str:
    return f"Answer requests that other agents address to {project}"


def quiet_seconds() -> float:
    raw = local_config.get(CONFIG_QUIET_MINUTES)
    if raw is None:
        return DEFAULT_QUIET_MINUTES * 60.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"local config {CONFIG_QUIET_MINUTES}={raw!r} is not a number of minutes")
    if value <= 0:
        raise ValueError(f"local config {CONFIG_QUIET_MINUTES}={raw!r} must be positive")
    return value * 60.0


# -- the two measurements resolution needs from outside ------------------------------


def enrolled_on_bus(project: str, *, runner: Callable[..., Any] = subprocess.run) -> Optional[bool]:
    """Whether the project has the bus's session-start hook wired. None when unmeasured.

    Read from the bus's own doctor (`hooks.session-start`), not from the project's settings:
    reading the file ourselves would duplicate the bus's resolution and miss a hook wired
    through a plugin. The `verdict` field is not used — it also warns for reasons that do not
    prevent a seat (measurements.md M6).
    """
    try:
        done = runner([SAC, "doctor", "--json", "--project", project],
                      capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("fleet desk: the bus doctor could not be run (%s)", type(exc).__name__)
        return None
    if getattr(done, "returncode", 1) != 0:
        logger.warning("fleet desk: the bus doctor exited %s", getattr(done, "returncode", "?"))
        return None
    try:
        rows = json.loads(done.stdout or "{}").get("projects")
    except ValueError:
        return None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("project") == project:
            hooks = row.get("hooks")
            return bool(isinstance(hooks, dict) and hooks.get("session-start"))
    # The doctor answered and does not know the project: it has no hooks there.
    return False


def trusted_by_runtime(root: str, *, record_path: Optional[str] = None) -> Optional[bool]:
    """Whether the runtime has a recorded trust decision for this folder. None when unmeasured.

    An untrusted folder stops an unattended start at a prompt. A missing entry is `False`:
    the runtime has never been opened there, which is exactly the case that hangs.
    """
    path = record_path or os.path.join(os.path.expanduser("~"), ".claude.json")
    try:
        with open(path, encoding="utf-8") as handle:
            projects = json.load(handle).get("projects")
    except (OSError, ValueError) as exc:
        logger.warning("fleet desk: the runtime's trust record is unreadable (%s)", type(exc).__name__)
        return None
    if not isinstance(projects, dict):
        return None
    entry = projects.get(root) or projects.get(os.path.realpath(root))
    return bool(isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True)


# -- resolution ------------------------------------------------------------------------


class DeskResolver:
    """Find a project's desk, or start one.

    `live_agents()` returns the inventory's agent rows (each with `pid`, `population`,
    `terminal_label`, `seat`, `session_id`, `scope`), or None when it cannot be read.
    `projects()` returns registry rows (`name`, `root`, `archived`).
    `start(...)` starts an agent and returns its payload; it raises `LabelHeld` or `StartFailed`.
    """

    def __init__(
        self,
        *,
        mandates: MandateStore,
        live_agents: Callable[[], Optional[List[Dict[str, Any]]]],
        projects: Callable[[], List[Dict[str, Any]]],
        start: Callable[..., Dict[str, Any]],
        start_location_ok: Callable[[str], bool],
        enrolled: Callable[[str], Optional[bool]] = enrolled_on_bus,
        trusted: Callable[[str], Optional[bool]] = trusted_by_runtime,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        ready_timeout: float = READY_TIMEOUT_SECONDS,
    ) -> None:
        self.mandates = mandates
        self._live_agents = live_agents
        self._projects = projects
        self._start = start
        self._start_location_ok = start_location_ok
        self._enrolled = enrolled
        self._trusted = trusted
        self._clock = clock
        self._sleep = sleep
        self.ready_timeout = ready_timeout

    # -- finding ----------------------------------------------------------------

    def _live_desk_row(self, project: str) -> Optional[Dict[str, Any]]:
        """The inventory row of the project's live desk, with its mandate id attached."""
        agents = self._live_agents()
        if agents is None:
            raise DeskRefused("unmeasured", "the fleet inventory could not be read")
        records = self.mandates.all()
        for row in agents:
            # Only an agent the framework holds can be a desk: it is the only kind that was
            # started with a mandate, and the only kind whose label is an enforced identity.
            if row.get("population") != "started-here":
                continue
            held = mandate.join(records, pid=row.get("pid"), unit=row.get("unit"),
                                session_id=row.get("session_id"))
            if not (held and held["kind"] == "desk" and held["project"] == project):
                continue
            if held["ended"] is None:
                return {**row, "mandate_id": held["id"]}
            # The agent is in the live listing and carries this desk mandate, yet the record
            # says it ended as missing: that end was written during a blind spot (measured
            # 2026-11-24 — the running desk kept its label, so no new desk could start and the
            # request failed `desk-not-ready`). Being live outranks the record; re-open it.
            if (held["ended"] or {}).get("reason") == "ended" and self.mandates.reopen(held["id"]):
                logger.info("fleet desk: re-adopted a live desk whose mandate had ended as missing "
                            "(mandate %s, pid %s)", held["id"], row.get("pid"))
                return {**row, "mandate_id": held["id"]}
        return None

    def find(self, project: str) -> Optional[Dict[str, Any]]:
        return self._live_desk_row(project)

    def _wait_for_seat(self, project: str, *, started: bool) -> Desk:
        """Poll until the desk has a bus seat, or fail with `desk-not-ready`."""
        deadline = self._clock() + self.ready_timeout
        while True:
            row = self._live_desk_row(project)
            if row and row.get("seat"):
                return Desk(project=project, label=row.get("terminal_label") or mandate.desk_label(project),
                            seat=row["seat"], mandate_id=row.get("mandate_id"),
                            started=started, pid=row.get("pid"))
            if self._clock() >= deadline:
                logger.warning("fleet desk: desk of a project has no bus seat after %.0f s (started=%s)",
                               self.ready_timeout, started)
                raise DeskRefused(
                    "desk-not-ready",
                    f"the desk did not obtain a bus seat within {self.ready_timeout:.0f} seconds")
            self._sleep(POLL_SECONDS)

    # -- resolving --------------------------------------------------------------

    def _project(self, name: str) -> Dict[str, Any]:
        for row in self._projects():
            if row.get("name") == name:
                return row
        raise DeskRefused("unknown-project", f"{name} is not a registered project")

    def resolve(self, project: str, *, requested_by: Optional[str]) -> Desk:
        """The project's desk, started if none is live. Raises `DeskRefused` with a reason."""
        row = self._project(project)
        if row.get("archived"):
            raise DeskRefused("archived", f"{project} is archived and is not to be developed")
        root = row.get("root") or row.get("path")
        if not root:
            raise DeskRefused("unknown-project", f"{project} has no recorded root")

        if self._live_desk_row(project) is not None:
            logger.info("fleet desk: resolved to the live desk (started=False)")
            return self._wait_for_seat(project, started=False)

        if not self._start_location_ok(root):
            raise DeskRefused("start-location", f"{project}'s root is not a place an agent may be started")
        enrolled = self._enrolled(project)
        if enrolled is None:
            raise DeskRefused("unmeasured", "whether the project is on the bus could not be measured")
        if not enrolled:
            raise DeskRefused("not-on-bus",
                              f"{project} is not enrolled on the bus; enrol it (`sac install` in the project)")
        trusted = self._trusted(root)
        if trusted is None:
            raise DeskRefused("unmeasured", "the runtime's trust record could not be read")
        if not trusted:
            raise DeskRefused("not-trusted",
                              f"the runtime has never been trusted in {project}'s folder; open it once by hand")

        label = mandate.desk_label(project)
        record = self.mandates.create(
            kind="desk", goal=desk_goal(project), project=project, cwd=root, label=label,
            requested_by=requested_by, source="start", carrier=True,
        )
        try:
            started = self._start(label=label, cwd=root, project=project, mandate_id=record["id"],
                                  mandate_kind="desk", requested_by=requested_by)
        except LabelHeld:
            # Somebody else's start won the race. That desk is the desk; ours never existed.
            self.mandates.remove(record["id"])
            logger.info("fleet desk: the desk label was already held; resolving to that desk")
            return self._wait_for_seat(project, started=False)
        except StartFailed as exc:
            self.mandates.remove(record["id"])
            raise DeskRefused(exc.reason, str(exc)) from exc
        unit = started.get("unit") if isinstance(started, dict) else None
        if unit:
            self.mandates.update(record["id"], unit=unit)
        logger.info("fleet desk: started a desk (mandate %s, pid %s)", record["id"],
                    started.get("pid") if isinstance(started, dict) else None)
        return self._wait_for_seat(project, started=True)


# -- the quiet sweep -------------------------------------------------------------------

KEEP = "keep"
STOP = "stop"


def _keep_reason(row: Dict[str, Any], live_engagements: Optional[int],
                 asking: Optional[int] = 0) -> Optional[str]:
    """Why the desk is kept on every condition EXCEPT the elapsed quiet time; None when none.

    Shared by the sweep and the close forecast, so the countdown a reader sees can never
    disagree with what the sweep will do. `asking` counts the live engagements this desk
    itself asked of another project: a desk waiting on an answer is quiet, not finished
    (measured 2026-11-24: one was swept while its own request was open, so the answer had
    nobody to come back to).
    """
    if live_engagements is None or asking is None:
        return "engagements-unmeasured"
    if live_engagements > 0:
        return "engagement-open"
    if asking > 0:
        return "asking-open"
    state = row.get("state")
    if state is None or state == "unknown":
        return "state-unmeasured"
    if state != "quiet":
        return f"state-{state}"
    moved = row.get("last_movement_seconds")
    if not isinstance(moved, (int, float)) or isinstance(moved, bool):
        return "movement-unmeasured"
    return None


def sweep_decision(row: Dict[str, Any], *, live_engagements: Optional[int],
                   quiet_after: float, asking: Optional[int] = 0) -> tuple:
    """(decision, why) for one live desk row.

    Stopped only when everything that could argue for keeping it was MEASURED and says quiet:
    no resolving-or-open engagement, a state that is quiet, and a last movement older than the
    bound. Anything unmeasured keeps the desk — a desk left running costs a seat, a desk
    stopped mid-answer costs the answer.
    """
    why = _keep_reason(row, live_engagements, asking)
    if why:
        return KEEP, why
    if row["last_movement_seconds"] <= quiet_after:
        return KEEP, "recent-movement"
    return STOP, "desk-quiet"


def close_forecast(row: Dict[str, Any], *, live_engagements: Optional[int],
                   quiet_after: float, asking: Optional[int] = 0) -> Optional[Dict[str, float]]:
    """`{closes_in_seconds, bound_seconds}` when only the quiet time still keeps the desk.

    None when anything else keeps it — an open engagement, a working state, an unmeasured
    input — because a countdown that is not going to run out is a false value. The seconds
    are never negative: past the bound the sweep acts on its next round.
    """
    if _keep_reason(row, live_engagements, asking):
        return None
    remaining = max(0.0, float(quiet_after) - float(row["last_movement_seconds"]))
    return {"closes_in_seconds": round(remaining, 1), "bound_seconds": float(quiet_after)}
