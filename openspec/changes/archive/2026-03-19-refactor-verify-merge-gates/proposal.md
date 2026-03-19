# Proposal: refactor-verify-merge-gates

## Why

The verify → merge → quality gate pipeline has accumulated bugs and structural debt from incremental feature additions. Two confirmed bugs can cause the orchestrator to exit prematurely (monitor exits with unmerged changes in queue) or fast-merge changes that failed rules/spec_verify gates on crash recovery. The core `handle_change_done` function is 600+ lines with 8x copy-pasted gate execution patterns, making each bug fix risky and each new gate addition error-prone.

## What Changes

- **BUG FIX**: `_check_completion` exits monitor loop even when `merge_queue` is non-empty — changes verified but never merged
- **BUG FIX**: `_verify_gates_already_passed` only checks 4 of 7+ gates — rules and spec_verify failures ignored on crash recovery fast-merge path
- **REFACTOR**: Extract `GatePipeline` abstraction from monolithic `handle_change_done` — unified gate execution, retry, and state update pattern
- **REFACTOR**: Batch state updates — replace 30+ individual `update_change_field` calls with single locked write
- **REFACTOR**: Deduplicate `_collect_smoke_screenshots` (two divergent implementations in merger.py and verifier.py)
- **CLEANUP**: Consolidate smoke pipeline helpers scattered between merger.py and verifier.py

## Capabilities

### New Capabilities
- `gate-pipeline-runner`: Core gate execution abstraction (GatePipeline class, GateResult, batch state updates)

### Modified Capabilities
- `verify-gate`: Bug fixes in completion detection and fast-merge gate checking
- `gate-profiles`: Integration with new GatePipeline runner (GateConfig consumed by pipeline)

## Impact

- **Files modified**: `lib/wt_orch/verifier.py` (major refactor), `lib/wt_orch/engine.py` (bug fixes), `lib/wt_orch/merger.py` (screenshot dedup), new `lib/wt_orch/gate_runner.py`
- **Risk**: `handle_change_done` is the most critical function in the orchestrator — refactor must preserve all existing gate behaviors exactly
- **Tests**: Existing unit tests in `tests/unit/test_verifier.py` and `tests/test_gate_profiles.py` must continue passing; new tests for GatePipeline
