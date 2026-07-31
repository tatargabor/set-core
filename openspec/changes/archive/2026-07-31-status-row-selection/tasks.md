# Before you start — the traps already measured on this surface

Carried forward from the sibling change's handoff, because they cost a session each and none of
them is discoverable from the code:

- **`npx tsc --noEmit -p tsconfig.json` is NOT the typecheck.** It reported clean while
  `pnpm build` failed on five import errors — that tsconfig is a project-references root covering
  none of these files. **Use `pnpm build`.**
- **`web/dist/` is tracked and `set-web` serves it from disk.** After any web change: `pnpm build`
  AND commit `dist/`, or the repository and port 7400 diverge.
- **Verify by driving, not by calling.** A harness that calls the selection helper tests a system
  where every control already works. Click the checkbox, change the filter, read the summary.
- **Then look at it.** Structural counts prove it renders; they say nothing about whether the
  summary line contradicts the row count next to it.

## 1. Selection state, keyed by identity

- [x] 1.1 Compute the table's identifying column: the first column whose values are scalar and
  unique across all rows. No field name is recognised — the column is chosen from the values
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 1.2 Hold the selection as a set of keys (identifying value, or row position when 1.1 finds no
  unique column), so re-sorting and re-filtering cannot change which rows are selected
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 1.3 In position-key fallback mode, state in the UI that sorting will invalidate the selection —
  before the reader sorts, not after
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 1.4 A key that matches no row in the current answer is not counted as selected — a refreshed
  answer that dropped a row must not leave a count that overstates what an action could reach
  [REQ: the-selection-states-its-own-size-and-what-it-withholds]

## 2. The controls

- [x] 2.1 A checkbox per row, in a column that does not disturb the existing column layout
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 2.2 A select-all control that acts on the rows currently showing, and NAMES that limit on the
  control itself [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 2.3 No selection control at all when the table has no rows — a control that cannot select
  anything reads as broken
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 2.4 A clear-selection control, reachable while part of the selection is hidden
  [REQ: the-selection-states-its-own-size-and-what-it-withholds]

## 3. The summary that cannot lie

- [x] 3.1 State the selected count; whenever any selected row is hidden by a search, a filter or the
  row cap, state how many [REQ: the-selection-states-its-own-size-and-what-it-withholds]
- [x] 3.2 A test that a selection of N with M hidden never displays as N−M anywhere the reader can
  see — the false-absence direction is the one that shrinks an action's blast radius silently
  [REQ: the-selection-states-its-own-size-and-what-it-withholds]

## 4. A batch action only where it is declared

- [x] 4.1 Parse a project-declared batch action from the ANSWER level, alongside the existing
  row-level `actions` parser, and add its key to the framework-level key list
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]
- [x] 4.2 Render one control for the whole selection when a batch action is declared, stating the
  TOTAL it would act on — including hidden rows
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]
- [x] 4.3 Where no batch action is declared, the summary says so in words; no disabled control with
  an unstated reason
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]
- [x] 4.4 A test holding the refuted approach: rows carry a row-level action and no batch action is
  declared → NO batch control appears. This is the "obvious improvement" a later session would add,
  and it would turn one assertion about a set into N independent assertions
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]
- [x] 4.5 Nothing is sent this round — assert that selecting rows and clicking any rendered batch
  control performs no write
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]

## 5. Prove it

- [ ] 5.1 **WITHDRAWN as written, and the reason is the finding.** "Byte-identical" was the wrong
  bar: the table gains a column, so its DOM changes by design. Three existing tests proved it by
  breaking — all three read `td:nth-child(2)`, which measures the LAYOUT rather than the data. They
  were repointed at `data-col="<name>"` instead of at `nth-child(3)`, because the positional
  selector would break again on the next column. What replaces this task: 170/170 web unit tests
  pass, and the three repointed assertions are unchanged in substance
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 5.2 Mutation-test each rule one at a time: identity key → index key, hidden-count → visible-count,
  declared-batch → derived-from-row. Apply, assert the mutation landed, run, then assert the RESTORE
  landed by re-reading the file
  [REQ: the-selection-states-its-own-size-and-what-it-withholds]
- [x] 5.3 Drive the page the way a reader reaches it — click the checkbox, change the filter, read the
  summary. Never call the selection helper directly
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table]
- [x] 5.4 Look at the screen with a real answer loaded: does the selection summary contradict the row
  count beside it, and is the checkbox column readable at the table's real density
  [REQ: the-selection-states-its-own-size-and-what-it-withholds]

## 6. Wired to the live declaration (added after the scope widened)

- [x] 6.1 A refused write reports the PROJECT's reason, not an exit code — their write commands are
  exit-code + stderr contracts, so that text is the only place the reason exists
  [REQ: a-refused-write-hands-back-the-projects-own-reason]
- [x] 6.2 The log keeps carrying the SHAPE only (command, exit code, byte count) — held by a test
  that fails if someone logs the reason alongside returning it
  [REQ: a-refused-write-hands-back-the-projects-own-reason]
- [x] 6.3 Measured against the live producer AFTER they published the declaration: the control
  appears, is disabled with a stated reason, offers their computed options, and enables on choice.
  Verified with every browser dialog refused and zero dialogs seen — nothing was written
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated]

## Acceptance Criteria (from spec scenarios)

### A reader can select rows, and the selection survives what narrows the table

- [x] AC-1: WHEN rows are selected and the reader then narrows the table so some no longer show
  THEN those rows remain selected, and are still selected when the narrowing is removed
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table, scenario: a-filter-changes-after-rows-are-selected]
- [x] AC-2: WHEN the reader selects all rows with one control while a filter is active THEN only the
  rows currently showing are added, and the control names that limit
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table, scenario: select-all-acts-on-what-is-showing-and-says-so]
- [x] AC-3: WHEN a table has no rows at all THEN no selection control is offered
  [REQ: a-reader-can-select-rows-and-the-selection-survives-what-narrows-the-table, scenario: a-table-with-no-rows]

### The selection states its own size and what it withholds

- [x] AC-4: WHEN some selected rows are hidden by a filter, a search or the row cap THEN the count of
  hidden-but-selected rows is shown beside the selection count
  [REQ: the-selection-states-its-own-size-and-what-it-withholds, scenario: selected-rows-hidden-by-a-narrowing-control]
- [x] AC-5: WHEN any row is selected THEN a clear-selection control is available without first
  removing the narrowing that hides part of it
  [REQ: the-selection-states-its-own-size-and-what-it-withholds, scenario: clearing-the-selection-is-always-reachable]

### A batch action is offered only where the project declares one, and its absence is stated

- [x] AC-6: WHEN rows are selected and the answer carries no batch action THEN the summary states
  that this project offers no action on a selection, with no disabled control whose reason is unstated
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated, scenario: a-project-declares-no-batch-action]
- [x] AC-7: WHEN rows carry a row-level action and no batch action is declared THEN no batch control
  appears
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated, scenario: a-row-level-action-exists-but-no-batch-action]
- [x] AC-8: WHEN the answer declares a batch action and at least one row is selected THEN one control
  is offered for the whole selection, stating how many rows it would act on including hidden ones
  [REQ: a-batch-action-is-offered-only-where-the-project-declares-one-and-its-absence-is-stated, scenario: a-declared-batch-action-is-rendered]
