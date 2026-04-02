# Design: merger-gate-integrity

## Decisions

### D1: "skipped" is a new terminal status
No-op changes get `status: "skipped"` — a terminal state like "merged" but meaning "never implemented, branch had no commits." The monitor treats it as complete (no retry). The coverage tracker ignores it.

### D2: Git verification uses merge-base --is-ancestor
This is the canonical git check for "is branch B in main's history." It's fast (no diff computation), works with ff-only merges, and handles rebased branches correctly.

### D3: integration_pre_build failure = gate failure
Simple: return False from `_run_integration_gates()` instead of logging a warning. The gate runner already handles False returns correctly (marks merge-blocked, removes from queue).

### D4: Verification happens inside merge_change(), not after
The git verification is added at the end of merge_change() — if the verify fails, the status is rolled back to "merge-failed". This keeps the verification atomic with the merge.

## File Map

| File | Lines | Change |
|------|-------|--------|
| `lib/set_orch/merger.py` | 1033-1036 | No-op → "skipped" instead of gates_passed=True |
| `lib/set_orch/merger.py` | 1057-1059 | Skip merge_change() for no-op |
| `lib/set_orch/merger.py` | 777-780 | pre_build False → return False |
| `lib/set_orch/merger.py` | 493+ | Post-merge git verification |
| `lib/set_orch/digest.py` | 860-870 | Git-verify before coverage update |
