## 1. Make the type list have one home

**MEASUREMENT CORRECTED DURING IMPLEMENTATION — "three places" was under-counted, and the
under-count is the finding.** The proposal, the design and the spec all say the list lives in
three places. Measured on `HEAD` before any edit, the verbatim six-name pipe-separated enum had
**five** live copies outside tests and specs — four in `templates.py` (the planner's JSON output
schemas) and one in the deployed decompose skill — plus a sixth prose restatement of the
mandatory values, plus `merger.py`'s exemption tuple.

**And the sixth was found by the new test, not by the sweep**, which is the half worth keeping:
`_BRIEF_OUTPUT_SCHEMA` carried a **three**-name enum (`infrastructure`, `schema`,
`foundational`), so a search built from the six-name string matched nothing. A pattern shaped
like the copy you expect is blind to the variant you did not, and it failed in the reassuring
direction — reporting five when there were six. That subset turned out to be *deliberate*
(a cross-cutting change is shared plumbing, never a feature), so it was named and validated
rather than widened; widening it would have changed planning advice while claiming to remove a
copy.

- [x] 1.1 Derive the valid change types from `UNIVERSAL_DEFAULTS` rather than restating them, and expose that as the single definition [REQ: the-set-of-valid-change-types-has-one-home]
- [x] 1.2 Remove `config` and `docs` from `merger.py:2442` — measured, they exist nowhere else, so the guard's exemption names two types nothing can produce. Correct rather than preserve: an exemption that matches nothing today is read as authoritative tomorrow [REQ: the-set-of-valid-change-types-has-one-home]
- [x] 1.3 `.claude/skills/set/decompose/SKILL.md:68` stops carrying a hand-written enum of the same six names. It deploys to consumers via `set-project init`, so a drifted copy travels [REQ: the-set-of-valid-change-types-has-one-home]
- [x] 1.4 A test that fails when any component names a change type absent from the single definition — the wrong pattern held in a test, so a later "tidy-up" cannot silently reintroduce a third copy [REQ: the-set-of-valid-change-types-has-one-home]

## 2. The project's mapping from its lanes to set-core's change types

- [x] 2.1 Read a project-declared mapping of lane signal names to change types, from the tree, with no service contacted — the same constraint the lane signal reader obeys and for the same reason [REQ: the-project-maps-its-lane-vocabulary-onto-set-cores-change-types]
- [x] 2.2 Refuse a near-miss key rather than treating the mapping as absent. Absent means "no exit obligation", which is the refusal path, so a typo would present as a project that declared nothing and the reason would be invisible [REQ: the-project-maps-its-lane-vocabulary-onto-set-cores-change-types]
- [x] 2.3 Assert, in a test, that nothing compares `LaneSignal.lane` to a change type. The coincidence of one consumer's vocabulary matching set-core's is the worst available reason to build the coupling, and it is the implementation a later reader will reach for [REQ: the-project-maps-its-lane-vocabulary-onto-set-cores-change-types]

## 3. The conditional lane

- [x] 3.1 `bugfix` resolves to a cheaper entrance ONLY when the project's mapping names a signal that resolves to ENFORCE for this change [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta] [REQ: an-exit-obligation-counts-only-when-it-blocks]
- [x] 3.2 Refuse with a named error otherwise, and NEVER substitute another change type's profile — the substitution is stricter, so the harm is the false belief, not the gates [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta]
- [x] 3.3 The error distinguishes "no mapping" from "mapped but the signal is still at WARN". Merged, a project that has not yet earned the promotion reads identically to one that declared nothing [REQ: an-exit-obligation-counts-only-when-it-blocks]
- [x] 3.4 A project declaring no `bugfix` lane is untouched — measured against today's behaviour, not asserted [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta]
- [x] 3.5 Define what the cheaper entrance actually is, and state the delta against `feature` in the code where the profile lives, so the next reader can see the difference without diffing two dictionaries [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta]

- [x] 3.6 An ENFORCE signal that cannot FIRE does not satisfy the obligation either — added
  after measuring, because the requirement's own words were satisfied while the discount stayed
  unpaid. `_KIND_HANDLERS` is empty by design in this version, so every declared signal is
  unevaluated, and an unevaluated outcome blocks only under `sole_enforcement`. Its own reason
  class, distinguishable from an unpromoted signal: the two need opposite next actions
  [REQ: an-exit-obligation-counts-only-when-it-blocks]

## 4. Prove the delta is real

- [x] 4.1 A test asserting the `bugfix` profile is NOT equal to any other profile in the dictionary — the direct guard against the failure already in the tree, where `feature` and `foundational` are byte-identical [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta]
- [x] 4.2 Mutation-test each refusal one at a time: apply, assert the mutation landed, run, assert the restore landed by re-reading the file. A test that also passes without the fix proves nothing and looks like proof forever
- [x] 4.3 Full unit suite against a baseline worktree, with the import roots set and the session-end leak check asserting zero — the number is not the check, and neither is a baseline that shares the working tree's code

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change declares `bugfix` in a project with no enforced exit obligation THEN the declaration is refused naming the missing obligation, no other profile is substituted, and no lane is reported [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta, scenario: a-bugfix-declaration-with-no-exit-obligation-is-refused]
- [x] AC-2: WHEN a project declares no `bugfix` lane THEN its changes behave exactly as today and no additional strictness applies [REQ: a-lane-entry-shall-not-be-able-to-exist-without-its-behavioural-delta, scenario: the-refusal-binds-the-declaration-not-the-project]
- [x] AC-3: WHEN a lane signal's own lane label equals a set-core change type THEN that coincidence is not treated as a mapping [REQ: the-project-maps-its-lane-vocabulary-onto-set-cores-change-types, scenario: a-signals-own-lane-label-is-not-compared-to-a-change-type]
- [x] AC-4: WHEN the mapping carries a near-miss key THEN it is refused naming both keys, and the mapping is not treated as absent [REQ: the-project-maps-its-lane-vocabulary-onto-set-cores-change-types, scenario: a-near-miss-key-in-the-mapping-is-refused-not-ignored]
- [x] AC-5: WHEN a mapped signal evaluates at WARN THEN the `bugfix` declaration is refused and the error names the unpromoted signal rather than reporting the mapping absent [REQ: an-exit-obligation-counts-only-when-it-blocks, scenario: a-warn-severity-exit-signal-does-not-buy-the-cheaper-entrance]
- [x] AC-6: WHEN a project introduces an exit signal and immediately declares `bugfix` THEN the declaration is refused until the signal's own promotion condition is satisfied and recorded [REQ: an-exit-obligation-counts-only-when-it-blocks, scenario: the-discount-is-not-available-on-day-one]
- [x] AC-7: WHEN a component names a change type absent from the single definition THEN it is corrected rather than preserved [REQ: the-set-of-valid-change-types-has-one-home, scenario: a-type-list-that-names-a-non-existent-type-is-a-defect]
- [x] AC-8: WHEN a change type is added to the single definition THEN every component validating or enumerating types sees it without a separate edit [REQ: the-set-of-valid-change-types-has-one-home, scenario: adding-a-type-reaches-every-consumer-of-the-list]
