## Why

E2E MiniShop Run #16 (11/11 merged, 3h13m, 4.6M tokens) exposed 4 framework bugs that required 5 manual interventions. Three bugs are blocking (caused pipeline stalls or deadlocks), one is recurring since Run #3. Fixing these reduces sentinel intervention rate and improves autonomous completion reliability.

## What Changes

- **Separate build-fix retries from verify retries** — build-failure→fix cycles no longer consume `verify_retry_count`, preventing premature retry exhaustion when the agent successfully self-heals build errors
- **Auto-resolve `.claude/*` runtime files during merge** — add prefix-based matching for `.claude/` directory to the generated file conflict resolver, covering `activity.json`, `loop-state.json`, `logs/*`, `ralph-terminal.pid`, `reflection.md`
- **PID-validated sentinel flock guard** — before failing on flock acquisition, check if the PID holding the lock is still alive; if dead, release stale lock and retry
- **Preserve verify gate results across monitor restart** — when monitor resumes and finds a change in "verifying" with all gates passed, proceed to merge instead of re-dispatching

## Capabilities

### New Capabilities
- `build-fix-retry-separation`: Separate retry counter for build-fix iterations vs verify gate retries, preventing budget exhaustion on self-healing builds

### Modified Capabilities
- `verify-gate`: Build-fix retry path uses separate counter; verify gate results preserved across monitor restart
- `merge-conflict-resolution`: Auto-resolve patterns extended with `.claude/` prefix matching for runtime files
- `stale-lock-recovery`: Sentinel flock guard validates PID liveness before rejecting restart

## Impact

- `lib/set_orch/verifier.py` — build retry logic, verify gate result persistence
- `lib/set_orch/engine.py` — monitor resume logic for verifying changes with passed gates
- `lib/set_orch/dispatcher.py` — `_CORE_GENERATED_FILE_PATTERNS` and conflict matching logic
- `bin/set-sentinel` — flock guard with PID validation
- `lib/set_orch/state.py` — new `build_retry_count` field on change dataclass (if needed)
