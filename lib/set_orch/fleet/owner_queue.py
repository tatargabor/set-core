"""The owner queue — a ranked, cross-project list a project publishes for the owner.

Layer 1 (abstract). The queue is an ordinary declared status-contract command:
`owner-queue` to read, `owner-queue-act` to hand an action back. set-core keeps no
built-in list of which project publishes it; it looks for the declaration, and when
two projects declare it the owner names one in local config (`now.publisher`).

Nothing here runs a subprocess on its own: the caller injects the contract reader
and writer (`set_orch.api.project_status` wires the cached, single-flight reader and
the write function). So the transport's caching, timeouts and failure classes are
the contract's own, and these functions are testable against a fake.

**Every text field is display-only.** `sentence`, `why`, option labels, `outcome`
and a refusal's reason are the publisher's words. They pass through to the card and
are never logged or stored — log lines here carry ids, counts and classes only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..project_status import StatusConfig, StatusResult, resolve_status_config
from .now import to_epoch

logger = logging.getLogger(__name__)

READ_COMMAND = "owner-queue"
WRITE_COMMAND = "owner-queue-act"

#: The actions `owner-queue-act` receives (spec owner-queue-contract).
ACTIONS = ("answer", "done", "delegate", "park-idea", "resume-note", "wind-down-handoff",
           # The owner's "Still current?" tap: the publisher verifies ONE item in the
           # background. It never closes the item; the result comes back as `check`.
           "recheck",
           # The day's focus projects, as a list in `projects`. Not bound to an item: the
           # publisher uses it to make sure every focus project has a card.
           "focus",
           # The owner is working on it right now. NOT closing: the publisher hides the item
           # until `until` (its own default when absent) and brings it back with the note.
           "in-progress")

#: `check.state` values the card understands (spec owner-queue-contract).
CHECK_STATES = ("running", "stands", "rewritten", "stale", "failed")

REQUIRED_FIELDS = ("id", "project", "sentence", "why")
OPTIONAL_FIELDS = ("estimateMinutes", "deadline", "unblocks", "options", "acceptsText",
                   "delegable", "link", "references")

#: Failure classes that a write can only produce AFTER the command exited 0: the
#: project recorded the action and printed something that is not an envelope. The
#: action was delivered; only the outcome text is missing.
_DELIVERED_UNPARSED = frozenset({
    "invalid-json", "invalid-envelope", "missing-version", "missing-data", "unsupported-version",
})

ConfigFor = Callable[[Path], Optional[StatusConfig]]


@dataclass
class Publisher:
    """Which project publishes the owner queue — or why none can be read."""

    #: ok | none | ambiguous | configured-missing
    state: str
    name: Optional[str] = None
    path: Optional[Path] = None
    config: Optional[StatusConfig] = None
    candidates: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    #: The write command this publisher must declare to accept actions — the one
    #: paired with the read command it was found by (`owner-queue-act`, `owner-goals-act`).
    write_command: str = WRITE_COMMAND

    @property
    def accepts_actions(self) -> bool:
        return bool(self.config and self.write_command in self.config.write_commands)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "project": self.name,
            "candidates": list(self.candidates),
            "reason": self.reason,
            "acceptsActions": self.accepts_actions,
        }


def find_publisher(projects: List[Dict[str, Any]], configured: Optional[str],
                   config_for: ConfigFor = resolve_status_config, *,
                   read_command: str = READ_COMMAND,
                   write_command: str = WRITE_COMMAND,
                   published: str = "ranked queue") -> Publisher:
    """The publisher: the configured project, else the one project that declares it.

    `not declared` (state `none`) is kept apart from `ambiguous` and from a configured
    name that does not declare the command — three different things for the owner to
    fix, and none of them is an empty queue.

    `read_command` / `write_command` name the pair being looked for, so every owner-facing
    command (`owner-queue`, `owner-goals`) is found the same way, under the same
    `now.publisher` override. `published` only words the not-declared reason.
    """
    def pub(state: str, *args: Any, **kwargs: Any) -> Publisher:
        return Publisher(state, *args, write_command=write_command, **kwargs)

    declaring: List[tuple] = []
    by_name: Dict[str, Path] = {}
    for entry in projects:
        name, raw_path = entry.get("name"), entry.get("path")
        if not name or not raw_path:
            continue
        path = Path(raw_path)
        by_name[name] = path
        if not path.is_dir():
            continue
        try:
            cfg = config_for(path)
        except Exception as exc:  # one broken project must not hide the others
            logger.warning("%s: contract of %s unreadable (%s)", read_command, name,
                           type(exc).__name__)
            continue
        if cfg is not None and read_command in cfg.commands:
            declaring.append((name, path, cfg))

    if configured:
        for name, path, cfg in declaring:
            if name == configured:
                return pub("ok", name, path, cfg, [n for n, _, _ in declaring])
        why = ("is not a registered project" if configured not in by_name
               else f"does not declare '{read_command}'")
        return pub("configured-missing", configured, by_name.get(configured), None,
                   [n for n, _, _ in declaring],
                   f"the configured publisher '{configured}' {why}")
    if not declaring:
        return pub("none", reason="no registered project declares "
                                  f"'{read_command}' — no {published} is published")
    if len(declaring) > 1:
        names = [n for n, _, _ in declaring]
        return pub("ambiguous", candidates=names,
                   reason=f"{len(names)} projects declare '{read_command}' "
                          f"({', '.join(names)}); name one with "
                          "`set-config set now.publisher <project>`")
    name, path, cfg = declaring[0]
    return pub("ok", name, path, cfg, [name])


@dataclass
class QueueRead:
    measured: bool
    reason: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    malformed: int = 0
    complete: Optional[bool] = None
    ranked_at: Optional[str] = None
    ranking_age_s: Optional[float] = None
    #: The publisher's own sources it could not read this round — display-only names.
    unread_sources: List[str] = field(default_factory=list)


def _clean_options(raw: Any) -> List[Dict[str, str]]:
    out = []
    if isinstance(raw, list):
        for opt in raw:
            if isinstance(opt, dict) and opt.get("id") is not None and opt.get("label") is not None:
                out.append({"id": str(opt["id"]), "label": str(opt["label"])})
    return out


def parse_item(raw: Any) -> Optional[Dict[str, Any]]:
    """One item in the card's shape, or None when a required field is missing."""
    if not isinstance(raw, dict):
        return None
    for key in REQUIRED_FIELDS:
        value = raw.get(key)
        if not isinstance(value, (str, int)) or str(value).strip() == "":
            return None
    item: Dict[str, Any] = {
        "source": READ_COMMAND,
        "id": str(raw["id"]),
        "project": str(raw["project"]),
        "sentence": str(raw["sentence"]),
        "why": str(raw["why"]),
        "options": _clean_options(raw.get("options")),
        "acceptsText": raw.get("acceptsText") is True,
        "delegable": raw.get("delegable") is True,
    }
    est = raw.get("estimateMinutes")
    if isinstance(est, (int, float)) and not isinstance(est, bool):
        item["estimateMinutes"] = est
    for key in ("deadline", "unblocks", "link"):
        if isinstance(raw.get(key), str) and raw[key].strip():
            item[key] = raw[key]
    if isinstance(raw.get("resumeNote"), str) and raw["resumeNote"].strip():
        item["resumeNote"] = raw["resumeNote"]
    # What the owner noted when he tapped "working on it" — shown when the item is back.
    if isinstance(raw.get("progressNote"), str) and raw["progressNote"].strip():
        item["progressNote"] = raw["progressNote"]
    if isinstance(raw.get("firstSeen"), str) and to_epoch(raw["firstSeen"]) is not None:
        item["firstSeen"] = raw["firstSeen"]
    check = raw.get("check")
    if isinstance(check, dict) and check.get("state") in CHECK_STATES:
        item["check"] = {k: str(check[k]) for k in ("state", "startedAt", "at", "evidence")
                         if isinstance(check.get(k), str) and check[k].strip()}
    refs = raw.get("references")
    if isinstance(refs, list):
        item["references"] = [{"source": r.get("source"), "id": str(r["id"])}
                              for r in refs if isinstance(r, dict) and r.get("id") is not None]
    return item


