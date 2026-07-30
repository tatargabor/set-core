## 1. Structured cells become first-class

- [x] 1.1 `cellText` walks a cell's scalar leaves instead of returning `''` for objects, joining them so a search for one leaf matches the row. Key names and punctuation are excluded — searching the serialised object matches every row and narrows nothing [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data]
- [x] 1.2 **Mostly already present, and measuring that saved building a second one.** `flattenUniformObjects` already spreads a uniform one-level object into `source.kind`-style columns, capped at 8 keys and refused for ragged shapes (a flattened ragged shape would invent columns most rows lack and render every gap as unknown). What was missing was not the columns but the INDEX — see 1.1. Remaining gap, recorded rather than assumed away: a sub-path whose value is a list stays a single column, which is correct for rendering and means it is narrowable only by search until 2.x lands. Sub-paths of a structured cell become candidate columns (`source.kind`, `source.date`), discovered from the rows rather than declared, and then subject to the same control rules as any other column [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data]
- [ ] 1.3 A structured cell renders its leaves — a matched row must show WHY it matched, or search reaches rows whose reason is invisible [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data]
- [x] 1.4 A test holding the refuted approach: searching the serialised object matches on a key name. It must fail, so a later "simplification" to `JSON.stringify` cannot look identical and quietly stop narrowing [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data]

## 2. Controls chosen by value shape

- [ ] 2.1 Classify a column from its values: categorical, all-numeric, all-dates, or none of these. One classifier, used by every control, so two controls cannot disagree about the same column [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values]
- [ ] 2.2 A numeric column whose facet would not narrow usefully receives a range control instead, reusing the facet's existing bounds rather than inventing a second notion of "too many values" [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values]
- [ ] 2.3 A column receives a period control only when EVERY non-empty value parses as a date. One non-date value disqualifies it — the check fails toward today's behaviour, which is the safe direction [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values]
- [ ] 2.4 A test that an identifier column containing dates in some values and not others gets NO period control and has no date extracted. The refuted pattern held in a test, because mining the slug is the obvious next "improvement" [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values]
- [ ] 2.5 No control is selected from a column's name — asserted by classifying columns whose names suggest one shape and whose values are another [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values]

## 3. The narrowed view is addressable

- [ ] 3.1 Active narrowing is written to the address and restored from it [REQ: a-narrowed-view-is-addressable-and-what-cannot-be-restored-is-reported]
- [ ] 3.2 A part that cannot be applied — an absent column, a value nothing carries — is REPORTED beside the row count, never dropped. Silently dropping it selects nothing, which looks exactly like a project with no rows [REQ: a-narrowed-view-is-addressable-and-what-cannot-be-restored-is-reported]
- [ ] 3.3 A test for the stale-address case specifically, since it is the one that produces a confident empty screen [REQ: a-narrowed-view-is-addressable-and-what-cannot-be-restored-is-reported]

## 4. Column visibility, without hiding a failure

- [ ] 4.1 Columns can be hidden and restored [REQ: a-hidden-column-may-not-conceal-a-failure]
- [ ] 4.2 Anything the surface marks inside a hidden column is counted beside the control that hid it, and names which column it is in [REQ: a-hidden-column-may-not-conceal-a-failure]
- [ ] 4.3 A test that hiding a column carrying a marked value does not reduce the marked count anywhere the reader can see [REQ: a-hidden-column-may-not-conceal-a-failure]

## 5. Per-column search

- [ ] 5.1 Search can be restricted to one column, using the same index as the global box rather than a second mechanism [REQ: narrowing-to-one-column-states-what-it-withheld]
- [ ] 5.2 The row count keeps saying how many rows are hidden and by which control, with two narrowing controls active [REQ: narrowing-to-one-column-states-what-it-withheld]

## 6. Prove it

- [ ] 6.1 A table of purely scalar rows renders and narrows byte-identically to today — measured against the pre-change behaviour, not asserted
- [ ] 6.2 Mutation-test each rule one at a time: leaf-walk → stringify, all-dates → any-date, report-unapplied → drop. Apply, assert the mutation landed, run, assert the restore landed by re-reading the file
- [ ] 6.3 Drive the rendered page the way a reader reaches it — clicking, typing, pasting an address — never by calling a helper. A harness that calls the filter function directly tests a system where every control already works
- [ ] 6.4 Look at it, with a real project's rows. Structural counts prove it renders; they say nothing about whether the row of controls has become the clutter this change was supposed to remove

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a cell holds a structure whose leaves include the search term THEN the row matches and the matched leaf is visible in the row [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data, scenario: a-leaf-inside-a-structured-cell-is-reachable-by-search]
- [ ] AC-2: WHEN a structured cell's sub-path holds values across rows THEN it is offered as a narrowable column under the same control rules [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data, scenario: a-sub-path-is-narrowed-like-any-other-column]
- [ ] AC-3: WHEN a structured cell is indexed THEN its key names and punctuation are not searchable text [REQ: a-structured-cell-is-searchable-and-filterable-or-it-is-not-offered-as-data, scenario: the-object-itself-is-never-searched-as-text]
- [ ] AC-4: WHEN a numeric column's facet would not narrow usefully THEN it receives a range control [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values, scenario: a-numeric-column-with-too-many-distinct-values-gets-a-range-not-a-facet]
- [ ] AC-5: WHEN a column is date-shaped except for one value THEN it receives no period control [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values, scenario: one-non-date-value-disqualifies-a-date-column]
- [ ] AC-6: WHEN identifiers contain dates in some values only THEN no date is derived and no period control is offered [REQ: a-narrowing-control-is-chosen-by-the-shape-of-a-columns-values, scenario: a-date-embedded-in-an-identifier-is-not-extracted]
- [ ] AC-7: WHEN an address carries a narrowing that no longer matches THEN the surface states what it could not apply and does not present the unfiltered set as unasked-for [REQ: a-narrowed-view-is-addressable-and-what-cannot-be-restored-is-reported, scenario: a-restored-filter-that-no-longer-matches-anything-says-so]
- [ ] AC-8: WHEN a column carrying a marked value is hidden THEN the count stays visible beside the control and names its column [REQ: a-hidden-column-may-not-conceal-a-failure, scenario: hiding-a-column-that-contains-a-marked-value-keeps-the-marking-visible]
- [ ] AC-9: WHEN a per-column search excludes rows THEN the row count says how many and the responsible control is identifiable [REQ: narrowing-to-one-column-states-what-it-withheld, scenario: a-per-column-search-reports-its-own-withholding]
