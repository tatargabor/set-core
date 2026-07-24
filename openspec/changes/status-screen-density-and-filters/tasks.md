## 1. The screen uses the screen

- [x] 1.1 Remove the `max-w-5xl` cap from the page container; the header, the contract line and the tab strip stay full width [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away]
- [x] 1.2 The table scrolls horizontally inside its own container and the page never does — measured on a real answer's column count, not assumed [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away]
- [x] 1.3 Sticky table header and monospace/tabular figures for the frame, reusing the dashboard's existing TUI vocabulary — frame only, no colour keyed on a value [REQ: set-cores-own-status-vocabulary-shall-not-be-applied-to-a-projects-values]

## 2. Dense rows without losing anything

- [x] 2.1 One line per row: cells clip rather than wrap, with the full value in `title` [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away]
- [x] 2.2 Clicking a row expands the complete record beneath it, rendered by the same value renderer at full depth, with deprecation and emphasis rules unchanged [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away]
- [x] 2.3 No column is ever dropped for density — a test asserts every delivered column is present [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away]

## 3. Filters, derived from shape

- [x] 3.1 Derive facet columns from the values: every present value scalar, distinct count ≤ 12 and ≤ half the rows. The thresholds live in one named constant each, next to the reason [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name]
- [x] 3.2 Each facet value carries a row count taken from the data, never from a declaration [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name]
- [x] 3.3 A free-text substring search across all rendered cells, case-insensitive [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction]
- [x] 3.4 A test that a column named as one of set-core's own domain words is treated exactly like an identically-shaped column with a nonsense name — the coupling this forbids is the easy implementation, so the guard is a test rather than a comment [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name]

## 4. Hiding is never silent

- [x] 4.1 The existing row count states rendered-of-received whenever anything is filtered, in the same place a reader is already looking [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction] [REQ: compacting-must-never-hide-a-failure]
- [x] 4.2 One control clears every filter and the search at once [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction]
- [x] 4.3 An empty result says so explicitly and keeps the clearing control reachable — an empty table must never read as an empty answer [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction]
- [x] 4.4 No claim about hidden rows when nothing is filtered — the false-absence direction, and the one the tests must cover from the hiding side [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction]

## 5. Sorting that can be undone

- [x] 5.1 Header click cycles delivered → ascending → descending → delivered [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order]
- [x] 5.2 Numbers compare numerically, everything else as text; absent values sort last in both directions [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order]
- [x] 5.3 The table states when it is not in the project's delivered order [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order]

## 6. Nothing is persisted

- [x] 6.1 All view state is React state; no `localStorage`, no cookie, no URL parameter [REQ: view-state-shall-not-be-persisted-anywhere-that-survives-the-tab]
- [x] 6.2 A test asserting that filtering writes nothing to browser storage and does not touch the URL [REQ: view-state-shall-not-be-persisted-anywhere-that-survives-the-tab]

## 7. Prove it

- [x] 7.1 Every new test stashed and re-run: a test that also passes without the change proves nothing and looks like proof forever
- [x] 7.2 Full `web` unit suite green, and the existing renderer honesty tests unchanged — if one needed changing, the change is the finding
- [x] 7.3 Look at the screen on a real answer before calling it done. Structural counts prove it renders; they say nothing about whether it is readable

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a table has a scalar column with few distinct values THEN a filter is offered with counts from the data [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name, scenario: a-categorical-column-offers-a-filter]
- [x] AC-2: WHEN a column's values are nearly all distinct THEN no filter is offered [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name, scenario: a-free-text-column-offers-none]
- [x] AC-3: WHEN two identically-distributed columns differ only in name THEN both behave identically [REQ: filters-shall-be-derived-from-the-shape-of-the-data-never-from-a-field-name, scenario: the-column-name-is-irrelevant-to-the-decision]
- [x] AC-4: WHEN any filter is active THEN rendered and received counts are both shown with a single clearing control [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction, scenario: a-filter-is-active]
- [x] AC-5: WHEN nothing is filtered THEN no claim about hidden rows is made [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction, scenario: no-filter-is-active]
- [x] AC-6: WHEN a filter matches no row THEN it is stated explicitly and clearing stays reachable [REQ: hiding-rows-shall-be-self-reporting-and-reversible-in-one-interaction, scenario: a-filter-selects-nothing]
- [x] AC-7: WHEN a column is sorted repeatedly THEN the cycle returns to the delivered order [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order, scenario: sorting-cycles-back-to-the-delivered-order]
- [x] AC-8: WHEN rows are not in the delivered order THEN the surface says so [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order, scenario: a-sorted-table-says-it-is-sorted]
- [x] AC-9: WHEN a sorted column has absent values THEN they sort last in both directions [REQ: sorting-shall-be-undoable-back-to-the-projects-delivered-order, scenario: absent-values-do-not-migrate-to-the-top]
- [x] AC-10: WHEN a cell exceeds its width THEN it is clipped visibly and the full value stays reachable [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away, scenario: a-long-value-is-clipped]
- [x] AC-11: WHEN a table is rendered densely THEN every delivered column is still present [REQ: a-dense-row-shall-keep-its-complete-record-one-interaction-away, scenario: density-never-costs-a-column]
- [x] AC-12: WHEN a reader filters, searches or sorts THEN nothing appears in browser storage or the URL [REQ: view-state-shall-not-be-persisted-anywhere-that-survives-the-tab, scenario: filtering-leaves-nothing-behind]
- [x] AC-13: WHEN the page is reloaded THEN every row is shown again [REQ: view-state-shall-not-be-persisted-anywhere-that-survives-the-tab, scenario: a-reload-starts-clean]
- [x] AC-14: WHEN a project value collides with a set-core status word THEN it renders like any other string [REQ: set-cores-own-status-vocabulary-shall-not-be-applied-to-a-projects-values, scenario: a-project-value-collides-with-a-set-core-status-word]
- [x] AC-15: WHEN rows are withheld by a filter THEN the number withheld is stated where the row count is shown [REQ: compacting-must-never-hide-a-failure, scenario: rows-withheld-by-a-filter]
