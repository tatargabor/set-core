# Spec: orchestration-logging

## Requirements

### R1: Single log file
All orchestration log writers (bash set-orchestrate, bash set-sentinel, Python engine monitor) MUST write to the same file: `~/.local/share/set-core/runtime/{project}/logs/orchestration.log` (resolved via `SetRuntime` / `WT_ORCHESTRATION_LOG`).

### R2: Single rotation mechanism
Only the Python `RotatingFileHandler` (5MB, 3 backups) handles log rotation. Bash rotation logic (`rotate_log()`) MUST be removed to prevent corruption.

### R3: Runtime dir exists before first log
The bash `log()` function MUST ensure the runtime logs directory exists before writing. This is already handled by `mkdir -p` in the existing `log()` function.

### R4: Backward compatibility
The `.claude/orchestration.log` path MAY still be created by old scripts. No consumer should depend on it. The watcher `_find_log()` already prefers the runtime path.

### R5: Documentation references updated
Any user-facing reference to `.claude/orchestration.log` (chat_context, e2e-report) MUST be updated to the runtime path.
