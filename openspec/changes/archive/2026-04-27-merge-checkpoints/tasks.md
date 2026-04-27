## 1. Checkpoint Save (merger hook)

- [ ] 1.1 Create `_save_merge_checkpoint()` function in `lib/set_orch/merger.py` that saves manifest entry + progress file snapshots [REQ: checkpoint-manifest-entry-after-merge]
- [ ] 1.2 Add manifest JSONL append: change name, commit SHA, phase, timestamp, merged_so_far list [REQ: checkpoint-manifest-entry-after-merge]
- [ ] 1.3 Add progress file snapshot: copy `coverage-merged.json` and `review-findings.jsonl` to `set/orchestration/checkpoints/orch-{change_name}/` [REQ: progress-file-snapshot-at-merge-time]
- [ ] 1.4 Hook `_save_merge_checkpoint()` in `merge_change()` after `archive_change()` (line ~655) and before `_remove_from_merge_queue()` [REQ: hook-point-in-merger-pipeline]
- [ ] 1.5 Ensure checkpoint save failure is WARNING, not fatal — merge continues regardless [REQ: hook-point-in-merger-pipeline]

## 2. Checkpoint List (Python + API)

- [ ] 2.1 Create `list_checkpoints(project_path)` function in `lib/set_orch/recovery.py` that parses manifest JSONL [REQ: list-checkpoints-from-python]
- [ ] 2.2 Handle missing manifest file (return empty list) and malformed JSONL lines (skip + warn) [REQ: list-checkpoints-api]
- [ ] 2.3 Add GET `/api/{project}/checkpoints` endpoint in `lib/set_orch/api/actions.py` returning JSON array [REQ: list-checkpoints-api]

## 3. Recovery Enhancement

- [ ] 3.1 Update `_reset_progress_files()` in `recovery.py` to check for checkpoint snapshot dir first [REQ: progress-restore-from-checkpoint]
- [ ] 3.2 If checkpoint dir exists, copy progress files from snapshot to canonical locations [REQ: progress-restore-from-checkpoint]
- [ ] 3.3 If no checkpoint dir, fall back to existing filtering logic (backward compat) [REQ: progress-restore-fallback-to-filtering]
- [ ] 3.4 Save `set/orchestration/checkpoints/` to temp before `git reset --hard` and restore after (same pattern as archive dirs) [REQ: checkpoint-manifest-preserved-during-recovery]
- [ ] 3.5 Update `render_preview()` to show checkpoint-based restore when available [REQ: progress-restore-from-checkpoint]

## 4. Web UI + API Integration

- [ ] 4.1 Add POST `/api/{project}/recover` endpoint that calls `recover_to_change()` with `yes=True` [REQ: list-checkpoints-api]
- [ ] 4.2 Add checkpoint list display on the dashboard (table: change, phase, date, commit) [REQ: list-checkpoints-api]
- [ ] 4.3 Add "Restore to this point" button per checkpoint row, calling the recover endpoint [REQ: list-checkpoints-api]

## 5. Documentation

- [ ] 5.1 Add recovery/checkpoint section to docs explaining: why checkpoints exist, how to list them, how to restore [REQ: checkpoint-manifest-entry-after-merge]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN first change merges THEN manifest.jsonl created with one record [REQ: checkpoint-manifest-entry-after-merge, scenario: first-change-merges]
- [ ] AC-2: WHEN subsequent change merges THEN new record appended with updated merged_so_far [REQ: checkpoint-manifest-entry-after-merge, scenario: subsequent-change-merges]
- [ ] AC-3: WHEN coverage-merged.json and review-findings.jsonl exist at merge time THEN both copied to checkpoint dir [REQ: progress-file-snapshot-at-merge-time, scenario: coverage-and-findings-are-snapshot]
- [ ] AC-4: WHEN progress files don't exist yet THEN checkpoint dir still created (empty or partial) [REQ: progress-file-snapshot-at-merge-time, scenario: missing-progress-files]
- [ ] AC-5: WHEN GET /api/{project}/checkpoints called with 3 checkpoints THEN JSON array of 3 records returned [REQ: list-checkpoints-api, scenario: project-with-checkpoints]
- [ ] AC-6: WHEN no manifest exists THEN empty array returned [REQ: list-checkpoints-api, scenario: project-with-no-checkpoints]
- [ ] AC-7: WHEN recovery targets a change with checkpoint dir THEN progress files restored from snapshot [REQ: progress-restore-from-checkpoint, scenario: progress-restore-from-checkpoint]
- [ ] AC-8: WHEN recovery targets a change without checkpoint dir THEN legacy filtering used [REQ: progress-restore-fallback-to-filtering, scenario: progress-restore-fallback-to-filtering]
- [ ] AC-9: WHEN git reset --hard runs during recovery THEN checkpoints dir is preserved [REQ: checkpoint-manifest-preserved-during-recovery, scenario: checkpoint-manifest-preserved-during-recovery]
