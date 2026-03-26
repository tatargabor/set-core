## Why

When all changes succeed (0 failed, 0 stalled), `auto_replan` still triggers a full Phase 2+3 re-decompose. The LLM always finds "something more to do" — generating duplicate changes that overlap with already-merged work. In micro-web-run4: 3/3 merged perfectly, but replan created 3 redundant changes (one was a complete no-op with 0 commits).

Root causes:
1. No "all green → skip replan" gate before `_handle_auto_replan`
2. `_detect_replan_trigger` returns "batch_complete" when nothing is wrong — which triggers full re-decompose
3. Novelty check only filters exact name matches against failed changes, not functional overlap with merged ones
4. No-op changes (0 commits) still go through merge + gates, wasting ~14K gate_ms

## What Changes

- Add coverage-based replan gate: if all requirements covered → skip replan, go to "done"
- "batch_complete" trigger should check coverage before deciding to re-decompose
- Add no-op detection: if agent produces 0 commits, skip merge (mark as "merged" without gates)
- Strengthen novelty check to detect functional overlap with merged changes

## Capabilities

### Modified Capabilities
- `replan-gate` — Coverage-aware gate that prevents unnecessary replan cycles
- `no-op-detection` — Skip merge for changes with 0 new commits

## Impact

- `lib/set_orch/engine.py` — replan gate logic, batch_complete handling
- `lib/set_orch/merger.py` — no-op detection in merge queue
- `lib/set_orch/digest.py` — coverage check helper (if needed)
