## ADDED Requirements

## IN SCOPE
- REST API endpoints for review findings, gate stats, reflections, and per-change timeline
- Unified learnings endpoint aggregating all sources
- Gate stats aggregation with per-gate and per-change-type breakdowns
- Reflections aggregation across all worktrees
- Per-change timeline reconstructed from events.jsonl

## OUT OF SCOPE
- WebSocket streaming for learnings (REST polling is sufficient)
- Cross-run learnings persistence (handled by orchestrator-memory)
- Rule suggestion generation from findings (future capability)
- Learnings export/download

### Requirement: Review findings API endpoint
The server SHALL expose `GET /api/{project}/review-findings` returning structured review findings data from the JSONL log. File path: `_resolve_project(project) / "wt" / "orchestration" / "review-findings.jsonl"` (with fallback to `_resolve_project(project) / "orchestration" / "review-findings.jsonl"`). Summary MD at same dir as `review-findings-summary.md`.

#### Scenario: Findings exist
- **WHEN** `review-findings.jsonl` exists and contains entries
- **THEN** the response SHALL include `entries` (array of parsed JSONL entries with fields: change, timestamp, attempt, issue_count, critical_count, high_count, issues[]), `summary` (rendered markdown from summary file if exists), and `recurring_patterns` (patterns appearing in 2+ changes, using same normalization as `generate_review_findings_summary()`: strip severity tag, first 50 chars)

#### Scenario: No findings
- **WHEN** `review-findings.jsonl` does not exist or is empty
- **THEN** the response SHALL return `{ "entries": [], "summary": "", "recurring_patterns": [] }`

### Requirement: Gate stats aggregation endpoint
The server SHALL expose `GET /api/{project}/gate-stats` returning aggregated gate performance metrics across all changes in the current run.

#### Scenario: Changes with gate results
- **WHEN** the orchestration state contains changes with gate results
- **THEN** the response SHALL include `per_gate` (object keyed by gate name — build, test, review, smoke from Change dataclass fields, e2e from extras — with total/pass/fail/skip counts, pass_rate as pass/(pass+fail) excluding skipped, avg_ms, total_ms), `retry_summary` (total_retries from verify_retry_count/redispatch_count, total_retry_ms, retry percentage of gate time, most retried gate and change), and `per_change_type` (average gate time and retries grouped by change_type field, defaulting to "unknown")

#### Scenario: No gate data
- **WHEN** no changes have gate results
- **THEN** the response SHALL return `{ "per_gate": {}, "retry_summary": {}, "per_change_type": {} }`

### Requirement: Reflections aggregation endpoint
The server SHALL expose `GET /api/{project}/reflections` returning reflection content from all worktrees that have reflections.

#### Scenario: Worktrees with reflections
- **WHEN** worktrees exist with `has_reflection: true`
- **THEN** the response SHALL include `reflections` (array of objects with `change`, `branch`, `content` fields), `total` (total worktree count), and `with_reflection` (count of worktrees having reflections)

#### Scenario: No reflections
- **WHEN** no worktrees have reflections
- **THEN** the response SHALL return `{ "reflections": [], "total": 0, "with_reflection": 0 }`

### Requirement: Per-change timeline endpoint
The server SHALL expose `GET /api/{project}/changes/{name}/timeline` returning state transition history for a specific change, reconstructed from events.jsonl.

#### Scenario: Change with transitions
- **WHEN** `orchestration-state-events.jsonl` (and rotated archives `orchestration-state-events-*.jsonl`) contains STATE_CHANGE events for the named change
- **THEN** the response SHALL include `transitions` (array of objects with `ts`, `from`, `to` fields sorted chronologically), `duration_ms` (total time from first to last transition), and `current_gate_results` (snapshot of current gate state from Change: build_result, test_result, review_result, smoke_result, verify_retry_count — per-attempt history is not available, only current state)

#### Scenario: Change with no events
- **WHEN** no STATE_CHANGE events exist for the named change
- **THEN** the response SHALL return `{ "transitions": [], "duration_ms": 0, "current_gate_results": [] }`

### Requirement: Unified learnings endpoint
The server SHALL expose `GET /api/{project}/learnings` that aggregates all learning sources into a single response.

#### Scenario: All sources available
- **WHEN** a client requests the unified endpoint
- **THEN** the response SHALL include `reflections` (from reflections endpoint), `review_findings` (from review findings endpoint), `gate_stats` (from gate stats endpoint), and `sentinel_findings` (from existing sentinel findings data)

#### Scenario: Partial data
- **WHEN** some learning sources have no data (e.g., no sentinel findings)
- **THEN** those sections SHALL return their empty defaults, not error
