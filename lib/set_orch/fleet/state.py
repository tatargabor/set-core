"""What an agent is doing — read from its session log, never from a status field.

Tasks 3.1/3.2/3.3/3.6 of the `fleet-view` change.

Why the log and not the record: the runtime writes a `status` into each session
record, and it looks authoritative. Measured 2026-08-18 across 23 live sessions,
the age of that field had a **median of 11 hours and a maximum of 83**, with 7
sessions over a day stale. It is a declaration about a moment that has passed.
The log's mtime is the moment itself.

Working is defined structurally rather than by a label: a `tool_use` block in
the tail with no matching `tool_result` means a call is outstanding, so the
session is mid-turn. Everything else is *unknown*, never *idle* — an agent whose
state cannot be determined must not be reported as resting, because that is the
reading someone acts on by leaving it alone.

The list path costs one `stat` plus a bounded tail per agent. No full parse.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

#: How much of the log's end to read for the outstanding-call scan. A turn's
#: worth of entries is far smaller than this; the bound is what keeps listing
#: every agent from reading every log in full (task 3.6).
TAIL_BYTES = 256 * 1024

#: Sentinel for "this state could not be determined". Never "idle".
UNKNOWN = "unknown"
WORKING = "working"
QUIET = "quiet"
#: Waiting for a PERSON. Not measurable from the log at all — see `read_state`.
WAITING = "waiting"
#: Stopped in front of a person by a tool that IS a question — see `QUESTION_TOOLS`.
#: Structurally certain, unlike WAITING, which is a declaration the record makes.
#:
#: ⚠ NOT called `blocked`, and the reason is a collision found while wiring this
#: up rather than foreseen: the envelope ALREADY carries `declared.blocked` —
#: the agent's own claim that something is holding it up, which may be a
#: dependency, a missing credential, anything. Two fields named `blocked` in one
#: payload, one a declaration and one a measurement, is the ambiguity this
#: codebase spends its comments warning about. `asking` says what was actually
#: measured: a question tool is open, so the agent is asking.
ASKING = "asking"

#: Tools whose outstanding call means the agent is stopped in front of a PERSON.
#:
#: Measured 2026-08-20 on a real session log, three instances: the `tool_use`
#: entry lands 8m13s, 9m32s and 1m43s BEFORE its matching `tool_result`. So the
#: call sits outstanding for the whole time the person is thinking, and reading
#: it as `working` — which is what this module did until then — reported the one
#: blockage a reader could act on immediately as the case needing nothing.
#:
#: ⚠ A PERMISSION PROMPT IS DELIBERATELY NOT HERE, and the reason is the whole
#: point of the list being a list. From the log, an agent waiting for permission
#: to run `Bash` and an agent running a slow `Bash` are the SAME entry: one
#: outstanding `tool_use` named `Bash`. Adding it by elapsed time would queue
#: every long-running command — a false positive on the busiest tool there is.
#: A tool joins this set when its outstanding call means a person is being
#: asked, never because its name sounds like it might be.
QUESTION_TOOLS = frozenset({"AskUserQuestion", "ExitPlanMode"})


@dataclass
class AgentState:
    """The measured state of one agent.

    `quiet` means the log was read and no call is outstanding — the agent
    finished its turn. It is deliberately not called *idle*: idle claims the
    agent has nothing to do, which this cannot know.
    """

    state: str = UNKNOWN
    #: Seconds since the session log last changed, or None when unmeasurable.
    last_movement_age: Optional[float] = None
    #: The tool whose call is outstanding, when the state is `working` or
    #: `blocked`. For `blocked` it is the QUESTION tool, not the oldest call —
    #: which one is outstanding is the reason for the state, so naming a
    #: different one would describe the wrong fact.
    tool: Optional[str] = None
    #: How long that call has been outstanding, in seconds.
    tool_elapsed: Optional[float] = None
    #: Why the state is unknown, when it is. Present for exactly that case.
    reason: Optional[str] = None
    #: Tools outstanding beyond the first, if any.
    other_tools: List[str] = field(default_factory=list)
    #: What the agent says it is waiting for, when the state is `waiting`.
    #: Verbatim from the runtime's record — this layer does not interpret it.
    waiting_for: Optional[str] = None
    #: Set when the record DECLARED a state the log contradicts. The measured
    #: state wins, and this says the declaration disagreed rather than hiding it:
    #: a contradiction the surface cannot see is one nobody will ever fix.
    declaration_ignored: Optional[str] = None
    #: The last thing said in this session, for the tile — task 7.3.
    #:
    #: `None` means no text was found, which is NOT the same as an empty
    #: session and must not render as one: an agent whose tail holds only tool
    #: traffic has said nothing recently, and a blank line would claim it said
    #: nothing at all.
    #:
    #: ⚠ CONFIDENTIALITY. This carries verbatim content from a session that may
    #: be running in a consumer project. The boundary in `CLAUDE.md` is
    #: PERSISTENCE, not display: this may be shown at runtime, and must never be
    #: written to a log, a cache, a memory or any committed artifact. Nothing
    #: here logs it, and nothing downstream may either.
    excerpt: Optional[str] = None
    #: Who said it — `agent` or `user`. Carried rather than guessed at by the
    #: surface, because the same sentence means different things depending on
    #: which end of the conversation it came from.
    excerpt_from: Optional[str] = None


def _tail(path: str, limit: int = TAIL_BYTES) -> Optional[List[str]]:
    """The last `limit` bytes of a file, as whole lines.

    Returns None when the file cannot be read at all — which is a different
    answer from "the file is empty", and the caller must not collapse the two.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > limit:
                fh.seek(size - limit)
                fh.readline()  # discard the partial line the seek landed inside
            raw = fh.read()
    except OSError as exc:
        logger.debug("fleet state: cannot tail %s: %s", path, exc)
        return None
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


