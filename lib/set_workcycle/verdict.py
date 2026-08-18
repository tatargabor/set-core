"""What a work unit returns, and what the tree says it actually did.

Two things live here and they are deliberately separate:

- the **verdict** — a schema-constrained answer from the unit, with open decisions in their
  own field;
- the **reality check** — a diff of that answer against the task markers the tree actually
  carries, reported in *both* directions.

**Why open decisions get a field rather than a paragraph.** A unit that mentions "someone
should decide whether X" in free text has not stopped anything: the next section reads the
note and answers on the human's behalf. So a note is context and a field is a stopper, and
nothing infers the second from the first. The converse matters just as much — a unit that
fills the field has stopped, whatever its prose says.

**Why a non-conforming return is a reporting failure rather than an outcome.** Guessing
`PARTIAL` from a shapeless answer produces a state the engine can act on, which is exactly
the problem: it advances on a fiction. `FAILED_TO_REPORT` cannot be mistaken for progress.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "Outcome",
    "OpenDecision",
    "Verdict",
    "VerdictSchemaError",
    "TreeDiff",
    "VERDICT_SCHEMA",
    "parse_verdict",
    "extract_verdict",
    "diff_against_tree",
]


class Outcome(str, Enum):
    """The only outcomes a unit may return, plus the one the engine records for itself."""

    GROUP_DONE = "GROUP_DONE"
    PARTIAL = "PARTIAL"
    NEEDS_INPUT = "NEEDS_INPUT"
    BLOCKED = "BLOCKED"
    #: Not returnable by a unit. The engine records it when the unit's answer did not match
    #: the schema — a reporting failure, never an inferred outcome.
    FAILED_TO_REPORT = "FAILED_TO_REPORT"

    @classmethod
    def returnable(cls) -> frozenset[str]:
        return frozenset({cls.GROUP_DONE.value, cls.PARTIAL.value,
                          cls.NEEDS_INPUT.value, cls.BLOCKED.value})


#: The declared schema, kept as data so it can be handed to a unit verbatim rather than
#: described in prose that drifts from what the parser accepts.
VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["outcome", "summary"],
    "properties": {
        "outcome": {"enum": sorted(Outcome.returnable())},
        "summary": {"type": "string"},
        "completed": {"type": "array", "items": {"type": "string"},
                      "description": "task identifiers this unit completed"},
        "open_decisions": {
            "type": "array",
            "description": "decisions needing a person. A decision described only in notes "
                           "is NOT a stop point — it must appear here.",
            "items": {
                "type": "object",
                "required": ["question"],
                "properties": {"task": {"type": "string"}, "question": {"type": "string"}},
            },
        },
        "notes": {"type": "string", "description": "carried to the next run as context only"},
    },
}


class VerdictSchemaError(ValueError):
    """The unit's answer does not match the schema. Not an outcome — a reporting failure."""


@dataclass(frozen=True)
class OpenDecision:
    """One decision a person must answer before the work it belongs to can continue."""

    question: str
    task: str = ""


@dataclass
class Verdict:
    """A unit's answer, constrained to the schema."""

    outcome: Outcome
    summary: str
    completed: tuple[str, ...] = ()
    open_decisions: tuple[OpenDecision, ...] = ()
    notes: str = ""
    #: Preserved verbatim so a later reader is not limited to what this dataclass models.
    raw: Optional[dict] = None

    @property
    def stops(self) -> bool:
        """True when this unit stopped for a person — decided by the FIELD, never the prose."""
        return bool(self.open_decisions)

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "summary": self.summary,
            "completed": list(self.completed),
            "open_decisions": [{"task": d.task, "question": d.question}
                               for d in self.open_decisions],
            "notes": self.notes,
        }


