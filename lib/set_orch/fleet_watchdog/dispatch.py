"""Hand a real finding to the project that owns it — never fix it here (D5).

The request goes through `set-fleet-ask`, so it is an engagement on the owner's own bus: the
fleet starts a desk when the project has none, and the panel can tell answered from not by
the bus's own link. The desk runs on the project's default provider; nothing here passes a
provider, so a fix never runs on GLM.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any, Callable, Dict, List, Optional

from .. import local_config
from .store import OPEN, Store

logger = logging.getLogger(__name__)

KEY_MODE = "watchdog.remediation"
KEY_DAILY = "watchdog.dispatch_daily"
MODES = ("off", "notify", "propose", "auto")
DEFAULT_MODE = "auto"
DEFAULT_DAILY = 3
COOLDOWN_S = 24 * 3600
COUNTER = "dispatches"
SEAT = "set-watchdog"

BRIEF = """The set-watchdog found an anomaly that its triage assigned to this project.

Finding: {probe} [{severity}] on {subject}
Summary: {summary}
Evidence (measured, shape only): {evidence}
Fingerprint: {fp}

Triage brief: {brief}

What to do, in this order:
1. Verify it against the source before believing it (the watchdog can be wrong).
2. If it is real, enter it in this project's bug register with how it was measured.
3. Fix it, and prove the fix (a test that fails without it, then passes).
4. Report done on the bus (reply to this request), naming the commit.
If it is not real, reply saying why, so the watchdog's triage can be rated.

You may NOT deploy anything, trigger a production pipeline, or send anything outward (email,
a message to a person). Those are out of scope for this request."""

Asker = Callable[[str, str, str], Dict[str, Any]]


def mode(get=local_config.get) -> str:
    value = str(get(KEY_MODE, default=DEFAULT_MODE)).strip().lower()
    if value not in MODES:
        logger.warning("watchdog: unknown %s %r; using notify", KEY_MODE, value)
        return "notify"
    return value


def brief_for(rec: Dict[str, Any]) -> str:
    tri = rec.get("triage") or {}
    return BRIEF.format(probe=rec.get("probe"), severity=rec.get("severity"), subject=rec.get("subject"),
                        summary=rec.get("summary"), evidence=rec.get("evidence"), fp=rec.get("fp"),
                        brief=tri.get("brief") or "(none)")


def set_fleet_ask(owner: str, text: str, subject: str) -> Dict[str, Any]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    env["SET_AGENT_NAME"] = SEAT
    try:
        res = subprocess.run(["set-fleet-ask", owner, text, "--subject", subject, "--from", SEAT],
                             capture_output=True, text=True, timeout=180, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": type(exc).__name__}
    if res.returncode != 0:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["?"]
        return {"ok": False, "reason": tail[0][:160]}
    m = re.search(r"engagement[ :]+([A-Za-z0-9_-]+)", res.stdout)
    return {"ok": True, "engagement": m.group(1) if m else None}


def holdback(rec: Dict[str, Any], store: Store, now: float, daily: int) -> Optional[str]:
    """Why this finding may not be dispatched now, or None. Holds in every mode.

    One open dispatch per fingerprint: a dispatched finding stays dispatched until it resolves.
    A finding that resolved and came back is not re-sent within the cooldown of its last send.
    """
    d = rec.get("dispatch") or {}
    if d.get("state") == "dispatched":
        return "already dispatched"
    last = d.get("last_dispatched_at")
    if last and now - float(last) < COOLDOWN_S:
        return "cooldown"
    if store.counter(COUNTER, now) >= daily:
        return "daily cap"
    return None


def _projects() -> set:
    from .probes import _registry
    return {n for n, e in _registry(None).items() if isinstance(e, dict)}


def owner_of(rec: Dict[str, Any], projects: Optional[set] = None) -> Optional[str]:
    """A probe's hint that names a registered project is a measurement (a unit's ExecStart
    path, a module doctor's project) and outranks the model's guess; the model fills a gap.
    Measured 2026-11-24: triage named set-core for two units whose programs live in another
    project's tree."""
    projects = _projects() if projects is None else projects
    hint = rec.get("owner_hint")
    if hint and hint in projects:
        return hint
    tri = rec.get("triage") or {}
    owner = tri.get("owner")
    if owner and owner in projects:
        return owner
    return None


def send(rec: Dict[str, Any], store: Store, now: float, asker: Asker) -> bool:
    owner = owner_of(rec)
    if not owner:
        rec["dispatch"] = {**(rec.get("dispatch") or {}), "state": "held", "reason": "no owner"}
        return False
    result = asker(owner, brief_for(rec), f"watchdog: {rec.get('probe')}")
    if result.get("ok"):
        store.bump(COUNTER, now)
        rec["dispatch"] = {"state": "dispatched", "owner": owner, "engagement": result.get("engagement"),
                           "at": now, "last_dispatched_at": now}
        logger.info("watchdog: dispatched %s to %s (engagement %s)", rec["fp"], owner, result.get("engagement"))
        return True
    rec["dispatch"] = {**(rec.get("dispatch") or {}), "state": "failed", "owner": owner,
                       "reason": result.get("reason"), "at": now}
    logger.warning("watchdog: dispatch of %s to %s failed: %s", rec["fp"], owner, result.get("reason"))
    return False


def dispatch_ready(store: Store, *, now: float, get=local_config.get, asker: Optional[Asker] = None) -> int:
    """Act on the triaged-real open findings according to the mode. Returns how many were sent."""
    m = mode(get)
    if m in ("off", "notify"):
        return 0
    try:
        daily = int(get(KEY_DAILY, default=DEFAULT_DAILY))
    except (TypeError, ValueError):
        daily = DEFAULT_DAILY
    sent = 0
    for rec in store.open_findings(now):
        if (rec.get("triage") or {}).get("verdict") != "real":
            continue
        d = rec.get("dispatch") or {}
        why = holdback(rec, store, now, daily)
        if why == "already dispatched":
            continue
        if why:
            rec["dispatch"] = {**d, "state": "held", "reason": why}
            continue
        if m == "propose":
            rec["dispatch"] = {**d, "state": "proposed", "owner": owner_of(rec)}
            continue
        if send(rec, store, now, asker or set_fleet_ask):
            sent += 1
    return sent


def dispatch_now(store: Store, fp: str, *, now: float, get=local_config.get,
                 asker: Optional[Asker] = None) -> Dict[str, Any]:
    """The panel's dispatch-now: skips the mode, never the limits except the daily cap's
    hold on THIS finding (a person asked)."""
    rec = store.findings.get(fp)
    if rec is None or rec.get("state") != OPEN:
        return {"ok": False, "reason": "no open finding"}
    d = rec.get("dispatch") or {}
    if d.get("state") == "dispatched":
        return {"ok": False, "reason": "already dispatched"}
    ok = send(rec, store, now, asker or set_fleet_ask)
    return {"ok": ok, "dispatch": rec.get("dispatch")}