#: How much of the last utterance the tile carries. Long enough to recognise
#: what is going on, short enough that a tile stays a tile — the density rule
#: in `ui-quality.md` is about the first screenful answering the question.
EXCERPT_CHARS = 240


def _last_text(lines: List[str], limit: int = EXCERPT_CHARS) -> tuple[Optional[str], Optional[str]]:
    """The last thing actually SAID in this session, and by whom.

    Read backwards from the tail the state pass already loaded, so this costs
    no extra I/O — the file is read once for both answers.

    What counts as "said" is text a person would recognise: an assistant's
    prose or a user's message. Tool calls, tool results and thinking blocks are
    skipped, because a tile showing `Bash` tells the reader nothing they do not
    already get from the state line, and a tile showing a thinking block shows
    something the conversation never contained.

    Returns `(None, None)` when nothing qualifies. That is deliberately not
    `("", ...)`: a tail made entirely of tool traffic means *nothing was said
    recently*, and an empty string on the tile would read as *nothing was ever
    said* — the false-absence class this module already refuses for state.
    """
    for line in reversed(lines):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in ("assistant", "user"):
            continue
        content = message.get("content")
        # A string content is the plain-text shape; a list is the block shape.
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        if not isinstance(blocks, list):
            continue
        for block in reversed(blocks):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text")
            if not isinstance(text, str):
                continue
            text = " ".join(text.split())
            if not text:
                continue
            if len(text) > limit:
                text = text[: limit - 1].rstrip() + "\u2026"
            return text, ("agent" if role == "assistant" else "user")
    return None, None


def _outstanding_calls(lines: List[str]) -> tuple[Dict[str, dict], bool]:
    """Tool calls in the tail with no matching result.

    Returns (outstanding by tool_use id, saw_any_entry).

    Sidechain entries are skipped: a session's own task children are out of this
    capability's scope, and counting their calls would report the parent as
    working on a tool it never invoked.
    """
    opened: Dict[str, dict] = {}
    closed: Set[str] = set()
    saw = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        saw = True
        if entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                call_id = block.get("id")
                if call_id:
                    opened[call_id] = {
                        "name": block.get("name"),
                        "timestamp": entry.get("timestamp"),
                    }
            elif kind == "tool_result":
                result_for = block.get("tool_use_id")
                if result_for:
                    closed.add(result_for)

    return {cid: meta for cid, meta in opened.items() if cid not in closed}, saw


def _age_seconds(iso_timestamp: Optional[str], now: Optional[float] = None) -> Optional[float]:
    if not iso_timestamp:
        return None
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    reference = now if now is not None else time.time()
    return max(0.0, reference - parsed.timestamp())


