# Tasks: Integration Test Orchestration

## 1. Test Infrastructure

- [x] 1.1 Create `tests/integration/conftest.py` with git repo fixtures (setup_repo, create_branch, create_state_file factories) [REQ: state-persistence-round-trip]
- [x] 1.2 Create stub CLI scripts in `tests/integration/fixtures/bin/` (set-merge, openspec, set-close) [REQ: merge-conflict-detection-and-status-transition]
- [x] 1.3 Create PATH override fixture that prepends stub bin dir + patches hook/event systems [REQ: merge-conflict-detection-and-status-transition]

## 2. Merge Pipeline Tests

- [x] 2.1 Test clean merge → status="merged" and git state correct [REQ: merge-conflict-detection-and-status-transition]
- [x] 2.2 Test conflict merge → status="merge-blocked" [REQ: merge-conflict-detection-and-status-transition]
- [x] 2.3 Test no conflict markers on main after successful merge [REQ: merge-conflict-detection-and-status-transition]
- [x] 2.4 Test already-merged branch (ancestor of HEAD) → skip_merged [REQ: already-merged-branch-detection]
- [x] 2.5 Test deleted branch → skip_merged [REQ: already-merged-branch-detection]
- [ ] 2.6 Test conflict fingerprint dedup — same conflict → immediate merge-blocked [REQ: conflict-fingerprint-deduplication]
- [x] 2.7 Test merge queue sequential drain — 3 changes merged in order [REQ: merge-queue-drain-ordering]
- [x] 2.8 Test generated file (.gitattributes merge=ours) auto-resolution [REQ: generated-file-auto-resolution]

## 3. State Machine Tests

- [x] 3.1 Test dependency cascade — A fails → B,C (transitive deps) auto-fail [REQ: dependency-cascade-on-failure]
- [x] 3.2 Test partial dependency — A fails, C (no dep) unaffected [REQ: dependency-cascade-on-failure]
- [x] 3.3 Test dependency satisfaction — A merged → B dispatchable [REQ: dependency-satisfaction-dispatch]
- [x] 3.4 Test dependency not satisfied — A running → B stays pending [REQ: dependency-satisfaction-dispatch]
- [x] 3.5 Test state save/load round-trip preserves all fields [REQ: state-persistence-round-trip]
- [x] 3.6 Test unknown fields preserved via extras dict [REQ: state-persistence-round-trip]
- [x] 3.7 Test missing worktree path → no crash [REQ: missing-worktree-recovery]

## 4. Verify Gate Tests

- [x] 4.1 Test node_modules/ ignored in git_has_uncommitted_work() [REQ: dirty-worktree-handling-before-verify]
- [x] 4.2 Test untracked files auto-committed before gates [REQ: dirty-worktree-handling-before-verify]
- [ ] 4.3 Test verify gate exception → not stuck in "verifying" [REQ: verify-gate-exception-recovery]
- [x] 4.4 Test post-merge sync ordering — sync called after archive [REQ: post-merge-sync-ordering]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change branch has no conflicts with main THEN merge_change() returns success=True, status="merged" [REQ: merge-conflict-detection-and-status-transition, scenario: clean-merge-succeeds]
- [x] AC-2: WHEN two changes modify the same file and the first is merged THEN merge_change() for the second returns success=False, status="merge-blocked" [REQ: merge-conflict-detection-and-status-transition, scenario: conflicting-merge-detected]
- [x] AC-3: WHEN any merge completes successfully THEN no file on main contains conflict markers [REQ: merge-conflict-detection-and-status-transition, scenario: no-conflict-markers-on-main-after-merge]
- [x] AC-4: WHEN a change branch has already been merged into main THEN merge_change() returns status="merged", smoke_result="skip_merged" [REQ: already-merged-branch-detection, scenario: branch-is-ancestor-of-head]
- [x] AC-5: WHEN a change branch no longer exists THEN merge_change() returns status="merged", smoke_result="skip_merged" [REQ: already-merged-branch-detection, scenario: branch-deleted]
- [ ] AC-6: WHEN a merge conflict produces the same fingerprint as the previous attempt THEN the change is marked merge-blocked immediately [REQ: conflict-fingerprint-deduplication, scenario: same-conflict-twice]
- [x] AC-7: WHEN change A fails and B depends_on A THEN B is automatically marked "failed" [REQ: dependency-cascade-on-failure, scenario: single-dependency-fails]
- [x] AC-8: WHEN change A fails, B depends_on A, C depends_on B THEN both B and C are marked "failed" [REQ: dependency-cascade-on-failure, scenario: transitive-dependency-chain]
- [x] AC-9: WHEN node_modules/ contains modified files THEN git_has_uncommitted_work() returns False [REQ: dirty-worktree-handling-before-verify, scenario: node-modules-ignored-in-dirty-check]
- [ ] AC-10: WHEN a verify gate raises an unhandled exception THEN the change does NOT remain in "verifying" status [REQ: verify-gate-exception-recovery, scenario: gate-throws-exception]
- [x] AC-11: WHEN a change's worktree_path points to a non-existent directory THEN the system does NOT crash [REQ: missing-worktree-recovery, scenario: worktree-path-deleted-but-state-references-it]
- [x] AC-12: WHEN state is saved to JSON and loaded back THEN all change fields are preserved exactly [REQ: state-persistence-round-trip, scenario: full-round-trip]
