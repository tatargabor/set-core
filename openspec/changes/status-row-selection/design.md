## Context

`StatusTable.tsx` renders a project's rows and already carries four narrowing mechanisms: free-text
search, facet filters bounded by `FACET_MAX_DISTINCT = 12` / `FACET_MAX_SHARE = 0.5`, a sort that
announces itself as *not the project's order*, and `ROW_CAP = 25` with an expand control. All four
change **which rows are visible**. None of them lets a reader name a set.

Measured on a live producer's table today: 173 rows, 50 open, 36 of those unplanned; `status`,
`severity` and the planning field all qualify as facets. So the narrowing needed to reach the
interesting rows exists — and the reader still cannot point at them.

The row-level write path exists (`statusShape.tsx:184-273`): a project attaches `actions` to a row,
the surface renders a button with a confirmation stating that the record is the clicker's own
assertion. The framework-level key list it belongs to is small and deliberate (`actions`,
`deprecated`, `_emphasis`, `caveats`, `sections`).

The eventual flow this serves — select unfixed items, plan them into an open release, then start an
investigation and a fix queue — is described and agreed with the user, but its producer half does
not exist yet: measured today, the release answer carries one open draft and no item list, and a
row's planning field points at a *change* while another points at the release a fix already shipped
in. Designing the framework's guess at "belongs to that open release" would be the parallel design
this track exists to prevent.

## Goals / Non-Goals

**Goals:**
- A reader can assemble a set of rows and see, without ambiguity, what is in it.
- The set is not silently altered by anything that changes the view.
- Where a project declares an action for a set, the surface offers exactly one control for it.
- Where it does not, the reader is told — not left with a screen that merely does nothing.

**Non-Goals:**
- No write is performed. There is no batch action to send yet.
- No release planning, no investigation, no fix queue — later changes, and their shape belongs on
  the channel first.
- No persistence of a selection (not to a URL, not to storage) — see D4.
- No change to the row-level `actions` path.

## Decisions

### D1. Selection is keyed by a project-supplied identity, and the fallback is stated

A selection must survive re-sorting and re-filtering, so it cannot be a set of row indices. It is a
set of **keys**, where the key is the row's own identifying value when the table has one, and the
row's position when it does not.

The framework may not recognise a domain field name — so it does not look for `id`. It uses the
column the table has already computed as identifying (the first column whose values are unique
across all rows and scalar). Where no such column exists, the key falls back to row position, and
in that mode selection is **not** preserved across a sort — because it cannot be, and pretending
otherwise would mean silently selecting a different row than the one clicked.

*Alternative rejected:* recognise `id`/`key`/`name`. That is a domain name in a domain-free layer,
and it fails on the first producer that names its identifier differently — which the surface's own
first requirement forbids.

**The fallback mode is stated in the UI, not just in this document.** A reader whose selection
would be invalidated by sorting must be told before they sort, not after.

### D2. A batch action is declared at the ANSWER level, not derived from rows

The producer attaches a batch action to the answer (beside its data), not to a row. Two reasons,
and the second is the load-bearing one:

- A batch call needs arguments the rows cannot carry — which command, and under what label.
- **Acting on a set is a different assertion from acting on each member.** The row action's
  confirmation says the record is the clicker's own statement about *that row*. Applying it twenty
  times produces twenty independent statements, which is not what "these twenty" means. Only the
  producer knows whether it has a write that takes a set.

So the framework never synthesises a batch control from a row-level one, and the spec holds that
as its own scenario. The exact declaration shape is an open question (below) — this change reads a
minimal shape and renders it; it does not send it.

### D3. The selection summary counts the invisible part explicitly

This is the surface's standing rule — *compacting must never hide a failure* — applied to the
reader's own set rather than to the project's values. A selection of 13 where 9 are hidden by a
filter reads as 4 unless the difference is stated. That is a false absence, the class this repo has
paid for repeatedly, and here it would silently shrink an action's blast radius: the reader
believes they are acting on what they see.

Therefore the count of selected-but-hidden rows is shown whenever it is non-zero, and any batch
control states the **total** it would act on, not the visible count.

### D4. The selection is not addressable, and that is deliberate for now

The sibling change `status-table-structured-cells-and-controls` makes *narrowing* addressable, and
the same argument would apply here — but a URL that carries selected identifiers is a URL that
carries the producer's domain values, which this repo must not persist anywhere it can leave the
machine. Left out until that boundary is worked through on its own.

### D5. Select-all means "all that are showing", and says so on the control

The alternative — selecting everything the table holds — is defensible and is the one that surprises
a reader who has just filtered. Naming the limit on the control itself is cheaper than being right
about which one people expect, and it fails toward the smaller set.

## Risks / Trade-offs

- **A stale selection after the data refreshes** → rows are keyed by identity (D1), so a refreshed
  answer that no longer contains a selected row drops it from the selection. The summary counts what
  is selected *and present*; a key that no longer matches any row is not counted as selected, because
  a count that includes vanished rows would overstate what an action could reach.
- **The fallback key mode is a real hole** → stated in the UI (D1) rather than hidden; a table with
  no unique column is the case where selection is least useful anyway.
- **A batch declaration whose shape we guessed wrong** → nothing is sent this round, so a wrong guess
  costs a parser rewrite, not a wrong write. The shape goes to the channel before anything sends.
- **Two changes touching `StatusTable.tsx` at once** → the sibling change is 3/30 and its live work is
  in `statusShape.tsx` classification; the overlap is the render path. Sequence them, do not run both
  in parallel worktrees.

## Open Questions

1. **The batch action declaration shape** — one call carrying the identifiers, or the framework
   repeating a row call? (The latter is rejected by D2 as a *derivation*, but a producer may still
   declare an explicit repeat.) Goes to the channel as its own thread.
2. **How an item is attached to an open release** — does not exist as producer data yet; theirs to
   shape, ours to render.
3. **Whether the eventual investigation/fix-queue controls belong on this selection at all**, or on
   a separate screen — the user's description allows either, and the answer depends on where the
   agent's questions surface.
