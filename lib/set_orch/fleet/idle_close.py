"""Close the fleet's long-idle interactive agents — the decision, the stop, the record.

An interactive agent nobody has typed into for days still costs tokens: watches, timers and bus
messages wake it, and every wake re-reads its whole context. This closes such agents through the
dashboard's own stop route, and the roster keeps them resumable.

**The signal is the owner's last input, never the last movement.** Measured on the live fleet the
day this was written: every abandoned agent had moved within the hour, because something woke it.
Movement is the cost being removed, so it cannot also be the evidence of use.

**Doubt keeps the agent.** An unmeasured idle time, a tool running right now, or no terminal label
(not framework-started, so the stop route cannot reach it) each keep the agent and say why. A wrongly
kept agent costs tokens until the next run; a wrongly closed one interrupts the owner's work.

Usage (through `bin/set-fleet-idle-close`):

    set-fleet-idle-close [--hours N] [--dry-run] [--json]
    set-fleet-idle-close install-timer [--at HH:MM]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config

logger = logging.getLogger(__name__)

CONFIG_KEY = "fleet_idle_close_hours"
DEFAULT_HOURS = 48.0
DEFAULT_BASE_URL = "http://localhost:7400"
UNIT_NAME = "set-fleet-idle-close"

CLOSE = "close"
KEEP_RECENT = "recent"
KEEP_UNMEASURED = "unmeasured"
KEEP_BUSY = "busy"
UNREACHABLE = "unreachable"
NOT_INTERACTIVE = "not-interactive"


def threshold_hours(cli_hours: Optional[float] = None) -> float:
    """`--hours`, else local config, else 48. A non-number in config is refused, not guessed."""
    if cli_hours is not None:
        return float(cli_hours)
    raw = local_config.get(CONFIG_KEY)
    if raw is None:
        return DEFAULT_HOURS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"local config {CONFIG_KEY}={raw!r} is not a number of hours")
    if value <= 0:
        raise ValueError(f"local config {CONFIG_KEY}={raw!r} must be positive")
    return value


def _is_busy(agent: Dict[str, Any]) -> bool:
    return bool(agent.get("tool")) or agent.get("runtime_status") == "busy"


def classify(agent: Dict[str, Any], threshold_s: float) -> str:
    """One agent's verdict. Order matters: the reasons to KEEP are checked before the one to close."""
    if agent.get("kind") != "interactive":
        return NOT_INTERACTIVE
    idle = agent.get("last_human_input_seconds")
    if not isinstance(idle, (int, float)) or isinstance(idle, bool):
        return KEEP_UNMEASURED
    if idle <= threshold_s:
        return KEEP_RECENT
    if not agent.get("terminal_label"):
        return UNREACHABLE
    if _is_busy(agent):
        return KEEP_BUSY
    return CLOSE


