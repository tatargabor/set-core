## Context

The orchestrator checkpoint system allows pausing orchestration after every N completed changes for operator review. The system currently has five gaps identified through production usage:

1. **Approval API disconnected from resume path** — The `/api/{project}/approve` endpoint records approval on the checkpoint record (`checkpoints[-1].approved = true`) but the monitor loop only checks the `checkpoint_auto_approve` directive, never the approval record. Users who approve via the API see no effect.

2. **No checkpoint timeout** — When `checkpoint_auto_approve=false` and the operator never approves, the monitor loop waits indefinitely. There is no mechanism to auto-resume after a configurable period.

3. **Counter accumulates instead of resetting** — `changes_since_checkpoint` increments but never resets. With `checkpoint_every=3`, checkpoints trigger at 3, 6, 9... changes total, not every 3 changes. The semantics are unclear and undocumented.

4. **Stale cycle-bound state on restart** — `phase_audit_results` and `phase_e2e_results` persist across orchestrator restarts, showing results from a previous execution context. The existing `restart-state-reconciliation` spec covers this for process reconciliation but not for checkpoint-specific fields like `checkpoint_reason`.

5. **Zero test coverage** — No unit or integration tests cover the checkpoint flow. All bugs were found in production E2E runs.

### Current Architecture

The checkpoint system spans four modules:

- **`engine.py`** — Monitor loop checkpoint handling (lines 320-330), trigger logic (lines 402-407), `trigger_checkpoint()` function
- **`state.py`** — `OrchestratorState` dataclass with `checkpoints`, `changes_since_checkpoint` fields
- **`api.py`** — `/api/{project}/approve` endpoint that records approval
- **`cli.py`** — `--checkpoint-auto-approve` CLI flag forwarded to engine

The monitor loop flow is: poll active changes → check checkpoint status → if checkpoint, check auto_approve directive → if not auto_approve, `continue` (skip dispatch).

## Goals / Non-Goals

**Goals:**
- Monitor loop checks approval records from API, not just the directive
- Configurable checkpoint timeout with auto-resume and warning event
- Counter resets to 0 after each checkpoint trigger for predictable N-change cadence
- Stale checkpoint-related state cleaned on restart
- Comprehensive unit tests covering all checkpoint transitions and edge cases

**Non-Goals:**
- Changing the checkpoint UI/dashboard (frontend changes)
- Multi-user approval workflows (only single approval needed)
- Checkpoint scheduling by time (only change-count-based triggers)
- Modifying the E2E test framework itself

## Decisions

### D1: Check approval record in monitor loop

**Decision:** Add an approval record check alongside the `checkpoint_auto_approve` directive check.

**Current code (engine.py, checkpoint block):**
```python
if d.checkpoint_auto_approve:
    logger.info("Checkpoint auto-approved — resuming")
    update_state_field(state_file, "status", "running")
else:
    continue
```

**New logic:**
```python
if d.checkpoint_auto_approve:
    logger.info("Checkpoint auto-approved — resuming")
    update_state_field(state_file, "status", "running")
elif _checkpoint_approved(state):
    logger.info("Checkpoint approved via API — resuming")
    update_state_field(state_file, "status", "running")
else:
    continue
```

The `_checkpoint_approved()` helper checks `state.checkpoints[-1].get("approved", False)` or `state.extras.get("checkpoints", [])[-1].get("approved", False)`.

**Why:** The approval API already records the intent. The monitor loop just needs to read it. This is a minimal change — one new condition in the existing `if/else` block.

**Alternative considered:** Having the API endpoint directly set `status="running"`. Rejected because the monitor loop should own all state transitions to avoid race conditions with the poll cycle.

### D2: Checkpoint timeout via directive

**Decision:** Add `checkpoint_timeout` directive (integer seconds, default 0 = no timeout). When the checkpoint has been active longer than the timeout, auto-resume with a warning event.

**Implementation:** Store `checkpoint_started_at` (epoch) when entering checkpoint status. In the checkpoint block of the monitor loop, compare current time against `checkpoint_started_at + checkpoint_timeout`.

