"""The Now card — one item at a time, and the state the card keeps about it.

Layer 1 (abstract). Nothing here knows what an item is ABOUT. It orders items it
was handed, remembers which ones the owner snoozed or dismissed, holds the day's
focus projects, decides when a sound cue is due, and counts what was closed. Every
key it stores is an opaque item id or a registry project name.

**The persistence boundary is the reason this module is shaped the way it is.**
Item titles, sentences, options, reasons and answers are the publishing project's
content. They are displayed at request time and never written here — not into the
state file, not into a log line. The one exception the spec names is owner-written
text when NO publisher is declared: a resume note is then kept locally, because
there is nowhere else to keep it. With a publisher it goes to the publisher.

Three parts, each a pure function over a state dict, so each is testable without
a clock, a file, or a server:

    merge          — the publisher's rank first, then the framework items it does
                     not reference, oldest first; snoozed and dismissed items out.
    apply_focus    — at most three focus projects; the rest held back and counted.
    decide_cue     — a cue only at a breakpoint (the owner's input moved project),
                     never inside a long block, with a backoff when cues are ignored.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .. import local_config

logger = logging.getLogger(__name__)

STATE_VERSION = 1
FOCUS_MAX = 3
#: Cue log entries kept for the one-week read-back (task 6.4). Bounded so the file
#: does not grow with use; 500 cues is months at the intended cadence.
CUE_LOG_MAX = 500
#: A dismissal of a framework item is kept this long, then forgotten.
DISMISS_RETENTION_S = 7 * 24 * 3600
#: Consecutive input in one project with gaps shorter than this is one block. The
#: same 30-minute rule the visit measurement in design.md used.
BLOCK_GAP_S = 30 * 60
#: The backoff never makes cues rarer than this multiple of the base interval.
MAX_BACKOFF_FACTOR = 16
#: Distinct tone shapes the page cycles through; the server only picks the index.
CUE_VARIANTS = 6

#: Configuration keys, read through `local_config` (machine- or env-scoped), with
#: the defaults used when a key is unset. Every cadence is configuration because
#: no study fixes it (design.md, Context) — the cue log is what tunes it.
CONFIG_DEFAULTS: Dict[str, Any] = {
    "now.publisher": None,
    "now.focus_threshold_minutes": 60,
    "now.offplan_nudge_minutes": 45,
    "now.cue_min_interval_minutes": 10,
    "now.cue_backoff_after": 3,
    "now.deadline_window_hours": 24,
    # The publisher ranks every 3 hours (2026-10-30); with 2 h here every cycle showed an hour
    # of false "stale" warnings. Stale now means a ranking was MISSED, not merely due.
    "now.stale_ranking_hours": 4,
    # Goals are synthesised about daily, so "stale" is a missed day and a half, not hours.
    "now.stale_goals_hours": 36,
    "now.wind_down_hour": 23,
}

Getter = Callable[..., Any]


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

def config(get: Getter = local_config.get) -> Dict[str, Any]:
    """Every card setting, numeric ones coerced; an unusable value falls back with a warning."""
    out: Dict[str, Any] = {}
    for key, default in CONFIG_DEFAULTS.items():
        raw = get(key, default=default)
        if default is None:
            out[key] = str(raw).strip() if raw not in (None, "") else None
            continue
        try:
            value = float(raw)
            if value < 0:
                raise ValueError("negative")
            out[key] = value
        except (TypeError, ValueError):
            logger.warning("now: config %s=%r is not a non-negative number; using %s",
                           key, raw, default)
            out[key] = float(default)
    return out


# --------------------------------------------------------------------------- #
# the state store
# --------------------------------------------------------------------------- #

def state_dir() -> Path:
    override = os.environ.get("SET_NOW_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "set-core" / "now"


def state_path() -> Path:
    return state_dir() / "state.json"


def today_str(now: float) -> str:
    return datetime.fromtimestamp(now).date().isoformat()


def empty_state(now: float) -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "day": today_str(now),
        # id → epoch seconds at which the item may return
        "snoozes": {},
        # id → epoch seconds of dismissal (framework items have no write path)
        "dismissed": {},
        "focus": [],
        "focusDay": None,
        # Projects the owner switched OFF on the card's tag strip. Unlike focus this does not
        # reset with the day: a switch stays where the owner put it.
        "mutedProjects": [],
        # project → note; ONLY used when no publisher is declared (spec)
        "resumeNotes": {},
        "closedToday": 0,
        "parkedIdeas": 0,
        "cue": {
            "inputProject": None,
            "inputSince": None,
            "lastInputAt": None,
            "lastCueAt": None,
            "lastCueFirst": None,
            "deadlineCued": None,
            "unacted": 0,
            "factor": 1,
            "nudged": {},
            "log": [],
        },
    }


def load_state(now: float, path: Optional[Path] = None) -> Dict[str, Any]:
    """The stored state merged over a fresh skeleton, so a missing key is never a KeyError."""
    path = path or state_path()
    state = empty_state(now)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (OSError, ValueError) as exc:
        logger.warning("now: state file %s unreadable (%s); starting fresh", path, type(exc).__name__)
        return state
    if not isinstance(raw, dict):
        logger.warning("now: state file %s is not an object; starting fresh", path)
        return state
    for key, value in raw.items():
        if key == "cue" and isinstance(value, dict):
            state["cue"].update(value)
        elif key in state:
            state[key] = value
    return state


def save_state(state: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Atomic write: a reader never sees half a file, a crash leaves the old one."""
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def roll_day(state: Dict[str, Any], now: float) -> None:
    """Start a new day's counts; drop expired snoozes and old dismissals."""
    today = today_str(now)
    if state.get("day") != today:
        logger.info("now: day rolled %s -> %s; closedToday %s -> 0",
                    state.get("day"), today, state.get("closedToday"))
        state["day"] = today
        state["closedToday"] = 0
        state["cue"]["nudged"] = {}
    state["snoozes"] = {k: v for k, v in (state.get("snoozes") or {}).items()
                        if isinstance(v, (int, float)) and v > now}
    state["dismissed"] = {k: v for k, v in (state.get("dismissed") or {}).items()
                          if isinstance(v, (int, float)) and now - v < DISMISS_RETENTION_S}


