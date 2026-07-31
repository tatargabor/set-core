## 1. Semantic tokens

- [ ] 1.1 Enumerate every distinct status meaning in use today by reading the six `statusColor()`-style branches and the 493 literal colour sites; produce a meaning→hue table and resolve whether `merge-blocked` orange is its own `blocked` token or folds into `warn` [REQ: status-colour-is-named-by-meaning-through-a-token]
- [ ] 1.2 Add the `@theme` block to `web/src/index.css` defining `--color-status-done|active|fail|warn|blocked|idle` from that table; verify Tailwind emits `text-status-*` utilities by using one in a scratch component and checking the built CSS [REQ: status-colour-is-named-by-meaning-through-a-token]
- [ ] 1.3 Prove the token indirection: change one token's value in `index.css`, rebuild, confirm every indicator of that meaning changed with no component file edited, then revert [REQ: status-colour-is-named-by-meaning-through-a-token]

## 2. The primitive module

- [ ] 2.1 Create `web/src/components/tui/` and move `TuiProgress`, `TuiStatus`, `TuiSection`, `statusColor` into it unchanged; keep `web/src/components/tui.tsx` as a re-export so the six importing files are untouched at this step [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation]
- [ ] 2.2 Convert the three moved primitives to the tokens from task 1.2 — no literal colour class remains in the module [REQ: a-primitive-names-status-by-meaning-never-by-hue]
- [ ] 2.3 Extract `TuiPanel` (the `rounded border border-neutral-8…` frame, 6 current sites) and `TuiBadge`, each with one implementation and the token colours [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation]
- [ ] 2.4 Extract `TuiChip` and `TuiKeyValue`; the chip list caps its visible items and renders the withheld count adjacent to the chips, never in a tooltip [REQ: a-primitive-that-compacts-states-what-it-withheld]
- [ ] 2.5 Extract `TuiTable` (frame, header, sticky behaviour) from the shape currently duplicated between `StatusTable.tsx` and `ChangeTable.tsx` [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation]
- [ ] 2.6 Give every compacting primitive a failure-aware collapsed state: a collapsed group containing a failing item carries the failure marker on its header [REQ: a-primitive-that-compacts-states-what-it-withheld]

## 3. Headless interactive behaviour

- [ ] 3.1 Add `@radix-ui/react-popover`, `@radix-ui/react-dialog`, `@radix-ui/react-tabs` to `web/package.json`; confirm no other Radix package is pulled in and the bundle still builds [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable]
- [ ] 3.2 Build `TuiPopover` on Radix Popover with TUI skin; convert the two hand-rolled sites (`StatusTable.tsx:577`, `manager/SentinelControl.tsx:92`), verifying each in the running app before moving on [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable]
- [ ] 3.3 Build `TuiDialog` on Radix Dialog; convert the three `fixed inset-0` sites (`UnifiedSidebar.tsx`, `issues/IssueDetail.tsx`, `ChangeTable.tsx`) [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable]
- [ ] 3.4 Build `TuiTabs` on Radix Tabs; convert the four hand-rolled tab strips (`SentinelPage`, `issues/IssueDetail`, `DigestView`, `Dashboard`) [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable]
- [ ] 3.5 Check Radix's default `body` portal against the status page's `flex flex-col h-full overflow-hidden` scroll container; if a portal escapes the layout, pin the container explicitly rather than reintroducing absolute positioning [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable]

## 4. Project Status — the proof screen

- [ ] 4.1 Delete the depth-based minimum width at `web/src/components/StatusValue.tsx:344` (`min-w-[18rem]` when `depth > 0`); confirm on a real project's answer that the table no longer exceeds the viewport [REQ: nesting-depth-never-decides-a-row-width]
- [ ] 4.2 Verify the narrow case did not regress — a two-key object in a narrow column is still readable, looked at in the running app, not inferred from a passing test [REQ: nesting-depth-never-decides-a-row-width]
- [ ] 4.3 Move a value that cannot fit its cell into a row-detail expansion instead of growing the row's height; the cell keeps a compact representation [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced]
- [ ] 4.4 Mark the collapsed row when a value was displaced, and carry the failure marker when the displaced value is in a failing state [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced]
- [ ] 4.5 Convert `ProjectStatus.tsx`, `StatusTable.tsx`, `StatusValue.tsx` onto the primitives from groups 2 and 3, removing their local copies [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation]
- [ ] 4.6 Look at the finished screen in the running app against a real project and record what was seen; structural counts do not settle a layout question [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced]

