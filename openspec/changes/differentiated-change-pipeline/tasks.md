## 1. Resolve the one structural choice first

- [x] 1.1 Decide where a lane signal declaration lives and record the decision with its reason in `design.md` — closed as D9: in the tree, never behind a running system, because signals are evaluated during worktree verification where no live project exists [REQ: the-declaration-lives-in-the-tree-being-verified-not-behind-a-running-system]
- [ ] 1.2 Implement the tree-only reader and assert it attempts no contract command, HTTP call or database connection [REQ: the-declaration-lives-in-the-tree-being-verified-not-behind-a-running-system]

## 2. Declaration reader (Layer 1, domain-free)

- [ ] 2.1 Add the declaration dataclass and reader in a new `lib/set_orch/` module — six fields, no defaults, refusal with a named error on any missing one [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case]
- [ ] 2.1b Refuse a signal that names no triggering case (date + identifier of the incident it was written for) [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case]
- [ ] 2.2 Refuse a condition expressed as a volume threshold (lines/files changed), with an error naming volume as the reason [REQ: a-signals-condition-shall-be-mechanically-decidable-and-shall-not-measure-quantity]
- [ ] 2.3 Refuse a declaration whose scope includes the document that declares it [REQ: a-signal-shall-not-evaluate-the-corpus-that-defines-it]
- [ ] 2.4 Make one refused signal non-fatal to the others: report the refusal alongside the remaining results [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case]
- [ ] 2.5 Add the `ProjectType` extension point that supplies declarations, with a default returning nothing — and a test asserting `lib/set_orch/` contains no built-in signal, path pattern, or defect-store name [REQ: set-core-holds-no-lane-signal-of-its-own]
- [ ] 2.6 Assert no declaration content is persisted into set-core's tree, cache or logs beyond the run [REQ: the-declaration-is-read-at-evaluation-time-and-never-persisted]

## 3. Evaluator and baseline

- [ ] 3.1 Evaluate a signal against a change's delivered artefacts and return one of three outcomes: fired / did not fire / could not be evaluated [REQ: the-gate-reports-what-it-could-not-decide-and-never-converts-that-into-a-pass]
- [ ] 3.2 Suppress baselined violations from the report [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink]
- [ ] 3.3 Fail the gate when a change would grow a baseline, independently of the signal's severity [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink]
- [ ] 3.4 Report outstanding baselined debt even when nothing new fired [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink]
- [ ] 3.5 Enforce WARN as the starting severity, and refuse a promotion whose declared measurement is not recorded — reporting the refusal rather than downgrading silently [REQ: a-signal-starts-at-warn-and-is-promoted-only-by-its-own-measured-condition]
- [ ] 3.6 Restrict evaluation to the signal's declared scope, and record an out-of-scope signal as not-evaluated rather than as a pass [REQ: every-signal-states-its-scope-and-the-gate-evaluates-only-within-it]

## 4. Gate wiring

- [ ] 4.1 Register the lane gate through the existing `gate-registry` mechanism so it inherits observability and per-change configuration [REQ: the-lane-is-measured-after-the-work-never-classified-before-it]
- [ ] 4.2 Report a contradiction naming the declared type and the contradicting artefact **together** — either alone reads as normal [REQ: the-lane-is-measured-after-the-work-never-classified-before-it]
- [ ] 4.3 Assert the gate emits no overall lane-correct verdict field, and that unevaluated signals are excluded from the did-not-fire count [REQ: the-gate-reports-what-it-could-not-decide-and-never-converts-that-into-a-pass]
- [ ] 4.4 Assert a project with no declarations sees no evaluation and **no all-clear** — absence must stay distinguishable from a clean run [REQ: set-core-holds-no-lane-signal-of-its-own]
- [ ] 4.5 Assert no model call and no new change-definition field is introduced by the gate [REQ: the-lane-is-measured-after-the-work-never-classified-before-it]

## 5. Prove the tests are load-bearing

