## MODIFIED Requirements

### Requirement: Stale digest detection
The system SHALL detect when the raw spec has changed since last digest by comparing source hashes.

#### Scenario: Spec modified after digest
- **WHEN** planner runs and `index.json` `source_hash` does not match current spec files hash
- **THEN** the system warns "Digest is stale" and auto-re-digests before proceeding with planning

#### Scenario: Spec unchanged
- **WHEN** planner runs and source hash matches
- **THEN** the existing digest is reused without re-processing

#### Scenario: Replan re-digest skipped when hash unchanged
- **WHEN** auto-replan triggers and `check_digest_freshness()` returns "stale"
- **AND** a redundant hash recomputation confirms the source hash matches the stored digest hash
- **THEN** the system SHALL skip re-digest and log "Hash re-check: still fresh, skipping re-digest"
- **AND** use the existing cached digest for planning
