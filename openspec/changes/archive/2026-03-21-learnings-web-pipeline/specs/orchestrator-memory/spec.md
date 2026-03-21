## ADDED Requirements

### Requirement: Gate stats persisted to memory at run end
A new `_persist_run_learnings(state_file)` helper in engine.py SHALL save aggregated gate statistics to persistent memory at terminal states. This helper is called alongside `_generate_review_findings_summary_safe()` at each terminal state site (lines 345, 875, 894, 918, 946, 960). It imports `orch_remember` from `orch_memory`.

#### Scenario: Run completes with gate data
- **WHEN** the orchestrator reaches a terminal state (done, time_limit, replan_limit, dep_blocked, total_failure, replan_exhausted)
- **AND** `orch_gate_stats(state)` returns non-empty result
- **THEN** `orch_remember()` SHALL be called with a formatted summary of pass rates and retry costs, type "Context", tags "source:orchestrator,type:gate-stats"

#### Scenario: Run completes without gate data
- **WHEN** `orch_gate_stats(state)` returns empty dict
- **THEN** no gate stats memory SHALL be saved

### Requirement: Review patterns persisted to memory at run end
The same `_persist_run_learnings()` helper SHALL read the review findings JSONL and save recurring patterns.

#### Scenario: Recurring patterns found
- **WHEN** the JSONL at `os.path.join(os.path.dirname(state_file), "wt", "orchestration", "review-findings.jsonl")` contains patterns appearing in 2+ changes (using the same normalization as `generate_review_findings_summary()`: strip severity tag, take first 50 chars)
- **THEN** `orch_remember()` SHALL be called with the patterns, type "Learning", tags "source:orchestrator,type:review-patterns"

#### Scenario: No recurring patterns
- **WHEN** no review finding patterns recur across changes, or the JSONL does not exist
- **THEN** no review pattern memory SHALL be saved

### Requirement: Merge conflict info persisted to memory
The merger SHALL save merge conflict information to persistent memory when a conflict is detected and fingerprinted. A module-level `_seen_conflict_fingerprints: set[str]` tracks duplicates within a run.

#### Scenario: Merge conflict detected
- **WHEN** `_compute_conflict_fingerprint()` (merger.py:591) returns a fingerprint
- **AND** the fingerprint is NOT in `_seen_conflict_fingerprints`
- **THEN** `orch_remember()` SHALL be called with the conflicting files and change name, type "Learning", tags "source:orchestrator,type:merge-conflict"
- **AND** the fingerprint SHALL be added to `_seen_conflict_fingerprints`

#### Scenario: Duplicate conflict
- **WHEN** the fingerprint IS in `_seen_conflict_fingerprints`
- **THEN** no additional memory SHALL be saved