- [ ] 5.1 For every test added above, stash the implementation and confirm the test fails — record which ones passed either way and fix them, since a test that passes without the fix proves nothing and looks like proof forever [REQ: the-gate-reports-what-it-could-not-decide-and-never-converts-that-into-a-pass]
- [ ] 5.2 Verify the full unit suite against the known-debt baseline (94 failed / 2631 passed / 21 errors on a pristine `HEAD`) and diff the failure set rather than reading the count [REQ: the-lane-is-measured-after-the-work-never-classified-before-it]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a change is verified in a project declaring no lane signals THEN no signal is evaluated and no all-clear, zero-count or passing lane gate is reported [REQ: set-core-holds-no-lane-signal-of-its-own, scenario: a-project-declaring-nothing-gets-todays-behaviour]
- [ ] AC-2: WHEN a project declares no signal but its tree contains recognisable structure THEN no signal is synthesised from it [REQ: set-core-holds-no-lane-signal-of-its-own, scenario: no-signal-is-inferred-from-the-frameworks-own-conventions]
- [ ] AC-3: WHEN a signal declares everything but a scope THEN it is refused with an error naming the missing field and is not evaluated [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case, scenario: a-declaration-missing-its-scope-is-refused]
- [ ] AC-4: WHEN one of three signals is refused THEN the other two are still evaluated and the refusal is reported alongside their result [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case, scenario: a-refused-signal-does-not-silently-disable-the-others]
- [ ] AC-5: WHEN a signal's condition is "more than 300 lines changed" THEN it is refused with an error naming volume [REQ: a-signals-condition-shall-be-mechanically-decidable-and-shall-not-measure-quantity, scenario: a-size-threshold-is-refused]
- [ ] AC-6: WHEN a signal's condition names a new source file matching the project's declared module pattern THEN the declaration is accepted [REQ: a-signals-condition-shall-be-mechanically-decidable-and-shall-not-measure-quantity, scenario: a-shape-condition-is-accepted]
- [ ] AC-7: WHEN a signal's scope includes the document declaring it THEN the declaration is refused with an error naming self-inclusion [REQ: a-signal-shall-not-evaluate-the-corpus-that-defines-it, scenario: a-scope-that-swallows-the-rule-that-defines-the-signal-is-refused]
- [ ] AC-8: WHEN a signal is declared without exclusions THEN it is incomplete and is not evaluated [REQ: a-signal-shall-not-evaluate-the-corpus-that-defines-it, scenario: specification-and-test-corpora-are-excluded-by-default-in-the-declaration]
- [ ] AC-9: WHEN a signal references project-internal identifiers THEN it is evaluated and those identifiers are not persisted under set-core's tree [REQ: the-declaration-is-read-at-evaluation-time-and-never-persisted, scenario: a-signal-naming-project-internal-identifiers-leaves-no-trace-in-the-framework]
- [ ] AC-10: WHEN a change's declared type skips review and a signal reports a new module with no specification touched THEN the contradiction is reported naming both together [REQ: the-lane-is-measured-after-the-work-never-classified-before-it, scenario: a-change-declared-trivial-that-delivers-a-new-capability-is-caught]
- [ ] AC-11: WHEN the gate runs THEN no model is invoked to determine a lane and no new change-definition field is required [REQ: the-lane-is-measured-after-the-work-never-classified-before-it, scenario: no-classification-prompt-is-added-anywhere]
- [ ] AC-12: WHEN a WARN-severity signal fires THEN it is reported and neither the gate nor the merge is blocked [REQ: a-signal-starts-at-warn-and-is-promoted-only-by-its-own-measured-condition, scenario: a-warn-signal-does-not-block]
- [ ] AC-13: WHEN a signal is set to ENFORCE without the recorded measurement THEN the promotion is refused, the signal evaluates at WARN, and the refusal is reported [REQ: a-signal-starts-at-warn-and-is-promoted-only-by-its-own-measured-condition, scenario: promotion-without-evidence-is-refused]
- [ ] AC-14: WHEN a baseline holds one violation and a change introduces a second THEN exactly the new one is reported [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink, scenario: a-pre-existing-violation-is-silent-a-new-one-is-not]
- [ ] AC-15: WHEN a change adds a violation and baselines it in the same change THEN the gate fails naming baseline growth, regardless of severity [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink, scenario: a-change-that-would-grow-the-baseline-fails]
- [ ] AC-16: WHEN nothing new fires and the baseline is non-empty THEN the outstanding count is reported and the change is not reported as violation-free [REQ: a-baseline-records-existing-violations-as-debt-and-may-only-shrink, scenario: the-remaining-debt-is-reported-even-when-nothing-new-fired]
- [ ] AC-17: WHEN a signal scoped to per-change verification is reached during a merge-time integration run THEN it is not evaluated and its absence is not recorded as a pass [REQ: every-signal-states-its-scope-and-the-gate-evaluates-only-within-it, scenario: a-signal-scoped-to-per-change-verification-does-not-run-at-merge-time]
- [ ] AC-18: WHEN a signal cannot be evaluated because its artefact is absent THEN it is reported as unevaluated with a reason and excluded from the did-not-fire set [REQ: the-gate-reports-what-it-could-not-decide-and-never-converts-that-into-a-pass, scenario: an-unevaluable-signal-is-not-a-pass]
- [ ] AC-19: WHEN every signal is evaluated and none fires THEN evaluated and unevaluated counts are reported and no lane-correct verdict field is emitted [REQ: the-gate-reports-what-it-could-not-decide-and-never-converts-that-into-a-pass, scenario: no-overall-lane-correct-verdict-is-emitted]
- [ ] AC-20: WHEN a signal declares everything but names no incident it was written for THEN it is refused with an error naming the missing triggering case [REQ: a-signal-declares-a-lane-a-condition-a-scope-a-baseline-a-promotion-condition-and-a-triggering-case, scenario: a-signal-with-no-triggering-case-is-refused]
- [ ] AC-21: WHEN a change is verified in a worktree with no database and no application server THEN declarations are read from the tree and no contract command, HTTP call or database connection is attempted [REQ: the-declaration-lives-in-the-tree-being-verified-not-behind-a-running-system, scenario: declarations-are-read-with-no-service-running]
- [ ] AC-22: WHEN a signal fires THEN the message includes the incident's date and identifier and the way to suppress that one signal [REQ: the-triggering-case-appears-in-the-gates-own-message-not-only-in-the-specification, scenario: a-firing-signal-states-why-it-exists]
