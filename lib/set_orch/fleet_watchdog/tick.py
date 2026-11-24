"""One watchdog tick: lock, run the due probes, record, triage the new, dispatch, exit.

Stateless between runs by design (D1): everything a tick knows comes from the store, so a
tick that dies loses nothing but its own observations, and nothing grows across a day.
"""

from __future__ import annotations

import fcntl
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config
from .probe import PROBE_ERROR, Context, Finding, Probe, registry
from .store import Store

logger = logging.getLogger(__name__)

KEY_ENABLED = "watchdog.enabled"
KEY_INTERVAL = "watchdog.interval_s"
DEFAULT_INTERVAL_S = 300


def enabled(get=local_config.get) -> bool:
    return str(get(KEY_ENABLED, default="true")).strip().lower() not in ("false", "0", "off", "no")


def tick_interval(get=local_config.get) -> int:
    try:
        return int(get(KEY_INTERVAL, default=DEFAULT_INTERVAL_S))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_S


class Locked(Exception):
    def __init__(self, holder: str):
        super().__init__(holder)
        self.holder = holder


class _Lock:
    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def __enter__(self) -> "_Lock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fh.seek(0)
            holder = self.fh.read().strip() or "?"
            self.fh.close()
            raise Locked(holder)
        self.fh.seek(0)
        self.fh.truncate()
        self.fh.write(str(os.getpid()))
        self.fh.flush()
        return self

    def __exit__(self, *exc) -> None:
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()


def _due(probe: Probe, store: Store, now: float, get) -> bool:
    last = store.probe_last_run(probe.name)
    return last is None or now - float(last) >= probe.interval(get) - 5  # 5 s timer jitter


def run_probes(probes: Dict[str, Probe], store: Store, ctx: Context, force: bool = False) -> Dict[str, Any]:
    ran: List[str] = []
    opened: List[str] = []
    resolved: List[str] = []
    for name, probe in probes.items():
        if not force and not _due(probe, store, ctx.now, ctx.get):
            continue
        ran.append(name)
        try:
            found = probe.collect(ctx)
        except Exception as exc:  # noqa: BLE001 — one probe never stops the others (AC-2)
            logger.warning("watchdog: probe %s raised %s", name, type(exc).__name__, exc_info=True)
            err = Finding(PROBE_ERROR, "warn", name, f"probe {name} raised {type(exc).__name__}",
                          {"exception": type(exc).__name__}, owner_hint="set-core")
            if store.upsert(err, ctx.now):
                opened.append(err.fp)
            store.mark_probe_run(name, ctx.now, ok=False)
            continue
        seen = set()
        for f in found:
            seen.add(f.fp)
            if store.upsert(f, ctx.now):
                opened.append(f.fp)
        resolved += store.resolve_absent(name, seen, ctx.now)
        store.mark_probe_run(name, ctx.now, ok=True)
    return {"ran": ran, "opened": opened, "resolved": resolved}


def tick(*, base: Optional[Path] = None, get=local_config.get, now: Optional[float] = None,
         probes: Optional[Dict[str, Probe]] = None, force: bool = False,
         triage: Optional[Callable[..., Any]] = None,
         dispatch: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """Run one tick. Returns the tick-log line (counts only)."""
    store = Store(base)
    if not enabled(get):
        logger.info("watchdog: disabled (%s); tick skipped", KEY_ENABLED)
        return {"skipped": "disabled"}
    started = time.time() if now is None else now
    try:
        with _Lock(store.base / "tick.lock"):
            store.load()
            ctx = Context(now=started, get=get, states=store.data.setdefault("probe_state", {}))
            result = run_probes(probes if probes is not None else registry(), store, ctx, force=force)
            triaged = dispatched = 0
            if result["opened"]:
                try:
                    if triage is None:
                        from .triage import triage_new as triage
                    triaged = triage(store, result["opened"], now=started, get=get) or 0
                except Exception:  # noqa: BLE001 — a failed triage leaves findings untriaged
                    logger.warning("watchdog: triage failed; findings stay untriaged", exc_info=True)
            try:
                if dispatch is None:
                    from .dispatch import dispatch_ready as dispatch
                dispatched = dispatch(store, now=started, get=get) or 0
            except Exception:  # noqa: BLE001
                logger.warning("watchdog: dispatch step failed", exc_info=True)
            store.prune(started)
            line = {"at": started, "duration_s": round(time.time() - started, 3) if now is None else 0,
                    "ran": result["ran"], "new": len(result["opened"]), "resolved": len(result["resolved"]),
                    "open": len(store.open_findings(started)), "triaged": triaged, "dispatched": dispatched,
                    "interval_s": tick_interval(get)}
            store.save()
            store.append_tick(line)
            logger.info("watchdog: tick ran=%d new=%d resolved=%d open=%d", len(result["ran"]),
                        line["new"], line["resolved"], line["open"])
            return line
    except Locked as held:
        logger.info("watchdog: another tick holds the lock (pid %s); this one exits", held.holder)
        return {"skipped": "locked", "holder": held.holder}
