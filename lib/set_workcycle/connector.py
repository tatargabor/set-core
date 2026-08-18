"""Setting a unit aside, and the directory answers arrive through.

The engine never learns who wrote an answer. A chat bridge, the framework's surface, or a
person with an editor all put a document in a directory; delivery, notification and the
decision to run again are the caller's business. That is what makes this a *connector* rather
than an answer flow.

Three properties are not optional, because all three were measured breaking in production:

- **Deferral before quarantine.** A document that will not parse is treated as an in-flight
  write and retried. Quarantining on the first failure buries a human decision over a timing
  accident — six documents sat quarantined that way.
- **Names carry source and time.** The key lives *inside* the document, which leaves the
  filename free — and therefore leaves two uploaders free to overwrite each other silently.
  Named by source and timestamp they cannot, and several answers for one key are kept.
- **Consumption is stamped, not inferred.** Directory state lied in both directions where
  this was measured: consumed answers still present, unconsumed answers taken for processed.
  Eighteen answers sat unconsumed, three of them answered the same day.

A fourth property comes from the engine rather than the connector, and is stated here because
this is where a reader looks for it: **a condition that is not named cannot be observed**, so
a unit cannot be set aside without one — and the condition is not limited to a human answer.
The third prospective consumer of this engine stops on an external system, not a person; had
the abstraction said "awaiting human", a word would have excluded them.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "ANSWERS_REL",
    "QUARANTINE_REL",
    "INTAKE_STATE_REL",
    "CONSUMPTION_LOG_REL",
    "MAX_PARSE_ATTEMPTS",
    "ConditionRequired",
    "ResumeCondition",
    "Answer",
    "IntakeResult",
    "answer_filename",
    "write_answer",
    "intake",
    "mark_awaiting",
    "clear_awaiting",
    "awaiting_tasks",
    "record_answer",
    "answers_for",
]

ANSWERS_REL = "set/runtime/work-cycle/answers"
QUARANTINE_REL = "set/runtime/work-cycle/answers/quarantine"
INTAKE_STATE_REL = "set/runtime/work-cycle/answers/.intake.json"
CONSUMPTION_LOG_REL = "set/runtime/work-cycle/answers/.consumed.jsonl"

#: How many successive intakes a document may fail to parse before it is quarantined. Greater
#: than one on purpose: one failure is indistinguishable from a write still in flight.
MAX_PARSE_ATTEMPTS = 3

HUMAN_DECISION = "human-decision"
EXTERNAL_SYSTEM = "external-system"


class ConditionRequired(ValueError):
    """A unit was set aside with no resume condition. Refused: nothing could observe it."""


@dataclass(frozen=True)
class ResumeCondition:
    """What has to become true before a set-aside unit can run again.

    `kind` is open rather than an enum of two: the two known kinds are a person's decision and
    an external system's availability, and a third consumer will have a third. What is closed
    is that there must BE one.
    """

    kind: str
    detail: str
    task: str = ""
    dependency: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail,
                "task": self.task, "dependency": self.dependency}

    @property
    def awaits_a_person(self) -> bool:
        return self.kind == HUMAN_DECISION

    @classmethod
    def human_decision(cls, question: str, task: str = "") -> "ResumeCondition":
        if not (question or "").strip():
            raise ConditionRequired("a decision with no question cannot be answered")
        return cls(kind=HUMAN_DECISION, detail=question.strip(), task=task)

    @classmethod
    def external_system(cls, dependency: str, detail: str = "") -> "ResumeCondition":
        if not (dependency or "").strip():
            raise ConditionRequired("an external dependency must be named")
        return cls(kind=EXTERNAL_SYSTEM, detail=detail or f"{dependency} is unavailable",
                   dependency=dependency.strip())

    @classmethod
    def require(cls, condition: Optional["ResumeCondition"]) -> "ResumeCondition":
        if condition is None:
            raise ConditionRequired(
                "a unit cannot be set aside without a resume condition — a condition that is "
                "not named cannot be observed, so nothing would ever release the unit"
            )
        return condition


# ── the answer directory ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Answer:
    """One answer document: its key, its content, and where it came from."""

    change: str
    task: str
    answer: str
    source: str = ""
    written_at: str = ""
    path: Optional[Path] = None
    raw: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.change}#{self.task}"


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def answer_filename(source: str, when: Optional[str] = None, suffix: str = ".json") -> str:
    """A name carrying source and time, so two uploaders cannot silently overwrite each other.

    The key is inside the document — which is what leaves the *name* free, and a free name is
    one two writers will collide on. This is the whole reason the name is generated rather
    than chosen.
    """
    stamp = when or time.strftime("%Y%m%dT%H%M%S")
    return f"{_SAFE.sub('-', source or 'unknown')}--{_SAFE.sub('-', stamp)}{suffix}"


def write_answer(
    tree: str | Path, change: str, task: str, answer: str, *, source: str,
    when: Optional[str] = None,
) -> Path:
    """Place an answer in the connector's directory. Any caller may do this."""
    directory = Path(tree) / ANSWERS_REL
    directory.mkdir(parents=True, exist_ok=True)
    written_at = when or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    path = directory / answer_filename(source, when)
    if path.exists():  # same source, same second — keep both rather than overwrite
        path = directory / answer_filename(source, f"{when or time.strftime('%Y%m%dT%H%M%S')}-2")
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps({
        "change": change, "task": task, "answer": answer,
        "source": source, "written_at": written_at,
    }, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    logger.info("answer written for %s#%s by %s: %s", change, task, source, path.name)
    return path


@dataclass
class IntakeResult:
    """What one intake pass found. Every category is reported; none is silent."""

    applied: list[Answer] = field(default_factory=list)
    unmatched: list[Answer] = field(default_factory=list)
    superseded: list[Answer] = field(default_factory=list)
    deferred: list[tuple[str, int, str]] = field(default_factory=list)   # name, attempts, why
    quarantined: list[tuple[str, str]] = field(default_factory=list)     # name, why
    already_consumed: list[str] = field(default_factory=list)

    def as_lines(self) -> list[str]:
        lines = [f"applied {a.key} (from {a.source})" for a in self.applied]
        lines += [f"unmatched {a.key} — left in place" for a in self.unmatched]
        lines += [f"superseded {a.key} — retained, a newer answer won" for a in self.superseded]
        lines += [f"deferred {n} (attempt {k}/{MAX_PARSE_ATTEMPTS}): {w}"
                  for n, k, w in self.deferred]
        lines += [f"quarantined {n}: {w}" for n, w in self.quarantined]
        return lines or ["no answers were pending"]


def _load_state(tree: Path) -> dict:
    path = tree / INTAKE_STATE_REL
    if not path.is_file():
        return {"attempts": {}, "consumed": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("intake state at %s is unreadable — starting from empty", path)
        return {"attempts": {}, "consumed": {}}
    data.setdefault("attempts", {})
    data.setdefault("consumed", {})
    return data


def _save_state(tree: Path, state: dict) -> None:
    path = tree / INTAKE_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _stamp_consumption(tree: Path, answer: Answer, when: str) -> None:
    """Record consumption on the answer AND in a log.

    Two carriers because the failure was measured in both directions. Directory state is
    never the only evidence, and a count of files is never evidence at all.
    """
    if answer.path is not None and answer.path.is_file():
        payload = dict(answer.raw)
        payload["consumed_at"] = when
        tmp = answer.path.with_name(answer.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(answer.path)
    log = tree / CONSUMPTION_LOG_REL
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"key": answer.key, "file": answer.path.name if answer.path else "",
                             "source": answer.source, "consumed_at": when}) + "\n")