#: `resumed_since` verdicts. Three, not a boolean — see the function.
RESUMED = "resumed"
NOT_RESUMED = "not-resumed"
RESUMPTION_UNKNOWN = "unknown"


def _epoch(iso_timestamp: Optional[str]) -> Optional[float]:
    """An ISO timestamp as epoch seconds, or None when it cannot be parsed."""
    if not iso_timestamp:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def resumed_since(session_log: Optional[str], since: Optional[str]) -> str:
    """Has this agent taken a new turn since `since`?

    The question the attention queue asks to decide whether a person dealt with
    the item on screen. Three answers, and the third is why this is not a bool:
    an unreadable log, an unparsable point, or a tail that does not reach back
    far enough are all *no information*, and reporting them as `not-resumed`
    would freeze the queue on an item nobody can ever clear.

    ## A new USER entry is not resumption, and that is the whole finding

    Measured on a live log 2026-08-19: interrupting a session writes a `user`
    entry whose text is `[Request interrupted by user]`. So the obvious test —
    *did the person type something* — reads an abandoned turn as an answered
    one, and pressing Esc would advance the queue. The alternative repair, a
    list of the runtime's synthetic markers, is a second copy of somebody else's
    format and drifts the day they add one.

    What this measures instead is the EFFECT: the agent moved. An assistant
    utterance, or a fresh tool call, recorded after `since`. Nothing a person
    types counts, which also makes it indifferent to whatever the runtime
    invents next.

    ## Why the boundary has to be visible for a negative

    The tail is bounded (`TAIL_BYTES`). If its earliest entry is already newer
    than `since`, entries between the two were never read — and one of them
    could be the assistant utterance being looked for. A positive is still safe
    (finding one is finding one); a negative is not, so it returns unknown.
    """
    if session_log is None or not os.path.exists(session_log):
        return RESUMPTION_UNKNOWN
    point = _epoch(since)
    if point is None:
        return RESUMPTION_UNKNOWN
    lines = _tail(session_log)
    if lines is None:
        return RESUMPTION_UNKNOWN

    earliest: Optional[float] = None
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        stamp = _epoch(entry.get("timestamp"))
        if stamp is None:
            continue
        if earliest is None or stamp < earliest:
            earliest = stamp
        if stamp <= point:
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        # Both carriers, because both exist and a fixture may set only one.
        # Measured on a real log: where both are present they always agree
        # (231 `user`/`user`, 396 `assistant`/`assistant`), and every entry
        # kind that carries neither has no `message` at all.
        if (message.get("role") or entry.get("type")) != "assistant":
            continue
        content = message.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                return RESUMED
            if block.get("type") == "text" and str(block.get("text") or "").strip():
                return RESUMED

    if earliest is None or earliest > point:
        # The tail never reached back to the point, so "nothing found" is not
        # the same as "nothing happened".
        return RESUMPTION_UNKNOWN
    return NOT_RESUMED


def _apply_declared_wait(state: AgentState, record: Optional[Dict]) -> AgentState:
    """Add *waiting for a person* to a quiet state, from the runtime's record.

    Task 3.8, and the division of labour is the finding rather than the code.
    The log can tell **working from not-working** — an outstanding `tool_use` is
    structural. It cannot tell **stopped at a prompt** from **finished its turn**,
    because both look like a turn that ended. Only the record knows, and the
    record is a declaration.

    So the two are composed rather than ranked: the measurement decides the
    state, and the declaration may refine a QUIET one into `waiting`. A record
    claiming `waiting` while a call is outstanding is contradicted and ignored,
    with the disagreement carried (see `declaration_ignored`).

    **The task asked for a freshness check on the record's timestamps, and there
    is none to make.** Measured 2026-08-19 on 25 live records: `updatedAt` equals
    `statusUpdatedAt` in **22 of 22** that carry both, so the record is written
    only when the status CHANGES. Its timestamp is therefore the age of the
    STATE, not the age of the observation — an agent waiting for three hours
    honestly carries a three-hour-old stamp, and rejecting it as stale would
    throw away the true positives first. (Measured the same day: the one agent
    whose record said `waiting` had a 9.5-hour-old stamp and was genuinely
    quiet.) An mtime cross-check does not work either: **22 of 22** logs had
    moved since their status stamp, so it rejects everything, including that
    true positive.

    What is left is the contradiction test above, and it is the one that fires on
    the real staleness: a record still saying `busy` while the log shows no
    outstanding call — measured on this machine, one of 22.
    """
    if not record:
        # No record is NOT "not waiting". The surface must be able to tell an
        # agent reported as not waiting from one nobody could ask.
        return state
    if record.get("status") != WAITING:
        return state
    waiting_for = record.get("waitingFor")
    return AgentState(
        state=WAITING,
        last_movement_age=state.last_movement_age,
        waiting_for=str(waiting_for) if waiting_for else None,
    )


