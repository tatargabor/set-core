<!--
Order matters here in one specific way: the meta-gate and the shared matching library come BEFORE
the first real gate. A gate written before its self-test exists is a gate whose first version was
never proven to fail, and this change's whole argument is that such a gate is indistinguishable
from an absent one.

Every gate task ships with (a) its self-test, (b) its baseline seeded from a measurement taken in
that task, and (c) the measured number written into the gate's own header — so a later reader can
tell whether the debt moved.
-->

## 1. The layer itself

- [ ] 1.1 Create `scripts/gates/` and the runner that discovers and executes gates, failing closed and printing file, rule and remedy for each failure. [REQ: gates-run-before-a-push-and-fail-closed]
- [ ] 1.2 Wire the runner into pre-push only; leave commits ungated, and state in the config why. [REQ: gates-run-before-a-push-and-fail-closed]
- [ ] 1.3 Shared matching library: strip fenced blocks before treating text as data, match whole lines where a marker is a line, and recognise a status in table-row, heading and list-item form. [REQ: gates-match-content-through-a-shared-library-not-by-ad-hoc-pattern]
- [ ] 1.4 Baseline mechanics: load, compare against the committed previous version, block on growth, allow growth only through an explicit visible mechanism. Match a baselined identifier in both bare and lifecycle-prefixed form. [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink]
- [ ] 1.5 Skip path: an explicit mechanism that leaves the reason where a reviewer sees it. [REQ: skipping-is-possible-deliberate-and-recorded]
- [ ] 1.6 Warn-mode support, so a prose-inferred signal can print without blocking, and record what promotion to blocking would require. [REQ: a-prose-signal-warns-and-does-not-block-until-it-is-measured-to-be-right]

## 2. The gate on the gates — before any real gate

- [ ] 2.1 `tests/gates/` harness that runs a gate against a fixture tree created outside this working tree and removed afterwards. [REQ: self-test-fixtures-live-outside-the-repository-being-checked]
- [ ] 2.2 Two-directional assertion helper: the gate must fail on the violating fixture and pass on the clean one; a single-direction test is rejected. [REQ: every-gate-carries-a-two-directional-self-test]
- [ ] 2.3 The meta-gate: fail when a gate exists with no self-test, and give the meta-gate its own two-directional self-test. [REQ: a-gate-without-a-self-test-is-itself-a-gate-failure]

## 3. The adversarial review — rule, agents, artifact

- [ ] 3.1 `.claude/rules/adversarial-spec-review.md`: when the review is mandatory, when it is not, and the artifact it must leave. [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins]
- [ ] 3.2 Agent for the code branch: reads the source not the plan, works a named attack list, requires `file:line` + failure scenario + severity per finding. [REQ: the-code-branch-reads-the-source-and-every-claim-carries-evidence]
- [ ] 3.3 Agent for the rules branch: checks the change item by item against this project's mandatory rules, producing a gap list with the rule section that requires each item. [REQ: the-review-runs-as-two-independent-branches]
- [ ] 3.4 Both agents: state an empty result plainly rather than manufacturing a finding, and close with an itemised statement of what was checked and found correct. [REQ: an-empty-result-is-stated-never-manufactured]
- [ ] 3.5 Findings artifact format: severity and status per finding, and a separate section for branches that are the user's decision rather than the reviewer's. [REQ: findings-carry-a-severity-and-a-status-and-a-critical-finding-blocks]
- [ ] 3.6 Wire the review into the change workflow at the point before implementation starts, so it is a step rather than a document someone remembers to write. [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins]

## 4. First gate — the review artifact

