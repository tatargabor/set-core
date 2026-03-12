## Why

A codebase audit revealed that 86% of shell scripts lack strict mode (`set -euo pipefail`), JSON state updates can silently corrupt data (empty `jq` output overwrites state files), and there is no locking on `state.json` — meaning parallel orchestration operations can race and lose updates. These are not hypothetical risks: memory entries (MEM#e615, MEM#0442) document real production incidents caused by silent failures and state corruption during orchestration runs.

## What Changes

- Introduce `safe_jq_update()` — a centralized JSON write function that validates output before overwriting, preventing state file truncation
- Introduce `with_state_lock()` — `flock`-based mutual exclusion around state.json read-modify-write sequences
- Add `set -euo pipefail` to all 28 entry point scripts (`bin/wt-*`) that currently lack it
- Audit and fix the ~295 instances of `|| true` / `2>/dev/null` error suppression — categorize as intentional (keep), hiding real errors (fix), or unnecessary (remove)
- Add `local` declarations to function variables that currently leak to global scope
- Fix platform-specific bugs: `stat --format=` on macOS (state.sh:395), `grep -oP` non-portable usage (verifier.sh)
- Replace bare `cd` in functions with subshells or `git -C` (dispatcher.sh lines 371, 600)

## Capabilities

### New Capabilities
- `safe-json-state`: Centralized safe JSON state manipulation with validation and flock-based locking
- `strict-mode-enforcement`: Consistent `set -euo pipefail` across all entry points with audit of error suppression patterns

### Modified Capabilities
- `orchestration-engine`: State update functions in state.sh, dispatcher.sh, merger.sh, watchdog.sh will use the new safe_jq_update + with_state_lock primitives
- `error-recovery-recall`: Error suppression audit changes how errors surface — previously hidden failures will now be visible

## Impact

- **lib/orchestration/state.sh** — Major refactor: all jq write calls replaced with safe_jq_update + flock
- **lib/orchestration/dispatcher.sh, merger.sh, watchdog.sh, verifier.sh, monitor.sh** — jq writes replaced, `cd` calls fixed, `local` added
- **bin/wt-*** (28 files) — `set -euo pipefail` added to each
- **lib/orchestration/utils.sh** — New shared functions (safe_jq_update, with_state_lock)
- **Existing tests** — May need updates where `|| true` removal changes exit behavior
- **No breaking changes** to CLI interface or external behavior
