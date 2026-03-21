# Tasks: orchestration-spec-switch

## 1. Sentinel: spec change detection

- [x] 1.1 Add `detect_spec_change()` function to `bin/set-sentinel` — reads `brief_hash` from state file, computes hash of `--spec` arg, returns 0 if changed. Handle missing state file and missing hash field.
- [x] 1.2 Add `--fresh` flag parsing to sentinel argument handling section

## 2. Sentinel: reset flow

- [x] 2.1 Add `reset_for_spec_switch()` function to `bin/set-sentinel` — deletes `orch/*` tags, calls `clean_old_worktrees()`, prunes merged `change/*` branches only (`git branch --merged main`), removes state/events/digest/plan/lock files
- [x] 2.2 Integrate into sentinel startup: after `fix_stale_state()`, before orchestrator launch — call reset if `detect_spec_change()` returns 0 or `--fresh` flag set

## 3. Dispatcher: change name dedup

- [x] 3.1 Add `_unique_worktree_name()` helper to `lib/set_orch/dispatcher.py` — checks branch + dir existence, appends `-N` suffix if collision
- [x] 3.2 Worktree path dedup included in same function (checks both branch and dir)
- [x] 3.3 Wired into `dispatch_change()` — `wt_name = _unique_worktree_name()` used for branch/worktree/find

## 4. Tests

- [ ] 4.1 Manual test: run sentinel with existing state + different spec → verify reset + fresh start
- [ ] 4.2 Manual test: run sentinel with existing state + same spec → verify resume (no reset)
- [ ] 4.3 Manual test: run sentinel with `--fresh` + same spec → verify forced reset
- [ ] 4.4 Manual test: verify unmerged `change/*` branches survive reset