def intake(
    tree: str | Path, *, awaiting: Optional[Iterable[str]] = None, now: Optional[str] = None,
    max_attempts: int = MAX_PARSE_ATTEMPTS,
) -> IntakeResult:
    """Take in every pending answer. Called at the entry point on **every** path.

    `awaiting` is the set of `<change>#<task>` keys currently waiting. An answer for anything
    else is reported as unmatched and **left in place** — discarding it would throw away a
    person's work because the engine's own state was momentarily behind.
    """
    root = Path(tree)
    directory = root / ANSWERS_REL
    result = IntakeResult()
    if not directory.is_dir():
        return result

    awaiting_keys = set(awaiting or ())
    state = _load_state(root)
    when = now or time.strftime("%Y-%m-%dT%H:%M:%S%z")

    parsed: list[Answer] = []
    for path in sorted(directory.glob("*.json")):
        if path.parent.name == "quarantine":
            continue
        # The connector's OWN bookkeeping lives in this directory, so a plain glob sweeps it
        # up and tries to read it as an answer — the measurement inside the corpus it
        # measures. Found by a smoke test, and its direction is the bad one: the intake state
        # file fails to parse as an answer, is deferred, and after three passes the connector
        # QUARANTINES its own memory of what it has already consumed.
        if path.name.startswith("."):
            continue
        name = path.name
        if name in state["consumed"]:
            result.already_consumed.append(name)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("an answer document must be an object")
            change = str(payload.get("change", "")).strip()
            task = str(payload.get("task", "")).strip()
            if not change or not task:
                raise ValueError("an answer must carry its own change and task")
        except (OSError, ValueError) as exc:
            attempts = int(state["attempts"].get(name, 0)) + 1
            state["attempts"][name] = attempts
            if attempts >= max_attempts:
                quarantine = root / QUARANTINE_REL
                quarantine.mkdir(parents=True, exist_ok=True)
                reason = f"failed to parse on {attempts} successive intakes: {exc}"
                (quarantine / (name + ".reason.txt")).write_text(reason + "\n", encoding="utf-8")
                path.replace(quarantine / name)
                state["attempts"].pop(name, None)
                result.quarantined.append((name, reason))
                logger.error("answer %s quarantined: %s", name, reason)
            else:
                result.deferred.append((name, attempts, str(exc)))
                logger.info(
                    "answer %s deferred (attempt %d/%d) — treated as an in-flight write: %s",
                    name, attempts, max_attempts, exc,
                )
            continue

        state["attempts"].pop(name, None)
        parsed.append(Answer(
            change=change, task=task, answer=str(payload.get("answer", "")),
            source=str(payload.get("source", "")),
            written_at=str(payload.get("written_at", "")),
            path=path, raw=payload,
        ))

    # Several answers may exist for one key: the newest is applied and the rest are RETAINED.
    # Ordering falls back to the filename, which carries a timestamp by construction.
    by_key: dict[str, list[Answer]] = {}
    for a in parsed:
        by_key.setdefault(a.key, []).append(a)

    for key, answers in by_key.items():
        answers.sort(key=lambda a: (a.written_at, a.path.name if a.path else ""))
        newest = answers[-1]
        if awaiting_keys and key not in awaiting_keys:
            result.unmatched.extend(answers)
            logger.info("answer for %s is unmatched (nothing awaits it) — left in place", key)
            continue
        result.applied.append(newest)
        result.superseded.extend(answers[:-1])
        _stamp_consumption(root, newest, when)
        state["consumed"][newest.path.name if newest.path else key] = when

    _save_state(root, state)
    logger.info(
        "intake: %d applied, %d unmatched, %d superseded, %d deferred, %d quarantined",
        len(result.applied), len(result.unmatched), len(result.superseded),
        len(result.deferred), len(result.quarantined),
    )
    return result


