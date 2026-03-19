# Design: refactor-verify-merge-gates

## Context

The verify → merge pipeline is the critical path of the orchestrator. `handle_change_done` (verifier.py) is 600+ lines with 8 copy-pasted gate execution blocks. Two confirmed bugs exist in the engine's completion detection and crash recovery paths. The code was migrated from bash and has grown organically.

Current architecture:
```
engine.py:_poll_active_changes
  → verifier.py:poll_change
    → verifier.py:handle_change_done (600+ lines, 30+ update_change_field calls)
      → gate_profiles.py:resolve_gate_config
      → 8x inline gate blocks (build, test, e2e, scope, test_files, review, rules, spec_verify)
  → engine.py:_drain_merge_then_dispatch
    → merger.py:merge_change (smoke pipeline)
```

## Goals / Non-Goals

**Goals:**
- Fix P0 bug: `_check_completion` must check merge_queue
- Fix P1 bug: `_verify_gates_already_passed` must check all blocking gates
- Fix P3 bug: `_recover_verify_failed` must not double-increment retry count
- Extract GatePipeline abstraction to eliminate copy-paste
- Batch state updates for gate results
- Unify screenshot collection

**Non-Goals:**
- Change gate execution order
- Add new gate types
- Modify smoke pipeline architecture (stays in merger.py)
- Change status lifecycle names (e.g., "done" → "verified" deferred)

## Decisions

### D1: GatePipeline as a class in new gate_runner.py

**Decision:** New `lib/set_orch/gate_runner.py` with `GatePipeline` class.

**Why not modify handle_change_done in-place?** The function is too tangled — each gate block has slightly different retry context, different field names, and different edge cases. A clean abstraction in a new file lets us test the pipeline logic independently.

**Why not a simple loop over gate configs?** Each gate has unique executor logic (build detection, test parsing, e2e port allocation, review prompt building). A pipeline with registered executors preserves this flexibility while unifying the retry/skip/warn-fail pattern.

**Alternatives considered:**
- Decorator pattern (too implicit, hard to debug)
- Simple function extraction (doesn't solve the retry duplication)

### D2: Gate executors as plain functions

**Decision:** Each gate executor is a function `(change, wt_path, gc, **ctx) -> GateResult`. The pipeline calls them in sequence.

**Why not Protocol/ABC?** Over-engineering for internal code. Functions are sufficient and easier to test.

### D3: Batch state update via context manager

**Decision:** `GatePipeline.commit_results()` writes all results in a single `locked_state` block.

**Why?** Current code does 30+ individual `update_change_field` calls, each locking/parsing/writing the state file. A single batch is faster and atomic.

**Trade-off:** If the orchestrator crashes mid-pipeline before `commit_results`, partial results are lost. This is acceptable because the pipeline will re-run on restart (gates are idempotent).

### D4: Build retry counter stays separate

**Decision:** Keep `build_fix_attempt_count` as a separate extras counter (existing design decision, documented in code). The GatePipeline handles this by allowing gates to specify `uses_own_retry_counter=True`.

### D5: Bug fixes as minimal changes first

**Decision:** Fix the three bugs (BUG-2, BUG-4, BUG-1) as targeted edits before the refactor. This way the fixes can be tested independently and the refactor doesn't need to also fix bugs.

## Risks / Trade-offs

- **[Risk] Behavioral regression in gate pipeline** → Mitigation: Existing tests must pass unchanged. Each gate executor is extracted from current inline code without logic changes. Integration test compares old vs new output.
- **[Risk] Batch update loses partial progress on crash** → Mitigation: Gates are idempotent; re-running on restart is safe. Same behavior as if crash happened during any individual `update_change_field`.
- **[Risk] handle_change_done callers (poll_change, CLI cmd_verify) break** → Mitigation: handle_change_done signature unchanged — it internally delegates to GatePipeline.

## Open Questions

None — all decisions validated during explore phase.
