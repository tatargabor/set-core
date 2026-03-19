## Context

The set-core codebase is ~31K lines of Bash across 79 files. A quality audit revealed:

- **86% of files** lack `set -euo pipefail` — errors silently propagate
- **940 jq calls** across 41 files — the core state manipulation pattern (`mktemp` + `jq` + `mv`) does not validate jq output, meaning a failed jq command can overwrite state.json with an empty file
- **No locking** on state.json — parallel orchestration operations (dispatcher, merger, monitor, watchdog) can race and lose updates
- **295+ `|| true` / `2>/dev/null` patterns** — many hide real errors
- Known production incidents: orphaned processes (MEM#e615), merge conflict loops (MEM#0442), `set -euo pipefail` killing `grep -v` with no matches (MEM#57fc)

Current state write pattern in `state.sh`:
```bash
update_state_field() {
    local tmp
    tmp=$(mktemp)
    jq ".$field = $value" "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
}
```
If `jq` fails (bad JSON, invalid filter), `$tmp` is empty, and `mv` overwrites the state file with nothing.

## Goals / Non-Goals

**Goals:**
- Eliminate state file corruption risk from failed jq writes
- Serialize concurrent state.json access with flock
- Make errors visible by adding strict mode to all entry points
- Classify and fix error suppression patterns systematically
- Fix known platform-specific bugs (macOS stat, non-portable grep)

**Non-Goals:**
- Rewriting the codebase in another language (Rust, Go, etc.)
- Changing the external CLI interface or behavior
- Adding new features — this is strictly defensive hardening
- Full test coverage of all modules (targeted tests for new code only)
- Refactoring the jq-based state model to something else (e.g., SQLite)

## Decisions

### D1: safe_jq_update as a centralized write primitive

**Decision:** Create a single `safe_jq_update()` function in `lib/orchestration/utils.sh` that all JSON state writes go through.

**Rationale:** Currently 24+ mktemp/jq/mv sequences are scattered across state.sh, dispatcher.sh, merger.sh, watchdog.sh. Each is independently fragile. A single function with validation means fixing the pattern once.

**Implementation:**
```bash
safe_jq_update() {
    local file="$1"; shift
    local tmp
    tmp=$(mktemp)
    trap 'rm -f "$tmp"' RETURN

    if ! jq "$@" "$file" > "$tmp"; then
        log_error "safe_jq_update: jq failed on $file with args: $*"
        return 1
    fi

    if [[ ! -s "$tmp" ]]; then
        log_error "safe_jq_update: jq produced empty output for $file"
        return 1
    fi

    mv "$tmp" "$file"
}
```

**Alternatives considered:**
- Inline validation at each call site — rejected because 24+ sites would need identical fixes
- Python wrapper for JSON — rejected because it adds a runtime dependency to every state operation

### D2: flock-based state locking

**Decision:** Introduce `with_state_lock()` that wraps state reads and writes in an exclusive flock.

**Rationale:** The orchestrator has multiple concurrent writers: dispatcher (dispatching/updating changes), merger (updating merge status), monitor (polling/updating), watchdog (crash recovery). Without locking, a read-modify-write sequence in one function can be interleaved with another, losing the first update.

**Implementation:**
```bash
with_state_lock() {
    (
        flock --timeout 10 200 || {
            log_error "with_state_lock: timeout acquiring lock on $STATE_FILENAME"
            return 1
        }
        "$@"
    ) 200>"${STATE_FILENAME}.lock"
}
```

**Usage pattern:**
```bash
# Before (unsafe):
update_change_field "my-change" "status" '"merged"'

# After (safe):
with_state_lock update_change_field "my-change" "status" '"merged"'
```

**Alternatives considered:**
- Advisory file locking with `mkdir` — rejected because not atomic on NFS (irrelevant here, but flock is standard)
- Always lock inside `update_change_field` — chosen as a SECONDARY approach: `update_change_field` and `update_state_field` will internally acquire the lock, so callers don't need to change. `with_state_lock` is exposed for compound operations (read + decide + write).

**Decision refinement:** Lock internally in `update_state_field` and `update_change_field`. Expose `with_state_lock` for compound read-modify-write sequences that need atomicity across multiple operations.

### D3: Strict mode rollout strategy

**Decision:** Add `set -euo pipefail` to all `bin/wt-*` entry points. Do NOT add it to `lib/` files (they are sourced and inherit from the caller).

**Rationale:** From MEM#57fc, we know that `set -euo pipefail` can break `grep -v` with no matches (exit code 1 under `set -e`). The rollout must be paired with an audit of patterns that fail under strict mode.

**Known patterns that break under `set -e`:**
- `grep -v` / `grep -c` with no matches → use `|| true` intentionally
- `local var=$(command_that_fails)` → `local` masks the exit code, need `local var; var=$(...)`
- Arithmetic on unset variables under `set -u` → need `${var:-0}` defaults

**Approach:** For each entry point:
1. Add `set -euo pipefail`
2. Run the command's test suite
3. Fix failures caused by strict mode
4. Categorize each `|| true` as intentional (keep with comment) or accidental (remove)

### D4: Error suppression classification

**Decision:** Audit all ~295 instances of `|| true` and `2>/dev/null` and classify into three categories:

| Category | Action | Example |
|----------|--------|---------|
| **Intentional** | Keep + add `# expected: ...` comment | `git show-ref ... 2>/dev/null` (branch may not exist) |
| **Error-hiding** | Remove suppression, add proper error handling | `jq ... 2>/dev/null \|\| true` (hides parse errors) |
| **Unnecessary** | Remove entirely | `rm -f "$tmp" \|\| true` (-f already suppresses) |

### D5: Platform compatibility fixes

**Decision:** Fix the two known non-portable patterns:

1. `state.sh:395` — `stat --format=%Y` → add macOS fallback chain:
   ```bash
   local mtime
   mtime=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null || echo 0)
   ```

2. `verifier.sh:1068` — `grep -oP` (Perl regex) → replace with POSIX-compatible alternative using `grep -oE` or `sed`.

## Risks / Trade-offs

**[Risk: Strict mode breaks existing functionality]**
- Mitigation: Rollout per-file with test runs. Known `grep` issue from MEM#57fc is already documented. Keep `|| true` where intentional but comment it.

**[Risk: flock overhead on every state write]**
- Mitigation: flock is essentially zero-cost when uncontended (~1 microsecond). Under contention, the 10-second timeout prevents deadlocks. The orchestrator already uses flock for memory (MEM#9434) without issues.

**[Risk: Changing error suppression surfaces new failures]**
- Mitigation: Classification audit before removal. Each removal is a separate, testable change. Existing tests catch regressions.

**[Risk: Compound state operations need explicit with_state_lock]**
- Mitigation: Identify all compound operations during implementation and wrap them. The most critical ones are in `update_change_field` (read old status → write new status → emit event) and `reconstruct_state_from_events`.

## Migration Plan

1. **Phase 1 (safe_jq_update + flock):** Add new functions to utils.sh, migrate state.sh callers first, then dispatcher/merger/watchdog
2. **Phase 2 (strict mode):** Add `set -euo pipefail` to entry points one at a time, fixing breakage as found
3. **Phase 3 (error suppression audit):** Classify and fix `|| true` patterns
4. **Phase 4 (platform + local):** Fix stat/grep portability, add missing local declarations

Each phase is independently deployable. Phase 1 is the highest value.
