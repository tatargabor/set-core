"""The fleet screen's ARRANGEMENT — groups, order, parked projects (D-2).

Decided by the user 2026-08-19: the project list is ordered by hand, in two
levels. Groups are ordered and render as blocks; a project moves only inside its
own group; projects are assigned to groups by hand from the surface. A parked
section holds what the user wants out of the way.

**Why this is stored on the server rather than in `localStorage`,** which is what
the dashboard uses for its other view preferences. Arranging 45 projects into
groups is work, and it is work the user does once and relies on. A collapse
toggle can be lost to a cleared cache without anyone minding; an arrangement
cannot, and it should not differ between two browsers on the same machine.

**What this file is NOT, and the distinction is the whole design.** It is
*arrangement*, never the inventory. Discovery says what exists; this says where
the user wants it. So:

- a project named here that no longer exists is **reported, not silently dropped**
  — a name disappearing from a hand-made arrangement is information;
- a project that exists but is named nowhere here appears in the ungrouped tail,
  never nothing. A project absent from a declaration is not an absent project.

This is the same rule as counting from the data and using the declaration only to
know what to look for.

**Group membership is a stored fact, not a name-prefix rule.** `set-*` looks like
a rule, and a rule re-evaluates: rename a project and it silently changes group;
add one whose name happens to start with `set-` and it lands somewhere nobody put
it. A prefix may *seed* a group as a one-time bulk act whose result the user can
see; what persists is the membership.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: The framework's durable per-user store — the same root that already holds
#: `memory`, `metrics`, `e2e-runs`, `manager` and `runtime`.
def default_layout_path() -> str:
    root = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(root, "set-core", "fleet-layout.json")


class LayoutConflict(RuntimeError):
    """A write was based on a version that is no longer current."""


#: The narrowest and widest a draggable divider may be stored at.
#:
#: The server does not know the viewport, so these are not a layout decision —
#: they are the range outside which a stored value would make the surface
#: unusable with no way back: a pane dragged to zero is indistinguishable from a
#: pane that is gone, and one dragged past the window cannot be grabbed again.
#: The client clamps to what actually fits; this clamps to what is recoverable.
MIN_SPLIT = 140
MAX_SPLIT = 1200

EMPTY: Dict[str, Any] = {
    "version": 0, "groups": [], "parked": [], "ungrouped_order": [], "splits": {},
}


def _normalise_group(raw: Any, seen: set) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    if not name:
        return None
    projects: List[str] = []
    for entry in raw.get("projects") or []:
        project = str(entry).strip()
        # One project, one place. A project listed in two groups would render
        # twice and its position would depend on iteration order — a arrangement
        # that changes without anyone moving anything.
        if project and project not in seen:
            seen.add(project)
            projects.append(project)
    return {
        "id": str(raw.get("id") or name),
        "name": name,
        "collapsed": bool(raw.get("collapsed")),
        "projects": projects,
    }


def _normalise_splits(raw: Any) -> Dict[str, int]:
    """Stored divider positions, in CSS pixels, keyed by which divider.

    **An absent key means "never dragged", and that is NOT zero.** The client
    then uses its own default width. Storing a zero for an untouched divider
    would be the false-absence class with the expensive direction: a pane
    collapsed to nothing looks exactly like a pane that was removed, and nobody
    would think to drag an edge they cannot see.

    So a value that is not a usable number is dropped rather than coerced —
    dropping it restores the default, coercing it would invent a position the
    user never chose.
    """
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, int] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            px = int(round(float(value)))
        except (TypeError, ValueError):
            logger.debug("fleet layout: divider %r has an unusable position %r; using the default", name, value)
            continue
        if px < MIN_SPLIT or px > MAX_SPLIT:
            logger.debug("fleet layout: divider %r at %spx is outside [%s, %s]; clamping", name, px, MIN_SPLIT, MAX_SPLIT)
            px = max(MIN_SPLIT, min(MAX_SPLIT, px))
        out[name] = px
    return out


def normalise(raw: Any) -> Dict[str, Any]:
    """Coerce whatever was stored or posted into the shape the surface expects.

    Deliberately forgiving about extra keys and strict about the two invariants
    that make the arrangement renderable at all: a group has a name, and a
    project appears at most once across every group and the parked list.
    """
    if not isinstance(raw, dict):
        return dict(EMPTY)
    seen: set = set()
    groups = [g for g in (_normalise_group(g, seen) for g in raw.get("groups") or []) if g]
    parked: List[str] = []
    for entry in raw.get("parked") or []:
        project = str(entry).strip()
        if project and project not in seen:
            seen.add(project)
            parked.append(project)
    # The unassigned block's own order. It is a preference rather than a
    # membership: a name here that later joins a group is dropped, so the
    # one-project-one-place rule holds without a second bookkeeping path.
    ungrouped_order: List[str] = []
    for entry in raw.get("ungrouped_order") or []:
        project = str(entry).strip()
        if project and project not in seen and project not in ungrouped_order:
            ungrouped_order.append(project)
    try:
        version = int(raw.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    return {
        "version": max(version, 0),
        "groups": groups,
        "parked": parked,
        "ungrouped_order": ungrouped_order,
        # Normalised explicitly, because this function DROPS every key it does
        # not name. A divider position added to the stored file but not handled
        # here would survive a read and vanish on the next save — silently, and
        # only for the user who had arranged something.
        "splits": _normalise_splits(raw.get("splits")),
    }


def load(path: Optional[str] = None) -> Dict[str, Any]:
    """The stored arrangement, or an empty one. Never raises for a missing file.

    A missing arrangement and an empty arrangement mean the same thing here —
    nothing has been arranged — and both must produce a screen, so this fails
    toward "no arrangement" rather than toward an error.
    """
    path = path or default_layout_path()
    try:
        with open(path, encoding="utf-8") as handle:
            return normalise(json.load(handle))
    except FileNotFoundError:
        return dict(EMPTY)
    except (OSError, ValueError) as exc:
        logger.warning("fleet layout: %s is unreadable (%s); treating as unarranged", path, exc)
        return dict(EMPTY)


def _write_atomically(payload: Dict[str, Any], path: str) -> None:
    """Temp file then rename — never opened for writing in the expression that reads it.

    One helper rather than one per writer: two copies of an atomic write drift,
    and the half that drifts is always the error handling nobody exercises.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=os.path.dirname(path), prefix=".fleet-layout.", delete=False
    )
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def save_splits(splits: Any, *, path: Optional[str] = None) -> Dict[str, int]:
    """Store where the draggable dividers sit, WITHOUT touching the arrangement.

    **Two deliberate differences from `save`, and both are load-bearing.**

    *It does not bump `version`.* That version is the optimistic lock protecting a
    hand-made arrangement, and a divider is not part of one. Bumping it would make
    every drag of an edge invalidate the base version an open project column is
    holding, so the next group edit in that tab would 409 — a conflict caused
    entirely by the conflict machinery.

    *It is last-write-wins, on purpose.* Losing a race here costs one number the
    user re-drags in a second. Losing one on an arrangement costs work they did
    once and rely on. The same reasoning the module header gives for storing the
    arrangement on the server rather than in `localStorage` decides this the other
    way, and that is the point of separating them.
    """
    path = path or default_layout_path()
    current = load(path)
    payload = dict(current)
    payload["splits"] = _normalise_splits(splits)
    _write_atomically(payload, path)
    logger.info("fleet layout: %d divider position(s) stored at version %s (unchanged)",
                len(payload["splits"]), payload["version"])
    return payload["splits"]