def read_state(
    session_log: Optional[str],
    *,
    now: Optional[float] = None,
    record: Optional[Dict] = None,
) -> AgentState:
    """Measure one agent's state from its session log.

    Every path that cannot reach an answer returns `unknown` **with a reason**.
    A missing key and an empty value are distinguished deliberately: a log that
    exists and holds no parsable entry is not the same as a log that is absent,
    and neither is the same as an agent that has finished its turn.
    """
    if session_log is None:
        return AgentState(state=UNKNOWN, reason="no session log is bound to this agent")
    if not os.path.exists(session_log):
        return AgentState(state=UNKNOWN, reason="the bound session log does not exist")

    reference = now if now is not None else time.time()
    try:
        movement = max(0.0, reference - os.path.getmtime(session_log))
    except OSError as exc:
        logger.warning("fleet state: cannot stat %s: %s", session_log, exc)
        return AgentState(state=UNKNOWN, reason="the session log could not be stat'ed")

    lines = _tail(session_log)
    if lines is None:
        return AgentState(
            state=UNKNOWN,
            last_movement_age=movement,
            reason="the session log could not be read",
        )

    excerpt, excerpt_from = _last_text(lines)

    outstanding, saw_entry = _outstanding_calls(lines)
    if not saw_entry:
        return AgentState(
            state=UNKNOWN,
            last_movement_age=movement,
            reason="the session log holds no parsable entry",
            # Carried even here: a log with no parsable ENTRY can still hold a
            # readable line, and the excerpt is the one thing that helps a
            # reader work out why the state could not be measured.
            excerpt=excerpt,
            excerpt_from=excerpt_from,
        )

    if not outstanding:
        return _apply_declared_wait(
            AgentState(
                state=QUIET,
                last_movement_age=movement,
                excerpt=excerpt,
                excerpt_from=excerpt_from,
            ),
            record,
        )

    ordered = sorted(
        outstanding.values(),
        key=lambda meta: meta.get("timestamp") or "",
    )

    # A tool that IS a question decides the state, whatever else is open, and it
    # is the one named — see `QUESTION_TOOLS`. Ordering picks the oldest such
    # call rather than the oldest call overall: the question is the reason for
    # the state, so naming a Bash that happens to be older would describe a fact
    # that is not the one the reader needs.
    asking = [m for m in ordered if m.get("name") in QUESTION_TOOLS]
    if asking:
        blocking = asking[0]
        return AgentState(
            state=ASKING,
            last_movement_age=movement,
            tool=blocking.get("name"),
            tool_elapsed=_age_seconds(blocking.get("timestamp"), reference),
            other_tools=[m.get("name") for m in ordered if m is not blocking and m.get("name")],
            # A record saying `waiting` AGREES with this state, so there is no
            # contradiction to carry — unlike the working case below.
            excerpt=excerpt,
            excerpt_from=excerpt_from,
        )

    first = ordered[0]
    # A record that says `waiting` while a call is outstanding is describing a
    # moment that has passed. The measurement wins; the disagreement is carried
    # rather than dropped.
    ignored = "waiting" if (record or {}).get("status") == WAITING else None
    return AgentState(
        state=WORKING,
        declaration_ignored=ignored,
        last_movement_age=movement,
        tool=first.get("name"),
        tool_elapsed=_age_seconds(first.get("timestamp"), reference),
        other_tools=[m.get("name") for m in ordered[1:] if m.get("name")],
        excerpt=excerpt,
        excerpt_from=excerpt_from,
    )
