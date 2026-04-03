# Proposal: Fix bash arithmetic crash in engine.sh token estimation

## Why

The Ralph loop's token/memory estimation code in `lib/loop/engine.sh` crashes with a bash arithmetic error when `set -o pipefail` is active. The pattern `grep ... | wc -c || echo 0` produces a multi-line value (`"0\n0"`) when grep finds no matches — grep exits 1, pipefail propagates the failure, `wc -c` outputs `0`, and `|| echo 0` also outputs `0`, resulting in `"0\n0"` being assigned. The subsequent `[[ $reminder_chars -eq 0 ]]` arithmetic test fails, crashing the agent. Additionally, the `cleanup_done` variable is uninitialized when the trap fires, causing an unbound variable error under `set -u`.

## What Changes

- **Fix grep|wc pipeline**: Wrap grep in `{ grep ... || true; }` to suppress the non-match exit code before piping to `wc -c`, preventing the multi-line output
- **Add default value guards**: Use `${reminder_chars:-0}` after each assignment to handle empty/unset edge cases
- **Fix unbound cleanup_done**: Use `${cleanup_done:-false}` in the cleanup trap guard to prevent crash under `set -u`

## Capabilities

### New Capabilities
_(none)_

### Modified Capabilities
- `loop-engine`: Fix arithmetic crash in context breakdown estimation code path

## Impact

- **`lib/loop/engine.sh`**: Lines 85-90 (cleanup guard) and 589-598 (memory injection estimation)
- **All consumer projects**: Any project using set-core's Ralph loop is affected — the crash is non-deterministic (depends on whether system-reminder blocks exist in iteration output)
- **No API or config changes**: Pure bug fix, no behavioral change when code works correctly