def snooze(state: Dict[str, Any], item_id: str, until: float) -> None:
    state.setdefault("snoozes", {})[item_id] = float(until)


def dismiss(state: Dict[str, Any], item_id: str, now: float) -> None:
    state.setdefault("dismissed", {})[item_id] = float(now)


def count_closed(state: Dict[str, Any]) -> int:
    state["closedToday"] = int(state.get("closedToday") or 0) + 1
    return state["closedToday"]


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #

def to_epoch(value: Any) -> Optional[float]:
    """An epoch number or an ISO-8601 date/datetime as epoch seconds; None when unreadable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.astimezone()       # a naive time is the owner's local time
        return dt.timestamp()
    return None


def deadline_within(item: Dict[str, Any], now: float, window_s: float) -> bool:
    when = to_epoch(item.get("deadline"))
    return when is not None and when - now <= window_s


# --------------------------------------------------------------------------- #
# merge and focus
# --------------------------------------------------------------------------- #

def _covered(item: Dict[str, Any], refs: List[Tuple[Optional[str], str]]) -> bool:
    item_id = str(item.get("id", ""))
    source = item.get("source")
    for ref_source, ref_id in refs:
        if ref_id == item_id and (ref_source in (None, "") or ref_source == source):
            return True
    return False


def merge(owner_items: List[Dict[str, Any]], framework_items: List[Dict[str, Any]],
          state: Dict[str, Any], now: float) -> List[Dict[str, Any]]:
    """The publisher's rank, then framework items it does not reference, oldest first.

    An owner-queue item that references a framework item REPLACES it, so the owner
    sees one thing once and in the publisher's position. Snoozed items stay out until
    their time; dismissed framework items stay out while their id persists.
    """
    snoozes = state.get("snoozes") or {}
    dismissed = state.get("dismissed") or {}

    def hidden(item_id: str) -> bool:
        until = snoozes.get(item_id)
        return (until is not None and until > now) or item_id in dismissed

    refs: List[Tuple[Optional[str], str]] = []
    for item in owner_items:
        for ref in item.get("references") or []:
            if isinstance(ref, dict) and ref.get("id") is not None:
                refs.append((ref.get("source"), str(ref["id"])))

    merged = [i for i in owner_items if not hidden(str(i.get("id")))]
    rest = [i for i in framework_items
            if not _covered(i, refs) and not hidden(str(i.get("id")))]
    # Stable sort: equal or unreadable ages keep the aggregator's own order.
    rest.sort(key=lambda i: to_epoch(i.get("since")) or float("inf"))
    return merged + rest


def apply_focus(items: List[Dict[str, Any]], focus: Iterable[str], now: float,
                deadline_window_s: float) -> Tuple[List[Dict[str, Any]], int]:
    """Items to show, and how many were held back for being outside the focus.

    With no focus picked, nothing is held back. With focus picked: focus items and
    any item whose deadline is inside the window; when no focus project has an
    item, everything — a focus is a preference, never a lock (design Non-Goals).
    """
    focus_set = {f for f in focus if f}
    if not focus_set:
        return list(items), 0
    if not any(i.get("project") in focus_set for i in items):
        return list(items), 0
    shown = [i for i in items
             if i.get("project") in focus_set or deadline_within(i, now, deadline_window_s)]
    return shown, len(items) - len(shown)


#: The tag-strip name of an item that names no project.
NO_PROJECT = "(no project)"


def group_of(item: Dict[str, Any]) -> str:
    return item.get("project") or NO_PROJECT


def apply_mute(items: List[Dict[str, Any]], muted: Iterable[str]) -> Tuple[List[Dict[str, Any]], int]:
    """Items whose project is switched on, and how many a switched-off project hid.

    Strict by the owner's own words ("nem jön fel ami nincs bekapcsolva"): a switched-off
    project shows nothing, deadline or not. What it hid is still COUNTED and shown, so the
    filter can never make the queue look emptier than it is.
    """
    off = {m for m in muted if m}
    if not off:
        return list(items), 0
    shown = [i for i in items if group_of(i) not in off]
    return shown, len(items) - len(shown)


def groups(items: List[Dict[str, Any]], muted: Iterable[str]) -> List[Dict[str, Any]]:
    """One tag per project that has an item, with its count and whether it is switched off.

    Ordered by first appearance in the merged order, so the publisher's top project leads.
    A switched-off project with no item left is still listed, so it can be switched back on.
    """
    off = [m for m in muted if m]
    counts: Dict[str, int] = {}
    for i in items:
        g = group_of(i)
        counts[g] = counts.get(g, 0) + 1
    for m in off:
        counts.setdefault(m, 0)
    return [{"name": g, "count": n, "muted": g in off} for g, n in counts.items()]


def set_muted(state: Dict[str, Any], projects: List[str]) -> List[str]:
    clean: List[str] = []
    for p in projects:
        p = str(p).strip()
        if p and p not in clean:
            clean.append(p)
    old = list(state.get("mutedProjects") or [])
    state["mutedProjects"] = clean
    logger.info("now: muted projects %s -> %s", old, clean)
    return clean


def set_focus(state: Dict[str, Any], projects: List[str], now: float) -> Dict[str, Any]:
    """Replace the focus list. More than three is refused with the swap question."""
    clean: List[str] = []
    for p in projects:
        if isinstance(p, str) and p.strip() and p.strip() not in clean:
            clean.append(p.strip())
    if len(clean) > FOCUS_MAX:
        return {"ok": False, "swap": True, "focus": list(state.get("focus") or []),
                "reason": f"at most {FOCUS_MAX} focus projects — choose one to swap out"}
    old = list(state.get("focus") or [])
    state["focus"] = clean
    state["focusDay"] = today_str(now)
    logger.info("now: focus %s -> %s", old, clean)
    return {"ok": True, "swap": False, "focus": clean,
            "removed": [p for p in old if p not in clean]}


# --------------------------------------------------------------------------- #
# cues
# --------------------------------------------------------------------------- #

def current_input(inputs: Iterable[Tuple[Optional[str], Optional[float]]],
                  now: float) -> Tuple[Optional[str], Optional[float]]:
    """The project of the owner's most recent input, and when it was (epoch)."""
    best: Tuple[Optional[str], Optional[float]] = (None, None)
    for project, age in inputs:
        if not project or age is None:
            continue
        at = now - float(age)
        if best[1] is None or at > best[1]:
            best = (project, at)
    return best


