## Context

What waits on the owner lives in four places today, and the fleet reads two of them:

| source | where it lives | fleet reads it today |
|---|---|---|
| agent questions | the attention class per agent (`fleet/state.py`), the question relay's waiting record (`fleet/question_relay.py`) | yes, as separate surfaces (PM mode, the relay chip) |
| framework run state | `fleet/awaiting.py` — manual, stalled, orphaned, decision | yes, a per-project count |
| project questions | the project's own ticket/decision data | no |
| bus entries addressed to the owner | `set-agent-comm` rooms | no — and today the addressing is prose inside broadcasts |

The project side is reached the way every other project datum is: a **declared read command**
speaking the versioned status contract. set-core keeps no built-in list of commands, and the
board strip was consumed this way with zero framework changes. The rule that governs the shape:
*the framework defines the SHAPE, the project supplies the VALUE* — and where a consumer already
computes the list, its shape is adopted rather than a parallel one invented.

## Goals / Non-Goals

**Goals:**
- One list, one API answer, one header control; every source's gap visible as a gap.
- Sources 1–2 shipped without waiting on anyone; sources 3–4 shipped the moment their shape is
  agreed, without reshaping what was built.

**Non-Goals:**
- Answering in the panel. Answers belong where the question lives; the panel is a map.
- A chat notifier. A notifier (the owner's copilot, a chat channel) reads the API; it does not get
  a second list. Building it is the copilot's work, not this change's.

## Decisions

### D1. One aggregator module, one source adapter per source

`lib/set_orch/fleet/waiting.py` holds four adapters with one signature —
`collect(now) -> SourceResult(name, measured, reason, items)` — and the aggregator that sums only
measured sources. An adapter that raises is caught, logged at WARNING with the source name, and
reported as unmeasured. This keeps "a gap is not a zero" in one place instead of four.

### D2. Agent questions are de-duplicated by session

The relay's waiting record and the attention class can describe the same pending question (while
the relay hook holds it, the agent reads as busy; once released, it reads as waiting). Items are
keyed by session id; the relay record wins because it carries the wait's start.

### D3. Project questions: a declared command named `questions` — shape PROPOSED, to be agreed

Proposed envelope `data` (the contract's own envelope, version and caveats are unchanged):

```
items: [
  { id:      string,                       # the project's own identifier
    kind:    "question" | "decision",
    title:   string,                       # display only, never persisted
    since:   ISO-8601 timestamp,
    blocks?: [ { kind: "release" | "change", id: string } ],
    ref?:    { command: string, row: string },   # a row in another declared command
    askedBy?: string }
]
complete: boolean                          # false when the project knows the list is partial
```

Why these fields: `since` orders the list; `blocks` is the one thing the owner triages by (the
consumer's own coordinator leads with the release-blocking items); `ref` lets the panel link into
the status table the framework already renders, without knowing the project's vocabulary.
`complete: false` is carried as a marker, never hidden — the false-absence class.

This is a **proposal** on the bus. If the consumer's coordinator already produces such a list, its
shape wins and this section is rewritten to it before the adapter is built.

### D4. Bus entries: a reserved `owner` addressee and a machine view — PROPOSED, to be agreed

Proposed to `set-agent-comm`: `--to owner` as a reserved addressee meaning *the human of this
machine*, stored in the entry's `to` like any other address; and a machine-readable view (for
example `sac owner --json`) listing owner-addressed entries that are still open, across rooms,
with room, entry id, timestamp, type, sender and text. What makes an entry *open* (an `ANSWER`
with `re:` pointing at it, an explicit close, or both) is the bus's decision, not ours.

Why not parse `→ <owner>` from text: that is the prose-read-as-fact class, and it fails in the
quiet direction — a phrasing change drops items without an error. Why not read the store files:
a second reader of another project's format drifts the day that format changes.

### D5. The header control is a chip beside the relay chip; the panel is an overlay

Placed with the PM toggle and the relay chip because all three are machine-wide. The panel is
absolutely positioned, closes on its control and Escape, and never auto-closes (it reports a
standing state). Its links reuse the existing jumps: `goTo` for an agent, the status page row for
a project item, the wire panel's room view for a bus entry.

## Risks / Trade-offs

- [Sources 3–4 never get agreed] → the panel shows them as unmeasured with the reason, which is
  the honest state; sources 1–2 are useful alone.
- [Polling four sources costs] → the adapters reuse the cached roster and the contract reader's
  transport cache; the endpoint is polled at the board strip's cadence, not the agent listing's.
- [Item titles carry consumer content] → read at request time, never logged or cached to disk;
  a test asserts no title reaches a log record.

## Migration Plan

None. New endpoint, new control; nothing existing changes shape.

## Open Questions

- The project command's shape (D3) — on the bus to the consumer.
- The owner addressee and its open/closed semantics (D4) — on the bus to `set-agent-comm`.