# ── the durable stop marker in the task file ──────────────────────────────────────────────
#
# Marking is the ONLY mutation the engine performs on a project's task file. Reformatting or
# rewriting it is out of scope, and the verdict/tree diff exists to catch a run whose claims
# and the file disagree.

_AWAITING_NOTE = "<!-- awaiting: {question} -->"
_AWAITING_RE = re.compile(r"<!--\s*awaiting:\s*(?P<question>.*?)\s*-->")


def _task_line_re(task: str) -> re.Pattern:
    return re.compile(rf"(?m)^(?P<indent>\s*)-\s*\[(?P<mark>[ xX?])\]\s+(?P<id>{re.escape(task)})\b")


def mark_awaiting(tasks_path: str | Path, task: str, question: str) -> bool:
    """Mark `task` as awaiting a person, recording the question beside it.

    The marker lives in the file, so it survives the run that produced it and any restart of
    the engine — and it is visible to a person reading the file, which a lock file is not.
    """
    path = Path(tasks_path)
    text = path.read_text(encoding="utf-8")
    match = _task_line_re(task).search(text)
    if match is None:
        logger.warning("mark_awaiting: no task %r in %s", task, path)
        return False

    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.start())
    line_end = len(text) if line_end == -1 else line_end
    line = text[line_start:line_end]

    updated_line = re.sub(r"^(\s*)-\s*\[[ xX?]\]", r"\1- [?]", line, count=1)
    updated_line = _AWAITING_RE.sub("", updated_line).rstrip()
    updated_line = f"{updated_line} {_AWAITING_NOTE.format(question=question.strip())}"

    _write(path, text[:line_start] + updated_line + text[line_end:])
    logger.info("task %s in %s marked as awaiting a person", task, path)
    return True


