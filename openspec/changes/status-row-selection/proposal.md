## Why

The status surface can answer *what is true*; it cannot yet be worked FROM. A reader who has
narrowed a table to the rows that matter has no way to say **"these ones"** — every control on
the page acts on a column or on a single row, never on a set the reader assembled.

**Measured on a live producer today**, through the framework's own API, on the table this is
wanted for: **173 rows, 50 of them still open, 36 of those with nothing planning them.** The
narrowing already works — `status` (4 distinct values), `severity` (4) and the planning field
(5) all qualify as facets under the existing bounds, so the reader can reach those 36 rows with
the controls that exist. What has no expression at all is the next sentence: *these thirteen.*

**The row-level write path is already built and is the wrong shape for this.** A project attaches
`actions` to a ROW and the surface renders a button on it (`statusShape.tsx:184-273`). Acting on
twenty rows would mean twenty confirmations, each an independent assertion — which is not what the
reader means, and each confirmation would be true while the SET they add up to is nobody's
statement.

**Why now, and why only this half.** The intended flow — select the unfixed ones, plan them into
an open release, then start investigation and a fix queue from the same screen — was described in
full by the user. The producer's side of it is **being designed right now**: measured today, their
release answer carries one open draft and no bug list, and a bug row carries a field pointing at a
*change* and another at the release a fix already shipped in — so **"this bug belongs to that open
release" does not exist as data yet**. Building the framework's guess at that shape would be the
parallel design this track exists to avoid. What is unambiguously ours, needs nothing from them,
and is the precondition for every later verb: **the selection itself.**

## What Changes

- **Rows can be selected.** A checkbox per row, plus select-all-that-are-showing, on any status
  table — nothing about bugs, releases or any other domain enters the surface.
- **The selection is a stated object, not a hidden one.** A summary states how many rows are
  selected and — the part that matters — how many of them are **not currently visible** because a
  filter, a search or the row cap hides them. A selection that silently shrinks when a filter
  changes is the same defect class as a compacted screen hiding a failure.
- **A batch action is offered only where the PROJECT declares one**, at the level a batch belongs
  to (the answer), not on a row. The framework never infers that a row-level action can be applied
  to many rows: repeating an assertion twenty times is not the same act as asserting it about a
  set, and only the producer knows which of its writes is which.
- **Where no batch action is declared, the absence is READABLE** — the selection summary says so
  in words. A selection that can be made and then does nothing, with no explanation, is a false
  affordance; and silence here would be indistinguishable from a broken button.
- **Nothing is started.** No investigation, no fix queue, no release planning. This change ends at
  a selection that can be handed to an action once one exists.

## Capabilities

### New Capabilities
<!-- None. Selection is how the existing surface is operated, not a second surface. -->

### Modified Capabilities
- `project-status-surface`: rows become selectable; the selection states its own size and what it
  withholds; a batch action appears only where the project declares one, and its absence is stated
  rather than silent.

## Impact

- `web/src/components/StatusTable.tsx` — selection state, the checkbox column, the summary line,
  interaction with the existing search / facets / sort / row cap.
- `web/src/components/statusShape.tsx` — parsing a project-declared batch action, alongside the
  existing row-level `actions` parser; the shared framework-level key list.
- `web/tests/unit/` — new specs, including the refuted patterns held as tests.

**Deliberately NOT changed:** no write is sent (there is no batch action to send yet), no field
name becomes meaningful, the row-level `actions` path is untouched, and no selection is persisted
anywhere — it lives in the page, like the filters do.

**A question for the producer, deliberately not answered here:** what shape a batch action takes
(one call carrying the identifiers, or the framework repeating a row call), and how a bug is
attached to an open release. That belongs on the channel, as its own thread.
