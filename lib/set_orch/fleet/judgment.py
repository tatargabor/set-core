"""Which quiet agents are asking a person for something — one model pass a cycle.

Group 2 of the `fleet-pm-mode` change, and the division of labour is the design
rather than a detail of it.

## What this module is NOT allowed to decide

The state layer already answers, structurally and for free, the two questions a
model would only agree with: an agent with an outstanding tool call is working,
and an agent with an outstanding *question* tool is `asking` — measured, certain,
and needing nobody's opinion. Those never reach the model, and a verdict may
never remove one (`reconcile`). A measurement outranks an opinion; the
disagreement is recorded rather than resolved.

What is left is genuinely a judgement about prose: a quiet agent's last turn
either asked for something or merely reported. Measured 2026-08-20 on this
machine, 17 quiet agents split 12 / 3 / 2 by who spoke last, and the ones that
mattered were indistinguishable by any keyword test — "⚠ Álljunk meg — más
ügynökök is commitolnak ebbe a repóba" contains no question mark.

## One call, no memory

One invocation per cycle carries every candidate. Not one per agent — the fleet
is 18 agents on this machine with no bound in the design — and not a long-lived
session either: a session accumulating a day of fleet output compacts, and a
compacted context keeps its confidence while losing its precision, which is
exactly how a queue starts re-presenting what it already showed. Everything
worth remembering is held by the caller, in code, and is re-derivable.

## Confidentiality

The prompt carries verbatim session text from projects that are not this
framework's. Per `CLAUDE.md` the boundary is PERSISTENCE, and this module writes
none of it: no log line here contains a subject's text, a verdict's reasoning is
discarded after the class is read, and what is retained between cycles is a class
and an identity. The runtime's own session journal is the one named exception —
invoking a model writes the prompt there by construction — and it is not widened.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import state as agent_state

logger = logging.getLogger(__name__)

__all__ = [
    "ASKING", "FINISHED", "STOPPED", "UNCLASSIFIED", "VERDICT_CLASSES",
    "Subject", "Verdict", "PassResult", "Watermark",
    "MAX_CANDIDATES", "CYCLE_SECONDS", "JUDGE_EXCERPT_CHARS",
    "watermark_of", "select_candidates", "structural_verdicts",
    "build_prompt", "parse_response", "reconcile", "run_pass",
]


# --------------------------------------------------------------------------- #
# the classes a verdict may name
# --------------------------------------------------------------------------- #

#: A person's answer is what this agent needs next.
ASKING = "asking"
#: The turn ended and nothing was asked. Counted, never queued.
FINISHED = "finished"
#: Interrupted, errored, or dropped — stopped for a reason that is not a question.
STOPPED = "stopped"
#: No verdict, or a verdict this build does not recognise. NEVER mapped onto a
#: neighbour: the direction that hurts is mapping an unknown class onto
#: `finished`, which makes an agent needing a person disappear.
UNCLASSIFIED = "unclassified"

#: What the model is allowed to say. `UNCLASSIFIED` is deliberately not here —
#: it is what the framework concludes, never what the model claims.
VERDICT_CLASSES = (ASKING, FINISHED, STOPPED)


# --------------------------------------------------------------------------- #
# configuration — declared, not scattered
# --------------------------------------------------------------------------- #

def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("fleet judgment: %s=%r is not an integer; using %d", name, raw, default)
        return default
    if value <= 0:
        logger.warning("fleet judgment: %s=%d is not positive; using %d", name, value, default)
        return default
    return value


#: The most candidates one pass may carry. A pass that would exceed this reports
#: what it did not cover rather than truncating silently — a bounded check that
#: hides its own boundary reads as a complete one.
MAX_CANDIDATES = _int_env("SET_FLEET_PM_MAX_CANDIDATES", 25)

#: How often a cycle may run, in seconds. Enforced by the caller; declared here
#: so the two numbers that decide this feature's cost sit in one place.
CYCLE_SECONDS = _int_env("SET_FLEET_PM_CYCLE_SECONDS", 60)

#: How much of the last utterance the judge sees. Larger than the tile's
#: excerpt, because a question truncated mid-sentence is a different question.
JUDGE_EXCERPT_CHARS = 1200


# --------------------------------------------------------------------------- #
# subjects, watermarks, verdicts
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Subject:
    """One agent a cycle may consider.

    Built by the caller from discovery and state, so this module stays free of
    both. `state` is the value the state layer measured — not a re-derivation.
    """

    pid: int
    project: str
    state: str
    session_log: Optional[str] = None
    label: Optional[str] = None
    #: Whether the reader can ANSWER this agent — a terminal the framework
    #: holds, or a seat on the messaging bus. Defaults True so a caller that
    #: does not measure it keeps every agent: an unmeasured channel must not
    #: read as a missing one.
    reachable: bool = True
    #: What answering this agent now still saves against letting its prompt
    #: cache expire, in USD. `None` means it was not measured — which is not
    #: zero, and the queue keeps the two apart.
    #:
    #: Measured by the caller for the same reason `state` is: this module and
    #: the queue below it read no files, so a figure that comes from a
    #: transcript arrives as an argument or not at all.
    recoverable_usd: Optional[float] = None


@dataclass(frozen=True)
class Watermark:
    """What the log looked like when this agent was last judged.

    Size AND mtime, not either alone: mtime has one-second granularity on many
    filesystems, so an append inside the same second is invisible to it, and a
    size alone cannot see a rewrite. `None` means never judged.
    """

    mtime: float
    size: int


@dataclass(frozen=True)
class Verdict:
    """What was concluded about one agent, and on what authority.

    `source` is not decoration. A structural verdict is a measurement and a
    model verdict is an opinion, and the surface has to be able to say which it
    is showing — the same distinction the state layer draws between `asking`
    (measured) and `waiting` (declared).
    """

    pid: int
    verdict: str
    source: str  # "structural" | "model" | "absent"
    #: Set when the model contradicted a structural measurement. The measurement
    #: stands; this says the two disagreed rather than hiding it.
    disagreed: Optional[str] = None


@dataclass
class PassResult:
    """The outcome of one cycle.

    `measured` is the field that must never be confused with an empty
    `verdicts`. "Nothing needs you" and "we could not look" lead to opposite
    actions, and the first is the one a reader acts on by walking away.
    """

    verdicts: Dict[int, Verdict] = field(default_factory=dict)
    measured: bool = True
    reason: Optional[str] = None
    #: Candidates the cap excluded. Named so a bounded pass cannot read complete.
    not_covered: List[int] = field(default_factory=list)
    #: Candidates skipped before the model, with why. Diagnostic only.
    skipped: Dict[int, str] = field(default_factory=dict)
    #: How many model invocations this pass made. One, or zero — never per-agent.
    invocations: int = 0


def watermark_of(session_log: Optional[str]) -> Optional[Watermark]:
    """The log's current (mtime, size), or None when it cannot be read.

    None is *no information*, and the caller must not read it as "unchanged":
    an unreadable log excludes its agent from the pass with a reason, rather
    than being silently carried forward on a stale verdict.
    """
    if not session_log:
        return None
    try:
        st = os.stat(session_log)
    except OSError as exc:
        logger.debug("fleet judgment: cannot stat a session log: %s", exc.__class__.__name__)
        return None
    return Watermark(mtime=st.st_mtime, size=st.st_size)


# --------------------------------------------------------------------------- #
# the candidate filter — structural, and it runs before the model
# --------------------------------------------------------------------------- #

def structural_verdicts(subjects: Iterable[Subject]) -> Dict[int, Verdict]:
    """Agents whose blockage the state layer already measured.

    These are queued without an opinion being asked for, and no opinion may
    remove them. They are the floor the model layer sits on.

    Reachability is checked HERE TOO, and that is not a duplicate of the
    candidate filter — it is the second door into the queue. This path skips the
    model entirely, so a filter that lived only in `select_candidates` would
    keep out an unreachable agent the model would have judged while letting
    through one the state layer measured. Same rule, both doors.
    """
    return {
        s.pid: Verdict(pid=s.pid, verdict=ASKING, source="structural")
        for s in subjects
        if s.state == agent_state.ASKING and s.reachable
    }


def select_candidates(
    subjects: Sequence[Subject],
    watermarks: Dict[int, Watermark],
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> Tuple[List[Subject], Dict[int, str], List[int]]:
    """Who this cycle asks about, who it skips and why, and who did not fit.

    Six tests, and each removes a class the model could only have agreed with:

      - not quiet — a working agent is not blocked, and an `asking` one is
        already measured, so neither needs an opinion;
      - the agent cannot be answered at all — no terminal, no bus seat, so
        queueing it would present something the reader cannot act on;
      - the log carries no utterance at all — an absent turn is not a quiet
        one, and the framework concludes that rather than asking;
      - the agent holds the floor — it owes the next utterance, so it cannot be
        waiting on a person whatever its last words were;
      - the log has not moved since the last verdict — the same input yields
        the same answer, and the previous verdict stands;
      - the log cannot be read — which is *no information*, so the agent is
        excluded WITH A REASON rather than carried on a stale verdict.

    The cap is applied last and what it drops is returned, never truncated
    quietly: a bounded pass that hides its own boundary reads as a complete one.
    """
    candidates: List[Subject] = []
    skipped: Dict[int, str] = {}

    for subject in subjects:
        if subject.state == agent_state.ASKING:
            skipped[subject.pid] = "already measured as asking — no opinion needed"
            continue
        if subject.state != agent_state.QUIET:
            skipped[subject.pid] = f"state is {subject.state}, which is not a blockage on a person"
            continue
        if not subject.reachable:
            # Nothing on this screen can answer it: no pty the framework holds,
            # and no seat on the bus. Presenting it costs the reader the one
            # promise the mode makes — that what is in front of them is theirs
            # to deal with — and no action clears it.
            skipped[subject.pid] = "unreachable — no terminal and no seat, so it cannot be answered"
            continue
        mark = watermark_of(subject.session_log)
        if mark is None:
            skipped[subject.pid] = "the session log could not be read"
            continue
        floor = agent_state.who_has_the_floor(subject.session_log)
        if floor == agent_state.FLOOR_UNKNOWN:
            # The tail carries no utterance at all, so there is no turn to judge.
            # Measured 2026-08-20 across the live fleet: one session's log was
            # 1201 bytes of `mode` and `system` lines and nothing else — never
            # spoken in. Sending it costs an excerpt-shaped hole the model has to
            # say something about, and the direction that hurts is `asking`,
            # which would put a session that never spoke in front of a person.
            skipped[subject.pid] = "no readable utterance — nothing to judge"
            continue
        if floor == agent_state.FLOOR_AGENT:
            # `quiet` only means no tool call was open at the last flush. The
            # runtime writes a `tool_use` together with its result, so an agent
            # running a command reads as quiet while the screen says it is
            # working. Whose turn it is survives that: after a tool result, or
            # after a person's prompt, the next word is the AGENT'S.
            skipped[subject.pid] = "mid-turn — the agent owes the next utterance"
            continue
        previous = watermarks.get(subject.pid)
        if previous is not None and previous == mark:
            skipped[subject.pid] = "the session log has not moved since the last verdict"
            continue
        candidates.append(subject)

    not_covered: List[int] = []
    if len(candidates) > max_candidates:
        not_covered = [c.pid for c in candidates[max_candidates:]]
        candidates = candidates[:max_candidates]
        logger.warning(
            "fleet judgment: %d candidate(s) exceed the per-pass cap of %d and were not covered",
            len(not_covered), max_candidates,
        )

    return candidates, skipped, not_covered


# --------------------------------------------------------------------------- #
# the invocation
# --------------------------------------------------------------------------- #

_INSTRUCTION = """\
You are classifying the last turn of several coding-agent sessions, to decide
which of them need a PERSON before they can continue.