def unread_sources(raw: Any) -> List[str]:
    """The publisher's unread inputs as display lines: `name` or `name — reason`.

    Shared by every owner-facing read (`owner-queue`, `owner-goals`). Entries of any
    other shape are dropped: they name nothing the owner could act on.
    """
    out: List[str] = []
    for src in raw if isinstance(raw, list) else []:
        if isinstance(src, str) and src.strip():
            out.append(src)
        elif isinstance(src, dict) and (src.get("name") or src.get("source")):
            name = str(src.get("name") or src.get("source"))
            reason = src.get("reason")
            out.append(f"{name} — {reason}" if isinstance(reason, str) and reason else name)
    return out


def parse_queue(result: StatusResult, now: float) -> QueueRead:
    """The publisher's answer as items in rank order, with its completeness markers."""
    if not result.ok:
        return QueueRead(measured=False,
                         reason=result.error or f"the '{READ_COMMAND}' command failed",
                         )
    data = result.data
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return QueueRead(measured=False,
                         reason=f"the '{READ_COMMAND}' answer carries no 'items' list")
    items: List[Dict[str, Any]] = []
    malformed = 0
    seen = set()
    for raw in data["items"]:
        item = parse_item(raw)
        if item is None or item["id"] in seen:
            malformed += 1
            continue
        seen.add(item["id"])
        items.append(item)
    if malformed:
        logger.warning("owner queue: %d item(s) missing a required field or duplicated; skipped",
                       malformed)
    complete = data.get("complete") if isinstance(data.get("complete"), bool) else None
    ranked_at = data.get("rankedAt") if isinstance(data.get("rankedAt"), str) else None
    ranked_epoch = to_epoch(ranked_at)
    return QueueRead(
        unread_sources=unread_sources(data.get("unreadSources")),
        measured=True, items=items, malformed=malformed, complete=complete,
        ranked_at=ranked_at,
        ranking_age_s=(max(0.0, now - ranked_epoch) if ranked_epoch is not None else None),
    )


