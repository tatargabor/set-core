"""The finding store and the tick log — local, mode 600, never inside a repository.

`findings.json` holds one record per fingerprint plus per-probe run times and the day's
counters. `ticks.jsonl` holds one line per tick with counts only. Both are shape-only
(see `probe.py`).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .probe import PROBE_ERROR, Finding

logger = logging.getLogger(__name__)

OPEN, RESOLVED = "open", "resolved"


def state_dir() -> Path:
    override = os.environ.get("SET_WATCHDOG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "set-core" / "watchdog"


def _today(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


class Store:
    def __init__(self, base: Optional[Path] = None):
        self.base = base or state_dir()
        self.path = self.base / "findings.json"
        self.log_path = self.base / "ticks.jsonl"
        self.data: Dict[str, Any] = {"findings": {}, "probes": {}, "counters": {}, "probe_state": {}}

    # ---- persistence -------------------------------------------------------------
    def load(self) -> "Store":
        try:
            raw = json.loads(self.path.read_text())
            if isinstance(raw, dict):
                self.data.update({k: raw.get(k, v) for k, v in self.data.items()})
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            # A corrupt store must not silence the watchdog: keep it aside and start fresh.
            aside = self.path.with_suffix(f".corrupt-{int(time.time())}")
            logger.warning("watchdog: store unreadable (%s); moved to %s", type(exc).__name__, aside)
            try:
                self.path.rename(aside)
            except OSError:
                pass
        return self

    def save(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base, 0o700)
        fd, tmp = tempfile.mkstemp(dir=str(self.base), prefix=".findings-")
        with os.fdopen(fd, "w") as fh:
            json.dump(self.data, fh, indent=1, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def append_tick(self, line: Dict[str, Any]) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        with open(self.log_path, "a") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
        if new:
            os.chmod(self.log_path, 0o600)

    def last_tick(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.log_path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 8192))
                lines = fh.read().decode("utf-8", "replace").strip().splitlines()
        except OSError:
            return None
        for line in reversed(lines):
            try:
                return json.loads(line)
            except ValueError:
                continue
        return None

    # ---- findings ----------------------------------------------------------------
    @property
    def findings(self) -> Dict[str, Dict[str, Any]]:
        return self.data["findings"]

    def upsert(self, finding: Finding, now: float) -> bool:
        """Record an observation. Returns True when this opened a finding (new or reopened)."""
        rec = self.findings.get(finding.fp)
        opened = rec is None or rec.get("state") != OPEN
        if rec is None:
            rec = {"fp": finding.fp, "first_seen": now, "triage": None, "dispatch": None}
            self.findings[finding.fp] = rec
            logger.info("watchdog: finding opened %s %s [%s] %s", finding.probe, finding.fp,
                        finding.severity, finding.subject)
        elif opened:
            logger.info("watchdog: finding reopened %s %s", finding.probe, finding.fp)
            rec["first_seen"] = now
            rec["triage"] = None
            rec["resolved_at"] = None
            # A dispatch belongs to one occurrence; only its time survives, for the cooldown.
            last = (rec.get("dispatch") or {}).get("last_dispatched_at")
            rec["dispatch"] = {"state": "none", "last_dispatched_at": last} if last else None
        elif rec.get("severity") != finding.severity:
            logger.info("watchdog: finding %s severity %s -> %s", finding.fp, rec.get("severity"), finding.severity)
        rec.update({"probe": finding.probe, "severity": finding.severity, "subject": finding.subject,
                    "summary": finding.summary, "evidence": finding.evidence,
                    "owner_hint": finding.owner_hint, "state": OPEN, "last_seen": now})
        return opened

    def resolve_absent(self, probe: str, seen: Set[str], now: float) -> List[str]:
        """A probe that ran and did not report an open fingerprint resolves it (a measurement)."""
        done = []
        for fp, rec in self.findings.items():
            if rec.get("state") != OPEN:
                continue
            owned = rec.get("probe") == probe
            # The error record about this probe resolves when the probe ran cleanly.
            owned_error = rec.get("probe") == PROBE_ERROR and rec.get("subject") == probe
            if (owned or owned_error) and fp not in seen:
                rec["state"], rec["resolved_at"] = RESOLVED, now
                done.append(fp)
                logger.info("watchdog: finding resolved %s %s", rec.get("probe"), fp)
        return done

    def mute(self, fp: str, days: float, now: float) -> bool:
        rec = self.findings.get(fp)
        if rec is None:
            return False
        rec["muted_until"] = now + days * 86400
        logger.info("watchdog: finding %s muted for %s days", fp, days)
        return True

    @staticmethod
    def is_muted(rec: Dict[str, Any], now: float) -> bool:
        until = rec.get("muted_until")
        return bool(until) and float(until) > now

    def open_findings(self, now: float, include_muted: bool = False) -> List[Dict[str, Any]]:
        return [r for r in self.findings.values() if r.get("state") == OPEN
                and (include_muted or not self.is_muted(r, now))]

    def prune(self, now: float, keep_resolved_s: float = 14 * 86400) -> None:
        for fp in [fp for fp, r in self.findings.items()
                   if r.get("state") == RESOLVED and now - float(r.get("resolved_at") or now) > keep_resolved_s
                   and not self.is_muted(r, now)]:
            del self.findings[fp]

    # ---- probes and counters -----------------------------------------------------
    def probe_last_run(self, name: str) -> Optional[float]:
        return (self.data["probes"].get(name) or {}).get("last_run")

    def mark_probe_run(self, name: str, now: float, ok: bool) -> None:
        self.data["probes"][name] = {"last_run": now, "ok": ok}

    def counter(self, name: str, now: float) -> int:
        c = self.data["counters"]
        if c.get("date") != _today(now):
            return 0
        return int(c.get(name, 0))

    def bump(self, name: str, now: float) -> int:
        c = self.data["counters"]
        if c.get("date") != _today(now):
            c.clear()
            c["date"] = _today(now)
        c[name] = int(c.get(name, 0)) + 1
        return c[name]
