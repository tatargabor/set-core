# RESUME HERE — written 2026-07-30 at the end of the session that started this change

**Read this before `/opsx:apply`.** It records what is done, what the next step actually is, and
the measurements already taken — so they are not re-derived from a summary. Every claim below
names how it was checked; re-run the check rather than trusting the sentence.

## Where this came from

A reader looked at a project's rows and asked for a `source` column that says *when* and *who*
instead of an opaque identifier. Two halves:

- **Theirs (deferred, NOT asked for yet — the user chose to build our half first).** The producer
  publishes `source` as a structure, e.g. `{ref, kind, date, participants[]}`. The framework cannot
  derive it: measured on a real answer, **three of five** source values embed a date and two do not,
  so a parser would succeed on some rows and fail silently on the rest.
- **Ours, and it is a PRECONDITION rather than a follow-up** — see the next section.

The message asking them for the structure is deliberately unsent and must go as its own thread, not
folded into another. See `docs/integration/bus-handoff.md` §4. **This session no longer owns the
channel** — another agent took it over at `S#150`.

## Done, with the evidence

- **1.1 / 1.4 — `searchText` (committed `1be62b06`).** `StatusTable.tsx` now has two functions
  where it had one: `cellText` (scalar only, for facets and titles) and `searchText` (walks every
  scalar leaf, for the index). Before this, `cellText` returned `''` for any object, so a
  structured cell contributed **nothing** to search — a producer improving their data would have
  watched it vanish, and the box would have said "no rows" rather than "not indexed". Leaves only:
  no key names, no punctuation, because `JSON.stringify` makes a search for a common key match
  every row. The refuted version is held in `tests/unit/statusTableStructured.test.tsx`, which
  asserts **both** halves — that stringify would have matched and that this does not — plus a
  companion test so the exclusion does not create a second blind spot.
  *Mutation-proven:* removing the leaf walk fails 4 of 7 tests.
- **1.2 — mostly already built, and measuring that saved writing a second one.**
  `flattenUniformObjects` (`statusShape.tsx`) already spreads a uniform one-level object into
  `source.kind`-style columns, caps at `FLATTEN_MAX_KEYS = 8`, and refuses ragged shapes. The gap
  was the index, not the columns.

## Next step, and why it is this one

**2.1, the classifier, is the keystone — do it before any control.** Every later task (2.2 range,
2.3 period, and the controls in 4 and 5) asks the same question of a column and must get the same
answer. Two controls disagreeing about one column is the defect to design out, not to fix later.

Signature to aim for, in `statusShape.tsx` so both renderer and table share it:
`classifyColumn(values) -> 'categorical' | 'numeric' | 'date' | 'none'`.

Constraints that are already decided (design D2/D3, spec scenarios):

- **A date-shaped COLUMN is detected; a date inside an identifier is never mined.** One non-date
  value disqualifies the column. Fails toward today's behaviour, which is the safe direction.
- **Numeric ranges reuse the facet's existing bounds** (`FACET_MAX_DISTINCT = 12`,
  `FACET_MAX_SHARE = 0.5`, `StatusTable.tsx`) rather than inventing a second notion of "too many
  values". Today `ageDays` of 49/54/56/85 over 20 rows technically qualifies as categorical and
  produces one-row chips — a control that cannot narrow, which this surface's own rules call worse
  than no control.
- **Nothing is chosen from a column's NAME.** Task 2.5 asserts it with columns whose names suggest
  one shape and whose values are another.

## Traps measured in this session — do not rediscover them

- **`npx tsc --noEmit -p tsconfig.json` is NOT the typecheck.** It reported clean while
  `pnpm build` failed on five import errors: that tsconfig is a project-references root and covers
  none of these files. **Use `pnpm build`.**
- **`web/dist/` is tracked and `set-web` serves it from disk.** After any web change: `pnpm build`
  AND commit `dist/`, or the repository and port 7400 diverge.
- **A running `set-web` holds the Python it started with.** After any `lib/` change:
  `systemctl --user restart set-web` — but check first that no orchestration is live
  (`pgrep -af 'set-sentinel|set-orchestrate'`, and discard the self-match).
- **The Python baseline for regression diffs lived in a scratchpad that is gone.** Recreate with
  `git worktree add -q --detach <dir> <sha>` and the import-root incantation in `CLAUDE.md` — the
  `PYTHONPATH` line and the session-end leak check are both load-bearing.

## How to verify when you get there

`cd web && npx vitest run tests/unit/` (147 passing at handoff). Then the four proof tasks in
section 6, of which **6.3 and 6.4 are the ones that matter**: drive the page by clicking and
typing, never by calling the filter function — a harness that calls the helper tests a system
where every control already works — and then *look at it*, because the risk this change carries is
that the row of controls becomes the clutter it was meant to remove.

---

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