## 5. Migrate the existing violations to zero

- [ ] 5.1 Replace the 81 `text-[9px|10px|11px]` occurrences across 15 files with `text-xs`/`text-sm`/`text-base`; re-measure to confirm the count is 0 [REQ: font-size-normalization]
- [ ] 5.2 Remove the 34 non-Battle `font-mono` usages; re-measure to confirm the count is 0 outside `components/battle/` [REQ: font-mono-class-removal]
- [ ] 5.3 Replace the 493 literal status colour classes across 47 files with tokens, reading each site to distinguish a *status* neutral from a *muted label* neutral — the two are not the same token and the difference is invisible in the class name [REQ: status-colour-is-named-by-meaning-through-a-token]
- [ ] 5.4 Capture Playwright screenshots of the affected screens before and after group 5; examine each pixel difference individually rather than accepting the set in bulk [REQ: status-colour-is-named-by-meaning-through-a-token]

## 6. The drift test — enabled last

- [ ] 6.1 Write `web/tests/unit/design-drift.test.ts` asserting zero `text-[<n>px]`, zero non-exempt `font-mono`, and zero literal status colour classes outside `index.css` and the primitive module; failures name file and line [REQ: design-system-drift-fails-the-build]
- [ ] 6.2 Carry exemptions as an explicit in-test list with a stated reason each (Battle, and the token definitions themselves); do not widen a pattern to accommodate one [REQ: font-mono-class-removal]
- [ ] 6.3 Exclude the test file from its own corpus — it contains every banned pattern as a string literal — and add an assertion that the exclusion is by identity, not by a substring that a future file could also match [REQ: design-system-drift-fails-the-build]
- [ ] 6.4 Prove the test fires: introduce one known violation of each of the three rules, confirm each fails, then restore and re-grep the file to confirm the original content is back before believing the green run [REQ: design-system-drift-fails-the-build]
- [ ] 6.5 Enable the test in the unit suite only once tasks 5.1–5.3 measure zero [REQ: design-system-drift-fails-the-build]

## 7. Verification

