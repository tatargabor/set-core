# Tasks: Isolation Backend

## 1. Backend Interface & Implementations

- [ ] 1.1 Create `lib/set_orch/isolation.py` with `IsolationBackend` ABC defining `create()`, `remove()`, `list_active()`, `sync_with_main()` methods [REQ: backend-interface-abstraction]
- [ ] 1.2 Implement `WorktreeBackend` wrapping existing `git worktree add/remove/list` logic [REQ: worktree-backend]
- [ ] 1.3 Implement `BranchCloneBackend` using `git clone --branch --single-branch` for create, `shutil.rmtree` for remove, path scanning for list [REQ: branch-clone-backend]
- [ ] 1.4 Add `get_isolation_backend(config)` factory function that reads `execution.isolation` and returns the correct backend instance [REQ: backend-interface-abstraction]

## 2. Config Integration

- [ ] 2.1 Add `execution.isolation` key support to orchestration config parsing (`config.py`) with default value `worktree` [REQ: backend-interface-abstraction]
- [ ] 2.2 Instantiate backend at orchestrator startup (`engine.py`) and thread it through dispatch/merge/plan calls [REQ: backend-interface-abstraction]

## 3. Dispatcher Migration

- [ ] 3.1 Replace `git worktree remove --force` in `redispatch_change()` (dispatcher.py:713) with `backend.remove()` [REQ: backend-interface-abstraction]
- [ ] 3.2 Replace `git worktree list --porcelain` in `_find_existing_worktree()` (dispatcher.py:805) with `backend.list_active()` [REQ: backend-interface-abstraction]
- [ ] 3.3 Replace worktree creation in dispatch flow (dispatcher.py, calls to wt-new) with `backend.create()` [REQ: backend-interface-abstraction]
- [ ] 3.4 Replace `sync_worktree_with_main()` (dispatcher.py:203) to delegate to `backend.sync_with_main()` [REQ: backend-interface-abstraction]

## 4. Merger & Planner Migration

- [ ] 4.1 Replace `git worktree remove --force` in `cleanup_worktree()` (merger.py:172) with `backend.remove()` [REQ: backend-interface-abstraction]
- [ ] 4.2 Replace `git worktree list --porcelain` in planner.py:1378 with `backend.list_active()` [REQ: backend-interface-abstraction]
- [ ] 4.3 Replace `git worktree list --porcelain` in api.py:172 with `backend.list_active()` [REQ: backend-interface-abstraction]

## 5. Milestone Migration

- [ ] 5.1 Replace `git worktree add/remove` calls in milestone.py (lines 70, 262, 319) with `backend.create()`/`backend.remove()` [REQ: backend-interface-abstraction]

## 6. CLI Script Migration

- [ ] 6.1 Add `set-orch-core isolation create` and `set-orch-core isolation remove` thin CLI entry points that call the Python backend [REQ: cli-backend-delegation]
- [ ] 6.2 Modify `bin/wt-new` to call `set-orch-core isolation create` instead of `git worktree add` (keep bootstrap steps in bash) [REQ: cli-backend-delegation]
- [ ] 6.3 Modify `bin/wt-close` to call `set-orch-core isolation remove` instead of `git worktree remove` (keep branch cleanup in bash) [REQ: cli-backend-delegation]

## 7. Tests

- [ ] 7.1 Unit tests for `WorktreeBackend` — create, remove, list in a temp git repo [REQ: worktree-backend]
- [ ] 7.2 Unit tests for `BranchCloneBackend` — create, remove, list, sync in a temp git repo [REQ: branch-clone-backend]
- [ ] 7.3 Unit test for `get_isolation_backend()` factory with both config values [REQ: backend-interface-abstraction]
- [ ] 7.4 Integration test: full dispatch→merge cycle with branch-clone backend [REQ: branch-clone-backend]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN orchestrator starts with `execution.isolation: branch-clone` THEN all isolation operations use BranchCloneBackend [REQ: backend-interface-abstraction, scenario: backend-is-resolved-from-config]
- [ ] AC-2: WHEN no `execution.isolation` key exists THEN system uses WorktreeBackend [REQ: backend-interface-abstraction, scenario: default-backend-is-worktree]
- [ ] AC-3: WHEN WorktreeBackend.create() is called THEN `git worktree add` executes and path is returned [REQ: worktree-backend, scenario: create-via-worktree-backend]
- [ ] AC-4: WHEN WorktreeBackend.remove() is called THEN `git worktree remove --force` executes [REQ: worktree-backend, scenario: remove-via-worktree-backend]
- [ ] AC-5: WHEN WorktreeBackend.list_active() is called THEN `git worktree list --porcelain` results are parsed [REQ: worktree-backend, scenario: list-via-worktree-backend]
- [ ] AC-6: WHEN BranchCloneBackend.create() is called THEN `git clone --branch --single-branch` executes and path is returned [REQ: branch-clone-backend, scenario: create-via-branch-clone-backend]
- [ ] AC-7: WHEN BranchCloneBackend.remove() is called THEN clone directory is deleted and branch removed from source [REQ: branch-clone-backend, scenario: remove-via-branch-clone-backend]
- [ ] AC-8: WHEN BranchCloneBackend.list_active() is called THEN active clones are found by path pattern [REQ: branch-clone-backend, scenario: list-via-branch-clone-backend]
- [ ] AC-9: WHEN BranchCloneBackend.sync_with_main() is called THEN main branch changes are merged into clone [REQ: branch-clone-backend, scenario: sync-clone-with-main]
- [ ] AC-10: WHEN change is dispatched with either backend THEN worktree_path in state.json contains the path [REQ: path-convention-preserved, scenario: state-compatibility]
- [ ] AC-11: WHEN wt-new runs with branch-clone config THEN clone is created with identical output format [REQ: cli-backend-delegation, scenario: wt-new-uses-configured-backend]
- [ ] AC-12: WHEN wt-close runs with branch-clone config THEN clone is removed with identical CLI behavior [REQ: cli-backend-delegation, scenario: wt-close-uses-configured-backend]
