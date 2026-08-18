## 0. Separate package, one-way dependency

<!-- depends: none -->

- [x] 0.1 Create the `set_workcycle` top-level package under `lib/` and register it in the project's package list [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 0.2 Add a test asserting the dependency direction — `set_workcycle` may import `set_orch`, `set_orch` may NOT import `set_workcycle` — that fails if the reverse import is introduced anywhere [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 0.3 Verify orchestration still imports and its unit tests still pass with the new package present but unused, so the baseline is established before any engine code exists [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]

## 1. Module install — how a capability reaches a project

<!-- depends: 0 -->

- [x] 1.0a Split each module into an executable part installed once per machine and a project-owned part; assert the executable part is never copied into a project [REQ: only-what-a-project-must-own-is-placed-in-the-project]
- [x] 1.0b Record the expected module version in the project's declaration and report any mismatch against what is installed machine-wide; report unknown as unknown, never as matching [REQ: a-project-states-the-version-it-expects-and-a-mismatch-is-reported]
- [x] 1.1 Define the module declaration: files with their treatment, required modules, own version; reject at validation a file entry that states no treatment [REQ: a-module-declares-itself-and-an-incomplete-declaration-is-refused]
- [x] 1.2 Fail the install when a declaration names a guard the installer does not implement or cannot apply — a declared guard that does not take effect is an error, not silence [REQ: a-declared-guard-that-does-not-take-effect-is-an-error]
- [x] 1.3 Decide every file from the recorded hash: matching may update, differing is the project's, unknown is left alone; a seed-time equality must not stand in for a current hash [REQ: every-file-decision-comes-from-recorded-provenance]
- [x] 1.3b Announce a module in the project's agent instruction file through a delimited section the installer owns; never touch a byte outside it, leave an edited section alone and report it, and report when there is no instruction file rather than creating one [REQ: a-module-is-announced-in-the-project-s-agent-instructions-through-a-marked-section]
- [x] 1.4 Report every skip with its reason, and report explicitly when an install wrote nothing [REQ: a-skip-is-reported-never-silent]
- [x] 1.5 Record removals durably and never recreate a removed file; make the recorded removals listable [REQ: deletion-is-durable]
- [x] 1.6 Compare generator stamps on generated artifacts and refuse to replace a newer stamp with an older one, reporting both versions; treat a missing stamp on either side as unknown [REQ: a-generated-artifact-is-never-replaced-by-an-older-generator-s-output]
- [x] 1.7 Enforce module requirements as mandatory: refuse to install a module whose required module is absent, naming what is missing [REQ: a-module-s-requirements-are-mandatory-not-advisory]
- [x] 1.8 Install only the modules a project asked for, and make the installed set with versions readable [REQ: a-project-installs-the-modules-it-asked-for]
- [x] 1.9 Audit the existing manifests against 1.1: every file entry must state a treatment; report the ones that do not, per module [REQ: a-module-declares-itself-and-an-incomplete-declaration-is-refused]
- [x] 1.10 Install tests for 1.1–1.8, including one that edits an installed file and asserts a later install leaves it alone and says so [REQ: every-file-decision-comes-from-recorded-provenance]

## 2. Measure before committing to reuse

<!-- depends: none -->

