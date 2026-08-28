"""What an agent is doing — the log says what it is stopped on, the record says whether it runs.

Tasks 3.1/3.2/3.3/3.6 of the `fleet-view` change, and the attention axis of
`fleet-input-attention`.

⚠ **This file used to say "never from a status field", and that is now wrong in
one direction. The correction is kept here rather than deleted, because the way
it was wrong is the useful part.** Measured 2026-08-18 across 23 live sessions,
the record's `status` had a median age of **11 hours**, and it was read as
STALE. It was not: the runtime writes the record only when the status CHANGES,
so an `idle` stamp eleven hours old is an eleven-hour WAIT, correctly recorded.
The proxy — age of the field — was measured instead of the thing: whether the
value is true.

Re-measured 2026-08-28 on runtime 2.1.251, both directions:

- `statusUpdatedAt` equalled the last log ENTRY's own timestamp in **10 of 10**
  live sessions holding a log;
- the log file's **mtime** was up to **90 minutes** later than any entry it held
  in **2 of those 10** — the file is rewritten without new entries, so mtime
  OVER-reports movement;
- a pty probe measured `idle → busy` at **0.6 s**, `busy → shell` when the agent
  backgrounded a command, and `shell → busy → idle` at the turn's end, each stamp
  landing within **0.2 s** of the change.

So the division of labour is: **the log decides working-versus-not** (an
outstanding `tool_use` is structural, and which tool it is cannot be read
anywhere else), and **the record decides whether a person is needed and since
when** — the difference between a finished turn, a finished turn with a
background command still running, and a permission prompt. Neither is
authoritative over the other's question.

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
from dataclasses import dataclass, field, replace
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


# --------------------------------------------------------------------------- #
# The ATTENTION axis — is a person needed here, and for how long
#
# A second axis rather than more `state` values, deliberately. Every existing
# reader of `state` — the tally, the header, the PM queue's candidate selection —
# stays correct, and a reader that has not learned this axis renders nothing
# rather than something wrong.
# --------------------------------------------------------------------------- #

#: The runtime's own four-value status, verbatim. Measured 2026-08-28 in the
#: binary of runtime 2.1.251: the validator accepts exactly
#: `["busy","shell","idle","waiting"]` and rejects anything else.
STATUS_BUSY = "busy"
STATUS_SHELL = "shell"
STATUS_IDLE = "idle"
STATUS_WAITING = "waiting"

#: Something is running: the model's turn is in flight.
ATTENTION_WORKING = "working"
#: The prompt is free, but a backgrounded command is still running.
#:
#: This is what `shell` MEANS, and it is the value this whole axis exists for.
#: Measured 2026-08-28 from the runtime binary, whose own expression is
#: `base === "idle" && hasRunningBackgroundBash ? "shell" : base`, with the
#: predicate `Object.values(tasks).some(t => t.type === "local_bash" && !done(t))`.
#: Confirmed live by a pty probe: the probe agent backgrounded `sleep 25`, ended
#: its turn, and the record went `busy → shell` and back to `busy → idle` when
#: the command finished.
ATTENTION_BACKGROUND = "background"
#: Waiting for a PERSON, with nothing running. The class a reader acts on.
ATTENTION_INPUT = "input"
#: Stopped at a permission prompt or a worker request — blocked on a person by
#: construction, so it does not need elapsed time to be believed.
ATTENTION_PROMPT = "prompt"
#: The record could not answer. NEVER `input`: see `attention_of`.
ATTENTION_UNMEASURED = "unmeasured"

#: Every class this build knows. A list, not an if/else chain, so a class added
#: later shows up as uncounted rather than vanishing — the same discipline the
#: API's state tally already uses.
ATTENTION_CLASSES = (
    ATTENTION_WORKING,
    ATTENTION_BACKGROUND,
    ATTENTION_INPUT,
    ATTENTION_PROMPT,
    ATTENTION_UNMEASURED,
)

#: Status -> class. The mapping is data so that an unrecognised status cannot
#: fall through into a neighbour: `attention_of` looks the value up and reports
#: `unmeasured` on a miss, naming the value it did not know.
_STATUS_ATTENTION = {
    STATUS_BUSY: ATTENTION_WORKING,
    STATUS_SHELL: ATTENTION_BACKGROUND,
    STATUS_IDLE: ATTENTION_INPUT,
    STATUS_WAITING: ATTENTION_PROMPT,
}

#: When an input wait starts being marked, and when it turns loud. Declared HERE
#: and carried to the surface in the API envelope, because a threshold written
#: once in Python and once in TypeScript is two thresholds that drift silently —
#: a screen colouring at 20 s beside a count colouring at 15 s reports two
#: different fleets.
INPUT_WAIT_AMBER_SECONDS = 15.0
INPUT_WAIT_RED_SECONDS = 180.0

TONE_PLAIN = "plain"
TONE_AMBER = "amber"
TONE_RED = "red"


def tone_for(seconds: Optional[float]) -> Optional[str]:
    """Which band an input wait of `seconds` falls in.

    `None` in, `None` out: an unmeasured wait has no tone, and a zero would
    place it in the calmest band — the false-absence direction this screen
    refuses everywhere.
    """
    if seconds is None:
        return None
    if seconds >= INPUT_WAIT_RED_SECONDS:
        return TONE_RED
    if seconds >= INPUT_WAIT_AMBER_SECONDS:
        return TONE_AMBER
    return TONE_PLAIN


def attention_of(record: Optional[Dict]) -> str:
    """The attention class the runtime's record supports, or `unmeasured`.

    A missing record, a record without a `status` key, and a status this build
    does not recognise all return `unmeasured` — never `input`. Measured
    2026-08-28 and unchanged since 2026-08-18: a headless run
    (`entrypoint: "sdk-cli"`) registers a record with **no `status` key at all**,
    so reading absence as idle would report a working orchestration agent as a
    person's problem.
    """
    if not record:
        return ATTENTION_UNMEASURED
    status = record.get("status")
    if not status or not isinstance(status, str):
        # An absent key and an empty value are the same answer here — nobody
        # wrote a status down — and neither is worth a warning. A NON-empty
        # value this build does not know is a different thing entirely, and it
        # gets one below.
        return ATTENTION_UNMEASURED
    known = _STATUS_ATTENTION.get(status)
    if known is None:
        # Named, not swallowed. A renamed status in a future runtime shows up
        # here as a log line with the value in it, rather than as a fleet that
        # quietly went calm.
        logger.warning(
            "fleet state: session record carries a status this build does not know: %r", status
        )
        return ATTENTION_UNMEASURED
    return known


def _status_age(record: Optional[Dict], reference: float) -> Optional[float]:
    """How long the record's CURRENT status has held, in seconds.

    From `statusUpdatedAt`, which the runtime writes only when the status
    changes — so the stamp is the age of the STATE, not of the observation.
    Measured 2026-08-28 across 10 live sessions holding a log: the stamp equalled
    the last log entry's own timestamp in 10 of 10, while the log file's **mtime**
    was up to 90 minutes later than any entry in 2 of the 10, because the file is
    rewritten without new entries. The stamp is the precise instrument here and
    the mtime is the noisy one — which is the reverse of what this module assumed
    until this measurement.
    """
    if not record:
        return None
    stamp = record.get("statusUpdatedAt")
    if not isinstance(stamp, (int, float)) or stamp <= 0:
        return None
    age = reference - (stamp / 1000.0)
    if age < 0:
        # A clock that disagrees with itself is not a negative wait.
        return 0.0
    return age


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
    #: Is a person needed here — see the ATTENTION axis above. Defaults to
    #: `unmeasured`, so an agent nothing could be read for never arrives at the
    #: surface claiming to be waiting for somebody.
    attention: str = ATTENTION_UNMEASURED
    #: How long this session has been waiting for a person with nothing running,
    #: in seconds. Set only for `input` and `prompt`; `None` everywhere else —
    #: including for a working agent, whose zero would sort it with the fresh
    #: waits rather than out of the question entirely.
    input_wait_seconds: Optional[float] = None
    #: The record's status verbatim (`busy` / `shell` / `idle` / `waiting`), or
    #: None. Carried uninterpreted so the surface can show what was actually
    #: read when the derived class surprises somebody.
    runtime_status: Optional[str] = None
    #: True when a backgrounded command is running — the case that looks idle
    #: and is not waiting for anybody.
    background_running: bool = False


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


def _epoch(iso_timestamp) -> Optional[float]:
    """An ISO timestamp as epoch seconds, or None when it cannot be parsed.

    A number passes through unchanged: the attention queue records its
    blockage points as epochs taken from the log's mtime, and making every
    caller format one into ISO just to have it parsed back is a conversion
    that exists only to satisfy a signature.
    """
    if isinstance(iso_timestamp, (int, float)) and not isinstance(iso_timestamp, bool):
        return float(iso_timestamp)
    if not iso_timestamp:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


#: Who is expected to speak next, measured from the log's last substantive entry.
FLOOR_AGENT = "agent"      # the agent owes the next utterance — it is mid-turn
FLOOR_PERSON = "person"    # the agent spoke last; a person may be the next mover
FLOOR_UNKNOWN = "unknown"  # unreadable, empty, or a tail that says nothing


def who_has_the_floor(session_log: Optional[str]) -> str:
    """Whose turn it is, from the log alone.

    ## Why this exists, and why the outstanding-call test is not enough

    Measured 2026-08-20 on a live session that the screen showed as
    `Running 2 shell commands… Razzmatazzing… (10m 9s)`: the log carried NO
    outstanding tool call, because the runtime writes a `tool_use` and its
    `tool_result` together rather than at the moment the call starts. So an
    agent that is visibly working reads as `quiet`, and PM mode put it in front
    of a person as something waiting on them.

    The floor is measurable even when the outstanding call is not. A
    `tool_result` is never the end of a turn — the model always speaks after
    one. A user entry with no reply after it is the same: the agent owes the
    answer. Only a log whose last substantive entry is the AGENT'S OWN
    utterance can be waiting on a person at all.

    Measured across 18 live agents the same day: 11 `person`, 5 `agent`
    (including this session, mid-command), 1 unknown — and the three the mode
    had wrongly queued were all `agent`.
    """
    lines = _tail(session_log) if session_log else None
    if not lines:
        return FLOOR_UNKNOWN
    floor = FLOOR_UNKNOWN
    for line in lines:
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if entry.get("isSidechain"):
            continue  # a subagent's turn is not the parent's floor
        message = entry.get("message") or {}
        role = message.get("role") or entry.get("type")
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        if role == "assistant":
            if any(b.get("type") == "tool_use" for b in blocks):
                floor = FLOOR_AGENT     # a call was made; its result is owed back
            elif any(b.get("type") == "text" and (b.get("text") or "").strip() for b in blocks):
                floor = FLOOR_PERSON
        elif role == "user":
            # A tool result and a typed prompt are the same shape here: in both
            # cases the next word is the agent's.
            if blocks or isinstance(content, str):
                floor = FLOOR_AGENT
    return floor


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


def _compose_attention(
    state: AgentState, record: Optional[Dict], reference: float
) -> AgentState:
    """Fill the ATTENTION axis on a state the log already decided.

    The division of labour, which is the design rather than a detail of it:

    - the **log** answers *what is this session stopped on* — an outstanding
      call, and whether it is a question. That is the more specific claim
      wherever it exists, so `asking` and `working` are never overturned here;
    - the **record** answers *is this loop running, and since when*. That is the
      only source for the difference between a turn that ended, a turn that
      ended while a background command runs, and a session held at a permission
      prompt.

    The two compose. A record that contradicts the log loses the STATE and keeps
    its contribution to the axis, because the disagreement is worth showing and
    a dropped fact is not.
    """
    status = record.get("status") if record else None
    background = status == STATUS_SHELL

    if state.state == ASKING:
        # Measured: a question tool is open. No record can make that not so.
        attention = ATTENTION_PROMPT
        wait = _status_age(record, reference)
        if wait is None:
            # The record said nothing; how long the question has been open is
            # the honest fallback, and it is measured from the log.
            wait = state.tool_elapsed
    elif state.state == WORKING:
        attention = ATTENTION_WORKING
        wait = None
    else:
        attention = attention_of(record)
        wait = _status_age(record, reference) if attention in (
            ATTENTION_INPUT, ATTENTION_PROMPT
        ) else None

    return replace(
        state,
        attention=attention,
        input_wait_seconds=wait,
        runtime_status=status if isinstance(status, str) else None,
        background_running=background,
    )


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

    Re-measured 2026-08-28 on runtime 2.1.251, and the second half now has a
    cause: **10 of 10** stamps equalled the last log entry's own timestamp, while
    **2 of 10** log files carried an mtime up to 90 minutes later than any entry
    inside them. The mtime moves without the session moving. That is why this
    module keeps `last_movement_age` as the age of the FILE and takes the input
    wait from `statusUpdatedAt` instead — see `_status_age`.

    This function still only promotes `quiet → waiting`. The four-value status is
    read on the separate attention axis (`_compose_attention`), so nothing that
    consumes `state` had to learn a new name to stay correct.

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
    reference = now if now is not None else time.time()

    def measured(state: AgentState) -> AgentState:
        """Every exit goes through here.

        A return that skips the attention axis is an agent rendered with no
        class at all — which the surface would draw as *unmeasured* while the
        record sitting right there could have answered. One funnel, so a path
        added later cannot forget.
        """
        return _compose_attention(state, record, reference)

    if session_log is None:
        return measured(
            AgentState(state=UNKNOWN, reason="no session log is bound to this agent")
        )
    if not os.path.exists(session_log):
        return measured(
            AgentState(state=UNKNOWN, reason="the bound session log does not exist")
        )

    try:
        movement = max(0.0, reference - os.path.getmtime(session_log))
    except OSError as exc:
        logger.warning("fleet state: cannot stat %s: %s", session_log, exc)
        return measured(
            AgentState(state=UNKNOWN, reason="the session log could not be stat'ed")
        )

    lines = _tail(session_log)
    if lines is None:
        return measured(
            AgentState(
                state=UNKNOWN,
                last_movement_age=movement,
                reason="the session log could not be read",
            )
        )

    excerpt, excerpt_from = _last_text(lines)

    outstanding, saw_entry = _outstanding_calls(lines)
    if not saw_entry:
        return measured(
            AgentState(
                state=UNKNOWN,
                last_movement_age=movement,
                reason="the session log holds no parsable entry",
                # Carried even here: a log with no parsable ENTRY can still hold
                # a readable line, and the excerpt is the one thing that helps a
                # reader work out why the state could not be measured.
                excerpt=excerpt,
                excerpt_from=excerpt_from,
            )
        )

    if not outstanding:
        return measured(
            _apply_declared_wait(
                AgentState(
                    state=QUIET,
                    last_movement_age=movement,
                    excerpt=excerpt,
                    excerpt_from=excerpt_from,
                ),
                record,
            )
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
        return measured(
            AgentState(
                state=ASKING,
                last_movement_age=movement,
                tool=blocking.get("name"),
                tool_elapsed=_age_seconds(blocking.get("timestamp"), reference),
                other_tools=[
                    m.get("name") for m in ordered if m is not blocking and m.get("name")
                ],
                # A record saying `waiting` AGREES with this state, so there is
                # no contradiction to carry — unlike the working case below.
                excerpt=excerpt,
                excerpt_from=excerpt_from,
            )
        )

    first = ordered[0]
    # A record claiming the prompt is FREE while a call is outstanding is
    # describing a moment that has passed. The measurement wins; the
    # disagreement is carried rather than dropped, and the value it disagreed
    # with is named — `waiting` was the only one named until 2026-08-28, which
    # made the far more common `idle` disagreement invisible.
    declared = (record or {}).get("status")
    ignored = declared if declared in (STATUS_WAITING, STATUS_IDLE, STATUS_SHELL) else None
    return measured(
        AgentState(
            state=WORKING,
            declaration_ignored=ignored,
            last_movement_age=movement,
            tool=first.get("name"),
            tool_elapsed=_age_seconds(first.get("timestamp"), reference),
            other_tools=[m.get("name") for m in ordered[1:] if m.get("name")],
            excerpt=excerpt,
            excerpt_from=excerpt_from,
        )
    )
