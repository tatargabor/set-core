## ADDED Requirements

### Requirement: Per-change timeline API from events
The server SHALL expose a per-change timeline endpoint that reconstructs state transition history from `orchestration-state-events.jsonl` for a specific change. Path resolution follows the existing pattern at api.py:1548 — first `project_path / "orchestration-state-events.jsonl"`, fallback to `project_path / "wt" / "orchestration" / "orchestration-state-events.jsonl"`.

Events are emitted by `update_change_field()` in state.py:471-479 with structure: `{"ts": "...", "type": "STATE_CHANGE", "change": "<name>", "data": {"from": "<old>", "to": "<new>"}}`.

#### Scenario: Events exist for change
- **WHEN** a client requests `GET /api/{project}/changes/{name}/timeline`
- **AND** the events file contains entries with `type=="STATE_CHANGE"` and `change==name`
- **THEN** the response SHALL include chronologically sorted `transitions` (array of `{ts, from, to}`), `duration_ms` from first to last transition, and `current_gate_results` (snapshot from state Change: build_result, test_result, review_result, smoke_result, verify_retry_count)

#### Scenario: Rotated event archives included
- **WHEN** the events file has been rotated and archived files exist (pattern: `orchestration-state-events-YYYYMMDDHHMMSS.jsonl`, last 3 kept)
- **THEN** the timeline endpoint SHALL also read archived event files to include the full transition history

#### Scenario: No events for change
- **WHEN** no STATE_CHANGE entries match the named change
- **THEN** the response SHALL return `{ "transitions": [], "duration_ms": 0, "current_gate_results": [] }`
