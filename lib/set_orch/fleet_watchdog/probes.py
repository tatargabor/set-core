"""The built-in probes — set features that fail quietly.

Every probe reads a measured source and returns shape-only findings. A probe that cannot
read its source says so as a `warn` finding: a probe that silently returns nothing when its
input is gone would report a calm machine it never looked at (design D2, spec "could not
measure").
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .probe import Context, Finding, Probe, register

logger = logging.getLogger(__name__)

DEFAULT_API = "http://127.0.0.1:7400"
HTTP_TIMEOUT_S = 20


def api_base(get) -> str:
    return str(get("watchdog.api", default=None) or os.environ.get("SET_WEB_API") or DEFAULT_API).rstrip("/")


def _http_json(url: str, timeout: float = HTTP_TIMEOUT_S) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — local dashboard
        return json.loads(resp.read().decode("utf-8"))


def fleet_payload(ctx: Context) -> Tuple[bool, Any]:
    return ctx.once("fleet", lambda: _http_json(api_base(ctx.get) + "/api/fleet/agents"))


def live_agents(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for project in payload.get("projects") or []:
        for agent in project.get("agents") or []:
            if agent.get("kind") == "interactive" and agent.get("session_id"):
                yield agent


def _int(get, key: str, default: float) -> float:
    try:
        return float(get(key, default=default))
    except (TypeError, ValueError):
        logger.warning("watchdog: bad value for %s; using %s", key, default)
        return float(default)


def unmeasured(probe: str, source: str, reason: str) -> Finding:
    return Finding(probe, "warn", f"source:{source}", f"{probe} could not read {source}",
                   {"reason": str(reason)[:120]}, owner_hint="set-core")


# ---------------------------------------------------------------------------------------
# wake-storm
# ---------------------------------------------------------------------------------------

WAKE_WINDOW_S = 2 * 3600
WAKE_COUNT = 3
#: The session counts as idle (asleep) only when nobody typed into it for this long.
WAKE_IDLE_S = 3600
#: "No known marker" is claimed only over enough turn starts to mean something.
UNCLASSIFIED_MIN = 3
TRANSCRIPT_TAIL = 4 << 20
INBOX_WATCH_DESCRIPTION = "agent-comm inbox"
BUS_STOP_PREFIX = "Stop hook feedback:"
BUS_STOP_MARK = "[set-agent-comm]"


def transcript_path(cwd: str, session_id: str, home: Optional[str] = None) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    return Path(home or os.path.expanduser("~")) / ".claude" / "projects" / slug / f"{session_id}.jsonl"


def _parse_ts(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _text_head(content: Any, limit: int = 400) -> str:
    """Only the start of a turn-opening record is read, and only to match a fixed marker."""
    if isinstance(content, str):
        return content[:limit]
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))[:limit]
    return ""


def classify_turn_start(record: Dict[str, Any]) -> Optional[str]:
    """`human` | `bus` | `own-task` | `other` for a turn-opening user record, None otherwise.

    The markers were measured on 2026-11-24 (design Context): `origin.kind` names a typed
    prompt or a task notification; a bus Stop-hook continuation is an `isMeta` record whose
    text starts with the Stop-hook prefix and the bus's tag.
    """
    if record.get("type") != "user" or record.get("toolUseResult") is not None:
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    origin = record.get("origin") or {}
    kind = origin.get("kind") if isinstance(origin, dict) else None
    head = _text_head(content)
    if kind == "human":
        return "human"
    if kind == "task-notification":
        return "bus" if INBOX_WATCH_DESCRIPTION in head else "own-task"
    if record.get("isMeta"):
        # A meta record is a turn start only when it is a Stop-hook continuation; the rest
        # (a skill body, a reminder) rides inside a turn something else started.
        if head.startswith(BUS_STOP_PREFIX):
            return "bus" if BUS_STOP_MARK in head else "hook"
        return None
    if head.lstrip().startswith(("<command-name>", "<local-command")):
        # A slash command row (measured: `/clear` at the top of a cleared session, no origin,
        # `rowSource: local`) — typed by a person or by the auto-clear watcher alike.
        return "command"
    return "other"


def read_tail(path: Path, tail: int = TRANSCRIPT_TAIL) -> List[Dict[str, Any]]:
    out = []
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - tail))
        if size > tail:
            fh.readline()
        for raw in fh:
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def count_wakes(records: List[Dict[str, Any]], now: float, window_s: float) -> Dict[str, int]:
    """Bus wakes since the last human prompt inside the window, plus classifier coverage."""
    counts = {"bus": 0, "own-task": 0, "hook": 0, "command": 0, "human": 0, "other": 0, "starts": 0}
    for rec in records:
        ts = _parse_ts(rec.get("timestamp"))
        if ts is None or now - ts > window_s:
            continue
        kind = classify_turn_start(rec)
        if kind is None:
            continue
        counts["starts"] += 1
        if kind == "human":
            # A person was here: wakes before this prompt are not a storm on an idle session.
            counts["bus"] = 0
            counts["human"] += 1
        else:
            counts[kind] += 1
    return counts


def _open_askers(ctx: Context) -> Optional[set]:
    ok, data = ctx.once("engagements", lambda: _http_json(api_base(ctx.get) + "/api/fleet/engagements"))
    if not ok or not isinstance(data, dict):
        return None
    return {e.get("asker") for e in data.get("engagements") or [] if e.get("state") == "open"}


def probe_wake_storm(ctx: Context) -> List[Finding]:
    ok, payload = fleet_payload(ctx)
    if not ok:
        return [unmeasured("wake-storm", "fleet payload", payload)]
    window = _int(ctx.get, "watchdog.wake_storm.window_s", WAKE_WINDOW_S)
    limit = _int(ctx.get, "watchdog.wake_storm.count", WAKE_COUNT)
    idle_s = _int(ctx.get, "watchdog.wake_storm.idle_s", WAKE_IDLE_S)
    askers = _open_askers(ctx) or set()
    out: List[Finding] = []
    unclassified = 0
    for agent in live_agents(payload):
        path = transcript_path(str(agent.get("cwd") or ""), str(agent["session_id"]))
        try:
            counts = count_wakes(read_tail(path), ctx.now, window)
        except OSError:
            continue
        if counts["starts"] >= UNCLASSIFIED_MIN and counts["starts"] == counts["other"]:
            unclassified += 1
            continue
        human_age = agent.get("last_human_input_seconds")
        idle = not isinstance(human_age, (int, float)) or human_age >= idle_s
        if counts["bus"] >= limit and idle and agent.get("seat") not in askers:
            out.append(Finding("wake-storm", "warn", f"session:{agent['session_id']}",
                               f"woken {counts['bus']}x by the bus in {int(window // 60)} min with no human prompt",
                               {"project": agent.get("project"), "bus_wakes": counts["bus"],
                                "window_min": int(window // 60), "tokens": (agent.get("context") or {}).get("tokens"),
                                "idle_min": None if not isinstance(human_age, (int, float)) else int(human_age // 60),
                                "seat": agent.get("seat")}, owner_hint="set-agent-comm"))
    if unclassified:
        out.append(Finding("wake-storm", "warn", "classifier", "turn starts in live transcripts match no known marker",
                           {"sessions": unclassified}, owner_hint="set-core"))
    return out


# ---------------------------------------------------------------------------------------
# auto-clear-miss
# ---------------------------------------------------------------------------------------

GRACE_S = 15 * 60
KILL_SWITCH = Path(".set") / "handoff" / ".no-autoclear"


def _registry(get) -> Dict[str, Any]:
    path = os.environ.get("SET_CORE_REGISTRY") or os.path.join(
        os.environ.get("SET_CONFIG_DIR") or os.path.expanduser("~/.config/set-core"), "projects.json")
    try:
        return (json.loads(Path(path).read_text()) or {}).get("projects") or {}
    except (OSError, ValueError):
        return {}


def threshold_for(tree: str, home: str, registry: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """The tokens at which the tree's watcher acts, and where the figure came from."""
    from set_doctor import auto_clear as ac
    units = ac.watcher_units(home, tree)
    if not units:
        return None, "no-unit"
    m = re.search(r"--threshold[= ](\d+)", units[0][1])
    if m:
        return int(m.group(1)), "unit"
    pkg = ac.package_path(registry)
    value = ac.package_default_threshold(pkg) if pkg else None
    return (value, "package") if value else (None, "unreadable")


