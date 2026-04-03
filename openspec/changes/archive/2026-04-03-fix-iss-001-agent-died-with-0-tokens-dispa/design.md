# Design: Fix bash arithmetic crash in engine.sh

## Context

The Ralph loop engine (`lib/loop/engine.sh`) estimates memory injection size by scanning iteration logs for `<system-reminder>` blocks. This runs after every iteration. When no reminders exist, `grep -oP` returns exit code 1 (no match). Under `set -o pipefail` (inherited from the calling shell), the pipeline `grep ... | wc -c || echo 0` produces `"0\n0"` — both `wc -c` output and the fallback `echo 0`. This crashes bash arithmetic evaluation.

## Goals / Non-Goals

**Goals:**
- Eliminate the arithmetic crash on grep no-match
- Fix unbound variable crash in cleanup trap
- Ensure fix is safe under any combination of `pipefail`, `nounset`, `errexit`

**Non-Goals:**
- Refactoring the context estimation logic
- Changing the reminder scanning approach

## Decisions

### 1. Wrap grep in `{ ... || true; }` subshell group

**Choice:** `{ grep ... || true; }` before the pipe to `wc -c`

**Rationale:** This suppresses grep's exit code 1 (no match) at the source, so `pipefail` never sees a failure in the pipeline. The `|| echo 0` fallback is removed since it's no longer needed and was the cause of the double-output.

**Alternative considered:** `set +o pipefail` locally — rejected because it would require save/restore and could mask real errors.

### 2. Add `${var:-0}` default after assignment

**Choice:** `reminder_chars=${reminder_chars:-0}` after each `wc -c` assignment.

**Rationale:** Belt-and-suspenders defense against empty command substitution (e.g., if `wc -c` somehow produces no output on an unusual system).

### 3. Use `${cleanup_done:-false}` in trap guard

**Choice:** Change `$cleanup_done` to `${cleanup_done:-false}`.

**Rationale:** The trap can fire before `cleanup_done=true` is ever set. Under `set -u` (nounset), this crashes. The default-value syntax handles the uninitialized case.

## Risks / Trade-offs

- [Low risk] The `{ ... || true; }` pattern swallows ALL grep errors, not just "no match" (exit 1). Mitigation: `2>/dev/null` is already present, and any grep failure should default to 0 chars (safe fallback).

## Open Questions

_(none — fix is straightforward)_
