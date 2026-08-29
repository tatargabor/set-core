## 1. Layer 1 — the declaration survives the parser

- [ ] 1.1 Add the `stageOrder` array form to the `display` parser in `lib/set_orch/project_status.py`, beside the existing string-argument paired forms, without loosening the string test that guards `progressOf` / `limitOf` [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]
- [ ] 1.2 Validate the argument: a non-array, an empty array, or an array holding a non-string or an empty string leaves the field entirely unroled — never a partial order [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]
- [ ] 1.3 Unit test: a well-formed declaration produces a stage role carrying the exact declared array, order preserved [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]
- [ ] 1.4 Unit test: each malformed shape from 1.2 yields NO role, and the answer still renders in full [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]
- [ ] 1.5 Unit test: an unrecognised role beside a valid `stageOrder` is still ignored silently, and does not suppress the valid one [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]

## 2. Layer 1 — the order is static

- [ ] 2.1 Resolve the declared order from the declaration alone, before any value is examined; never append, reorder or filter it from the data [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 2.2 Unit test: a stage named in the order but matched by no value stays in the order, in position, reported as holding nothing [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 2.3 Unit test: the same declaration resolved against two answers with disjoint value sets yields identical orders in identical positions [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 2.4 Unit test: a value absent from the order does not extend the order and displaces no declared stage [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 2.5 Unit test — the boundary against the shipped presence rule: a declared order for a field NO row carries produces no role, no placeholder and no statement of absence [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]

## 3. Renderer — the declaration reaches the surface

- [ ] 3.1 Teach the role resolver in `web/src/components/statusShape.tsx` the array-argument form, so it stops returning `null` for a declared stage order [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]
- [ ] 3.2 Unit test: the resolver returns a stage role with the declared order intact, and still returns `null` for every malformed shape [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]

## 4. Renderer — grouping, the first declaration `StatusTable` reads

- [ ] 4.1 Read the role declaration inside `StatusTable` via the existing `useRoles()` hook rather than threading a new prop [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 4.2 Group rows into the declared stages in the row-ordering pipeline (`StatusTable.tsx:739-768`), applying grouping ONLY when a stage role is declared for a field [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 4.3 Render a declared stage that holds no rows: its header appears in position with a count of zero [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 4.4 Render values outside the declared order in a distinct trailing group carrying a structural marker in the DOM — a labelled region, not a colour or an icon, so the mark survives restyling [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 4.5 Mark that group as *outside the declared process*, never as an error; reserve error styling for broken things [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]

## 5. Renderer — the counts must not lie

- [ ] 5.1 Derive every group count and every emptiness verdict from the FULL row set, before `ROW_CAP` is applied [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 5.2 Unit test: a stage holding more rows than `ROW_CAP` reports its TRUE count, not the rendered slice's [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 5.3 Unit test — the trap this exists for: a stage whose every row falls past the cap must NOT report as empty [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]

## 6. Renderer — nothing changes for anyone who declares nothing

- [ ] 6.1 Unit test: with no stage order declared, row ordering is byte-identical to today's and no grouping is applied [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 6.2 Run the existing `StatusTable` / `StatusValue` suites and confirm a zero-diff failure set against a HEAD baseline, per the `regression-baseline` skill [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]

## 7. Proving the fix is a fix

- [ ] 7.1 Stash-and-rerun every new test from groups 1–5 against unfixed code and confirm each one FAILS; a test that passes both ways proves nothing and must be rewritten [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 7.2 Record which assertion fails without the fix for the two silent-drop paths specifically — the Python fall-through and the resolver's `null` — since "nothing threw" would pass on unfixed code [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert]

## 8. Looking at it — required, not optional

- [ ] 8.1 Open the running dashboard in the browser against a fixture declaring a stage order, and LOOK at the table: bands in declared order, an empty band visible with its zero, an undeclared value present and marked [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 8.2 Look at a fixture with more rows than `ROW_CAP` across several bands and confirm the counts read honestly beside the stated remainder [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 8.3 If the browser cannot be reached, leave 8.1 and 8.2 OPEN and say so in the commit and to the user — never substitute a structural count or a green suite for having looked [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]

## 9. Closing the loop

- [ ] 9.1 Close B-124 in `openspec/bugs/README.md` with the commit sha and the evidence, leaving the entry in place [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]
- [ ] 9.2 Record in `docs/integration/consumer-integration.md` that the framework's half is shipped, naming what was verified and how [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer]
- [ ] 9.3 Tell the producer on the channel that it is real, where "real" means a test that fails without the code — not that the tasks are ticked [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked]

## Acceptance Criteria (from spec scenarios)

### the-role-vocabulary-is-closed-and-an-unknown-role-is-inert

- [ ] AC-1: WHEN an answer declares `display: {"size": "bytes"}` and `bytes` is not a recognised role THEN `size` renders as it would with no declaration at all, and nothing on screen reports a problem [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert, scenario: a-producer-ships-a-role-the-framework-does-not-know-yet]
- [ ] AC-2: WHEN an answer's `display` is a list, a string, or null THEN the answer renders in full with no roles applied [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert, scenario: a-malformed-declaration-does-not-cost-the-answer]
- [ ] AC-3: WHEN an answer declares `display: {"lane": {"stageOrder": ["planned", "done"]}}` THEN the `lane` field carries a stage role whose declared order is exactly `["planned", "done"]` [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert, scenario: a-stage-order-is-carried-through-as-a-role]
- [ ] AC-4: WHEN a `stageOrder` argument is a string, is an empty array, or contains a non-string or an empty string THEN the field carries no stage role at all, and the answer renders in full [REQ: the-role-vocabulary-is-closed-and-an-unknown-role-is-inert, scenario: a-malformed-stage-order-leaves-the-field-unroled-rather-than-half-ordered]

### a-declared-stage-order-is-static-and-is-never-computed-from-the-answer

- [ ] AC-5: WHEN an order declares `["planned", "specified", "done"]` and no value in the answer is `specified` THEN `specified` is still part of the resolved order, in position, marked as holding nothing [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer, scenario: an-empty-declared-stage-survives]
- [ ] AC-6: WHEN the same declaration is resolved against one answer holding only `planned` values and another holding only `done` values THEN both resolve to the identical declared order, in the identical positions [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer, scenario: two-answers-over-different-value-sets-yield-the-same-order]
- [ ] AC-7: WHEN `display` declares a stage order for `lane` and no row in the answer carries `lane` THEN nothing is roled and the surface says nothing about the declared stages [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer, scenario: a-field-the-answer-does-not-carry-stays-unroled-despite-its-declaration]
- [ ] AC-8: WHEN the answer holds a value that appears nowhere in the declared order THEN the declared order is unchanged — the value is not appended to it and does not displace any declared stage [REQ: a-declared-stage-order-is-static-and-is-never-computed-from-the-answer, scenario: a-value-outside-the-order-never-extends-it]

### a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked

- [ ] AC-9: WHEN the order declares a stage that no row matches THEN that stage appears in its declared position, shown as holding no rows [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked, scenario: a-declared-stage-holding-nothing-is-drawn]
- [ ] AC-10: WHEN a row carries a stage value that appears nowhere in the declared order THEN the row is present on screen and is marked as outside the declared order [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked, scenario: a-value-outside-the-order-is-visible-and-marked]
- [ ] AC-11: WHEN rows carry a mix of declared values and one undeclared value THEN the undeclared value is not rendered as an unmarked final stage, and cannot be mistaken for the end of the process [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked, scenario: an-unmatched-value-is-never-quietly-last]
- [ ] AC-12: WHEN no stage order is declared for a field THEN that field's values are ordered exactly as they are today, with no stage presentation applied [REQ: a-declared-stage-order-governs-presentation-and-a-value-outside-it-stays-visible-and-marked, scenario: an-absent-declaration-changes-nothing]
