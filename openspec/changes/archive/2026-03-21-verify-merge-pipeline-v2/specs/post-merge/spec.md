# Spec: Post-Merge Simplification

## Requirements

### REQ-PM-001: Remove redundant post-merge checks
After ff-only merge, the code on main is bitwise identical to the verified worktree. Smoke and scope checks are redundant.

**Acceptance Criteria:**
- [ ] AC1: `_run_smoke_pipeline()` call removed from `merge_change()`
- [ ] AC2: `verify_merge_scope()` call removed from `merge_change()`
- [ ] AC3: Post-merge steps preserved: deps_install, custom_cmd, plugin_directives, i18n_sidecar, hooks, cleanup, worktree_sync
- [ ] AC4: `_run_smoke_pipeline()` function removed if no other callers exist; kept only if still referenced elsewhere
- [ ] AC5: Smoke-related state fields (`smoke_result`) no longer set during merge — `MergeResult` return updated
