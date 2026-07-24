## Context

This screen already carries eight requirements about honesty and exactly one about layout —
*compacting must never hide a failure*, written when a long list of identifiers swallowed the
rows beneath it. Everything this change adds is a compaction mechanism, so that one
requirement is the spine of the design rather than a constraint on it.

The difference in scale is the point. Shortening a chip list withholds values inside one cell,
where the row is still visible. A **filter withholds rows**, a **sort moves them**, and a
**clipped cell withholds text** — three ways for something bad to be on screen and not seen,
all of them chosen by the reader, which is precisely when nobody goes looking for what is
missing.

## Goals / Non-Goals

**Goals:**

- Make dozens of rows across nine columns readable on a wide screen without dropping anything.
- Keep every mechanism shape-driven, so the second project to publish a contract gets the same
  behaviour without a change here.
- Make every act of hiding self-reporting and one interaction from undone.

**Non-Goals:**

- Interpreting any value. No severity ordering, no status colouring, no "important" column.
- Persisting anything at all, including view state — see D2.
- The unmarked-bad-news mechanism (a project declaring which values are problem indicators).
  That is a contract change and belongs to its own change.

## Decisions

**D1 — A facet is chosen by SHAPE, and its counts come from the data.**
A column qualifies when every present value is a scalar (or absent) and the number of distinct
values is small both absolutely (≤ 12) and relative to the rows (≤ ½ of them). That is a
description of *categoricalness*, which is a property of the values — not of the name.

Rejected: a list of known filterable names (`severity`, `status`, `category`). It would work
today, on one consumer, and it is the exact coupling the renderer's first line forbids. The
tell that it is wrong is that it is *easy* — the names are right there on the screen.

The threshold pair matters. An absolute cap alone would make a nearly-all-distinct column
a facet of one-row chips; a relative cap alone would make a 2-value column on 4 rows
a facet that filters nothing. Both are noise, and noise is what gets a control ignored.

**D2 — View state is memory-only. Not `localStorage`, and NOT the URL.**
The confidentiality boundary here is persistence, not visibility: this surface may render the
consumer's domain, and must write none of it anywhere that survives the tab.

A facet selection **is** domain data — the value is a string the consumer chose, and clicking
it puts that string into whatever holds the view state. `localStorage` is disk. The address bar
is *also* disk: the browser writes history, it syncs, and a screenshot of the window carries it.
A shareable filtered link is the natural thing to build next and it is the leak.

The price is real and accepted: a reload loses the filter. It is the same trade this page
already makes by never caching an answer, and stating it here is what stops the next reader
"fixing" it.

**D3 — Sorting is undoable back to the project's order, and the surface says when it is not in
it.** Delivery order is a decision by the side that owns the data — the `sections` requirement
already establishes that position carries meaning on this screen. A sort that cannot be undone
overwrites that decision permanently for the reader.

So the cycle is *project order → ascending → descending → project order*, and while a sort is
applied the header states it. Comparison is by value type (numbers numerically, everything else
as text, absent values last regardless of direction), never by a meaning attached to the word.

**D4 — Density comes from clipping plus a detail row, never from dropping a column.**
One line per row, cells clipped with the full text in `title`; clicking the row expands the
complete record beneath it, rendered by the same value renderer at full depth, with the
deprecation and emphasis rules intact.

Rejected: hiding low-value columns automatically. There is no domain-free way to know which
column is low-value, and guessing produces the worst failure this surface has — something
missing that nobody was told about.

**D5 — The TUI vocabulary may style the FRAME, never the DATA.**
`tui.tsx` maps `done` / `running` / `failed` to colours. Those are set-core's words for
set-core's own runs. A project publishing `status: FIXED` must not be coloured by that table:
it would be domain name recognition arriving through a styling helper, and it would assert that
set-core knows what the project's word means. Monospace, rules, sticky headers and block
characters are frame; colour keyed on a value is interpretation. A test asserts a project value
that collides with a set-core status word is rendered no differently from any other string.

**D6 — Hiding is reported where the reader stands, not where the hidden thing lives.**
The row count above the table already exists and already says *rows*, deliberately. When a
filter or a search is active it states, in the same place: how many rows are shown, how many
the answer contained, and a control that clears every filter at once. The strong form of the
rule this obeys is that a reader must never have to *remember* that they filtered.

## Risks / Trade-offs

- **A filter is the most effective way yet invented to hide a failure** → the whole of D6, plus
  the tests are written from the hiding side: what is *not* shown is the assertion, not what is.
- **Clipping hides text** → the full value is in `title` and in the detail row, and no cell is
  ever clipped without the detail being one click away. Clipping without an expansion path would
  be a silent truncation, which the existing requirement already forbids.
- **Reload loses the view state** (D2) → accepted, and named in the spec so it reads as a
  decision rather than a bug.
- **Facet thresholds are numbers chosen by judgement** → they are stated in the spec as bounds
  rather than as the truth, and the failure mode of getting them wrong is a control that does
  not appear, never data that disappears.

## Open Questions

None. The one thing this design deliberately leaves to another change — the project declaring
which of its values are problem indicators — is named in the proposal so the next reader does
not take its absence for an oversight.