def save(new: Dict[str, Any], *, path: Optional[str] = None, base_version: Optional[int] = None) -> Dict[str, Any]:
    """Replace the arrangement, refusing a write based on a stale version.

    **Optimistic concurrency rather than last-write-wins**, because the thing
    being overwritten is hand-made. Two dashboard tabs are ordinary, and the
    loser of a silent race would find an arrangement they never made, with no
    event to explain it and no way back.

    Written through a temp file and renamed — never opened for writing in the
    same expression that reads it, which truncates the file before the read.
    """
    path = path or default_layout_path()
    current = load(path)
    if base_version is not None and int(base_version) != int(current["version"]):
        raise LayoutConflict(
            f"the arrangement changed since you read it (yours {base_version}, "
            f"current {current['version']}); reload before saving"
        )

    payload = normalise(new)
    payload["version"] = int(current["version"]) + 1
    # A caller that says nothing about dividers is not asking for them to be
    # cleared. `normalise` returns `{}` for both "no dividers" and "not
    # mentioned", so without this the project column — which posts groups and
    # nothing else — would wipe the user's dragged edges on every drag of a
    # project, silently and only for someone who had arranged both.
    if new.get("splits") is None:
        payload["splits"] = dict(current.get("splits") or {})

    _write_atomically(payload, path)
    logger.info(
        "fleet layout: saved version %s (%d group(s), %d parked)",
        payload["version"], len(payload["groups"]), len(payload["parked"]),
    )
    return payload