- [ ] 7.1 Run the unit suite and diff the failure set against a `git worktree add --detach` baseline of `HEAD` with `PYTHONPATH`/import roots set — an empty diff, not a count, is the pass condition [REQ: design-system-drift-fails-the-build]
- [ ] 7.2 Rebuild `web/` from clean (`rm -rf dist && pnpm build`) and run the Playwright suite against the freshly built bundle with a real project — never a cached one; `web/`'s build product has not been measured for the generated-artefact hybrid problem [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced]
- [ ] 7.3 Mutation-check the layout fix: restore `min-w-[18rem]` into the built bundle, confirm the layout regression test fails, then remove it and re-grep the built asset to confirm the restore actually happened [REQ: nesting-depth-never-decides-a-row-width]
- [ ] 7.4 Drive the new row-detail behaviour with real user actions (`page.mouse`, real clicks) rather than programmatic calls — the harness has powers the reader does not [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced]
- [ ] 7.5 Confirm the six pre-existing importers of `components/tui` render identically to before the move [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a component that imported `TuiProgress` renders after the move THEN it imports from `components/tui/` and renders the same block-character bar [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation, scenario: an-existing-primitive-keeps-its-output]
- [ ] AC-2: WHEN a component file outside the module contains the panel-frame class string or an `absolute z-` dropdown container THEN the drift test fails and names the file and line [REQ: the-primitives-live-in-one-module-and-are-the-only-implementation, scenario: a-hand-rolled-pattern-is-rejected]
- [ ] AC-3: WHEN a reader opens the column-filter popover and presses `Escape` THEN it closes and focus returns to the opening button [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable, scenario: escape-closes-a-popover-and-returns-focus]
- [ ] AC-4: WHEN a dialog is open and the reader presses `Tab` repeatedly THEN focus cycles within the dialog and never reaches an element behind it [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable, scenario: a-dialog-does-not-leak-focus-to-the-page-behind-it]
- [ ] AC-5: WHEN a tab has focus and the reader presses the right arrow key THEN the next tab becomes selected and focused [REQ: a-primitive-that-opens-a-transient-surface-is-keyboard-operable, scenario: arrow-keys-move-between-tabs]
- [ ] AC-6: WHEN a chip list is given 9 values and renders 5 THEN a visible `+4 more` affordance appears beside the rendered chips [REQ: a-primitive-that-compacts-states-what-it-withheld, scenario: a-capped-chip-list-names-its-remainder]
- [ ] AC-7: WHEN a collapsed group contains an item in a failing state THEN the collapsed header carries a failure marker [REQ: a-primitive-that-compacts-states-what-it-withheld, scenario: a-collapsed-group-carrying-a-failure-marks-itself]
- [ ] AC-8: WHEN the status indicator renders a `merged` status THEN it applies the done-status token and its source contains no literal `blue-400` [REQ: a-primitive-names-status-by-meaning-never-by-hue, scenario: a-status-indicator-uses-a-token]
- [ ] AC-9: WHEN a component renders a merged or completed status THEN it applies the done-status token and its file contains no literal `blue-400` [REQ: status-colour-is-named-by-meaning-through-a-token, scenario: a-component-expresses-a-done-status]
- [ ] AC-10: WHEN the value of `--color-status-fail` changes in `index.css` THEN every failing indicator changes with it and no component file is edited [REQ: status-colour-is-named-by-meaning-through-a-token, scenario: meaning-survives-a-palette-change]
- [ ] AC-11: WHEN a component adds `text-[11px]` and the unit suite runs THEN the drift test fails and names that file and line [REQ: design-system-drift-fails-the-build, scenario: a-reintroduced-arbitrary-font-size-fails]
- [ ] AC-12: WHEN a known violation is introduced THEN the drift test fails, and when removed it passes — so green distinguishes clean from cannot-detect [REQ: design-system-drift-fails-the-build, scenario: the-test-is-proven-to-fire-before-its-pass-is-believed]
- [ ] AC-13: WHEN inspecting any rendered text element THEN the font size is 12px, 14px or 16px [REQ: font-size-normalization, scenario: no-arbitrary-font-sizes]
- [ ] AC-14: WHEN the unit suite runs against the source tree THEN a `text-[<n>px]` occurrence in any component file fails the run [REQ: font-size-normalization, scenario: the-rule-is-measured-not-assumed]
- [ ] AC-15: WHEN searching component sources for `font-mono` THEN zero matches are found outside Battle [REQ: font-mono-class-removal, scenario: no-font-mono-in-components]
- [ ] AC-16: WHEN reading the drift test THEN the Battle exemption appears as a named entry with its reason [REQ: font-mono-class-removal, scenario: the-exemption-is-explicit]
- [ ] AC-17: WHEN a row contains a cell whose value is a multi-key object THEN the table's width is unchanged and the page does not scroll horizontally [REQ: nesting-depth-never-decides-a-row-width, scenario: a-nested-object-inside-a-cell-does-not-widen-the-table]
- [ ] AC-18: WHEN the same object renders at top level and inside a table cell THEN each fits the width available and neither imposes a minimum [REQ: nesting-depth-never-decides-a-row-width, scenario: the-same-value-renders-at-two-depths]
- [ ] AC-19: WHEN a cell's value is a paragraph of prose THEN the row's height stays comparable to its neighbours and the full text is reachable from that row [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced, scenario: a-prose-value-does-not-build-a-tower]
- [ ] AC-20: WHEN a row holds a displaced value THEN the collapsed row carries a marker saying so without being expanded [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced, scenario: the-displacement-is-visible-before-expanding]
- [ ] AC-21: WHEN the displaced value is in a failing state THEN the collapsed row carries the failure marker, not merely a "more" affordance [REQ: a-value-too-large-for-its-cell-moves-and-the-move-is-announced, scenario: a-displaced-value-carrying-a-failure-is-marked]