- [x] 2.1 Determine whether `GatePipeline` can be pointed at one tree and a subset of gates without inheriting merge semantics (retry policy, baseline-diff scope, new-API-surface detection); record the finding and which of the two acceptable outcomes applies [REQ: the-gate-runs-through-the-project-profile]
- [x] 2.2 Identify which part of the stream-json consumption in `chat.py` is reusable outside a websocket-bound session, and record what has to be extracted versus re-expressed [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 2.3 Record both findings in `design.md` under D4, replacing the open question with the measurement [REQ: the-gate-runs-through-the-project-profile]

## 3. Task-group resolution (Layer 1, domain-free)

<!-- depends: none -->

- [x] 3.1 Parse numbered group headings out of a change's `tasks.md` and bind every task line to exactly one group, including lines preceding the first heading [REQ: task-groups-are-read-from-the-change-s-task-file]
- [x] 3.2 Parse dependency annotations attached to a group, defaulting an unannotated group to depend on its predecessor, and honouring an explicit declaration of independence [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed]
- [x] 3.3 Detect dependency cycles and refuse to declare any group runnable, naming the cycle [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed]
- [x] 3.4 Select the next runnable group deterministically, skipping groups awaiting an answer rather than blocking behind them, and reporting per-group reasons when nothing is runnable [REQ: the-next-runnable-group-is-selected-deterministically]
- [x] 3.5 Cut the slice handed to a run — the group's block only — and honour a caller-supplied task limit within the group [REQ: a-run-receives-its-slice-not-the-whole-file]
- [x] 3.6 Assemble carry-over: the notes of the most recent completed run for the same group and for the preceding group, dropping older runs [REQ: carry-over-travels-from-the-previous-run]
- [x] 3.7 Assemble the reading list from every markdown artifact in the change directory except the task file, including artifacts written by earlier runs [REQ: the-reading-list-includes-the-change-s-own-artifacts]
- [x] 3.8 Unit tests for 2.1–2.7, each verified against the un-fixed code (stash the implementation, confirm the test fails) before being accepted as proof [REQ: the-next-runnable-group-is-selected-deterministically]

## 4. Work-unit engine core

<!-- depends: 2, 3 -->

- [x] 4.1 Define the work unit and its lifecycle — run, verdict, gate, commit, or set aside — with the unit kind as an attribute so slice, phase and lens are expressible [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 4.2 Acquire a tree-scoped lock recording a session-scoped seat; refuse a seat that identifies only a project; report a lock whose holder is dead as stale, distinguishably from running [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped]
- [x] 4.3 Run the unit as a full agent session (not a subagent) with the project's hooks and rules active, consuming its event stream as it runs [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 4.4 Constrain the verdict to a declared schema with outcome, summary and a separate open-decisions field; record a non-conforming return as a reporting failure rather than inferring an outcome [REQ: the-verdict-is-schema-constrained]
- [x] 4.5 Persist the verdict durably **before** the gate runs, so a run interrupted between verdict and commit stays attributable [REQ: the-verdict-is-durable-before-the-gate-runs]
- [x] 4.6 Diff the verdict against the task markers in the tree and report divergence in both directions [REQ: the-verdict-is-checked-against-the-tree]
- [x] 4.7 Resolve gate steps through `resolve_gate_config` and run them per the 1.1 finding; record "no gate ran" as a state distinct from "gate passed" when the profile declares none [REQ: the-gate-runs-through-the-project-profile]
- [x] 4.8 Commit only behind a green gate, referencing the change and unit; on failure leave the work in the tree, make no commit, and do not advance [REQ: a-commit-happens-only-behind-a-green-gate]
- [x] 4.8b On gate failure, report whether the failure implicates files this unit changed or files changed elsewhere in the tree; where attribution cannot be established, say so rather than defaulting to the unit [REQ: a-gate-failure-states-whether-it-came-from-this-unit-s-own-work]
- [x] 4.9 Derive reported progress from completed task markers, never from turn or event counts [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [x] 4.10 Unit tests for 3.1–3.9, including a test that fails if progress is ever derived from an activity counter [REQ: the-verdict-is-checked-against-the-tree]
- [x] 4.11 Allow a unit's input to be other units' verdicts, and preserve every input verdict in full when such a unit is set aside; a projection of the comparison must carry its verdict, not decide for it [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them]

## 5. Deferred-work connector

<!-- depends: 4 -->

- [x] 5.1 Set a unit aside with a machine-readable resume condition that expresses both a human decision and an external dependency; refuse to set one aside with no condition [REQ: a-set-aside-unit-names-its-resume-condition]
- [x] 5.2 Write an open decision into the change's task file as a durable stop marker carrying the question, surviving engine restart [REQ: an-open-decision-becomes-a-durable-stop-marker]
- [x] 5.3 Read answers from a directory keyed inside the document on change and task; report an answer for a non-awaiting task as unmatched and leave it in place [REQ: answers-arrive-through-a-keyed-directory]
- [x] 5.4 Defer an unparseable answer document and retry it on later intake; quarantine with a recorded reason only after a bounded number of failed attempts [REQ: the-connector-tolerates-a-partially-written-answer]
- [x] 5.5 Accept several documents for one key — newest applied, others retained — and name written documents by source and timestamp so two uploaders cannot collide [REQ: several-answers-may-exist-for-one-key]
- [x] 5.6 Run answer intake at the engine's entry point on every path, including the status path, so a released task is reported runnable [REQ: answer-intake-runs-at-the-entry-point-on-every-path]
- [x] 5.7 Stamp consumption on the answer or in the log, and make consumed and unconsumed distinguishable without counting files [REQ: consumption-is-recorded-not-inferred]
- [x] 5.8 Tests for 4.1–4.7, including one that fails if intake is reachable from only some entry points, and one that writes a truncated document mid-intake [REQ: answer-intake-runs-at-the-entry-point-on-every-path]

## 6. Entry point — one way in

<!-- depends: 4, 5 -->

- [x] 6.1 Ship a command entry point invocable from a project's own tree, requiring no running framework service and no network access to the framework [REQ: the-engine-is-entered-by-a-command-run-from-the-project-s-tree]
- [x] 6.2 Report per-group reasons when nothing is runnable, and refuse with the holder named when a unit already holds the tree's lock [REQ: the-engine-is-entered-by-a-command-run-from-the-project-s-tree]
- [x] 6.3 Make the framework's surface start a unit by invoking that same command; add a test that fails if a second start path is introduced [REQ: there-is-one-way-into-the-engine-and-every-caller-uses-it]
- [x] 6.4 Write run state where a reader can read it directly — live run, finished run, and a stale claim distinguishable from a live one — without executing anything [REQ: run-state-is-readable-without-a-running-engine-or-service]
- [x] 6.5 Run answer intake on every command invocation, including invocations that only report state [REQ: the-command-path-takes-in-answers-like-every-other-path]
- [x] 6.6 Entry-point tests for 5.1–5.5, including one asserting that an agent-started run and a surface-started run produce the same state shape [REQ: there-is-one-way-into-the-engine-and-every-caller-uses-it]

## 7. Adoption — any project, several at once

<!-- depends: 4, 5, 6 -->

- [x] 7.1 Take the project as an input on every operation and keep lock, run state and pending answers separate per project; assert that an operation naming one project cannot touch another [REQ: several-projects-are-driven-from-one-place-with-state-kept-apart]
- [x] 7.2 Read what varies between projects from the resolved profile and the project's declaration only; add a test that fails if any project name or project path appears in the engine package [REQ: the-engine-carries-no-project-specific-knowledge]
- [x] 7.3 Refuse to run against a project whose declaration is missing, naming what is missing; never substitute a guessed default for an undeclared gate [REQ: adoption-is-a-declaration-and-its-absence-is-not-guessed]
- [x] 7.4 Report an un-adopted project as un-adopted — distinct from an adopted project with no open work — so that zero runnable groups is never read as "up to date" [REQ: an-un-adopted-project-is-distinguishable-from-a-finished-one]
- [x] 7.5 Drive a task file that carries no dependency annotations under the serial default, requiring no edit to that file before the first run [REQ: adoption-does-not-require-the-project-to-change-how-it-works]
- [x] 7.6 Adoption tests: two projects driven concurrently with no state bleed, and an un-adopted project queried [REQ: several-projects-are-driven-from-one-place-with-state-kept-apart]

## 8. Evidence

<!-- depends: 6 -->

- [ ] 8.1 Run the engine on a change of this repository with real group dependencies and at least one human stop; record what the run produced, not that it exited zero [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 8.2 Confirm the answer written from the surface reaches a stopped unit and releases it, observed end to end rather than asserted per layer [REQ: an-open-decision-can-be-answered-over-the-api]
- [?] 8.3 Coordinate the crossing run on the consuming project's tree and compare it against that project's own engine — requires the other side's participation and their choice of change [REQ: a-commit-happens-only-behind-a-green-gate]

## Acceptance Criteria (from spec scenarios)

<!-- module-install -->
- [ ] AC-1: WHEN a module is installed into a project THEN the module's executable part is not placed in that project / the project invokes it from the machine-wide installation [REQ: only-what-a-project-must-own-is-placed-in-the-project, scenario: the-executable-part-is-not-copied]
- [ ] AC-2: WHEN a module is installed into a project THEN its declaration and configuration are placed in the project [REQ: only-what-a-project-must-own-is-placed-in-the-project, scenario: the-project-owned-part-is-placed]
- [ ] AC-3: WHEN a module writes run state, locks or pending answers while working THEN those are not treated as installed files / an install neither creates nor removes them [REQ: only-what-a-project-must-own-is-placed-in-the-project, scenario: runtime-state-is-not-an-install-artifact]
- [ ] AC-4: WHEN a module that must be announced is installed THEN the announcement is written between the installer's own delimiters / every line outside those delimiters is byte-identical to what was there before [REQ: a-module-is-announced-in-the-project-s-agent-instructions-through-a-marked-section, scenario: announcement-is-written-into-its-own-section]
- [ ] AC-5: WHEN the content between the delimiters differs from what the installer last wrote THEN the installer leaves it alone and reports the divergence / it does NOT silently restore its own version [REQ: a-module-is-announced-in-the-project-s-agent-instructions-through-a-marked-section, scenario: the-project-edited-inside-the-section]
- [ ] AC-6: WHEN the project has no agent instruction file THEN the installer reports that the module could not be announced / it does NOT create the file as a side effect of installing [REQ: a-module-is-announced-in-the-project-s-agent-instructions-through-a-marked-section, scenario: no-instruction-file-present]
- [ ] AC-7: WHEN a module's announcement is withdrawn THEN only the delimited section is removed / the rest of the file is unchanged [REQ: a-module-is-announced-in-the-project-s-agent-instructions-through-a-marked-section, scenario: uninstalling-removes-only-the-section]
- [ ] AC-8: WHEN a project expects one version and another is installed machine-wide THEN the difference is reported, naming both [REQ: a-project-states-the-version-it-expects-and-a-mismatch-is-reported, scenario: machine-wide-version-differs-from-the-project-s-expectation]
- [ ] AC-9: WHEN either version cannot be read THEN the framework reports it as unknown / it does NOT report the versions as matching [REQ: a-project-states-the-version-it-expects-and-a-mismatch-is-reported, scenario: version-cannot-be-determined]
- [ ] AC-10: WHEN a module declares a file without stating how later installs must treat it THEN validation fails and names that file / the install does not proceed with a guessed treatment [REQ: a-module-declares-itself-and-an-incomplete-declaration-is-refused, scenario: a-file-entry-with-no-treatment-stated]
- [ ] AC-11: WHEN every declared file states its treatment THEN validation passes [REQ: a-module-declares-itself-and-an-incomplete-declaration-is-refused, scenario: a-complete-declaration-validates]
- [ ] AC-12: WHEN a module declares a guard the installer does not recognise THEN the install fails and names the unrecognised guard [REQ: a-declared-guard-that-does-not-take-effect-is-an-error, scenario: unknown-guard-named]
- [ ] AC-13: WHEN a declared guard cannot be applied to a file THEN the install fails for that file rather than installing it unguarded [REQ: a-declared-guard-that-does-not-take-effect-is-an-error, scenario: a-guard-that-cannot-be-applied]
- [ ] AC-14: WHEN a file's current content differs from what was recorded at install THEN the installer leaves it alone [REQ: every-file-decision-comes-from-recorded-provenance, scenario: the-project-edited-an-installed-file]
- [ ] AC-15: WHEN a file's current content matches what was recorded at install THEN the installer may update it [REQ: every-file-decision-comes-from-recorded-provenance, scenario: an-untouched-file-may-be-updated]
- [ ] AC-16: WHEN a file exists at a destination the installer has no record for THEN the installer leaves it alone [REQ: every-file-decision-comes-from-recorded-provenance, scenario: unknown-provenance-is-not-overwritten]
- [ ] AC-17: WHEN a file was identical to its template when first installed and has since diverged THEN the installer detects the divergence from the recorded hash / the fact that it was once identical does not authorise an update [REQ: every-file-decision-comes-from-recorded-provenance, scenario: a-seed-time-decision-does-not-stand-in-for-a-hash]
- [ ] AC-18: WHEN an install leaves files alone because the project modified them THEN each is named in the install's output with its reason [REQ: a-skip-is-reported-never-silent, scenario: skipped-files-are-listed]
- [ ] AC-19: WHEN an install writes no files THEN it reports that outcome explicitly rather than exiting quietly [REQ: a-skip-is-reported-never-silent, scenario: a-run-that-changed-nothing-says-so]
- [ ] AC-20: WHEN a project deletes a previously installed file and the module is installed again THEN the file is not recreated [REQ: deletion-is-durable, scenario: a-removed-file-stays-removed]
- [ ] AC-21: WHEN a project's install record is read THEN the recorded removals can be listed [REQ: deletion-is-durable, scenario: removals-are-inspectable]
- [ ] AC-22: WHEN the destination carries a newer generator stamp than the file being installed THEN the installer refuses to replace it and reports the version on each side [REQ: a-generated-artifact-is-never-replaced-by-an-older-generator-s-output, scenario: incoming-artifact-is-older]
- [ ] AC-23: WHEN either side carries no generator stamp THEN the installer treats the comparison as unknown and leaves the destination alone [REQ: a-generated-artifact-is-never-replaced-by-an-older-generator-s-output, scenario: stamp-missing-on-one-side]
- [ ] AC-24: WHEN a module requiring another is installed into a project that does not have it THEN the install fails and names the missing requirement [REQ: a-module-s-requirements-are-mandatory-not-advisory, scenario: a-required-module-is-absent]
- [ ] AC-25: WHEN every declared requirement is present THEN the install proceeds [REQ: a-module-s-requirements-are-mandatory-not-advisory, scenario: requirements-are-satisfied]
- [ ] AC-26: WHEN a project asks for one module and others are available THEN only the requested module's files are installed [REQ: a-project-installs-the-modules-it-asked-for, scenario: an-unrequested-module-is-not-installed]
- [ ] AC-27: WHEN a project's install record is read THEN it states which modules are installed and at which version [REQ: a-project-installs-the-modules-it-asked-for, scenario: the-installed-set-is-readable]

<!-- work-unit-engine -->
- [ ] AC-28: WHEN the engine starts a work unit THEN it launches a full agent session with the project's hooks and rules active / it consumes the session's event stream as the run proceeds [REQ: a-work-unit-runs-in-a-fresh-full-agent-context, scenario: unit-runs-as-a-full-session]
- [ ] AC-29: WHEN the engine reports how far a unit has got THEN the figure is derived from completed task markers in the change's `tasks.md` / the count of turns or events is NOT presented as progress [REQ: a-work-unit-runs-in-a-fresh-full-agent-context, scenario: progress-is-measured-from-the-tree-not-from-the-transcript]
- [ ] AC-30: WHEN a work unit is started while another holds the lock for the same tree THEN the engine refuses the second unit and names the holder [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-second-unit-is-refused-while-one-runs]
- [ ] AC-31: WHEN a seat identifier is supplied that identifies the project rather than a session THEN the engine refuses to record it / the refusal states that a seat must identify one session [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-project-scoped-seat-is-refused]
- [ ] AC-32: WHEN a lock exists but the process that took it is no longer alive THEN the engine reports the lock as stale rather than as running / the stale state is distinguishable from a live run in the engine's own output [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-lock-whose-holder-is-gone-does-not-block-forever]
- [ ] AC-33: WHEN a work unit returns output that does not match the verdict schema THEN the engine records the run as failed to report rather than inventing an outcome [REQ: the-verdict-is-schema-constrained, scenario: a-verdict-outside-the-schema-is-refused]
- [ ] AC-34: WHEN a unit describes a decision needing a human in its free-text notes but leaves the open decisions field empty THEN the engine does NOT treat it as a stop point / the notes are carried forward as context only [REQ: the-verdict-is-schema-constrained, scenario: an-open-decision-in-the-notes-does-not-stop-the-cycle]
- [ ] AC-35: WHEN a unit returns one or more entries in the open decisions field THEN the engine marks the corresponding work as awaiting a human answer [REQ: the-verdict-is-schema-constrained, scenario: an-open-decision-in-its-own-field-stops-the-unit]
- [ ] AC-36: WHEN the verdict lists completed work that the file does not mark as complete THEN the engine reports the discrepancy and does not adopt the claim [REQ: the-verdict-is-checked-against-the-tree, scenario: claimed-more-than-was-marked]
- [ ] AC-37: WHEN the file marks work complete that the verdict does not mention THEN the engine reports that discrepancy too [REQ: the-verdict-is-checked-against-the-tree, scenario: marked-more-than-was-claimed]
- [ ] AC-38: WHEN a work unit finishes and a gate is due THEN the steps executed are those the project's profile declares [REQ: the-gate-runs-through-the-project-profile, scenario: gate-steps-come-from-the-profile]
- [ ] AC-39: WHEN the profile declares no gate steps THEN the engine runs no gate and records that no gate was run / it does NOT substitute a default command [REQ: the-gate-runs-through-the-project-profile, scenario: no-declared-gate-means-no-gate]
- [ ] AC-40: WHEN the gate reports a failure THEN no commit is made / the work remains in the working tree / the engine stops rather than starting the next unit [REQ: a-commit-happens-only-behind-a-green-gate, scenario: gate-fails]
- [ ] AC-41: WHEN the gate passes THEN the engine commits the unit's changes with a reference to the change and unit it belongs to [REQ: a-commit-happens-only-behind-a-green-gate, scenario: gate-passes]
- [ ] AC-42: WHEN the engine's process ends after a unit returns its verdict but before the commit completes THEN the recorded verdict survives / the engine's later output shows a started unit with no completion, rather than showing the unit as never attempted [REQ: the-verdict-is-durable-before-the-gate-runs, scenario: killed-between-verdict-and-commit]
- [ ] AC-43: WHEN a gate fails and the failure implicates only files this unit did not change THEN the engine reports the failure as originating outside the unit's own work / the unit is not described as having broken it [REQ: a-gate-failure-states-whether-it-came-from-this-unit-s-own-work, scenario: failure-outside-the-unit-s-own-files]
- [ ] AC-44: WHEN a gate fails and the failure implicates files this unit changed THEN the engine attributes it to the unit [REQ: a-gate-failure-states-whether-it-came-from-this-unit-s-own-work, scenario: failure-in-the-unit-s-own-files]
- [ ] AC-45: WHEN the engine cannot establish which files a failure implicates THEN it says so / it does NOT default to attributing the failure to the unit [REQ: a-gate-failure-states-whether-it-came-from-this-unit-s-own-work, scenario: attribution-cannot-be-determined]
- [ ] AC-46: WHEN a unit whose input is several other units' verdicts is set aside instead of producing an outcome THEN every input verdict remains retrievable in full / no input verdict is replaced by a summary of it [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them, scenario: comparing-unit-is-set-aside]
- [ ] AC-47: WHEN the comparison's result is projected into a single outcome for a caller THEN the projection carries the comparison's own verdict rather than deciding on its behalf / where the comparison reached no decision, the projection is a stop rather than a choice [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them, scenario: a-mechanical-projection-of-the-comparison-does-not-decide]

<!-- task-group-resolution -->
- [ ] AC-48: WHEN a `tasks.md` contains numbered group headings with task lines beneath them THEN the resolver reports one group per heading, each carrying its own task lines [REQ: task-groups-are-read-from-the-change-s-task-file, scenario: groups-are-identified]
- [ ] AC-49: WHEN task lines appear before the first group heading THEN the resolver reports them as a group rather than discarding them [REQ: task-groups-are-read-from-the-change-s-task-file, scenario: tasks-outside-any-group]
- [ ] AC-50: WHEN a group declares that it depends on specific earlier groups THEN the resolver treats it as runnable only once those groups are complete [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: declared-dependencies]
- [ ] AC-51: WHEN a group carries no dependency annotation THEN the resolver treats it as depending on the immediately preceding group [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: no-annotation-means-serial]
- [ ] AC-52: WHEN a group explicitly declares that it has no dependencies THEN the resolver treats it as runnable regardless of earlier groups [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: explicit-independence]
- [ ] AC-53: WHEN declared dependencies form a cycle THEN the resolver reports the cycle and declares no group runnable / it does NOT pick an arbitrary order [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: a-cycle-is-reported-not-silently-ordered]
- [ ] AC-54: WHEN the lowest-ordered group with open tasks depends on a group that still has open tasks THEN it is not selected [REQ: the-next-runnable-group-is-selected-deterministically, scenario: dependencies-unsatisfied]
- [ ] AC-55: WHEN a group is awaiting a human answer and a later independent group is runnable THEN the later group is selected / the awaiting group remains reported as awaiting [REQ: the-next-runnable-group-is-selected-deterministically, scenario: a-group-awaiting-an-answer-is-skipped-not-blocked-behind]
- [ ] AC-56: WHEN every group with open tasks is either blocked by dependencies or awaiting an answer THEN the resolver reports that no group is runnable, and why for each [REQ: the-next-runnable-group-is-selected-deterministically, scenario: nothing-runnable]
- [ ] AC-57: WHEN a group is selected for a run THEN the handed-over work description contains that group's tasks / it does not contain other groups' tasks [REQ: a-run-receives-its-slice-not-the-whole-file, scenario: only-the-group-s-block-is-handed-over]
- [ ] AC-58: WHEN a caller limits a run to a number of tasks smaller than the group THEN the slice contains at most that many open tasks from the group [REQ: a-run-receives-its-slice-not-the-whole-file, scenario: hard-slicing-within-a-group]
- [ ] AC-59: WHEN a group is selected that a previous run left partially complete THEN that previous run's notes travel with the new slice [REQ: carry-over-travels-from-the-previous-run, scenario: resuming-a-partial-group]
- [ ] AC-60: WHEN a group is selected whose predecessor produced notes THEN those notes travel with the slice [REQ: carry-over-travels-from-the-previous-run, scenario: discoveries-reach-the-next-group]
- [ ] AC-61: WHEN several earlier runs exist for the same group THEN only the most recent one's notes are included [REQ: carry-over-travels-from-the-previous-run, scenario: stale-notes-are-dropped]
- [ ] AC-62: WHEN an earlier run wrote a new markdown artifact into the change's directory THEN a later run's reading list includes it [REQ: the-reading-list-includes-the-change-s-own-artifacts, scenario: an-artifact-produced-by-an-earlier-group-is-included]
- [ ] AC-63: WHEN the reading list is assembled THEN the task file is excluded, because the slice is handed over separately [REQ: the-reading-list-includes-the-change-s-own-artifacts, scenario: the-task-file-is-not-duplicated]

<!-- deferred-work-connector -->
- [ ] AC-64: WHEN a unit is set aside because a decision needs a person THEN the recorded condition identifies the decision awaiting an answer [REQ: a-set-aside-unit-names-its-resume-condition, scenario: awaiting-a-human-answer]
- [ ] AC-65: WHEN a unit is set aside because a system it depends on is unavailable THEN the recorded condition names that dependency / the engine does NOT describe the unit as waiting for a human [REQ: a-set-aside-unit-names-its-resume-condition, scenario: awaiting-an-external-system]
- [ ] AC-66: WHEN a unit is set aside with no condition given THEN the engine refuses, because a condition that is not named cannot be observed [REQ: a-set-aside-unit-names-its-resume-condition, scenario: a-unit-cannot-be-set-aside-without-a-condition]
- [ ] AC-67: WHEN a unit returns an open decision naming a task THEN that task is marked in the file as awaiting a human answer / the question text is recorded with it [REQ: an-open-decision-becomes-a-durable-stop-marker, scenario: open-decision-is-written-into-the-task-file]
- [ ] AC-68: WHEN the engine is restarted after a unit returned an open decision THEN the marked task is still reported as awaiting an answer [REQ: an-open-decision-becomes-a-durable-stop-marker, scenario: the-marker-outlives-the-run]
- [ ] AC-69: WHEN an answer document naming a change and an awaiting task is placed in the directory THEN the engine records the answer against that task and the task is no longer awaiting [REQ: answers-arrive-through-a-keyed-directory, scenario: an-answer-releases-its-task]
- [ ] AC-70: WHEN an answer names a task that is not awaiting an answer THEN the engine reports it as unmatched and leaves it in place rather than discarding it [REQ: answers-arrive-through-a-keyed-directory, scenario: an-answer-for-an-unknown-task]
- [ ] AC-71: WHEN an answer document cannot be parsed on its first intake THEN it is deferred and remains eligible for a later intake / it is NOT quarantined on that first failure [REQ: the-connector-tolerates-a-partially-written-answer, scenario: half-written-file-is-retried-not-quarantined]
- [ ] AC-72: WHEN a document has failed to parse on the configured number of successive intakes THEN it is quarantined and the reason is recorded alongside it [REQ: the-connector-tolerates-a-partially-written-answer, scenario: persistently-malformed-file-is-quarantined-with-its-reason]
- [ ] AC-73: WHEN a document that was deferred parses successfully on a later intake THEN it is consumed as any other answer [REQ: the-connector-tolerates-a-partially-written-answer, scenario: a-deferred-file-that-later-parses-is-consumed-normally]
- [ ] AC-74: WHEN two answer documents for the same key are present THEN the most recent is applied / the other is retained [REQ: several-answers-may-exist-for-one-key, scenario: two-uploaders-answer-the-same-question]
- [ ] AC-75: WHEN an answer document is written by an uploader THEN its name carries the uploader's identity and a timestamp / a second uploader writing for the same key produces a different name [REQ: several-answers-may-exist-for-one-key, scenario: names-do-not-collide]
- [ ] AC-76: WHEN the engine is asked to run one work unit THEN pending answers are taken in before the unit is selected [REQ: answer-intake-runs-at-the-entry-point-on-every-path, scenario: intake-happens-on-a-single-unit-run]
- [ ] AC-77: WHEN the engine is asked what is runnable THEN pending answers are taken in before the answer is computed / a task released by a pending answer is reported as runnable [REQ: answer-intake-runs-at-the-entry-point-on-every-path, scenario: intake-happens-on-a-status-query]
- [ ] AC-78: WHEN an answer is applied to a task THEN the time of consumption is recorded [REQ: consumption-is-recorded-not-inferred, scenario: a-consumed-answer-is-stamped]
- [ ] AC-79: WHEN answers are present in the directory THEN those already consumed are distinguishable from those not yet consumed / neither state is concluded from the number of files present [REQ: consumption-is-recorded-not-inferred, scenario: an-unconsumed-answer-is-distinguishable]

<!-- work-cycle-control -->
- [ ] AC-80: WHEN an agent working in a project's tree invokes the command to run the next unit THEN the unit runs against that tree / no framework service needs to be running [REQ: the-engine-is-entered-by-a-command-run-from-the-project-s-tree, scenario: an-agent-starts-a-unit-from-its-own-session]
- [ ] AC-81: WHEN the command is invoked and no unit is runnable THEN it reports why per group and exits without starting anything [REQ: the-engine-is-entered-by-a-command-run-from-the-project-s-tree, scenario: no-runnable-unit]
- [ ] AC-82: WHEN the command is invoked while a unit holds the lock for that tree THEN it refuses and identifies the holder [REQ: the-engine-is-entered-by-a-command-run-from-the-project-s-tree, scenario: a-unit-is-already-running]
- [ ] AC-83: WHEN the framework's surface starts a unit for a project THEN it invokes the same command an agent would invoke / the resulting run is indistinguishable from an agent-started one except in what recorded who started it [REQ: there-is-one-way-into-the-engine-and-every-caller-uses-it, scenario: the-surface-starts-a-unit]
- [ ] AC-84: WHEN the engine's interfaces are enumerated THEN exactly one of them starts a work unit [REQ: there-is-one-way-into-the-engine-and-every-caller-uses-it, scenario: no-parallel-start-path]
- [ ] AC-85: WHEN a unit is running and the framework is asked where it has got to THEN it reads the recorded state / it does not start a process to find out [REQ: run-state-is-readable-without-a-running-engine-or-service, scenario: the-framework-reads-a-live-run]
- [ ] AC-86: WHEN a run has finished and its process is gone THEN the recorded state still reports the outcome of that run [REQ: run-state-is-readable-without-a-running-engine-or-service, scenario: the-framework-reads-a-finished-run]
- [ ] AC-87: WHEN recorded state claims a run in progress whose process is no longer alive THEN the reader can tell that state apart from a live run [REQ: run-state-is-readable-without-a-running-engine-or-service, scenario: a-stale-run-is-reported-as-stale]
- [ ] AC-88: WHEN an answer for an awaiting task is placed in the connector and the command is then invoked THEN the answer is taken in before unit selection / the released task's group is eligible to run [REQ: the-command-path-takes-in-answers-like-every-other-path, scenario: answer-arrives-before-a-command-run]
- [ ] AC-89: WHEN the command is invoked only to report state THEN answer intake still runs / the reported state reflects answers that had arrived [REQ: the-command-path-takes-in-answers-like-every-other-path, scenario: answer-intake-on-a-reporting-invocation]

<!-- work-cycle-adoption -->
- [ ] AC-90: WHEN the engine is run against a project it has never been run against before THEN it operates using only that project's resolved profile and declaration / no framework code names that project [REQ: the-engine-carries-no-project-specific-knowledge, scenario: a-second-project-needs-no-framework-change]
- [ ] AC-91: WHEN two projects need different gate steps THEN the difference is expressed in their profiles / the engine's behaviour is identical in both cases [REQ: the-engine-carries-no-project-specific-knowledge, scenario: project-specific-behaviour-arrives-through-the-profile]
- [ ] AC-92: WHEN an adopted project declares no gate steps THEN the engine runs no gate and says so / it does NOT fall back to a command it guessed from the project's contents [REQ: adoption-is-a-declaration-and-its-absence-is-not-guessed, scenario: an-undeclared-gate-is-not-invented]
- [ ] AC-93: WHEN the engine is asked to run against a project that has not declared where its changes live THEN it refuses and names the missing declaration [REQ: adoption-is-a-declaration-and-its-absence-is-not-guessed, scenario: a-missing-declaration-is-named]
- [ ] AC-94: WHEN the state of a project that has not been adopted is queried THEN the response states that the project is not adopted / it does NOT report zero runnable groups as though the project were up to date [REQ: an-un-adopted-project-is-distinguishable-from-a-finished-one, scenario: un-adopted-project-queried]
- [ ] AC-95: WHEN the state of an adopted project with no open tasks is queried THEN the response distinguishes this from the un-adopted case [REQ: an-un-adopted-project-is-distinguishable-from-a-finished-one, scenario: adopted-project-with-no-open-work]
- [ ] AC-96: WHEN work units are running for two different projects at once THEN each holds its own lock / neither project's state, answers or verdicts appear in the other's [REQ: several-projects-are-driven-from-one-place-with-state-kept-apart, scenario: concurrent-projects]
- [ ] AC-97: WHEN an answer is submitted naming a change in one project THEN a task of the same name in another project is unaffected [REQ: several-projects-are-driven-from-one-place-with-state-kept-apart, scenario: an-answer-reaches-only-its-own-project]
- [ ] AC-98: WHEN a work unit fails or is blocked in one project THEN operations against other projects continue to be accepted [REQ: several-projects-are-driven-from-one-place-with-state-kept-apart, scenario: a-failure-in-one-project-does-not-stop-another]
- [ ] AC-99: WHEN a project's task file carries groups but no dependency annotations THEN the engine drives it under the serial default / it requires no edit to that file before the first run [REQ: adoption-does-not-require-the-project-to-change-how-it-works, scenario: task-file-without-dependency-annotations]
- [ ] AC-100: WHEN an adopted project already marks tasks in its own established way THEN the engine reads those markings rather than requiring a different notation [REQ: adoption-does-not-require-the-project-to-change-how-it-works, scenario: existing-conventions-are-honoured-not-replaced]
