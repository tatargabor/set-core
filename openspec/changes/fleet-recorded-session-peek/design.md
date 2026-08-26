## Context

The restore disclosure shipped the same day this change was written, and looking at it on a real
record found two things at once: a label repeated six times with only an age to tell the rows
apart (B-80), and no way to answer the question that actually decides which one to pick — *what
was this conversation*.

The second is nearly free, and that is worth stating because it changes what the right design is.
`fleet/conversation.py::read_conversation(session_log, limit=…)` already exists, already reads
from the END of the file, and is already the parse behind the live agent's log view. It takes a
**path**, not a pid — so it works on a recorded entry with nothing running on it, and
`roster.read()` already resolves that path per entry. Measured on the live record: three
recorded, non-running sessions of 439 / 156 / 314 turns each answered a 3-turn read immediately.

## Goals / Non-Goals

**Goals:**

- Make a repeated label choosable: one lineage, opened to its conversations.
- Let a person see what a recorded conversation was, without resuming it.
- Keep the read strictly a read — nothing started, nothing written down.

**Non-Goals:**

- Changing what the record holds. Six entries under one label is *correct*: they are six
  conversations. This is about how they are presented, not about merging them.
- Summarising, searching or titling a transcript. The last turns, as they are.
- A second log viewer. The live agent's log view stays as it is; this is the same parse reached
  by a different key.

## Decisions

### The peek is addressed by the roster key, not by a pid

The existing log route is `/api/fleet/agents/{pid}/log`, and a pid is exactly what a recorded
entry does not have — that is the condition the roster exists for. So the new route is
`GET /api/fleet/roster/{project}/{key}/peek`, resolving the entry through `roster.read()` and
handing its `session_log` to the same parse.

`{key:path}`, for the reason the forget route already gives: an entry with no session id is keyed
on a synthetic name containing a slash, and a route that could not address it would leave exactly
those entries — the ones the runtime never named — unaddressable. They are refused with a stated
reason rather than being unreachable.

*Alternative considered: extend the existing route to take a session id.* Rejected because the
guard on that route ("whatever log a stale pid maps to would serve one session's conversation
under another's name") is written against a pid, and loosening its key would loosen that guard
for the live path too.

### A not-found key is a 404, and an unreadable transcript is a 200 with a problem

They are different facts and the surface says different things about them: the first means *this
entry is not in the record* (a bug, or a race with a `forget`), the second means *this entry is
in the record and its conversation is gone* — which is information about the agent, and is
already what `not_resumable_reason` says on the same entry.

### The lineage is grouped by LABEL, and the group is not a new kind of thing

Grouping happens in `fleetRoster.ts` as a pure function over the entries the surface already has,
returning either an entry or a group of entries. The list renders both, and the selection stays
per-entry throughout — a group is a way of *showing* rows, never a thing that can be restored as
a unit. A "restore this lineage" act would start six conversations of one agent at once, which is
the defect B-78 just removed, re-entering through a different door.

An entry with no label at all groups under its key, so it is never silently merged with another
unlabelled one.

### Turns are rendered as what they are, including the ones with no text

Measured on the live record: the last turn of a recorded session is often a `/compact`, an empty
user entry, or a tool-only assistant turn. Filtering those out would make the peek *look* like it
found nothing, and dropping the filter would render blank lines. So a turn with no text renders
as what it did — a tool call, a result — and the count of turns shown is stated, so a short
answer cannot read as a whole conversation.

## Risks / Trade-offs

- **A peek renders a project's data on screen.** → That is what the framework is for and it is
  explicitly allowed; what is forbidden is persisting it. The route holds no cache, the client
  holds it in component state only, and nothing about it reaches `localStorage`, a log line or a
  committed artifact. Held by a requirement and a test rather than by intention.
- **Grouping hides rows behind a disclosure.** → The same rule as the list itself: the group
  states its count, and nothing that is *wrong* is hidden — the reasons that block an entry stay
  on the entry, and a group whose entries are all unusable still says so at the group level.
- **A very large transcript.** → The parse already tails a bounded number of bytes; this path
  adds no new exposure and the measured cost on a 439-turn log was immediate.

## Migration Plan

None. No stored shape changes; the route is additive; the surface degrades to today's flat list
if the peek route is unavailable, because the read is a component-level fetch whose failure
renders as a stated problem.

## Open Questions

None.