- [ ] 4.1 Gate: a change with a started task must hold a substantive review artifact; an empty or stub file counts as absent. [REQ: a-change-with-started-work-carries-its-review-artifact]
- [ ] 4.2 Extend it to changes archived within the pushed range, so implement-then-archive is not a way around the review. [REQ: a-change-with-started-work-carries-its-review-artifact]
- [ ] 4.3 Block on an unresolved critical finding, matching all three status shapes through the shared library, with a warn-only prose signal for a file that claims it is blocked. [REQ: findings-carry-a-severity-and-a-status-and-a-critical-finding-blocks]
- [ ] 4.4 Seed the baseline from the measured 24 changes that have started work with no review artifact — re-measure at implementation time rather than trusting this number. [REQ: each-first-gate-is-scoped-to-be-passable-when-it-lands]
- [ ] 4.5 Two-directional self-test for this gate, including a fixture whose critical status appears as a heading rather than a table row — the exact shape that made the adopted implementation fail open. [REQ: every-gate-carries-a-two-directional-self-test]

## 5. First gates — rules this repository already states

- [ ] 5.1 Gate: an exception handler whose whole body discards the error without logging. Detect by AST, not by pattern — the measurement that found 404 of them found 0 bare `except:`, so a text pattern aimed at the obvious form would have reported almost nothing. [REQ: an-error-is-not-swallowed-silently]
- [ ] 5.2 Seed its baseline from a fresh AST measurement, and record the count in the gate header with its date. [REQ: each-first-gate-is-scoped-to-be-passable-when-it-lands]
- [ ] 5.3 Gate: run strict validation on changes touched by the push only, and pass through the validator's own output. [REQ: a-touched-change-validates]
- [ ] 5.4 Gate: rule documents may not cite a repository path that does not exist; paths inside fenced examples are not citations. [REQ: a-rule-does-not-cite-a-file-that-does-not-exist]
- [ ] 5.5 Fix, or baseline with a stated reason, the 14 dead citations the measurement found — a truthfulness gate landing on top of a corpus that fails it is the credibility problem this change is about. [REQ: a-rule-does-not-cite-a-file-that-does-not-exist]
- [ ] 5.6 Two-directional self-tests for 5.1, 5.3 and 5.4. [REQ: every-gate-carries-a-two-directional-self-test]

## 6. Proof — the parts that fail reassuringly

- [ ] 6.1 Mutation-test every gate: break the gate's own matching and confirm its self-test fails. Clear `__pycache__` and disable bytecode writing between runs, and assert each mutation pattern occurs exactly once rather than replacing the first match. [REQ: every-gate-carries-a-two-directional-self-test]
- [ ] 6.2 Assert the restore after each mutation by re-reading the file, not by a revert command chosen for the tracked case — a new gate script may be untracked, where `git checkout` silently restores nothing. [REQ: every-gate-carries-a-two-directional-self-test]
- [ ] 6.3 Prove the baseline-growth check fires: add a line to a baseline in a fixture tree and assert the block; remove one and assert it passes. [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink]
- [ ] 6.4 Prove the fence stripping and whole-line matching on the shapes that actually broke: a violating example inside a fenced block, and a negated sentence containing the marker. [REQ: gates-match-content-through-a-shared-library-not-by-ad-hoc-pattern]
- [ ] 6.5 Measure the whole chain's latency on a real push and record it. If it is not acceptable, scope by what the push touches rather than dropping a gate. [REQ: gates-run-before-a-push-and-fail-closed]
- [ ] 6.6 Regression check against a real baseline worktree with `PYTHONPATH` at its own source roots and the session-end leak assertion; compare failure sets, not counts. [REQ: a-touched-change-validates]

## 7. Run the new mechanism on itself

- [ ] 7.1 Run the two-branch adversarial review on **this** change before its own implementation is finished, and carry the findings. A review mechanism whose first change skipped it would be arguing against itself. [REQ: the-review-runs-as-two-independent-branches]
- [ ] 7.2 Record in the design what the review on this change cost and what it found, so the cost claim quoted from another project is replaced by one measured here. [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins]

## Acceptance Criteria (from spec scenarios)

### adversarial-spec-review

**A change with code impact is reviewed adversarially before implementation begins**

