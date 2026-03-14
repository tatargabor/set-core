## 1. Worktree Preparation Functions

- [x] 1.1 Implement `sync_worktree_with_main()` — git merge main into worktree branch, auto-resolve generated file conflicts, abort on real conflicts
- [x] 1.2 Implement `bootstrap_worktree()` — copy .env files, detect package manager, install deps if node_modules missing
- [x] 1.3 Implement `prune_worktree_context()` — remove orchestrator commands from worktree .claude/, git rm tracked files, commit if pruned

## 2. Model Routing

- [x] 2.1 Implement `resolve_change_model()` — three-tier model resolution (explicit > complexity > default), doc-change detection, sonnet override guard

## 3. Core Dispatch Engine

- [x] 3.1 Implement `dispatch_change()` — worktree creation, bootstrap, prune, proposal enrichment (memory, project-knowledge, siblings, design, digest, retry), token reset, wt-loop launch
- [x] 3.2 Implement `dispatch_via_wt_loop()` — start wt-loop in subprocess, poll for loop-state.json, extract terminal PID, update state
- [x] 3.3 Implement `dispatch_ready_changes()` — topological order iteration, phase gating, complexity sort (L>M>S), parallel limit enforcement
- [x] 3.4 Implement proposal enrichment helpers — `_build_dispatch_memory()`, `_build_pk_context()`, `_build_sibling_context()`, `_build_proposal()`

## 4. Lifecycle Management

- [x] 4.1 Implement `pause_change()` — PID identity check via process.check_pid, SIGTERM, status update
- [x] 4.2 Implement `resume_change()` — token snapshot, watchdog baseline, retry context handling (build vs merge), model resolve, wt-loop restart
- [x] 4.3 Implement `resume_stopped_changes()` — iterate stopped changes, resume with worktree or reset to pending
- [x] 4.4 Implement `resume_stalled_changes()` — 300s cooldown check, resume eligible changes

## 5. Recovery

- [x] 5.1 Implement `recover_orphaned_changes()` — detect running/verifying/stalled with no worktree+dead PID, reset to pending, emit CHANGE_RECOVERED
- [x] 5.2 Implement `redispatch_change()` — safe-kill, salvage partial work, build retry_context, clean worktree, reset watchdog, set pending
- [x] 5.3 Implement `retry_failed_builds()` — iterate failed builds, check gate_retry_count, set retry_context with build output, resume

## 6. CLI Bridge

- [x] 6.1 Add `wt-orch-core dispatch` subcommands to cli.py — dispatch-change, dispatch-ready, pause, resume, resume-stopped, resume-stalled, recover-orphans, redispatch, retry-builds, resolve-model, sync-worktree, bootstrap, prune-context
- [x] 6.2 Replace dispatcher.sh functions with thin wrappers calling `wt-orch-core dispatch *`

## 7. Tests

- [x] 7.1 Tests for worktree prep — bootstrap_worktree, _detect_package_manager
- [x] 7.2 Tests for resolve_change_model — explicit model, complexity routing, doc change, sonnet override, default fallback
- [x] 7.3 Tests for dispatch lifecycle — _build_sibling_context, resume_stalled_changes cooldown
- [x] 7.4 Tests for recovery — recover_orphaned_changes, retry_failed_builds
