"""The watchdog's state for a reader — the CLI's `status` and `GET /api/fleet/watchdog`.

The badge has four states, and STALE is not zero (D6): a watchdog that stopped ticking must
not read as a calm machine.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import local_config
from .store import OPEN, RESOLVED, Store
from .tick import enabled, tick_interval

STALE_FACTOR = 3
RECENT_RESOLVED_S = 24 * 3600
LIST_MAX = 100


def badge_state(last_tick_at: Optional[float], interval_s: int, open_recs: List[Dict[str, Any]],
                now: float) -> str:
    if last_tick_at is None or now - last_tick_at > STALE_FACTOR * interval_s:
        return "stale"
    if any(r.get("severity") == "fail" for r in open_recs):
        return "red"
    return "count" if open_recs else "ok"


def _row(rec: Dict[str, Any], now: float) -> Dict[str, Any]:
    tri = rec.get("triage")
    return {k: rec.get(k) for k in ("fp", "probe", "severity", "subject", "summary", "evidence", "state",
                                     "first_seen", "last_seen", "resolved_at", "muted_until", "dispatch",
                                     "owner_hint")} | {
        "triage": tri, "untriaged": tri is None, "muted": Store.is_muted(rec, now)}


def summary(base=None, *, get=local_config.get, now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    store = Store(base).load()
    last = store.last_tick()
    last_at = float(last["at"]) if last and isinstance(last.get("at"), (int, float)) else None
    interval = int((last or {}).get("interval_s") or tick_interval(get))
    recs = list(store.findings.values())
    open_unmuted = [r for r in recs if r.get("state") == OPEN and not store.is_muted(r, now)]
    muted = [r for r in recs if r.get("state") == OPEN and store.is_muted(r, now)]
    resolved = [r for r in recs if r.get("state") == RESOLVED and now - float(r.get("resolved_at") or 0) < RECENT_RESOLVED_S]
    order = lambda r: (r.get("severity") != "fail", -float(r.get("last_seen") or 0))
    return {
        "schema": "set-watchdog/1",
        "enabled": enabled(get),
        "last_tick_at": last_at,
        "last_tick_age_s": None if last_at is None else round(now - last_at, 1),
        "interval_s": interval,
        "badge": badge_state(last_at, interval, open_unmuted, now),
        "counts": {
            "open": len(open_unmuted),
            "fail": sum(1 for r in open_unmuted if r.get("severity") == "fail"),
            "warn": sum(1 for r in open_unmuted if r.get("severity") == "warn"),
            "untriaged": sum(1 for r in open_unmuted if r.get("triage") is None),
            "dispatched": sum(1 for r in open_unmuted if (r.get("dispatch") or {}).get("state") == "dispatched"),
            "muted": len(muted),
            "resolved_24h": len(resolved),
        },
        "counters": dict(store.data.get("counters") or {}),
        "open": [_row(r, now) for r in sorted(open_unmuted, key=order)[:LIST_MAX]],
        "muted": [_row(r, now) for r in sorted(muted, key=order)[:LIST_MAX]],
        "resolved": [_row(r, now) for r in sorted(resolved, key=lambda r: -float(r.get("resolved_at") or 0))[:LIST_MAX]],
    }


def mute(fp: str, days: float, base=None, now: Optional[float] = None) -> bool:
    from .tick import _Lock
    now = time.time() if now is None else now
    store = Store(base)
    with _Lock(store.base / "tick.lock"):
        store.load()
        ok = store.mute(fp, days, now)
        if ok:
            store.save()
    return ok


def dispatch_now(fp: str, base=None, *, get=local_config.get, now: Optional[float] = None,
                 asker=None) -> Dict[str, Any]:
    from . import dispatch
    from .tick import _Lock
    now = time.time() if now is None else now
    store = Store(base)
    with _Lock(store.base / "tick.lock"):
        store.load()
        result = dispatch.dispatch_now(store, fp, now=now, get=get, asker=asker)
        store.save()
    return result