- [ ] AC-1: WHEN a change's planning artifacts are complete and its implementation would touch code THEN the adversarial review runs and its findings artifact exists before any task is started [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins, scenario: a-code-affecting-change-is-reviewed-before-apply]
- [ ] AC-2: WHEN a change has no code impact THEN no review is required, and the exemption is a stated property of the change rather than an omission [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins, scenario: a-documentation-only-change-is-exempt]
- [ ] AC-3: WHEN a change validates cleanly against its schema THEN the review is still required, because validation measures structure and not fit [REQ: a-change-with-code-impact-is-reviewed-adversarially-before-implementation-begins, scenario: validation-passing-is-not-a-substitute]

**The review runs as two independent branches**

- [ ] AC-4: WHEN the review runs THEN both branches contribute to the findings artifact, each identifiable [REQ: the-review-runs-as-two-independent-branches, scenario: both-branches-produce-findings]
- [ ] AC-5: WHEN one branch reports no findings THEN the other branch still runs and still records what it checked [REQ: the-review-runs-as-two-independent-branches, scenario: one-branch-finding-nothing-does-not-excuse-the-other]

**The code branch reads the source, and every claim carries evidence**

- [ ] AC-6: WHEN the code branch reports a defect THEN it names the source location, the input that triggers it, and the wrong result [REQ: the-code-branch-reads-the-source-and-every-claim-carries-evidence, scenario: a-finding-carries-its-evidence]
- [ ] AC-7: WHEN an observation can be made without reading the source THEN it does not belong to this branch's findings [REQ: the-code-branch-reads-the-source-and-every-claim-carries-evidence, scenario: a-plan-only-observation-is-not-a-code-finding]

**An empty result is stated, never manufactured**

- [ ] AC-8: WHEN a branch finds no genuine defect THEN it says so, and does not report a finding to fill the space [REQ: an-empty-result-is-stated-never-manufactured, scenario: nothing-found-is-said-plainly]
- [ ] AC-9: WHEN a branch completes THEN it lists what it examined and found correct, itemised rather than summarised [REQ: an-empty-result-is-stated-never-manufactured, scenario: coverage-is-stated]

**Findings carry a severity and a status, and a critical finding blocks**

- [ ] AC-10: WHEN a critical finding's status is still open THEN implementation of that change is blocked [REQ: findings-carry-a-severity-and-a-status-and-a-critical-finding-blocks, scenario: an-unresolved-critical-finding-blocks]
- [ ] AC-11: WHEN a critical finding is rejected with a stated reason THEN it no longer blocks, and the reason remains in the artifact [REQ: findings-carry-a-severity-and-a-status-and-a-critical-finding-blocks, scenario: a-rejected-finding-unblocks-with-its-reason]
- [ ] AC-12: WHEN a finding presents a choice between two legitimate designs THEN it is recorded as an open decision for the user, not resolved in the findings [REQ: findings-carry-a-severity-and-a-status-and-a-critical-finding-blocks, scenario: a-branch-for-the-user-is-not-decided-by-the-reviewer]

### repo-gate-layer

**Gates run before a push and fail closed**

- [ ] AC-13: WHEN a gate detects a violation THEN the push does not proceed, and the output names the file, the rule and the remedy [REQ: gates-run-before-a-push-and-fail-closed, scenario: a-violation-stops-the-push]
- [ ] AC-14: WHEN no gate detects a violation THEN the push proceeds and the layer reports only that it passed [REQ: gates-run-before-a-push-and-fail-closed, scenario: a-clean-push-is-not-slowed-by-ceremony]
- [ ] AC-15: WHEN work is committed locally THEN no gate runs [REQ: gates-run-before-a-push-and-fail-closed, scenario: committing-is-unaffected]

**A gate that meets existing debt carries a baseline, and the baseline may only shrink**