def listed_agents(listing: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every agent in a `GET /api/fleet/agents` answer, flattened out of its projects."""
    out: List[Dict[str, Any]] = []
    for project in listing.get("projects") or []:
        for agent in project.get("agents") or []:
            if isinstance(agent, dict):
                out.append(agent)
    return out


def select(agents: List[Dict[str, Any]], threshold_s: float) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for agent in agents:
        groups.setdefault(classify(agent, threshold_s), []).append(agent)
    return groups


def log_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "set-core" / "fleet-idle-close.jsonl"


def _record(agent: Dict[str, Any], now: float) -> Dict[str, Any]:
    idle = agent.get("last_human_input_seconds")
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "label": agent.get("terminal_label"),
        "pid": agent.get("pid"),
        "project": agent.get("project"),
        "session_id": agent.get("session_id"),
        "idle_hours": round(idle / 3600, 1) if isinstance(idle, (int, float)) else None,
    }


def _append_log(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _http_json(method: str, url: str, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local dashboard
        body = resp.read()
    return json.loads(body) if body else None


def run(base_url: str = DEFAULT_BASE_URL, *, threshold_s: float, dry_run: bool = False,
        http: Callable[[str, str], Any] = _http_json, now: Optional[float] = None,
        log_file: Optional[Path] = None) -> Dict[str, Any]:
    """Read the listing, close what qualifies, record each close. Raises if the listing is unreachable."""
    now = time.time() if now is None else now
    base = base_url.rstrip("/")
    listing = http("GET", f"{base}/api/fleet/agents")
    groups = select(listed_agents(listing or {}), threshold_s)

    closed: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    for agent in groups.get(CLOSE, []):
        row = _record(agent, now)
        if dry_run:
            closed.append(row)
            continue
        label = urllib.parse.quote(str(agent["terminal_label"]), safe="")
        try:
            answer = http("POST", f"{base}/api/fleet/agents/{label}/stop")
        except urllib.error.HTTPError as exc:
            failed.append({**row, "error": f"HTTP {exc.code}"})
            logger.warning("fleet idle-close: stop %s refused (HTTP %s)", row["label"], exc.code)
            continue
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failed.append({**row, "error": type(exc).__name__})
            logger.warning("fleet idle-close: stop %s failed (%s)", row["label"], type(exc).__name__)
            continue
        if not (isinstance(answer, dict) and answer.get("found")):
            failed.append({**row, "error": "not found"})
            continue
        closed.append(row)
        logger.info("fleet idle-close: closed %s (project %s, idle %sh)",
                    row["label"], row["project"], row["idle_hours"])

    if not dry_run:
        _append_log(closed, log_file or log_path())

    def brief(key: str) -> List[Dict[str, Any]]:
        return [_record(a, now) for a in groups.get(key, [])]

    return {
        "threshold_hours": round(threshold_s / 3600, 1),
        "dry_run": dry_run,
        "closed": closed,
        "failed": failed,
        "kept_busy": brief(KEEP_BUSY),
        "kept_unmeasured": brief(KEEP_UNMEASURED),
        "unreachable": brief(UNREACHABLE),
        "recent": len(groups.get(KEEP_RECENT, [])),
    }


# --------------------------------------------------------------------------- #
# What the fleet screen shows
# --------------------------------------------------------------------------- #

LOG_LIMIT = 30


def read_log(path: Optional[Path] = None, limit: int = LOG_LIMIT) -> List[Dict[str, Any]]:
    """The newest closes first. A line that is not a JSON object is skipped and counted in the log."""
    path = path or log_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    bad = 0
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(row, dict) and row.get("session_id"):
            rows.append(row)
        if len(rows) >= limit:
            break
    if bad:
        logger.warning("fleet idle-close: %d unreadable line(s) in the close log", bad)
    return rows


def upcoming(agents: List[Dict[str, Any]], threshold_s: float, until_next_s: Optional[float]) -> List[Dict[str, Any]]:
    """Agents the next run will close if nobody types into them first, longest-idle first.

    Same rule as `classify` but measured at the moment of the next run. A busy agent is listed
    with `busy` set — it is closed only if it is idle when the run comes.
    """
    ahead = max(0.0, until_next_s or 0.0)
    out: List[Dict[str, Any]] = []
    for a in agents:
        idle = a.get("last_human_input_seconds")
        if a.get("kind") != "interactive" or not a.get("terminal_label"):
            continue
        if not isinstance(idle, (int, float)) or isinstance(idle, bool):
            continue
        if idle + ahead <= threshold_s:
            continue
        out.append({
            "label": a.get("terminal_label"), "project": a.get("project"),
            "session_id": a.get("session_id"), "idle_hours": round(idle / 3600, 1),
            "busy": _is_busy(a),
        })
    out.sort(key=lambda r: -r["idle_hours"])
    return out


def _usec_to_s(value: Any) -> Optional[float]:
    return value / 1_000_000 if isinstance(value, (int, float)) and value > 0 else None


def timer_state(runner: Callable[..., Any] = subprocess.run) -> Dict[str, Any]:
    """Is the daily timer installed and enabled, and when does it fire next / did it fire last.

    `None` for a time systemd does not report. If systemctl itself cannot be asked, `known` is
    false — an unreadable timer is not a disabled one.
    """
    unit = f"{UNIT_NAME}.timer"
    try:
        enabled = runner(["systemctl", "--user", "is-enabled", unit],
                         capture_output=True, text=True, timeout=10)
        listed = runner(["systemctl", "--user", "list-timers", unit, "--all", "-o", "json", "--no-pager"],
                        capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("fleet idle-close: systemctl unreadable (%s)", type(exc).__name__)
        return {"known": False, "installed": None, "enabled": None, "next_run": None, "last_run": None}
    word = (enabled.stdout or "").strip()
    rows: List[Dict[str, Any]] = []
    try:
        parsed = json.loads(listed.stdout or "[]")
        rows = [r for r in parsed if isinstance(r, dict) and r.get("unit") == unit]
    except ValueError:
        pass
    row = rows[0] if rows else {}
    return {
        "known": True,
        "installed": word not in ("", "not-found") and "No such file" not in (enabled.stderr or ""),
        "enabled": word == "enabled",
        "next_run": _usec_to_s(row.get("next")),
        "last_run": _usec_to_s(row.get("last")),
    }


def default_command() -> str:
    return os.environ.get("SET_FLEET_IDLE_CLOSE_BIN") or str(
        Path(__file__).resolve().parents[3] / "bin" / "set-fleet-idle-close")


def set_enabled(enabled: bool, runner: Callable[..., Any] = subprocess.run,
                command: Optional[str] = None) -> None:
    """Switch the daily run on (installing the timer the first time) or off. Raises on failure."""
    unit = f"{UNIT_NAME}.timer"
    if enabled:
        state = timer_state(runner)
        if not state.get("installed"):
            install_timer(command or default_command(), systemctl=runner)
            return
        runner(["systemctl", "--user", "enable", "--now", unit], check=True, capture_output=True, text=True)
    else:
        runner(["systemctl", "--user", "disable", "--now", unit], check=True, capture_output=True, text=True)
    logger.info("fleet idle-close: timer %s", "enabled" if enabled else "disabled")


def status(agents: List[Dict[str, Any]], *, threshold_s: float, timer: Dict[str, Any],
           closed: List[Dict[str, Any]], live_ids: Optional[set], now: float) -> Dict[str, Any]:
    """The answer of `GET /api/fleet/idle-close`."""
    next_run = timer.get("next_run")
    until_next = (next_run - now) if (timer.get("enabled") and next_run) else 0.0
    return {
        "threshold_hours": round(threshold_s / 3600, 1),
        "timer": timer,
        "upcoming": upcoming(agents, threshold_s, until_next),
        "closed": [{**row, "running": None if live_ids is None else row.get("session_id") in live_ids}
                   for row in closed],
        "liveness_known": live_ids is not None,
    }


# --------------------------------------------------------------------------- #
# The schedule
# --------------------------------------------------------------------------- #

def unit_texts(command: str, at: str = "04:00") -> Dict[str, str]:
    service = (
        "[Unit]\n"
        "Description=Close fleet agents with no owner input for longer than the threshold\n"
        "After=set-web.service\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={command}\n"
    )
    timer = (
        "[Unit]\n"
        "Description=Daily close of long-idle fleet agents\n\n"
        "[Timer]\n"
        f"OnCalendar=*-*-* {at}:00\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    return {f"{UNIT_NAME}.service": service, f"{UNIT_NAME}.timer": timer}


def install_timer(command: str, at: str = "04:00", unit_dir: Optional[Path] = None,
                  systemctl: Callable[..., Any] = subprocess.run) -> Path:
    unit_dir = unit_dir or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name, text in unit_texts(command, at).items():
        (unit_dir / name).write_text(text, encoding="utf-8")
    systemctl(["systemctl", "--user", "daemon-reload"], check=True)
    systemctl(["systemctl", "--user", "enable", "--now", f"{UNIT_NAME}.timer"], check=True)
    logger.info("fleet idle-close: timer installed in %s, daily at %s", unit_dir, at)
    return unit_dir


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _print_human(result: Dict[str, Any]) -> None:
    verb = "would close" if result["dry_run"] else "closed"
    print(f"threshold: {result['threshold_hours']} h without owner input")
    print(f"{verb}: {len(result['closed'])}")
    for r in result["closed"]:
        print(f"  {r['label']}  ({r['project']}, idle {r['idle_hours']} h, session {r['session_id']})")
    for key, title in (("failed", "FAILED"), ("kept_busy", "kept, busy right now"),
                       ("kept_unmeasured", "kept, idle time unmeasured"),
                       ("unreachable", "not reachable (no terminal label)")):
        if result[key]:
            print(f"{title}: {len(result[key])}")
            for r in result[key]:
                extra = f" — {r['error']}" if r.get("error") else ""
                print(f"  {r['label'] or 'pid ' + str(r.get('pid'))}  ({r['project'] or 'no project'}){extra}")
    print(f"recent, kept: {result['recent']}")
    if result["closed"] and not result["dry_run"]:
        print(f"log: {log_path()} · bring one back from the fleet's roster")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="set-fleet-idle-close", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    inst = sub.add_parser("install-timer", help="write and enable a daily systemd user timer")
    inst.add_argument("--at", default="04:00", help="time of day, HH:MM (default 04:00)")
    parser.add_argument("--hours", type=float, help=f"threshold (default: local config {CONFIG_KEY}, else 48)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be closed, close nothing")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--base-url", default=os.environ.get("SET_WEB_URL", DEFAULT_BASE_URL))
    args = parser.parse_args(argv)

    if args.cmd == "install-timer":
        where = install_timer(default_command(), args.at)
        print(f"installed {UNIT_NAME}.timer in {where}, daily at {args.at}; "
              f"threshold from local config {CONFIG_KEY} (default 48 h)")
        return 0

    try:
        hours = threshold_hours(args.hours)
    except ValueError as exc:
        print(f"set-fleet-idle-close: {exc}", file=sys.stderr)
        return 2
    try:
        result = run(args.base_url, threshold_s=hours * 3600, dry_run=args.dry_run)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"set-fleet-idle-close: the fleet listing is unreachable ({type(exc).__name__}); "
              f"nothing was closed", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        _print_human(result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