For each session below, answer with exactly one class:

  "asking"   — the agent needs something from a person: it asked a question,
               offered a choice, requested a decision or approval, or said it
               lacks information it cannot obtain itself. A request phrased as
               a statement still counts ("I'll need the API key first").
  "finished" — the agent completed its turn and reported. It asked for nothing.
               A summary, a result, a "done" — however long — is this class.
  "stopped"  — the turn ended for some other reason: interrupted, an error it
               did not recover from, or it simply stops mid-thought.

Judge only what is in front of you. Do not guess about work you cannot see, and
do not infer urgency — the class is about whether a person is required, not
about how important the work is.

Reply with JSON only, and nothing else: an object whose keys are the session
ids given below and whose values are one of "asking", "finished", "stopped".
Include every id. Do not add commentary, explanation or any other key.
"""


def _excerpt_for(session_log: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """The last thing said in this session, at the judge's length."""
    if not session_log:
        return None, None
    lines = agent_state._tail(session_log)
    if lines is None:
        return None, None
    return agent_state._last_text(lines, limit=JUDGE_EXCERPT_CHARS)


def build_prompt(candidates: Sequence[Subject]) -> str:
    """One prompt carrying every candidate.

    Sessions are addressed by pid, which is an identity this framework already
    uses and which carries no domain. The excerpt is the only content that
    crosses, and it crosses once per cycle.
    """
    parts = [_INSTRUCTION, ""]
    for subject in candidates:
        text, who = _excerpt_for(subject.session_log)
        parts.append(f"### session {subject.pid}")
        if text is None:
            # Said plainly rather than omitted: a session with nothing readable
            # is a real case, and an absent block would leave the model to
            # invent a reason for the gap.
            parts.append("(no readable utterance in the tail of this session)")
        else:
            parts.append(f"last spoken by: {who or 'unknown'}")
            parts.append(text)
        parts.append("")
    parts.append(
        "Reply with JSON only: {"
        + ", ".join(f'"{c.pid}": "..."' for c in candidates)
        + "}"
    )
    return "\n".join(parts)


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_response(raw: Optional[str], candidates: Sequence[Subject]) -> Dict[int, Verdict]:
    """Read the verdicts, and conclude UNCLASSIFIED wherever one is not there.

    Every failure here resolves toward `unclassified` and never toward
    `finished`, because those two lead to opposite actions: one keeps the agent
    visible, the other removes it from the queue. An unparsable reply, an
    unrecognised class and a missing id are all "we do not know".
    """
    verdicts: Dict[int, Verdict] = {
        c.pid: Verdict(pid=c.pid, verdict=UNCLASSIFIED, source="absent") for c in candidates
    }
    if not raw:
        return verdicts

    match = _JSON_BLOCK.search(raw)
    if not match:
        logger.warning("fleet judgment: the reply held no JSON object; every candidate is unclassified")
        return verdicts
    try:
        payload = json.loads(match.group(0))
    except ValueError:
        logger.warning("fleet judgment: the reply's JSON did not parse; every candidate is unclassified")
        return verdicts
    if not isinstance(payload, dict):
        logger.warning("fleet judgment: the reply parsed to %s, not an object", type(payload).__name__)
        return verdicts

    known = {c.pid for c in candidates}
    for key, value in payload.items():
        try:
            pid = int(key)
        except (TypeError, ValueError):
            continue
        if pid not in known:
            # A verdict about somebody who was not asked about. Dropped, and
            # said out loud — it means the reply is not describing this pass.
            logger.warning("fleet judgment: a verdict names pid %s, which was not a candidate", pid)
            continue
        if value in VERDICT_CLASSES:
            verdicts[pid] = Verdict(pid=pid, verdict=value, source="model")
        else:
            logger.warning("fleet judgment: pid %s got a class this build does not know", pid)
            verdicts[pid] = Verdict(pid=pid, verdict=UNCLASSIFIED, source="model")
    return verdicts


