# Design: Fix engine.sh arithmetic crash (ISS-001)

## Context

`lib/loop/engine.sh` sources `set-common.sh` which sets `set -euo pipefail`. The context-tracking section (lines ~589-600) uses `grep | wc -c` and `sed | wc -c` pipelines to estimate memory injection size. When grep finds no matches (exit 1), `pipefail` propagates the failure, and the `|| true` inside `{ grep ... || true; }` fires — but its output ("" or newline) concatenates with wc's output, producing multi-line strings like `"0\n0"` that fail in `$(( ))` arithmetic.

The trap handler references `cleanup_done` which is declared with `local` in the parent function scope but may not be visible when the trap fires in certain contexts under `set -u`.

## Goals / Non-Goals

**Goals:**
- Fix the three crash sites so ralph loop survives past iteration 1
- Minimal, surgical changes — no refactoring

**Non-Goals:**
- Changing the context estimation algorithm
- Removing `set -euo pipefail`

## Decisions

### 1. Wrap grep/sed in `{ ... || true; }` groups
**Choice:** Keep the existing `{ cmd || true; } | wc -c` pattern but ensure it's correctly scoped.
**Rationale:** The pattern is correct when `|| true` is inside the braces — the group exits 0, and `wc -c` gets clean input. No need for a different approach.

### 2. Add `${var:-0}` default guards
**Choice:** Use `reminder_chars=${reminder_chars:-0}` after each command substitution.
**Rationale:** Belt-and-suspenders defense — even if the command substitution somehow produces empty output, the arithmetic won't crash.

### 3. Use `${cleanup_done:-false}` in trap handler
**Choice:** Default-value expansion in the condition check.
**Rationale:** Simplest fix — no need to change variable declaration scope. The guard handles all edge cases where the trap fires early.

## Risks / Trade-offs

- [Risk] Fix is bash-version-sensitive → Tested pattern works on bash 4.4+ which is the minimum for set-core
- [Risk] Edge case in very large log files → `wc -c` handles arbitrary input sizes, no risk

## Open Questions

None — fix is well-understood and verified.