def clear_awaiting(tasks_path: str | Path, task: str) -> bool:
    """Release a task an answer has arrived for: back to open, question note removed."""
    path = Path(tasks_path)
    text = path.read_text(encoding="utf-8")
    match = _task_line_re(task).search(text)
    if match is None or match.group("mark") != "?":
        return False
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.start())
    line_end = len(text) if line_end == -1 else line_end
    line = _AWAITING_RE.sub("", text[line_start:line_end]).rstrip()
    line = re.sub(r"^(\s*)-\s*\[\?\]", r"\1- [ ]", line, count=1)
    _write(path, text[:line_start] + line + text[line_end:])
    logger.info("task %s in %s released — an answer arrived", task, path)
    return True


def awaiting_tasks(tasks_path: str | Path) -> list[tuple[str, str]]:
    """Every `(task id, question)` currently marked as awaiting a person."""
    text = Path(tasks_path).read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*\[\?\]\s+(?P<id>\S+)", line)
        if not m:
            continue
        q = _AWAITING_RE.search(line)
        out.append((m.group("id"), q.group("question") if q else ""))
    return out


def _write(path: Path, text: str) -> None:
    """Temp-file-and-replace. Never open for writing in the expression that reads."""
    tmp = path.with_name(path.name + ".set-tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ── answers, kept where the NEXT run can still find them ──────────────────────────────────
#
# Releasing a task is not the same as delivering the answer. A live run showed the gap: a
# reporting-only invocation took the answer in and released the task, and by the time a unit
# ran, the answer's TEXT was gone — so the unit asked the same question again. The release
# survived in the task file; the content had nowhere to live. It does now.

ANSWER_LOG_REL = "set/runtime/work-cycle/{change}/answers.jsonl"


def record_answer(tree: str | Path, change: str, task: str, answer: str,
                  source: str = "", when: Optional[str] = None) -> Path:
    """Keep an applied answer with its change, so any later run can carry it forward."""
    path = Path(tree) / ANSWER_LOG_REL.format(change=change)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "task": task, "answer": answer, "source": source,
            "recorded_at": when or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }) + "\n")
    logger.info("answer for %s#%s recorded for later runs", change, task)
    return path


def answers_for(tree: str | Path, change: str,
                tasks: Optional[Iterable[str]] = None) -> list[tuple[str, str]]:
    """Every answer recorded for `change`, newest per task, optionally limited to `tasks`."""
    path = Path(tree) / ANSWER_LOG_REL.format(change=change)
    if not path.is_file():
        return []
    wanted = {str(t) for t in tasks} if tasks is not None else None
    latest: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        task = str(row.get("task", ""))
        if not task or (wanted is not None and task not in wanted):
            continue
        latest[task] = str(row.get("answer", ""))
    return sorted(latest.items())
