# Spec: Comprehensive Logging and E2E Fixes

## Overview
Add DEBUG/WARNING logging to all ~100 silent failure paths, fix broken E2E two-phase gate and coverage gate, update sentinel prompt for log awareness.

## Requirements

### REQ-LOG-010: Every return path logs why
Every function returning empty/None/False/[] logs at DEBUG level with the reason and the path/input that caused it.

### REQ-LOG-011: Every fallback logs at WARNING
When an except handler falls back to a default value, log at WARNING level showing what failed and what fallback was used.

### REQ-LOG-012: Every path resolution is visible
When constructing file paths (digest_dir, wt_path, state_file, plan_path), log the resolved path at DEBUG level so post-mortem analysis can trace which directory was used.

### REQ-LOG-013: Gate executor entry/exit logging
Every gate executor logs START (with change, wt_path, command) and END (with result, elapsed_ms) at INFO level.

### REQ-FIX-001: Own spec detection works post-integration-merge
`_detect_own_spec_files()` correctly identifies change-owned spec files after main has been merged into the branch, using filesystem comparison instead of git merge-base.

### REQ-FIX-002: Coverage gate uses correct digest path
Coverage gate in `_run_integration_gates()` resolves digest_dir from state_file parent, not SetRuntime().

### REQ-FIX-003: Manifest validated at agent completion
`handle_change_done()` scans worktree for actual spec files and updates e2e-manifest.json before gates run.

### REQ-FIX-004: SetRuntime() eliminated from hot paths
All `SetRuntime().digest_dir` calls in merger.py and engine.py replaced with state_file-relative resolution.

### REQ-SENT-001: Sentinel log scanning directive
Sentinel prompt includes directive to grep for `[ANOMALY]` and WARNING in orchestration logs, investigate root causes, and add missing logging alongside bug fixes.

### REQ-BASH-001: Bash script logging at decision points
Shell scripts (set-orchestrate, set-merge) log key decisions (which python, which config, which state file) using consistent log_info/log_warn helpers.
