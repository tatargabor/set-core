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

#: The edges a view may be docked to. Anything else is not a smaller mistake —
#: it is a different layout system (floating panels imply z-order, focus,
#: collision and restore-position, each of which is its own problem).
DOCK_EDGES = ("left", "right", "top", "bottom")

EMPTY: Dict[str, Any] = {
    "version": 0, "groups": [], "parked": [], "ungrouped_order": [], "splits": {},
    # Keyed by project since 2026-08-20 — see `_normalise_docks`.
    "docks": {}, "docks_legacy": [],
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


def _normalise_dock_list(raw: Any) -> List[Dict[str, Any]]:
    """One project's docked views, in order, and to which edge each is docked.

    **A list, not a map keyed by edge.** Two views can share an edge, and the
    order they sit in along it is a thing the user arranged — a map would either
    forbid the second one or lose the order, and both look like the screen
    forgetting something.

    **An unknown edge drops the entry rather than defaulting to one.** Placing a
    view on an edge nobody chose is the false-value class: it renders, it looks
    deliberate, and it is wrong. Dropping it makes the view undocked, which is
    the state it can be dragged out of.

    The SIZE of a docked view is deliberately not here — it lives in `splits`
    under the same divider mechanism every other edge uses. One position store,
    not two that can disagree about the same edge.
    """
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind") or "").strip()
        ident = str(entry.get("id") or "").strip()
        edge = str(entry.get("edge") or "").strip()
        if not kind or not ident:
            continue
        if edge not in DOCK_EDGES:
            logger.debug("fleet layout: dock %r/%r names edge %r, which is not one of %s; undocking it",
                         kind, ident, edge, DOCK_EDGES)
            continue
        # One instance, one place. The same id docked twice would render twice
        # and its position would depend on iteration order.
        key = (kind, ident)
        if key in seen:
            continue
        seen.add(key)
        entry_out: Dict[str, Any] = {"kind": kind, "id": ident, "edge": edge}
        # Collapsed is stored, not held in the browser, because it is part of
        # the arrangement: a reader who tidies a band away means it to stay
        # tidied. Only written when TRUE — an absent flag is the ordinary case
        # and does not need a key in every entry.
        if bool(entry.get("collapsed")):
            entry_out["collapsed"] = True
        out.append(entry_out)
    return out


def _normalise_docks(raw: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Docking, keyed by the PROJECT it belongs to.

    **Per project, not per screen — corrected by the user on 2026-08-20.** This
    used to be one flat list, on the reasoning that a docked band is a property
    of the screen rather than of a project. The reasoning was tidy and the effect
    was not: a terminal docked while looking at one project stayed docked while
    looking at every other one, where its own renderer could only say *"no
    running agent with this terminal in <other project>"*. So the reader lost
    the whole right-hand side of the fleet screen to an empty band that named a
    project they were not looking at — a false absence produced by the layout,
    which is exactly the class this screen exists to refuse.

    The identity that makes a dock renderable is an agent's terminal label, and
    a label belongs to a project. Keying by project is therefore not a scoping
    preference; it is the missing half of the entry's identity.

    An empty list is stored as no key at all: "nothing docked here" and "never
    docked here" render the same, and keeping a key per project the reader once
    docked in would grow the document forever.
    """
    if not isinstance(raw, dict):
        # A legacy flat list arrives here. It is NOT dropped — `_normalise_dock_legacy`
        # keeps it verbatim, because a dock without a project cannot be placed
        # without guessing which project it belonged to, and guessing is what
        # produced the defect above.
        return {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for project, entries in raw.items():
        name = str(project).strip()
        if not name:
            continue
        docked = _normalise_dock_list(entries)
        if docked:
            out[name] = docked
    return out


def _normalise_dock_legacy(raw: Any) -> List[Dict[str, Any]]:
    """The pre-2026-08-20 flat dock list, preserved verbatim and never rendered.

    Kept rather than deleted for one reason: a deleted entry and one that was
    never written are indistinguishable. It is not adopted into a project
    either, because the document does not say which project each entry belonged
    to — only the live agent inventory could answer that, and it is not what
    this module reads. The API states it so the answer is inspectable.
    """
    return _normalise_dock_list(raw)


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
        # Same rule as `splits`: named explicitly, because this function drops
        # every key it does not name. Keyed by project since 2026-08-20; a
        # document written before that carries a flat list, which lands in
        # `docks_legacy` instead of being guessed into a project.
        "docks": _normalise_docks(raw.get("docks")),
        "docks_legacy": _normalise_dock_legacy(
            raw.get("docks") if isinstance(raw.get("docks"), list) else raw.get("docks_legacy")
        ),
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


def save_docks(docks: Any, *, project: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Store which views ONE PROJECT has docked, without touching the arrangement.

    Same two properties as `save_splits`, and for the same reasons: the version
    guarding the hand-made arrangement does not move, and last-write-wins is
    accepted because what a race costs is a docking a person redoes in a second.

    Kept as a separate function rather than a flag on one writer: the two write
    different keys, and a shared writer with a mode parameter is where a caller
    eventually passes the wrong mode and clears the other key.

    **`project` is required and replaces only that project's list.** A write
    that named no project is what made docking global; refusing one here means
    the shape cannot regress to a screen-wide list by a caller forgetting an
    argument. Every other project's docking is left exactly as it was, so
    docking a terminal in one project cannot take one apart in another.
    """
    name = str(project or "").strip()
    if not name:
        raise ValueError("save_docks needs the project the docking belongs to")
    path = path or default_layout_path()
    current = load(path)
    payload = dict(current)
    stored = {k: list(v) for k, v in (current.get("docks") or {}).items()}
    docked = _normalise_dock_list(docks)
    if docked:
        stored[name] = docked
    else:
        # Nothing docked is stored as no key: see `_normalise_docks`.
        stored.pop(name, None)
    payload["docks"] = stored
    _write_atomically(payload, path)
    logger.info("fleet layout: %d docked view(s) stored for project %r at version %s (unchanged)",
                len(docked), name, payload["version"])
    return docked


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
    # And the same for docking, for the same reason and with the same escape:
    # omission preserves, an explicit empty list clears.
    if new.get("docks") is None:
        payload["docks"] = {k: list(v) for k, v in (current.get("docks") or {}).items()}
    # The legacy list is never written by a caller; it only ever survives.
    if not payload.get("docks_legacy"):
        payload["docks_legacy"] = list(current.get("docks_legacy") or [])

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
        # Keyed by project since 2026-08-20 — a docked view belongs to the
        # project whose agent it shows, not to the screen. Unjoined all the
        # same: the client picks its own project's list out of the map.
        "docks": {k: list(v) for k, v in (layout.get("docks") or {}).items()},
        # Stated rather than dropped: docking arranged before it became
        # per-project. Preserved, never rendered — see `_normalise_dock_legacy`.
        "docks_legacy": list(layout.get("docks_legacy") or []),
    }


def relabel_dock(kind: str, old_id: str, new_id: str, *,
                 path: Optional[str] = None) -> Dict[str, int]:
    """Carry a docked view's placement AND its width to a new identity.

    Both, because both are keyed on the identity: the dock entry names it, and
    the divider key is `dock:<kind>:<id>` — derived from identity on purpose, so
    that dragging a panel to another edge keeps the size the user gave it. That
    same derivation makes a rename orphan the width unless it is carried here,
    and a panel that moves but silently resizes reads as the screen deciding.

    Returns what changed, per store, rather than a boolean: a dock moved with no
    stored width is the ordinary case, and it must not look like a failure.
    """
    path = path or default_layout_path()
    current = load(path)
    docks = {p: [dict(e) for e in entries] for p, entries in (current.get("docks") or {}).items()}
    moved = 0
    for entries in docks.values():
        for entry in entries:
            if entry.get("kind") == kind and entry.get("id") == old_id:
                entry["id"] = new_id
                moved += 1

    splits = dict(current.get("splits") or {})
    old_key = f"dock:{kind}:{old_id}"
    resized = 0
    if old_key in splits:
        splits[f"dock:{kind}:{new_id}"] = splits.pop(old_key)
        resized = 1

    if not moved and not resized:
        return {"docked": 0, "splits": 0}

    payload = dict(current)
    payload["docks"] = docks
    payload["splits"] = splits
    payload["version"] = int(current["version"]) + 1
    _write_atomically(payload, path)
    logger.info("fleet layout: %s %r -> %r (%d dock(s), %d divider(s))",
                kind, old_id, new_id, moved, resized)
    return {"docked": moved, "splits": resized}
