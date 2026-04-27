# Change Timeline Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Visual phase timeline for changes
Each change displays a horizontal timeline bar showing its progression through orchestration phases.

#### Scenario: Running change timeline
- **WHEN** a change is in progress (running/verifying)
- **THEN** a horizontal bar shows completed phases in color and the current phase with a pulse animation
- **THEN** phases include: Dispatch → Implement → Build → Test → Review → Smoke → Merge

#### Scenario: Completed change timeline
- **WHEN** a change has status "done" or "merged"
- **THEN** all phases show as completed with their duration
- **THEN** failed-then-retried phases show the retry count

#### Scenario: Timeline data sources
- **WHEN** rendering the timeline
- **THEN** use `started_at`/`completed_at` for overall duration
- **THEN** use `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms` for gate phase durations
- **THEN** use `gate_total_ms` for total gate time

#### Scenario: Timeline in change detail
- **WHEN** a change row is expanded (via gate detail click or dedicated expand)
- **THEN** the timeline is shown at the top of the expanded area
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