- [ ] AC-16: WHEN a gate is introduced and its baseline lists the current violations THEN pushes continue to pass while those violations remain [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink, scenario: existing-debt-does-not-block]
- [ ] AC-17: WHEN a violation appears that is not in the baseline THEN the gate blocks [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink, scenario: a-new-violation-is-blocked]
- [ ] AC-18: WHEN a baseline gains an entry relative to its committed previous version THEN the layer blocks and names the added entries [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink, scenario: growing-the-baseline-is-refused-by-default]
- [ ] AC-19: WHEN growth is requested through the explicit mechanism THEN it is allowed, and the request is visible in the change that made it [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink, scenario: growth-is-possible-but-explicit]
- [ ] AC-20: WHEN a baselined item's identifier acquires a prefix or suffix through a normal lifecycle step THEN the baseline still matches it, rather than turning a known-debt entry into a new failure [REQ: a-gate-that-meets-existing-debt-carries-a-baseline-and-the-baseline-may-only-shrink, scenario: an-identifier-that-changes-form-is-still-matched]

**Skipping is possible, deliberate and recorded**

- [ ] AC-21: WHEN a gate must be bypassed for a legitimate reason THEN an explicit mechanism allows it [REQ: skipping-is-possible-deliberate-and-recorded, scenario: a-skip-is-available]
- [ ] AC-22: WHEN a gate is skipped THEN the fact and its reason are recorded where a reviewer will see them [REQ: skipping-is-possible-deliberate-and-recorded, scenario: a-skip-leaves-a-trace]

**Gates match content through a shared library, not by ad-hoc pattern**

- [ ] AC-23: WHEN a document contains a fenced block showing a violating example THEN the gate does not treat it as a violation [REQ: gates-match-content-through-a-shared-library-not-by-ad-hoc-pattern, scenario: an-example-is-not-data]
- [ ] AC-24: WHEN a marker appears inside a sentence that quotes or negates it THEN it is not matched as a verdict [REQ: gates-match-content-through-a-shared-library-not-by-ad-hoc-pattern, scenario: a-quoted-marker-is-not-a-verdict]
- [ ] AC-25: WHEN a status appears as a table row in one document and as a heading or list item in another THEN the gate recognises both, because the writer chooses the form and the gate must not [REQ: gates-match-content-through-a-shared-library-not-by-ad-hoc-pattern, scenario: several-shapes-of-the-same-claim-are-recognised]

**A prose signal warns and does not block until it is measured to be right**

- [ ] AC-26: WHEN a gate infers a violation from prose alone THEN it prints a warning and the push proceeds [REQ: a-prose-signal-warns-and-does-not-block-until-it-is-measured-to-be-right, scenario: an-inferred-violation-warns]
- [ ] AC-27: WHEN a warning signal is measured to be correct at least half the time over a sustained period THEN it may be promoted to blocking, and the measurement is recorded [REQ: a-prose-signal-warns-and-does-not-block-until-it-is-measured-to-be-right, scenario: promotion-is-earned]

### gate-self-test

**Every gate carries a two-directional self-test**

- [ ] AC-28: WHEN the self-test runs the gate against a fixture that violates the rule THEN the gate fails [REQ: every-gate-carries-a-two-directional-self-test, scenario: the-gate-fires-on-the-violation]
- [ ] AC-29: WHEN the self-test runs the gate against a fixture that does not violate the rule THEN the gate passes [REQ: every-gate-carries-a-two-directional-self-test, scenario: the-gate-is-silent-on-a-clean-case]
- [ ] AC-30: WHEN a gate's self-test asserts only that it passes on clean input THEN the self-test is incomplete and the gate counts as untested [REQ: every-gate-carries-a-two-directional-self-test, scenario: a-one-directional-test-is-not-enough]

**A gate without a self-test is itself a gate failure**

- [ ] AC-31: WHEN a gate exists with no corresponding self-test THEN the meta-check fails and names the gate [REQ: a-gate-without-a-self-test-is-itself-a-gate-failure, scenario: a-new-gate-without-a-self-test-is-caught]
- [ ] AC-32: WHEN the meta-check runs THEN it is subject to the same two-directional requirement as any other gate [REQ: a-gate-without-a-self-test-is-itself-a-gate-failure, scenario: the-meta-check-tests-itself-too]

