# RESUME HERE — 26/30 done, written 2026-07-30

**The mechanism is built, shipped and verified against a live producer. What is left is PROOF, not
features** — which is exactly the part this repo refuses to skip, so none of it is ticked.

## What works today, measured through the whole chain

The producer publishes `caveats` on every command (default `{}`), and their tenth command carries
`"*"` plus four per-field keys. Through the framework's own API: **10 commands, 0 gaps**, all four
per-field keys present in the data, so four caveats render beside their numbers and the
absent-key diagnostics list is correctly **empty**.

In a real browser, driven by clicking the way a reader reaches it: **5 notes — 1 in the section
header (the `"*"`, 155 characters) and 4 inside `<dd>` elements**, heights 15–30 px (the
150-character one wraps to two lines), no horizontal overflow, no page errors. Then looked at:
numbers stay dominant, caveats read as secondary, nothing styled as an alarm.

Commits: `dbc08388` (envelope), `67dbedae` (the missing `project-status-contract` delta),
`66b7caae` (rendering), `649c1baf` (dist).

## The four open tasks, and what each actually needs

- **4.4 — a COMMITTED end-to-end test.** The browser check above was *run* and is not *committed*,
  so nothing re-runs it. Needs a Playwright spec that clicks into the project, opens the status
  surface, selects the command, and asserts an alarming-sounding key is not styled as an error.
  Drive it by clicking; a harness that calls the component tests a different system.
- **6.1 — the no-caveats baseline.** An envelope without `caveats` must produce byte-identical
  output to before. Measure from a detached worktree at `82d735a2` with its own import roots, not
  by assertion.
- **6.2 — mutation-test the three rules**: additive→replacing, data-count→declaration-count,
  diagnostics→gate. Assert the mutation landed, run, assert the restore landed by **re-reading the
  file**, and clear `__pycache__` between runs. Use a helper that refuses an ambiguous pattern
  rather than replacing the first match — that guard already caught one ambiguous pattern here.
- **6.3 — full suites against the baseline**, with the session-end leak check asserting zero and
  **the checker proven able to fire first** (it reported 6 leaks on a deliberate working-tree
  import, which is what makes its zero mean something).

Last full run at handoff: Python **81 failed / 3194 passed / 21 errors**, failure-set diff against
the isolated baseline **empty**; web **147 passed**; `openspec validate --strict` clean.

## One task deliberately not built as written

**3.1** asked for a resolver merging the `"*"` sentence with the per-field one. Not built, and the
task was wrong rather than the code: merging would repeat the command-level sentence beside every
value, which requirement AC-7 of this same change forbids. Additivity is delivered by **placement**
— header plus field. Do not "fix" this later without re-reading AC-7.

---

## 1. Carry the declaration through the envelope

