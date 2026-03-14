## Why

Phase 7 of the 8-phase Python migration (per master plan). Three closely related bash modules remain: `monitor.sh` (586 LOC, main orchestration loop), `merger.sh` (672 LOC, merge pipeline + worktree cleanup), and `milestone.sh` (242 LOC, phase milestone checkpoints). Combined ~1500 LOC. These modules own the top-level orchestration control flow — polling, merge queue, replan, token budgets, time limits, self-watchdog, milestone servers, and worktree lifecycle. Migrating them to Python enables structured directive parsing, proper typing for the complex merge pipeline, and testable control flow for the monitor loop.

## What Changes

- New `lib/wt_orch/merger.py` (~400 LOC) with 1:1 function mapping from merger.sh: merge pipeline, worktree cleanup, archive, merge queue, post-merge sync, smoke pipeline
- New `lib/wt_orch/milestone.py` (~150 LOC) with 1:1 function mapping from milestone.sh: milestone checkpoint, email, worktree lifecycle
- New `lib/wt_orch/engine.py` (~400 LOC) with 1:1 function mapping from monitor.sh: main orchestration loop, directive parsing, token budget, time limit, self-watchdog, replan, phase completion
- New CLI subcommands under `wt-orch-core merge *`, `wt-orch-core milestone *`, `wt-orch-core engine *`
- `lib/orchestration/merger.sh`, `milestone.sh`, `monitor.sh` replaced with thin bash wrappers (~50 LOC each)
- Unit tests for all pure-logic functions

## Capabilities

### New Capabilities
- `merge-pipeline`: Merge change pipeline, post-merge verification, smoke pipeline, worktree cleanup, archive, merge queue with retry and conflict fingerprint dedup
- `milestone-checkpoint`: Phase milestone tagging, worktree creation, dev server lifecycle, milestone email, cleanup
- `orchestration-engine`: Main monitor loop, directive parsing, token budget enforcement, time limits, self-watchdog, replan cycle management, phase completion detection

### Modified Capabilities
<!-- No existing spec requirements change — this is a 1:1 reimplementation -->

## Impact

- `lib/orchestration/monitor.sh` — rewritten to thin wrapper
- `lib/orchestration/merger.sh` — rewritten to thin wrapper
- `lib/orchestration/milestone.sh` — rewritten to thin wrapper
- `lib/wt_orch/cli.py` — new `merge`, `milestone`, `engine` subcommand groups
- `lib/wt_orch/merger.py` — new module
- `lib/wt_orch/milestone.py` — new module
- `lib/wt_orch/engine.py` — new module
- `tests/unit/test_merger.py`, `test_milestone.py`, `test_engine.py` — new test files
- Dependencies: existing `state`, `events`, `process`, `notifications`, `verifier`, `dispatcher`, `subprocess_utils` modules
