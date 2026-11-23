## 1. Orphan reconciler (Layer 1, core)

- [ ] 1.1 Add `reconcile_fix_iss_orphans(state_file, project_root, *, event_bus=None) -> list[str]` to `lib/set_orch/issues/manager.py`. The function returns the list of newly-registered orphan names (empty when nothing was adopted). [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll]
- [ ] 1.2 Implementation: `os.scandir` `openspec/changes/`, filter to entries whose name matches `^fix-iss-\d{3}-`, dedupe against current `state.changes` names under a single `locked_state`, register via the existing `_register_fix_iss_in_state` (already idempotent on duplicate name). [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll, Registration is safe under concurrent escalation paths]
- [ ] 1.3 Add `_derive_parent_from_proposal(proposal_path: Path, state_changes: list[Change]) -> str | None` helper implementing the three ordered strategies: HTML comment `<!-- parent: <name> -->`, Why-line regex `Parent change \`([^\`]+)\``, slug-prefix match (minimum 4 char overlap, longest match wins). [REQ: Registration uses parent attribution heuristics]
- [ ] 1.4 Tolerate malformed orphans: directories without `proposal.md` SHALL be skipped with a WARN log (directory name + missing-file reason); directories missing `tasks.md` / `design.md` SHALL be registered anyway. [REQ: Reconciler tolerates malformed orphan directories]
- [ ] 1.5 Emit `FIX_ISS_ORPHAN_REGISTERED` per registered orphan via the injected `event_bus` (no event when `event_bus is None` — for unit tests). Event `data` includes `source="on_disk_orphan"` and `parent_name_guess` (the derived value or `null`). [REQ: Reconciler emits FIX_ISS_ORPHAN_REGISTERED event distinct from FIX_ISS_ESCALATED]
- [ ] 1.6 When no parent-attribution strategy yields a confident match, register with `depends_on=[]` and `phase=state.current_phase` (the SAFE fallback — orphan dispatches alongside peers in the active phase). [REQ: Registration uses parent attribution heuristics]

## 2. Wire reconciler into the monitor loop

- [ ] 2.1 Locate the per-poll entry point in `lib/set_orch/engine.py` monitor loop and call `reconcile_fix_iss_orphans` once per cycle, before dispatch evaluation. [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll]
- [ ] 2.2 Wrap the call in try/except — a reconciler failure MUST NOT halt the poll loop. Log at ERROR with traceback on exception; continue. [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll]

## 3. Make `escalate_change_to_fix_iss` proposals self-attributing

