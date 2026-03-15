## Why

E2E run #13 exposed that the checkpoint system was never properly integrated end-to-end. Bugs #21-#23 were all checkpoint-related, with #23 causing **data loss** (4 merged changes lost on restart). While all 3 bugs have been fixed individually, the checkpoint subsystem needs hardening — the fixes were reactive patches, not a systematic audit.

### Bugs found in run #13

| Bug | Severity | Root cause | Fix commit |
|-----|----------|------------|------------|
| #21 | blocking | `engine.py` skipped `_poll_active_changes()` during checkpoint — dead Ralph never detected | aa4296fc7 |
| #22 | blocking | `checkpoint_auto_approve` directive parsed but never checked in monitor loop | bb53d3a07 |
| #23 | **CRITICAL** | `dispatcher.sh` resume logic didn't include "checkpoint" — fell through to `init_state()`, overwrote state file | 9422dc7ba |
| CLI | blocking | `--checkpoint-auto-approve` CLI flag not forwarded from bash to Python engine | 091130b0d |

### Remaining gaps (post-fix audit)

1. **Checkpoint approval API records intent but doesn't resume** — `/api/{project}/approve` sets `approved=true` but monitor loop only checks `checkpoint_auto_approve` directive, not the approval record
2. **No checkpoint timeout** — if `checkpoint_auto_approve=false` and user never approves, monitor loop waits forever
3. **`changes_since_checkpoint` counter never resets** — accumulates forever (triggers at 3, 6, 9...), semantics unclear
4. **`phase_audit_results` not cleared on restart** — stale audit data from previous cycles persists (from memory MEM#ef06)
5. **No integration test** — checkpoint flow has zero test coverage, all bugs found in production E2E

### Current code locations

- `lib/wt_orch/engine.py:300-330` — checkpoint handling in monitor loop (post-fix)
- `lib/wt_orch/engine.py:405-407` — checkpoint trigger logic
- `lib/orchestration/dispatcher.sh:367-368` — bash resume logic (post-fix)
- `lib/wt_orch/cli.py` — CLI flag parsing and forwarding
- `lib/wt_orch/state.py` — OrchestratorState dataclass with checkpoint fields

## What Changes

### 1. Checkpoint Approval API Integration
- Monitor loop checks both `checkpoint_auto_approve` directive AND approval records in state
- When user approves via API (`/api/{project}/approve`), next poll cycle resumes to "running"
- Currently: approval is recorded but never read in the resume path

### 2. Checkpoint Timeout
- New directive: `checkpoint_timeout: 3600` (seconds, default: no timeout)
- If checkpoint has been active longer than timeout, auto-resume with warning event
- Prevents orchestrator from hanging indefinitely when user forgets to approve

### 3. Counter Reset Semantics
- Document and implement clear semantics: `changes_since_checkpoint` resets to 0 after each checkpoint trigger
- Current behavior (accumulate) means checkpoint_every=3 triggers at 3, 6, 9 — which may be intentional but is undocumented
- Decision: reset to 0, so checkpoint triggers every N changes consistently

### 4. Restart State Cleanup
- On restart/replan, clear `phase_audit_results` from previous cycles
- Prevents stale audit data from appearing in dashboard and confusing operators
- Clean up any other cycle-bound state that should reset

### 5. Integration Tests
- Test: checkpoint triggers after N changes → status = "checkpoint"
- Test: checkpoint_auto_approve=true → auto-resumes to "running"
- Test: restart with checkpoint status → resumes correctly (no state loss)
- Test: CLI --checkpoint-auto-approve → forwarded to engine
- Test: checkpoint timeout → auto-resumes with warning

## Capabilities

### New Capabilities
- `checkpoint-timeout`: Auto-resume from checkpoint after configurable timeout
- `checkpoint-approval-integration`: Monitor loop checks API approval records, not just directive

### Modified Capabilities
- `checkpoint-trigger`: Counter reset semantics documented and implemented
- `orchestrator-restart`: Clears stale cycle-bound state (phase_audit_results)
- `checkpoint-resume`: Checks both directive and approval record for resume decision

## Impact

- **Modified**: `lib/wt_orch/engine.py` — approval check, timeout logic, counter reset
- **Modified**: `lib/wt_orch/state.py` — checkpoint timeout field, restart cleanup
- **Modified**: `lib/orchestration/dispatcher.sh` — restart state cleanup
- **New**: Integration tests for checkpoint flow
- **Documentation**: Checkpoint state machine documented with all transitions
- **No breaking changes**: New directives are optional with safe defaults
