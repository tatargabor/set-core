## Why

When a change fails during orchestration (e.g., due to spec issues, budget exhaustion, or implementation complexity), it blocks the entire pipeline if other changes depend on it — even indirectly through the dependency graph. Currently the only options are to fix the failing change or manually hack the state file. We need a clean "skip" mechanism that marks a failed/stalled change as accepted-but-not-implemented, allowing the pipeline to continue while preserving full traceability in reporting.

## What Changes

- New `wt-orchestrate skip <name>` CLI command to mark a change as "skipped"
- `deps_satisfied()` treats "skipped" as terminal (same as "merged") for dependency resolution
- Monitor loop counts "skipped" as terminal — no active processing needed
- HTML reporter shows "skipped" with distinct amber/yellow styling, separate from merged (green) and failed (red)
- Quality gate summary in final report distinguishes skipped vs failed vs merged counts
- State file records skip reason and timestamp for audit trail

## Capabilities

### New Capabilities
- `orchestration-skip`: CLI command, state transitions, dependency resolution, and reporting for skipping changes during orchestration

### Modified Capabilities
- `orchestration-engine`: deps_satisfied() accepts "skipped" as terminal status; monitor completion logic includes skipped count
- `orchestration-html-report`: New CSS class and status display for skipped changes; summary section includes skipped count

## Impact

- `lib/orchestration/state.sh` — deps_satisfied(), status validation
- `lib/orchestration/monitor.sh` — terminal status check, completion condition
- `lib/orchestration/reporter.sh` — CSS, status rendering, summary stats
- `bin/wt-orchestrate` — new `skip` subcommand
- State JSON — new "skipped" status value with metadata (reason, timestamp)