def reconcile(
    model_verdicts: Dict[int, Verdict],
    structural: Dict[int, Verdict],
) -> Dict[int, Verdict]:
    """The measurement wins, and the disagreement is carried rather than dropped.

    A structural verdict may not be removed or changed by an opinion. Where the
    two differ the structural one stands, with `disagreed` naming what the model
    said — a contradiction the surface never sees is one nobody ever fixes.
    """
    out = dict(model_verdicts)
    for pid, measured in structural.items():
        opinion = model_verdicts.get(pid)
        if opinion is not None and opinion.verdict != measured.verdict:
            out[pid] = Verdict(
                pid=pid, verdict=measured.verdict, source="structural",
                disagreed=opinion.verdict,
            )
        else:
            out[pid] = measured
    return out


def _default_runner(prompt: str, model: str) -> Optional[str]:
    """Invoke the model once. Isolated so tests never spawn a process.

    ⚠ `is_error` and `timed_out` are read BEFORE `stdout`, and `ClaudeResult`'s
    own docstring says why: a run can fail while the process exits 0 — a stalled
    stream, a turn limit, an execution error. Handing that stdout to the parser
    produces "every candidate unclassified", which reads as *the model gave a
    bad answer* when what happened was *the call did not complete*. The two need
    opposite responses, and this module distinguishes them by returning None,
    which the caller reports as an UNMEASURED pass rather than as verdicts.
    """
    from ..subprocess_utils import run_claude_logged

    result = run_claude_logged(
        prompt,
        purpose="fleet-pm-judgment",
        model=model,
        timeout=180,
    )
    if getattr(result, "timed_out", False):
        logger.warning("fleet judgment: the invocation timed out")
        return None
    if getattr(result, "is_error", False):
        logger.warning("fleet judgment: the runtime reported the invocation as failed")
        return None
    if getattr(result, "exit_code", 0) != 0:
        logger.warning("fleet judgment: the invocation exited %s", getattr(result, "exit_code", "?"))
        return None
    return getattr(result, "stdout", None)