def parse_verdict(payload: Any) -> Verdict:
    """Turn a unit's answer into a `Verdict`, or raise `VerdictSchemaError`.

    Nothing is inferred. An outcome outside the enum, a missing summary, a payload that is
    not an object — each is a refusal, because every one of them is a case where guessing
    would produce something the engine could act on.
    """
    if not isinstance(payload, dict):
        raise VerdictSchemaError(
            f"a verdict must be an object; got {type(payload).__name__}")

    outcome_raw = payload.get("outcome")
    if not isinstance(outcome_raw, str) or outcome_raw not in Outcome.returnable():
        raise VerdictSchemaError(
            f"outcome {outcome_raw!r} is not one of {sorted(Outcome.returnable())}")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise VerdictSchemaError("a verdict must carry a non-empty summary")

    completed_raw = payload.get("completed") or []
    if not isinstance(completed_raw, list):
        raise VerdictSchemaError("`completed` must be a list of task identifiers")
    completed = tuple(str(c).strip() for c in completed_raw if str(c).strip())

    decisions_raw = payload.get("open_decisions") or []
    if not isinstance(decisions_raw, list):
        raise VerdictSchemaError("`open_decisions` must be a list")
    decisions: list[OpenDecision] = []
    for d in decisions_raw:
        if isinstance(d, dict):
            q = str(d.get("question", "")).strip()
            if not q:
                raise VerdictSchemaError(
                    "an open decision without a question cannot be answered, so it cannot "
                    "be recorded as one")
            decisions.append(OpenDecision(question=q, task=str(d.get("task", "")).strip()))
        elif isinstance(d, str) and d.strip():
            decisions.append(OpenDecision(question=d.strip()))
        else:
            raise VerdictSchemaError(f"unreadable open decision: {d!r}")

    verdict = Verdict(
        outcome=Outcome(outcome_raw),
        summary=summary.strip(),
        completed=completed,
        open_decisions=tuple(decisions),
        notes=str(payload.get("notes") or ""),
        raw=payload,
    )
    logger.info(
        "verdict parsed: outcome=%s completed=%d open_decisions=%d",
        verdict.outcome.value, len(verdict.completed), len(verdict.open_decisions),
    )
    return verdict


#: A fenced JSON block. The LAST one wins: a unit that shows an *example* verdict while
#: explaining itself and then emits the real one must not have its example read as the
#: answer. Reading an example as an instruction is a defect class this repository names.
_FENCED = re.compile(r"```(?:json)?\s*\n(?P<body>\{.*?\})\s*\n```", re.DOTALL)


def extract_verdict(text: str) -> Verdict:
    """Find a unit's verdict in its final message.

    Deliberately small. The measurement that shaped this change found free-text extraction
    running to 332 lines on one lane against 13 on the other, and most of that length is
    eliminable rather than portable — it exists because the phase returns prose. A unit that
    is *asked* for a schema returns one, so this looks for a fenced object and nothing more
    clever.
    """
    if not isinstance(text, str) or not text.strip():
        raise VerdictSchemaError("the unit returned no text at all")

    blocks = list(_FENCED.finditer(text))
    if blocks:
        body = blocks[-1].group("body")
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise VerdictSchemaError("no JSON object found in the unit's answer")
        body = text[start:end + 1]

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise VerdictSchemaError(f"the unit's answer is not valid JSON: {exc}") from exc
    return parse_verdict(payload)


# ── the reality check ─────────────────────────────────────────────────────────────────────


@dataclass
class TreeDiff:
    """Where a unit's claim and the tree disagree — in both directions."""

    claimed_but_unmarked: tuple[str, ...] = ()
    marked_but_unclaimed: tuple[str, ...] = ()

    @property
    def agrees(self) -> bool:
        return not self.claimed_but_unmarked and not self.marked_but_unclaimed

    def as_lines(self) -> list[str]:
        lines = []
        for k in self.claimed_but_unmarked:
            lines.append(f"claimed complete but not marked in the file: {k}")
        for k in self.marked_but_unclaimed:
            lines.append(f"marked complete in the file but not claimed: {k}")
        if not lines:
            lines.append("the verdict and the file agree")
        return lines


def diff_against_tree(
    verdict: Verdict, marked_done: Iterable[str], *, before: Optional[Sequence[str]] = None,
) -> TreeDiff:
    """Compare what the verdict claims against what the file marks.

    **Both directions, and the second one is the one that gets dropped.** "Claimed but not
    marked" is an overclaim and everyone thinks to check it. "Marked but not claimed" is work
    that happened and went unreported — the run's own summary understates it, so the next
    run's carry-over is wrong and nobody knows why.

    `before` is the set already marked when the unit started; passing it keeps a task
    completed by an *earlier* run out of this unit's divergence report.
    """
    already = set(before or ())
    marked = {str(m).strip() for m in marked_done if str(m).strip()} - already
    claimed = {c for c in verdict.completed}

    diff = TreeDiff(
        claimed_but_unmarked=tuple(sorted(claimed - marked)),
        marked_but_unclaimed=tuple(sorted(marked - claimed)),
    )
    if not diff.agrees:
        logger.warning("verdict/tree divergence: %s", "; ".join(diff.as_lines()))
    return diff