def apply_to(layout: Dict[str, Any], existing: Sequence[str]) -> Dict[str, Any]:
    """Join the arrangement to what discovery actually found.

    The two failure directions this exists to prevent, and both are silent:

    - a project the user arranged that no longer exists would simply not render,
      so the arrangement would appear to have changed by itself. It is reported
      as `missing` instead, and the surface can say so where the reader stands.
    - a project that exists but was never arranged would fall out of the screen
      entirely — the false-absence class. It lands in `ungrouped`, which is
      rendered as one more group at the end rather than as a second layout mode.
    """
    known = list(dict.fromkeys(existing))
    known_set = set(known)
    placed: set = set()

    groups: List[Dict[str, Any]] = []
    missing: List[str] = []
    for group in layout.get("groups", []):
        stored = list(group["projects"])
        present = [p for p in stored if p in known_set]
        gone = [p for p in stored if p not in known_set]
        placed.update(present)
        missing.extend(gone)
        # `order` is the stored list VERBATIM, and it exists so a client saving
        # the arrangement back does not have to reconstruct it. Merging `present`
        # and `missing` by hand loses each missing member's POSITION — it can
        # only be re-appended — so an absent project silently drifts to the end
        # of its group every time anything is saved.
        groups.append({**group, "projects": present, "missing": gone, "order": stored})

    stored_parked = list(layout.get("parked", []))
    parked = [p for p in stored_parked if p in known_set]
    parked_missing = [p for p in stored_parked if p not in known_set]
    missing.extend(parked_missing)
    placed.update(parked)

    # The unassigned block, in the user's order where they gave one. Names they
    # ordered that have since joined a group or vanished are simply not here;
    # projects they never ordered follow, in discovery's order.
    preferred = [p for p in layout.get("ungrouped_order", []) if p in known_set and p not in placed]
    ungrouped = preferred + [p for p in known if p not in placed and p not in preferred]
    return {
        "version": layout.get("version", 0),
        "groups": groups,
        "parked": parked,
        # Stated rather than left to subtraction. The client used to derive this
        # by removing every group's missing from the total, which is an inference
        # standing in for data — and inferences are where a wrong answer looks
        # like a computed one.
        "parked_missing": parked_missing,
        "parked_order": stored_parked,
        "ungrouped": ungrouped,
        # Named rather than counted from the declaration: this list IS the data,
        # derived by comparing the arrangement against what discovery found.
        "missing": missing,
        # Passed through unjoined: a divider belongs to the screen, not to a
        # project, so there is nothing for it to be missing FROM.
        "splits": dict(layout.get("splits") or {}),
    }