def probe_auto_clear_miss(ctx: Context) -> List[Finding]:
    ok, payload = fleet_payload(ctx)
    if not ok:
        return [unmeasured("auto-clear-miss", "fleet payload", payload)]
    grace = _int(ctx.get, "watchdog.auto_clear.grace_s", GRACE_S)
    home = os.path.expanduser("~")
    registry = _registry(ctx.get)
    state = ctx.state("auto-clear-miss")
    crossed: Dict[str, float] = state.setdefault("crossed", {})
    live = set()
    out: List[Finding] = []
    thresholds: Dict[str, Tuple[Optional[int], str]] = {}
    for agent in live_agents(payload):
        tree = str(agent.get("project_root") or agent.get("cwd") or "")
        sid = str(agent["session_id"])
        live.add(sid)
        if not tree or (Path(tree) / KILL_SWITCH).exists():
            continue
        if tree not in thresholds:
            thresholds[tree] = threshold_for(tree, home, registry)
        threshold, source = thresholds[tree]
        if source == "no-unit":
            continue                       # not armed here: service-health owns a missing unit
        if threshold is None:
            out.append(Finding("auto-clear-miss", "warn", f"threshold:{agent.get('project')}",
                               "auto-clear threshold unreadable", {"project": agent.get("project")},
                               owner_hint="set-claude-handoff"))
            continue
        tokens = (agent.get("context") or {}).get("tokens")
        if not isinstance(tokens, (int, float)):
            continue
        if tokens < threshold:
            crossed.pop(sid, None)
            continue
        since = crossed.setdefault(sid, ctx.now)
        minutes = (ctx.now - since) / 60
        if ctx.now - since >= grace:
            out.append(Finding("auto-clear-miss", "fail", f"session:{sid}",
                               f"{int(tokens)} tokens >= {threshold} for {int(minutes)} min without a clear",
                               {"project": agent.get("project"), "tokens": int(tokens), "threshold": threshold,
                                "threshold_source": source, "minutes_above": int(minutes),
                                "runtime_status": agent.get("runtime_status")}, owner_hint="set-claude-handoff"))
    # A session id that left the fleet was cleared or ended: its crossing is history.
    for sid in [s for s in crossed if s not in live]:
        crossed.pop(sid, None)
    return out


