# Spec: Orchestration Spec Switch

## Requirements

### REQ-SS-001: Spec change detection
The sentinel MUST detect when the `--spec` argument differs from the stored `brief_hash` in the existing state file and trigger an orchestration reset.

**Acceptance Criteria:**
- [ ] `detect_spec_change()` function reads `brief_hash` from `orchestration-state.json`
- [ ] Computes hash of current `--spec` argument using existing `brief_hash()` utility
- [ ] Returns true (spec changed) or false (same spec, resume)
- [ ] Handles missing state file (fresh start, no switch)
- [ ] Handles missing `brief_hash` in state (legacy state, treat as fresh)

### REQ-SS-002: Orchestration reset on spec change
When a spec change is detected, the sentinel MUST reset all orchestration state while preserving git history.

**Acceptance Criteria:**
- [ ] Removes `orchestration-state.json`, events file, lock files
- [ ] Removes `wt/orchestration/digest/` directory
- [ ] Removes `wt/orchestration/plan.json`
- [ ] Does NOT modify main branch or git commits
- [ ] Logs clear message with old and new spec paths

### REQ-SS-003: `orch/*` tag cleanup on spec switch
The reset MUST delete `orch/*` tags from prior completed runs so that `clean_old_worktrees()` is not blocked.

**Acceptance Criteria:**
- [ ] `orch/*` tags deleted before `clean_old_worktrees()` call
- [ ] Tags only deleted during spec-switch, NOT during normal resume
- [ ] Log shows number of tags removed

### REQ-SS-004: Safe branch cleanup
The reset MUST only delete `change/*` branches that are merged to main. Unmerged branches are preserved.

**Acceptance Criteria:**
- [ ] Uses `git branch --merged main` to identify safe-to-delete branches
- [ ] Only deletes branches matching `change/*` pattern
- [ ] Unmerged `change/*` branches remain intact
- [ ] Log shows number of branches pruned

### REQ-SS-005: `--fresh` flag
The sentinel MUST accept a `--fresh` flag that forces orchestration reset even when the spec hash matches.

**Acceptance Criteria:**
- [ ] `--fresh` parsed in argument handling
- [ ] Triggers same reset flow as spec-change detection
- [ ] Works with same or different spec path

### REQ-SS-006: Change name dedup on dispatch
The dispatcher MUST check for existing `change/<name>` branches before creating new ones and append a numeric suffix if collision detected.

**Acceptance Criteria:**
- [ ] Checks `git branch --list change/<name>` before creating
- [ ] Appends `-2`, `-3`, etc. if branch exists
- [ ] Same dedup for worktree path
- [ ] State updated with actual branch/worktree name used

### REQ-SS-007: Flock guard
All spec-switch logic MUST run inside the existing flock guard, after `fix_stale_state()`.

**Acceptance Criteria:**
- [ ] Detection + reset happens after flock acquired (line ~147)
- [ ] Detection + reset happens after `fix_stale_state()` (line ~620)
- [ ] No race window between detection and reset
