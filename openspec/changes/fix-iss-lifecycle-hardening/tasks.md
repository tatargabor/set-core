## 1. Orphan purge helper

- [x] 1.1 Add `_purge_fix_iss_child(issue, state_file, project_path, *, reason)` in `lib/set_orch/issues/manager.py` — module-level helper, returns structured result dict `{"state_removed": bool, "dir_removed": bool, "skipped_reason": str|None}` [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.2 Implement safe-remove predicate: return early (no-op, log DEBUG) if `issue.change_name` empty or not `fix-iss-` prefixed [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.3 Skip with WARN (set `skipped_reason="active_dispatch"`) when the child's state entry has status in `dispatched`/`running`/`verifying`/`integrating` [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.4 Skip with DEBUG (set `skipped_reason="already_merged"`) when child status is `merged` [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.5 Perform state entry removal via `locked_state` context: filter `state.changes` to drop the child's name [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.6 Perform openspec dir removal via `shutil.rmtree` on `openspec/changes/<child_name>/` if the path is a directory; skip silently if absent [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.7 Emit INFO log with reason, parent name, child name, and which artifacts were removed [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]
- [x] 1.8 Add unit tests in `tests/unit/test_fix_iss_orphan_purge.py` covering: both-present purge, dir-only, state-only, neither, active-dispatch skip, merged skip, non-fix-iss change_name no-op [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts]

## 2. Native-merge auto-resolve hook

- [x] 2.1 In `lib/set_orch/issues/manager.py:_check_affected_change_merged`, after `self._transition(issue, IssueState.RESOLVED)` and before `return True`, call `_purge_fix_iss_child(issue, state_path, project_path, reason="parent_merged")` [REQ: native-merge-auto-resolve-triggers-orphan-cleanup]
- [x] 2.2 Derive `project_path` from `issue.environment_path` (already available on the issue) — the state_path resolver already uses it [REQ: native-merge-auto-resolve-triggers-orphan-cleanup]
- [x] 2.3 Wrap the purge call in try/except; on any exception log WARN with issue id + parent name but still return True (state transition is primary, cleanup is best-effort) [REQ: native-merge-auto-resolve-triggers-orphan-cleanup]
- [x] 2.4 Emit an additional `fix_iss_orphan_purged` audit entry when the purge actually removed artifacts (not a no-op) [REQ: native-merge-auto-resolve-triggers-orphan-cleanup]
- [x] 2.5 Add unit tests: parent-merged scenario with orphan pending child verifies both transition AND purge; parent-merged with no linked child verifies transition only; purge exception path verifies resolve still succeeds [REQ: native-merge-auto-resolve-triggers-orphan-cleanup]

## 3. Escalation idempotency

- [x] 3.1 In `escalate_change_to_fix_iss` (`lib/set_orch/issues/manager.py`), read the parent change from state near the top of the function; check `parent.fix_iss_child` [REQ: escalation-idempotency-via-fix_iss_child-link]
- [x] 3.2 If the link points at a live child (state entry exists with non-terminal+non-failed status AND dir exists), return the existing name immediately — log INFO, skip proposal write, skip registry register, skip event emit [REQ: escalation-idempotency-via-fix_iss_child-link]
- [x] 3.3 If the link is stale (entry missing OR dir missing OR entry status is `integration-failed`/`merge-failed`), log WARN listing the missing component, clear `parent.fix_iss_child = None` via `update_change_field`, then fall through to the fresh escalation path [REQ: escalation-idempotency-via-fix_iss_child-link]
- [x] 3.4 Do NOT introduce a `force` kwarg — operator-driven re-escalation goes through the new CLI [REQ: escalation-idempotency-via-fix_iss_child-link]
- [x] 3.5 Add unit tests covering: first-time escalation (baseline), re-escalation with live link (no-op return), stale-link-dir-missing re-escalation (auto-repair + fresh claim), stale-link-state-missing re-escalation (same) [REQ: escalation-idempotency-via-fix_iss_child-link]

## 4. Orphan cleanup CLI

- [x] 4.1 Locate the `set-orch-core` entry point (either `bin/set-orch-core` or equivalent) and identify its subcommand dispatch pattern [REQ: cli-command-for-orphan-cleanup]
- [x] 4.2 Add `issues cleanup-orphans` subcommand with flags: `--project <name>` (required), `--dry-run` (no mutations), `--yes` (skip confirmation) [REQ: cli-command-for-orphan-cleanup]
- [x] 4.3 Implement the orphan-scan in a new helper `scan_fix_iss_orphans(project_path) -> list[OrphanRecord]` in `lib/set_orch/issues/manager.py` (module-level, reusable) covering all three criteria from D4 [REQ: cli-command-for-orphan-cleanup]
- [x] 4.4 CLI formats the scan output as a table: parent name, parent status, issue state, state entry present?, dir present?, skip reason [REQ: cli-command-for-orphan-cleanup]
- [x] 4.5 On confirmation (interactive `y` or `--yes`), iterate orphans and call `_purge_fix_iss_child` for each; tally purged / skipped / total and print summary [REQ: cli-command-for-orphan-cleanup]
- [x] 4.6 `--dry-run` skips the confirmation prompt and performs zero mutations; exits 0 regardless of count [REQ: cli-command-for-orphan-cleanup]
- [x] 4.7 Empty scan prints informational line and exits 0 without prompting [REQ: cli-command-for-orphan-cleanup]
- [x] 4.8 Add integration test in `tests/unit/test_fix_iss_cleanup_cli.py` that seeds multiple orphans, runs the scan helper + cleanup iteration, verifies correct removal [REQ: cli-command-for-orphan-cleanup]

## 5. Integration validation

- [x] 5.1 Add an end-to-end regression test in `tests/unit/test_fix_iss_lifecycle_regression.py` reproducing the observed scenario: parent change merges natively, `_check_affected_change_merged` runs, orphan child is auto-purged, re-escalation for the same parent (different trigger) produces a fresh fix-iss without colliding [REQ: auto-resolve-on-parent-merge-cleans-orphan-fix-iss-child] [REQ: escalation-is-idempotent-against-live-parent-child-link]
- [x] 5.2 Verify existing test suite still passes (`pytest tests/unit/test_issue_state_machine.py tests/unit/test_issues_auto_resolve.py tests/unit/test_fix_iss_escalation.py`); note any pre-existing failures unrelated to this change [REQ: auto-resolve-on-parent-merge-cleans-orphan-fix-iss-child]
- [x] 5.3 Manual smoke test: seed a project with an orphan fix-iss child, run `set-orch-core issues cleanup-orphans --project <p> --dry-run`, verify correct listing, then rerun with `--yes` and verify cleanup [REQ: cli-surfaces-orphan-inventory-and-supports-dry-run-cleanup]

## Acceptance Criteria (from spec scenarios)

### fix-iss-orphan-cleanup

- [x] AC-1: WHEN pending fix-iss with dir on disk THEN state + dir removed + INFO log [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: pending-fix-iss-with-dir-on-disk-purged]
- [x] AC-2: WHEN fix-iss is merged THEN helper is a no-op + DEBUG log [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: fix-iss-already-merged-skip]
- [x] AC-3: WHEN fix-iss is dispatched/running THEN helper skips with WARN [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: fix-iss-is-actively-dispatched-skip-with-warn]
- [x] AC-4: WHEN state entry present, dir gone THEN state removed, dir skip silently [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: state-entry-present-dir-already-gone]
- [x] AC-5: WHEN dir present, no state entry THEN dir removed [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: dir-present-no-state-entry]
- [x] AC-6: WHEN neither present THEN full no-op [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: neither-state-nor-dir-full-no-op]
- [x] AC-7: WHEN change_name empty or not fix-iss THEN immediate return [REQ: purge-helper-removes-orphan-fix-iss-child-artifacts, scenario: issue-change_name-is-missing-or-not-a-fix-iss]
- [x] AC-8: WHEN parent merged + pending child THEN transition to RESOLVED + purge [REQ: native-merge-auto-resolve-triggers-orphan-cleanup, scenario: parent-merged-fix-iss-child-purged-on-auto-resolve]
- [x] AC-9: WHEN parent merged + no child linked THEN transition only, purge is no-op [REQ: native-merge-auto-resolve-triggers-orphan-cleanup, scenario: parent-merged-no-fix-iss-child-linked]
- [x] AC-10: WHEN purge raises exception THEN WARN logged, state transition still succeeds [REQ: native-merge-auto-resolve-triggers-orphan-cleanup, scenario: purge-failure-does-not-block-state-transition]
- [x] AC-11: WHEN re-escalation with live prior child THEN return existing name, no side effects [REQ: escalation-idempotency-via-fix_iss_child-link, scenario: re-escalation-with-live-prior-child-return-existing]
- [x] AC-12: WHEN re-escalation with stale link THEN clear link + fresh claim proceeds [REQ: escalation-idempotency-via-fix_iss_child-link, scenario: re-escalation-with-stale-link-clear-and-proceed]
- [x] AC-13: WHEN first-time escalation THEN behaves as before (unchanged baseline) [REQ: escalation-idempotency-via-fix_iss_child-link, scenario: first-time-escalation-unaffected]
- [x] AC-14: WHEN `--dry-run` THEN lists orphans, no mutations, exit 0 [REQ: cli-command-for-orphan-cleanup, scenario: dry-run-lists-orphans-without-modification]
- [x] AC-15: WHEN interactive without `--yes` THEN prompts + only acts on `y` [REQ: cli-command-for-orphan-cleanup, scenario: interactive-cleanup-requires-confirmation]
- [x] AC-16: WHEN `--yes` THEN skips prompt and purges all found [REQ: cli-command-for-orphan-cleanup, scenario: non-interactive-cleanup-with-yes]
- [x] AC-17: Orphan detection matches the 3 criteria (parent-merged + pending child, resolved-issue + pending child, disk-only divergence) [REQ: cli-command-for-orphan-cleanup, scenario: orphan-detection-criteria]
- [x] AC-18: WHEN zero orphans THEN info message + exit 0, no prompt [REQ: cli-command-for-orphan-cleanup, scenario: no-orphans-found]

### issue-state-machine

- [x] AC-19: WHEN native merge + orphan pending child THEN RESOLVED + `fix_iss_orphan_purged` audit entry [REQ: auto-resolve-on-parent-merge-cleans-orphan-fix-iss-child, scenario: native-merge-orphan-pending-fix-iss-child]
- [x] AC-20: WHEN native merge + active child THEN RESOLVED, no purge, WARN log [REQ: auto-resolve-on-parent-merge-cleans-orphan-fix-iss-child, scenario: native-merge-active-fix-iss-child]
- [x] AC-21: WHEN parent has live link THEN re-escalation returns existing name, no new proposal/registry/event [REQ: escalation-is-idempotent-against-live-parent-child-link, scenario: parent-already-linked-prior-child-still-live]
- [x] AC-22: WHEN link stale (entry/dir missing) THEN auto-repair: clear link + fresh claim [REQ: escalation-is-idempotent-against-live-parent-child-link, scenario: parent-linked-but-prior-child-gone-clear-and-re-escalate]
- [x] AC-23: WHEN prior child status `integration-failed`/`merge-failed` THEN proceed with fresh claim, log WARN [REQ: escalation-is-idempotent-against-live-parent-child-link, scenario: parent-linked-but-prior-child-is-terminal-failed]
- [x] AC-24: CLI `--dry-run` prints report without mutation [REQ: cli-surfaces-orphan-inventory-and-supports-dry-run-cleanup, scenario: dry-run-enumeration]
- [x] AC-25: CLI requires confirmation unless `--yes` [REQ: cli-surfaces-orphan-inventory-and-supports-dry-run-cleanup, scenario: interactive-confirmation]
- [x] AC-26: CLI `--yes` batch removes every orphan, prints summary [REQ: cli-surfaces-orphan-inventory-and-supports-dry-run-cleanup, scenario: batch-cleanup-with-yes]
- [x] AC-27: CLI zero-orphan exits 0 without prompting [REQ: cli-surfaces-orphan-inventory-and-supports-dry-run-cleanup, scenario: zero-orphans]