**Self-test fixtures live outside the repository being checked**

- [ ] AC-33: WHEN a self-test needs a fixture that violates the rule THEN the fixture is created outside the working tree and removed afterwards [REQ: self-test-fixtures-live-outside-the-repository-being-checked, scenario: a-violating-fixture-does-not-break-real-pushes]
- [ ] AC-34: WHEN a self-test runs THEN the gate's target is the fixture tree, and the result does not depend on this repository's current state [REQ: self-test-fixtures-live-outside-the-repository-being-checked, scenario: the-gate-is-run-against-the-fixture-not-against-the-repository]

### rule-enforcement-gates

**A change with started work carries its review artifact**

- [ ] AC-35: WHEN a change has a completed task and no review artifact THEN the push is blocked, naming the change [REQ: a-change-with-started-work-carries-its-review-artifact, scenario: started-work-without-a-review-is-blocked]
- [ ] AC-36: WHEN a review artifact exists but contains no severity marker and no statement of no findings THEN the gate treats it as absent [REQ: a-change-with-started-work-carries-its-review-artifact, scenario: an-empty-artifact-does-not-satisfy-the-gate]
- [ ] AC-37: WHEN a change is archived within the pushed range and holds no review artifact THEN the push is blocked [REQ: a-change-with-started-work-carries-its-review-artifact, scenario: archiving-does-not-bypass-the-review]
- [ ] AC-38: WHEN a review artifact records a critical finding whose status is still open THEN the push is blocked until the status records resolution or a stated rejection [REQ: a-change-with-started-work-carries-its-review-artifact, scenario: an-unresolved-critical-finding-blocks-the-push]

**An error is not swallowed silently**

- [ ] AC-39: WHEN a new exception handler discards its error with no logging THEN the gate blocks and names the location [REQ: an-error-is-not-swallowed-silently, scenario: a-new-silent-handler-is-blocked]
- [ ] AC-40: WHEN a handler is listed in the gate's baseline THEN it does not block, and remains counted as debt [REQ: an-error-is-not-swallowed-silently, scenario: existing-ones-do-not-block]
- [ ] AC-41: WHEN a handler records the error at any level before continuing THEN the gate accepts it [REQ: an-error-is-not-swallowed-silently, scenario: a-handler-that-logs-is-accepted]

**A touched change validates**

- [ ] AC-42: WHEN a change modified in the pushed range fails strict validation THEN the push is blocked with the validator's own output [REQ: a-touched-change-validates, scenario: a-touched-invalid-change-blocks]
- [ ] AC-43: WHEN a change that the push does not modify fails validation THEN the push proceeds [REQ: a-touched-change-validates, scenario: untouched-debt-does-not-block]

**A rule does not cite a file that does not exist**

- [ ] AC-44: WHEN a rule document cites a path that does not exist THEN the gate blocks and names both the rule and the path [REQ: a-rule-does-not-cite-a-file-that-does-not-exist, scenario: a-dead-citation-blocks]
- [ ] AC-45: WHEN a path appears inside a fenced example block THEN it is not checked for existence [REQ: a-rule-does-not-cite-a-file-that-does-not-exist, scenario: an-example-path-is-not-a-citation]

**Each first gate is scoped to be passable when it lands**

- [ ] AC-46: WHEN a gate is introduced against existing violations THEN a push that changes none of them passes [REQ: each-first-gate-is-scoped-to-be-passable-when-it-lands, scenario: a-gate-lands-without-blocking-existing-work]
- [ ] AC-47: WHEN a reader opens a gate THEN the gate states how it is scoped and what would remove the scoping [REQ: each-first-gate-is-scoped-to-be-passable-when-it-lands, scenario: the-scoping-is-discoverable]