def decide_cue(state: Dict[str, Any], *, inputs: Iterable[Tuple[Optional[str], Optional[float]]],
               first: Optional[Dict[str, Any]], focus: Iterable[str], now: float,
               cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Whether a cue plays now, and why. Mutates the cue section of `state`.

    A breakpoint is the project of the owner's most recent input changing. Inside a
    block — input staying in one project longer than the focus threshold — nothing
    cues, except one nudge per day when that project is not a focus project. Every
    cue that is not followed by an action counts toward the backoff; after the
    configured number, the interval doubles and the card says so.
    """
    cs = state["cue"]
    focus_set = {f for f in focus if f}
    today = today_str(now)
    base_interval = cfg["now.cue_min_interval_minutes"] * 60
    threshold = cfg["now.focus_threshold_minutes"] * 60
    offplan_after = cfg["now.offplan_nudge_minutes"] * 60
    window = cfg["now.deadline_window_hours"] * 3600
    backoff_after = max(1, int(cfg["now.cue_backoff_after"]))

    project, at = current_input(inputs, now)
    switched = False
    if project is not None and at is not None:
        last_at = cs.get("lastInputAt")
        if project != cs.get("inputProject"):
            switched = cs.get("inputProject") is not None
            cs["inputProject"] = project
            cs["inputSince"] = at
        elif last_at is not None and at - last_at > BLOCK_GAP_S:
            cs["inputSince"] = at          # same project after a long gap: a new block
        cs["lastInputAt"] = at

    in_block = (cs.get("lastInputAt") is not None and cs.get("inputSince") is not None
                and now - cs["lastInputAt"] < BLOCK_GAP_S)
    dwell = (now - cs["inputSince"]) if in_block else 0.0

    # Backoff is decided BEFORE the next cue: N cues in a row nobody acted on.
    if int(cs.get("unacted") or 0) >= backoff_after:
        old = int(cs.get("factor") or 1)
        cs["factor"] = min(MAX_BACKOFF_FACTOR, old * 2)
        cs["unacted"] = 0
        logger.info("now: %d cues without an action; cue interval factor %d -> %d",
                    backoff_after, old, cs["factor"])
    factor = int(cs.get("factor") or 1)
    interval = base_interval * factor
    since_last = now - cs["lastCueAt"] if cs.get("lastCueAt") is not None else float("inf")

    reason: Optional[str] = None
    first_id = str(first.get("id")) if first else None
    if first_id is not None:
        long_block = dwell > threshold
        if (in_block and dwell > offplan_after and focus_set and cs.get("inputProject")
                and cs["inputProject"] not in focus_set
                and (cs.get("nudged") or {}).get(cs["inputProject"]) != today):
            reason = "off-plan"
        elif long_block:
            reason = None
        elif switched and first_id != cs.get("lastCueFirst") and since_last >= interval:
            reason = "switch"
        elif (deadline_within(first, now, window) and cs.get("deadlineCued") != first_id
              and since_last >= interval):
            reason = "deadline"

    decision = {
        "play": reason is not None,
        "reason": reason,
        "variant": None,
        "slowed": factor > 1,
        "intervalSeconds": int(interval),
        "inputProject": cs.get("inputProject"),
        "blockSeconds": int(dwell),
    }
    if reason is None:
        return decision

    log = cs.setdefault("log", [])
    variant = len(log) % CUE_VARIANTS
    cs["lastCueAt"] = now
    cs["lastCueFirst"] = first_id
    cs["unacted"] = int(cs.get("unacted") or 0) + 1
    if reason == "deadline":
        cs["deadlineCued"] = first_id
    if reason == "off-plan":
        cs.setdefault("nudged", {})[cs["inputProject"]] = today
    log.append({"at": now, "reason": reason, "acted": False})
    del log[:-CUE_LOG_MAX]
    decision["variant"] = variant
    logger.info("now: cue %s (variant %d, unacted %d, factor %d)",
                reason, variant, cs["unacted"], factor)
    return decision


def mark_action(state: Dict[str, Any]) -> None:
    """An owner action: the last cue counts as acted on, and the backoff resets."""
    cs = state["cue"]
    if cs.get("log"):
        cs["log"][-1]["acted"] = True
    if cs.get("unacted") or int(cs.get("factor") or 1) != 1:
        logger.info("now: action taken; cue backoff reset (unacted %s, factor %s)",
                    cs.get("unacted"), cs.get("factor"))
    cs["unacted"] = 0
    cs["factor"] = 1


# --------------------------------------------------------------------------- #
# wind-down
# --------------------------------------------------------------------------- #

def is_wind_down(now: float, hour: float) -> bool:
    """After the configured evening hour, and before 05:00 the next morning."""
    local = datetime.fromtimestamp(now)
    return local.hour >= int(hour) or local.hour < 5


def utc_iso(now: float) -> str:
    return datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