```python
if d.checkpoint_timeout > 0:
    started = state.extras.get("checkpoint_started_at", 0)
    if started and (int(time.time()) - started) >= d.checkpoint_timeout:
        logger.warning("Checkpoint timed out after %ds — auto-resuming", d.checkpoint_timeout)
        update_state_field(state_file, "status", "running")
        if event_bus:
            event_bus.emit("CHECKPOINT_TIMEOUT", data={"elapsed": int(time.time()) - started})
```

**Why `checkpoint_started_at` in extras:** The `trigger_checkpoint()` function already writes `checkpoint_reason` to state extras. Adding `checkpoint_started_at` follows the same pattern and avoids modifying the `OrchestratorState` dataclass for what is transient metadata.

**Alternative considered:** Using the last checkpoint record's timestamp. Rejected because checkpoint records use `approved_at` (set on approval) and don't track when the checkpoint started.

### D3: Counter reset after checkpoint trigger

**Decision:** Reset `changes_since_checkpoint` to 0 in `trigger_checkpoint()` immediately after setting status to "checkpoint".

```python
def trigger_checkpoint(state_file, reason, event_bus=None):
    update_state_field(state_file, "status", "checkpoint")
    update_state_field(state_file, "checkpoint_reason", reason)
    update_state_field(state_file, "changes_since_checkpoint", 0)  # NEW
    ...
```

**Why reset to 0:** With `checkpoint_every=3`, operators expect a checkpoint every 3 changes. The accumulating behavior (3, 6, 9...) is confusing and makes the directive value meaningless after the first checkpoint. Resetting to 0 gives predictable cadence.

**Alternative considered:** Keep accumulating and document it. Rejected because it makes the `checkpoint_every` value a one-shot threshold rather than a periodic interval, which contradicts the name "every".

### D4: Clear checkpoint-specific state on restart

**Decision:** In the resume path (existing `restart-state-reconciliation` logic), additionally clear:
- `checkpoint_reason` from state extras
- `checkpoint_started_at` from state extras (the new field from D2)
- Reset `changes_since_checkpoint` to 0

**Why:** These fields are meaningful only within a single orchestrator execution. On restart, any prior checkpoint reason or timer is stale. The counter should reset so the new execution gets fresh checkpoint cadence.

**Note:** `phase_audit_results` and `phase_e2e_results` cleanup is already specified in the `restart-state-reconciliation` spec. This change adds checkpoint-specific fields to the same cleanup path.

### D5: Test strategy — unit tests with pytest

**Decision:** Add checkpoint-focused tests to `tests/unit/test_engine.py` (existing file) covering:
1. `trigger_checkpoint()` resets counter
2. Monitor loop auto-approve via directive
3. Monitor loop approve via API record
4. Monitor loop checkpoint timeout
5. Counter reset semantics (triggers at N, 2N, 3N with reset)

**Why unit tests over integration tests:** The checkpoint logic is self-contained in `engine.py` with clear state file I/O. Mocking `load_state`/`save_state` or using temp files is straightforward. Integration tests for the full monitor loop are expensive (require process lifecycle) and already covered by E2E runs.

**Test fixtures:** Create `_make_checkpoint_state(state_file, ...)` helper that writes a state file with configurable checkpoint fields.

## Risks / Trade-offs

**[Risk] Approval check adds one `load_state` read per poll cycle during checkpoint** → Minimal impact. The state is already loaded at the top of the checkpoint block (`state = load_state(...)` on line 304). The approval check uses the same `state` object — no extra I/O.

**[Risk] Timeout auto-resume may surprise operators who intentionally paused** → Mitigated by: default timeout is 0 (disabled), timeout emits a `CHECKPOINT_TIMEOUT` warning event, and the directive must be explicitly configured.

**[Risk] Counter reset changes behavior for existing users** → Mitigated by: the old behavior was undocumented and arguably a bug. The `checkpoint_every` name strongly implies periodic cadence. Any user relying on the accumulating behavior would need `checkpoint_every` set to a multiple anyway.

**[Trade-off] Storing `checkpoint_started_at` in extras vs. dataclass field** → Extras is slightly less type-safe but avoids schema migration. Since this is transient metadata (cleared on restart), extras is appropriate.