# ---------------------------------------------------------------------------------------
# relay-hold
# ---------------------------------------------------------------------------------------

RELAY_HOLD_S = 15 * 60


def probe_relay_hold(ctx: Context) -> List[Finding]:
    from ..fleet import question_relay as qr
    bound = _int(ctx.get, "watchdog.relay_hold.bound_s", RELAY_HOLD_S)
    try:
        waiting = qr.list_waiting()
    except OSError as exc:
        return [unmeasured("relay-hold", "relay waiting records", type(exc).__name__)]
    out = []
    for rec in waiting:
        if rec.get("kind") == "continuation":
            continue                       # a finished turn waiting for a next step is not held
        started = rec.get("started")
        if not isinstance(started, (int, float)) or ctx.now - started < bound:
            continue
        sid = str(rec.get("session_id") or "")
        out.append(Finding("relay-hold", "warn", f"session:{sid}",
                           f"a relayed question held for {int((ctx.now - started) // 60)} min",
                           {"minutes": int((ctx.now - started) // 60), "questions": rec.get("questions"),
                            "kind": rec.get("kind") or "ask"}, owner_hint="set-core"))
    return out


# ---------------------------------------------------------------------------------------
# service-health
# ---------------------------------------------------------------------------------------

def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=15)


def unit_owner(unit: str, registry: Dict[str, Any], home: Optional[str] = None) -> Optional[str]:
    """The registered project whose tree holds the unit's ExecStart program, or None."""
    home = home or os.path.expanduser("~")
    path = Path(home) / ".config" / "systemd" / "user" / unit
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    words = []
    for line in text.splitlines():
        if line.startswith("ExecStart="):
            words += line[len("ExecStart="):].replace("%h", home).split()
    trees = sorted(((os.path.realpath(os.path.expanduser(str(e.get("path")))), n) for n, e in registry.items()
                    if isinstance(e, dict) and e.get("path")), key=lambda t: -len(t[0]))
    for word in words:
        real = os.path.realpath(word) if word.startswith("/") else None
        if not real:
            continue
        for tree, name in trees:
            if real == tree or real.startswith(tree + os.sep):
                return name
    return None