def act_payload(item_id: str, action: str, *, option: Optional[str] = None,
                text: Optional[str] = None, reasons: Optional[List[str]] = None,
                until: Optional[str] = None,
                projects: Optional[List[str]] = None) -> Dict[str, Any]:
    """`{ id, action, option?, text?, reasons?, until?, projects? }` — absent keys are left out."""
    if action not in ACTIONS:
        raise ValueError(f"not an owner-queue action: {action!r}")
    payload: Dict[str, Any] = {"id": item_id, "action": action}
    if option is not None:
        payload["option"] = option
    if text is not None:
        payload["text"] = text
    if reasons:
        payload["reasons"] = list(reasons)
    if until is not None:
        payload["until"] = until
    if projects is not None:
        payload["projects"] = list(projects)
    return payload


def write_args(payload: Dict[str, Any]) -> Dict[str, str]:
    """The payload as the write transport's `{flag: value}` — ONE flag, `--json <object>`.

    One JSON value rather than a flag per field, for a reason the transport states:
    it refuses a value that starts with `-`, and free text (a dictated answer, a
    reason) can. A JSON object always starts with `{`.
    """
    return {"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}


@dataclass
class ActResult:
    delivered: bool
    outcome: Optional[str] = None
    reason: Optional[str] = None
    error_class: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"delivered": self.delivered, "outcome": self.outcome,
                "reason": self.reason, "errorClass": self.error_class}


def interpret_write(result: StatusResult) -> ActResult:
    """Delivered with the publisher's outcome, delivered without one, or refused with its reason."""
    if result.ok:
        data = result.data
        outcome = data.get("outcome") if isinstance(data, dict) else None
        return ActResult(True, outcome=str(outcome) if isinstance(outcome, str) and outcome else None)
    if result.error_class in _DELIVERED_UNPARSED:
        # Exit 0: the project recorded it. Say what we know and nothing more.
        return ActResult(True, outcome=None, error_class=result.error_class)
    return ActResult(False, reason=result.error, error_class=result.error_class)