def run_pass(
    subjects: Sequence[Subject],
    watermarks: Dict[int, Watermark],
    *,
    runner: Optional[Callable[[str, str], Optional[str]]] = None,
    model: Optional[str] = None,
    project_dir: str = ".",
    max_candidates: int = MAX_CANDIDATES,
) -> PassResult:
    """One cycle: filter, ask once, reconcile.

    Returns a `PassResult` whose `measured` flag is the thing a surface must
    read before its `verdicts`. A pass that could not run leaves the caller's
    previous verdicts standing — this function does not clear them, because it
    does not hold them.
    """
    structural = structural_verdicts(subjects)
    candidates, skipped, not_covered = select_candidates(
        subjects, watermarks, max_candidates=max_candidates,
    )

    if not candidates:
        # No invocation at all. An empty pass is measured — we looked and there
        # was nothing to ask about — which is a different fact from a failure.
        return PassResult(
            verdicts=dict(structural), measured=True,
            not_covered=not_covered, skipped=skipped, invocations=0,
        )

    if model is None:
        try:
            from ..model_config import resolve_model

            model = resolve_model("pm", project_dir=project_dir)
        except Exception as exc:
            logger.warning("fleet judgment: the pm model role could not be resolved: %s", exc)
            return PassResult(
                verdicts=dict(structural), measured=False,
                reason="the pm model role could not be resolved",
                not_covered=not_covered, skipped=skipped, invocations=0,
            )

    call = runner or _default_runner
    try:
        raw = call(build_prompt(candidates), model)
    except Exception as exc:
        # The message names the class, never the body — the prompt carries
        # session text and this line must stay safe to write down.
        logger.warning("fleet judgment: the pass failed (%s)", exc.__class__.__name__)
        return PassResult(
            verdicts=dict(structural), measured=False,
            reason=f"the judgment pass failed ({exc.__class__.__name__})",
            not_covered=not_covered, skipped=skipped, invocations=1,
        )

    if raw is None:
        return PassResult(
            verdicts=dict(structural), measured=False,
            reason="the judgment pass returned nothing",
            not_covered=not_covered, skipped=skipped, invocations=1,
        )

    parsed = parse_response(raw, candidates)
    # A reply arrived and NOTHING in it could be used. That is not "the model
    # said nobody needs you" — it is a pass that did not produce an answer, and
    # the difference matters because `unclassified` agents are not queued: left
    # as measured, an unusable reply would empty the queue and look like calm.
    # Still returns the verdicts, so the unclassified agents stay visible.
    if candidates and all(v.source == "absent" for v in parsed.values()):
        logger.warning("fleet judgment: the reply yielded no usable verdict for any candidate")
        return PassResult(
            verdicts=reconcile(parsed, structural), measured=False,
            reason="the judgment pass produced no usable verdict",
            not_covered=not_covered, skipped=skipped, invocations=1,
        )

    verdicts = reconcile(parsed, structural)
    logger.info(
        "fleet judgment: %d candidate(s) judged in 1 invocation, %d skipped, %d not covered",
        len(candidates), len(skipped), len(not_covered),
    )
    return PassResult(
        verdicts=verdicts, measured=True,
        not_covered=not_covered, skipped=skipped, invocations=1,
    )