def probe_service_health(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    ok, payload = fleet_payload(ctx)
    if not ok:
        out.append(Finding("service-health", "fail", "unit:set-web", "set-web does not answer the fleet API",
                           {"error": str(payload)[:80]}, owner_hint="set-core"))
    elif isinstance(payload, dict):
        if payload.get("owner_reachable") is False:
            out.append(Finding("service-health", "fail", "unit:set-agent-owner", "the agent owner is unreachable",
                               {}, owner_hint="set-core"))
        if payload.get("bus_reachable") is False:
            out.append(Finding("service-health", "fail", "bus", "the agent bus is unreachable",
                               {}, owner_hint="set-agent-comm"))
    registry = _registry(ctx.get)
    try:
        res = _systemctl("list-units", "--failed", "--plain", "--no-legend")
        for line in res.stdout.splitlines():
            unit = line.split()[0] if line.split() else ""
            if unit:
                owner = unit_owner(unit, registry)
                out.append(Finding("service-health", "fail", f"unit:{unit}", f"user unit {unit} is failed",
                                   {"unit": unit, "project": owner}, owner_hint=owner))
    except (OSError, subprocess.TimeoutExpired) as exc:
        out.append(unmeasured("service-health", "systemctl --failed", type(exc).__name__))
    # Armed auto-clear watchers that are not running.
    from set_doctor import auto_clear as ac
    home = os.path.expanduser("~")
    for name, entry in registry.items():
        if not isinstance(entry, dict) or entry.get("archived") or entry.get("auto_clear") is False:
            continue
        tree = os.path.expanduser(str(entry.get("path") or ""))
        if not tree or not os.path.isdir(tree) or (Path(tree) / KILL_SWITCH).exists():
            continue
        for unit, _ in ac.watcher_units(home, tree):
            if ac.unit_active(unit, dict(os.environ)) is False:
                out.append(Finding("service-health", "fail", f"unit:{unit}",
                                   f"auto-clear watcher {unit} is not active", {"unit": unit, "project": name},
                                   owner_hint="set-claude-handoff"))
    return out


# ---------------------------------------------------------------------------------------
# doctor-delta
# ---------------------------------------------------------------------------------------

DOCTOR_TIMEOUT_S = 240


def _doctor_records() -> List[Dict[str, Any]]:
    res = subprocess.run(["set-doctor", "--json"], capture_output=True, text=True, timeout=DOCTOR_TIMEOUT_S)
    data = json.loads(res.stdout)
    return [r for r in data.get("checks") or [] if isinstance(r, dict)]


def doctor_key(rec: Dict[str, Any]) -> str:
    return "|".join(str(rec.get(k) or "") for k in ("module", "project", "section", "name"))


def probe_doctor_delta(ctx: Context, fetch=_doctor_records) -> List[Finding]:
    try:
        records = fetch()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return [unmeasured("doctor-delta", "set-doctor --json", type(exc).__name__)]
    state = ctx.state("doctor-delta")
    fails = {doctor_key(r): r for r in records if r.get("status") == "fail"}
    if "baseline" not in state:
        # The first run learns what already fails; only what fails LATER is a finding.
        state["baseline"] = sorted(fails)
        logger.info("watchdog: doctor-delta baseline of %d fail record(s)", len(fails))
        return []
    baseline = set(state["baseline"])
    # A baseline record that recovered and fails again later is new news.
    state["baseline"] = sorted(k for k in baseline if k in fails)
    out = []
    for key, rec in fails.items():
        if key in baseline:
            continue
        subject = ":".join(str(rec.get(k) or "-") for k in ("module", "project", "name"))
        out.append(Finding("doctor-delta", "fail", f"doctor:{subject}"[:160],
                           f"set-doctor: {rec.get('section')} / {str(rec.get('name'))[:80]} is fail",
                           {"module": rec.get("module"), "project": rec.get("project"),
                            "section": rec.get("section"), "check": str(rec.get("name"))[:80]},
                           owner_hint=rec.get("module") or None))
    return out


register(Probe("wake-storm", 600, probe_wake_storm, "idle sessions woken by the bus without a human prompt"))
register(Probe("auto-clear-miss", 300, probe_auto_clear_miss, "sessions above the auto-clear threshold that never clear"))
register(Probe("relay-hold", 300, probe_relay_hold, "relayed questions held past a bound"))
register(Probe("service-health", 300, probe_service_health, "set-web, the owner, the bus, failed and inactive units"))
register(Probe("doctor-delta", 1800, probe_doctor_delta, "new fail records in set-doctor --json, module doctors included"))
