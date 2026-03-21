# Tasks: run-lifecycle-cleanup

## 1. Archive function

- [x] 1.1 Add `archive_previous_run()` function to `bin/set-sentinel` — checks state file exists and status is terminal, creates `wt/orchestration/runs/<timestamp>/` dir, copies state/events/coverage/findings/state-archive
- [x] 1.2 Write `meta.json` in archive dir — extract spec_hash, status, change counts, started_at from state; add archived_at timestamp
- [x] 1.3 Clean per-run files after archive — delete state, events, findings, lock; reset coverage.json to empty `{"coverage": {}, "uncovered": []}`
- [x] 1.4 Make archive idempotent — skip if state file doesn't exist or status is not terminal

## 2. Integrate into sentinel startup

- [x] 2.1 Call `archive_previous_run()` from sentinel startup when state is done/stopped (before existing cleanup logic at lines 373-419)
- [x] 2.2 Update `reset_for_spec_switch()` — call `archive_previous_run()` at the top before git tag/worktree/branch cleanup
- [x] 2.3 Remove now-redundant state file deletion from `reset_for_spec_switch()` (archive function handles it)

## 3. Integrate into set-orchestrate reset

- [x] 3.1 `cmd_reset --full` — inline archive logic before full reset (copies state/events/coverage/findings to timestamped runs/ dir)
- [x] 3.2 `cmd_reset --partial` — no archive, keep existing behavior (unchanged)

## 4. Preserve digest spec-derived files

- [x] 4.1 Ensure `archive_previous_run()` only cleans `coverage.json` from digest dir, NOT requirements/dependencies/ambiguities/conventions/index
- [x] 4.2 `reset_for_spec_switch()` continues to delete entire digest dir (spec changed = regenerate everything)

## 5. Tests

- [x] 5.1 Verify archive creates correct directory structure with all expected files
- [x] 5.2 Verify coverage.json is reset to empty after archive
- [x] 5.3 Verify digest requirement files are preserved after normal archive
- [x] 5.4 Verify digest dir is deleted on spec switch (existing behavior preserved)
- [x] 5.5 Verify idempotent — calling archive twice doesn't error or duplicate
