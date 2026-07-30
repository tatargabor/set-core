## 1. Carry the declaration through the envelope

- [ ] 1.1 `StatusResult.caveats` — read from the envelope, defaulted to empty, never decided here. Mirror `deprecated`'s dataclass field and its comment about whose call it is [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 1.2 A validator alongside `_deprecated_fields`: accept a mapping of key → non-empty string, drop nothing silently, and refuse nothing on the grounds of an unrecognised key — the key space is the project's [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 1.3 A malformed `caveats` (not a mapping, or values that are not strings) must not take the answer down. The command succeeded; the caveat is the decoration. Log the SHAPE only — a caveat's text is the project's material [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 1.4 Expose it on the JSON the dashboard reads, beside `deprecated` [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 1.5 A test asserting no caveat key or caveat sentence appears anywhere in `lib/` or `web/src/` — the wrong pattern held in a test, because the natural "improvement" is to special-case one producer's key [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]

## 2. Presence counted from the data

- [ ] 2.1 A `presentCaveats(value, keys)` alongside `presentDeprecations`, walking the answer and returning only the declared keys actually found. Reuse the traversal rather than writing a second one [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]
- [ ] 2.2 `"*"` is never looked for in the data — it qualifies the command, not a field. Assert that separately, or the walker will report it absent for every project that declares one [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]
- [ ] 2.3 A test that a per-field caveat for a field the project stopped sending renders nothing AND announces nothing — the false-absence case this rule exists for [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]

## 3. Additive resolution

- [ ] 3.1 A resolver returning the caveats that apply to one field: the `"*"` sentence plus the field's own, in that order, deduplicated only on exact equality [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]
- [ ] 3.2 No replacement path exists — not a flag, not a sentinel value, not an empty string meaning "suppress". A test asserting that a per-field entry cannot remove the `"*"` sentence, so the semantics cannot be reintroduced later as a convenience [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]
- [ ] 3.3 A test for the mistyped-key case: a per-field key matching nothing leaves the `"*"` intact, so no value is ever left with nothing beside it [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]

## 4. Rendering, where the reader is standing

- [ ] 4.1 The `"*"` sentence renders once in the command section's header [REQ: a-caveat-renders-beside-the-value-it-qualifies]
- [ ] 4.2 A per-field caveat renders adjacent to its value, in the same visual block — not a tooltip, not a disclosure, not another tab [REQ: a-caveat-renders-beside-the-value-it-qualifies]
- [ ] 4.3 Caveat weight is distinct from error and warning weight, and is derived from the field's role, never from words in the key or the sentence [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is]
- [ ] 4.4 A test driving the rendered page the way a user reaches it — not by calling a helper — that an alarming-sounding key is not styled as an error [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is]
- [ ] 4.5 Look at the screen with a real answer carrying a `"*"` and two per-field caveats. Structural counts prove it renders; they say nothing about whether it is readable or whether a long sentence collapses the row it sits in [REQ: a-caveat-renders-beside-the-value-it-qualifies]

## 5. Diagnostics, not a gate

- [ ] 5.1 A listing of declared caveat keys absent from the current answer, available on request [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]
- [ ] 5.2 Assert, in a test, that the listing changes no exit status, no gate result, and produces no badge or count on the main surface — the guard against this quietly becoming the gate D4 refuses [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]
- [ ] 5.3 `"*"` is excluded from the absent-key listing for the same reason as 2.2, or every producer that declares one is reported as having a missing key [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]

## 6. Prove it

- [ ] 6.1 An envelope with no `caveats` produces byte-identical output to today — measured against the pre-change behaviour from a detached baseline worktree with its own import roots, not asserted [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 6.2 Mutation-test each rule one at a time: additive→replacing, data-count→declaration-count, diagnostics→gate. Apply, assert the mutation landed, run, assert the restore landed by re-reading the file, clear `__pycache__` between runs
- [ ] 6.3 Full unit suite plus the web unit tests against the baseline, with the session-end leak check asserting zero and the checker proven able to fire first

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a project's answer carries no `caveats` key THEN the framework renders it exactly as today and reports nothing missing, hidden or suppressed [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them, scenario: an-envelope-without-caveats-behaves-exactly-as-before]
- [ ] AC-2: WHEN the `caveats` object uses the project's own vocabulary THEN the keys are carried verbatim and validated against no known set [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them, scenario: a-caveat-key-the-framework-has-never-seen-is-carried-unchanged]
- [ ] AC-3: WHEN both `"*"` and a matching per-field key are declared THEN the reader is shown both and the per-field sentence does not suppress the `"*"` [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it, scenario: a-value-with-its-own-caveat-still-carries-the-command-level-one]
- [ ] AC-4: WHEN a per-field key matches no field and `"*"` is declared THEN the `"*"` still shows and no value is left with no caveat at all [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it, scenario: a-mistyped-per-field-key-loses-only-the-narrow-half]
- [ ] AC-5: WHEN a per-field key appears nowhere in the answer THEN nothing renders for it and nothing states that a caveat was withheld [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for, scenario: a-caveat-for-a-field-the-project-no-longer-sends-is-silent]
- [ ] AC-6: WHEN a declared key is absent from the answer THEN it appears in the diagnostics listing and no gate, exit status or on-screen alarm changes [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate, scenario: an-absent-declared-key-is-listable-but-does-not-fail-anything]
- [ ] AC-7: WHEN `"*"` is declared and the command renders many values THEN the sentence appears once in the section header and is not repeated beside every value [REQ: a-caveat-renders-beside-the-value-it-qualifies, scenario: the-command-level-caveat-is-stated-once-not-repeated-per-value]
- [ ] AC-8: WHEN a caveat key or sentence contains alarming words THEN it renders at caveat weight and is not styled or counted as an error [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is, scenario: an-alarming-sounding-key-gets-no-alarming-treatment]