- [x] 1.1 `StatusResult.caveats` — read from the envelope, defaulted to empty, never decided here. Mirror `deprecated`'s dataclass field and its comment about whose call it is [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [x] 1.2 A validator alongside `_deprecated_fields`: accept a mapping of key → non-empty string, drop nothing silently, and refuse nothing on the grounds of an unrecognised key — the key space is the project's [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [x] 1.3 A malformed `caveats` (not a mapping, or values that are not strings) must not take the answer down. The command succeeded; the caveat is the decoration. Log the SHAPE only — a caveat's text is the project's material [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [x] 1.4 Expose it on the JSON the dashboard reads, beside `deprecated` [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [x] 1.5 A test asserting the framework holds no caveat vocabulary. **Reshaped during implementation, and the reason is the confidentiality boundary:** the obvious form greps the source for a real producer's keys, which would require writing that producer's register vocabulary into this repository in order to prove the framework does not hold it — the test file becomes the carrier of exactly what the rule forbids. Asserted structurally instead: arbitrary keys (accented, non-Latin, spaced, mixed-case) survive unchanged, and exactly one caveat-key constant exists [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]

## 2. Presence counted from the data

- [x] 2.1 A `presentCaveats(value, keys)` alongside `presentDeprecations`, walking the answer and returning only the declared keys actually found. Reuse the traversal rather than writing a second one [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]
- [x] 2.2 `"*"` is never looked for in the data — it qualifies the command, not a field. Assert that separately, or the walker will report it absent for every project that declares one [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]
- [x] 2.3 A test that a per-field caveat for a field the project stopped sending renders nothing AND announces nothing — the false-absence case this rule exists for [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for]

## 3. Additive resolution

- [x] 3.1 **Not built as a merged list, and the task was wrong rather than the code.** It asked for a resolver returning the `"*"` sentence plus the field's own together — which contradicts requirement AC-7 in the same change: the `"*"` is stated ONCE in the section header and must not be repeated beside every value. Additivity is delivered by PLACEMENT (header + field), which is what the reader experiences; a merged per-field list would have satisfied this task and broken the requirement [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]
- [x] 3.2 No replacement path exists — not a flag, not a sentinel value, not an empty string meaning "suppress". A test asserting that a per-field entry cannot remove the `"*"` sentence, so the semantics cannot be reintroduced later as a convenience [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]
- [x] 3.3 A test for the mistyped-key case: a per-field key matching nothing leaves the `"*"` intact, so no value is ever left with nothing beside it [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it]

## 4. Rendering, where the reader is standing

- [x] 4.1 The `"*"` sentence renders once in the command section's header [REQ: a-caveat-renders-beside-the-value-it-qualifies]
- [x] 4.2 A per-field caveat renders adjacent to its value, in the same visual block — not a tooltip, not a disclosure, not another tab [REQ: a-caveat-renders-beside-the-value-it-qualifies]
- [x] 4.3 Caveat weight is distinct from error and warning weight, and is derived from the field's role, never from words in the key or the sentence [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is]
- [ ] 4.4 **STILL OPEN** — a COMMITTED test driving the rendered page the way a user reaches it — not by calling a helper — that an alarming-sounding key is not styled as an error [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is]
- [x] 4.5 Look at the screen with a real answer carrying a `"*"` and two per-field caveats. Structural counts prove it renders; they say nothing about whether it is readable or whether a long sentence collapses the row it sits in [REQ: a-caveat-renders-beside-the-value-it-qualifies]

## 5. Diagnostics, not a gate

- [x] 5.1 A listing of declared caveat keys absent from the current answer, available on request [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]
- [x] 5.2 Assert, in a test, that the listing changes no exit status, no gate result, and produces no badge or count on the main surface — the guard against this quietly becoming the gate D4 refuses [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]
- [x] 5.3 `"*"` is excluded from the absent-key listing for the same reason as 2.2, or every producer that declares one is reported as having a missing key [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate]

## 6. Prove it

- [ ] 6.1 An envelope with no `caveats` produces byte-identical output to today — measured against the pre-change behaviour from a detached baseline worktree with its own import roots, not asserted [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them]
- [ ] 6.2 Mutation-test each rule one at a time: additive→replacing, data-count→declaration-count, diagnostics→gate. Apply, assert the mutation landed, run, assert the restore landed by re-reading the file, clear `__pycache__` between runs
- [ ] 6.3 Full unit suite plus the web unit tests against the baseline, with the session-end leak check asserting zero and the checker proven able to fire first

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a project's answer carries no `caveats` key THEN the framework renders it exactly as today and reports nothing missing, hidden or suppressed [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them, scenario: an-envelope-without-caveats-behaves-exactly-as-before]
- [x] AC-2: WHEN the `caveats` object uses the project's own vocabulary THEN the keys are carried verbatim and validated against no known set [REQ: a-project-declares-caveats-and-the-framework-interprets-none-of-them, scenario: a-caveat-key-the-framework-has-never-seen-is-carried-unchanged]
- [x] AC-3: WHEN both `"*"` and a matching per-field key are declared THEN the reader is shown both and the per-field sentence does not suppress the `"*"` [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it, scenario: a-value-with-its-own-caveat-still-carries-the-command-level-one]
- [x] AC-4: WHEN a per-field key matches no field and `"*"` is declared THEN the `"*"` still shows and no value is left with no caveat at all [REQ: the-command-level-default-always-applies-and-per-field-caveats-add-to-it, scenario: a-mistyped-per-field-key-loses-only-the-narrow-half]
- [x] AC-5: WHEN a per-field key appears nowhere in the answer THEN nothing renders for it and nothing states that a caveat was withheld [REQ: the-count-comes-from-the-data-and-the-declaration-only-says-what-to-look-for, scenario: a-caveat-for-a-field-the-project-no-longer-sends-is-silent]
- [x] AC-6: WHEN a declared key is absent from the answer THEN it appears in the diagnostics listing and no gate, exit status or on-screen alarm changes [REQ: a-declared-key-absent-from-the-answer-is-diagnostics-never-a-gate, scenario: an-absent-declared-key-is-listable-but-does-not-fail-anything]
- [x] AC-7: WHEN `"*"` is declared and the command renders many values THEN the sentence appears once in the section header and is not repeated beside every value [REQ: a-caveat-renders-beside-the-value-it-qualifies, scenario: the-command-level-caveat-is-stated-once-not-repeated-per-value]
- [x] AC-8: WHEN a caveat key or sentence contains alarming words THEN it renders at caveat weight and is not styled or counted as an error [REQ: a-caveat-is-not-an-alarm-and-the-framework-never-infers-that-it-is, scenario: an-alarming-sounding-key-gets-no-alarming-treatment]