- [ ] 3.1 Annotate `escalate_change_to_fix_iss` in `lib/set_orch/issues/manager.py` to emit an explicit `<!-- parent: <name> -->` HTML comment in the auto-generated `proposal.md` (placed right after the `## Why` section so the reconciler's parent-attribution heuristic finds it deterministically for any future auto-escalation that orphans due to other bugs). [REQ: Registration uses parent attribution heuristics]
- [ ] 3.2 Verify existing readers tolerate the comment: a `proposal.md` parsed by openspec validate, the dashboard's proposal viewer, and the planner's spec-coverage logic SHALL continue to work unchanged. [REQ: Registration uses parent attribution heuristics]

## 4. Tests

- [ ] 4.1 Unit tests for `reconcile_fix_iss_orphans` in `tests/unit/test_fix_iss_orphan_registration.py`: empty `openspec/changes`, single orphan, multiple orphans, already-registered idempotency, missing `proposal.md` warn-skip, missing `tasks.md` ok, parent-attribution all three strategies (comment, why-line, slug-prefix), no-parent fallback to `current_phase`. [REQ: All requirements in fix-iss-orphan-registration spec]
- [ ] 4.2 Race-condition test: spawn two threads — one calling `escalate_change_to_fix_iss`, one calling `reconcile_fix_iss_orphans` — for the same fix-iss name. Assert exactly one registration; assert one `FIX_ISS_ESCALATED` and zero `FIX_ISS_ORPHAN_REGISTERED` (or vice versa, whichever wins). [REQ: Registration is safe under concurrent escalation paths]
- [ ] 4.3 Unit test that the new HTML-comment annotation in `escalate_change_to_fix_iss` produces a parseable `proposal.md`: invoke the function with mocked state, then run `_derive_parent_from_proposal` against the output and assert it returns the expected parent. [REQ: Registration uses parent attribution heuristics]

## 5. Live verification on an active orchestration run

- [ ] 5.1 After landing this change in the framework, restart the running orchestrator on a project that has accumulated orphan `fix-iss-*` directories. The reconciler's first poll SHALL adopt them into state. Verify via `cat orchestration-state.json | jq '.changes[] | select(.name | startswith("fix-iss"))'` — entries should appear with `status="pending"`. [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll]
- [ ] 5.2 Confirm the dispatcher picks up the registered orphans on a subsequent poll cycle (DISPATCH event for each). [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll]
- [ ] 5.3 Confirm `FIX_ISS_ORPHAN_REGISTERED` events appear in `orchestration-events.jsonl`, distinct from any `FIX_ISS_ESCALATED` events. [REQ: Reconciler emits FIX_ISS_ORPHAN_REGISTERED event distinct from FIX_ISS_ESCALATED]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN openspec/changes contains no fix-iss directories THEN reconciler returns empty and emits no events [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll, scenario: empty-directory-listing-produces-no-work]
- [ ] AC-2: WHEN a single orphan fix-iss-007-foo exists with proposal.md and is not in state THEN it is registered as pending and FIX_ISS_ORPHAN_REGISTERED is emitted [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll, scenario: single-orphan-detected-and-registered]
- [ ] AC-3: WHEN state.changes already contains the fix-iss name THEN no duplicate is added and no orphan event fires [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll, scenario: already-registered-fix-iss-is-skipped]
- [ ] AC-4: WHEN two orphans appear on the same poll THEN both register in one locked transaction with two distinct events [REQ: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll, scenario: multiple-orphans-on-the-same-poll]
- [ ] AC-5: WHEN proposal.md has both `<!-- parent: real-parent -->` and a Why-line `Parent change \`other\`` THEN the comment wins [REQ: Registration uses parent attribution heuristics, scenario: explicit-parent-comment-wins]
- [ ] AC-6: WHEN proposal.md has only a Why-line `Parent change \`some-name\`` THEN depends_on is set from that line [REQ: Registration uses parent attribution heuristics, scenario: why-line-attribution]
- [ ] AC-7: WHEN proposal.md has no parent markers but the slug suffix prefixes a state change name THEN the longest-prefix match is chosen [REQ: Registration uses parent attribution heuristics, scenario: slug-prefix-fallback]
- [ ] AC-8: WHEN no parent can be derived THEN depends_on is empty and phase equals current_phase [REQ: Registration uses parent attribution heuristics, scenario: no-parent-derivable]
- [ ] AC-9: WHEN escalate_change_to_fix_iss and reconcile_fix_iss_orphans race for the same name THEN exactly one registration succeeds [REQ: Registration is safe under concurrent escalation paths, scenario: race-with-escalate-change-to-fix-iss]
- [ ] AC-10: WHEN reconciler registers an orphan THEN FIX_ISS_ORPHAN_REGISTERED fires (not FIX_ISS_ESCALATED) [REQ: Reconciler emits FIX_ISS_ORPHAN_REGISTERED event distinct from FIX_ISS_ESCALATED, scenario: orphan-registered-emits-orphan-event]
- [ ] AC-11: WHEN escalate_change_to_fix_iss registers a fix-iss THEN only FIX_ISS_ESCALATED fires (no orphan event) [REQ: Reconciler emits FIX_ISS_ORPHAN_REGISTERED event distinct from FIX_ISS_ESCALATED, scenario: escalation-path-registration-does-not-emit-orphan-event]
- [ ] AC-12: WHEN an orphan dir lacks proposal.md THEN it is skipped with WARN [REQ: Reconciler tolerates malformed orphan directories, scenario: missing-proposal-md-skipped-with-warning]
- [ ] AC-13: WHEN an orphan dir has proposal.md but lacks tasks.md THEN it IS registered (dispatcher handles the gap) [REQ: Reconciler tolerates malformed orphan directories, scenario: missing-tasks-md-does-not-block-registration]
