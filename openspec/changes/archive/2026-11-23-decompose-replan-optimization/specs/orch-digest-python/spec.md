## ADDED Requirements

### Requirement: Digest delegates to per-section pipeline when enabled
When the directive `digest_strategy: diff_update` is configured, `set-orch-core digest run` SHALL delegate to the per-section pipeline defined in capability `digest-diff-update` instead of running a single full-spec Claude call.

#### Scenario: Diff-update strategy invoked
- **WHEN** `digest_strategy: diff_update` is configured AND the digest is invoked
- **THEN** the system SHALL execute the per-section pipeline: section identification, hashing, per-section Claude calls for changed sections, and the deterministic Python reducer

#### Scenario: Default strategy unchanged
- **WHEN** no `digest_strategy` is configured OR `digest_strategy: full` is set
- **THEN** the system SHALL run the full-spec Claude digest as today

### Requirement: Replan trigger detection no longer fires on AMBs alone in JIT mode
When `amb_resolution: jit` is configured, the digest's contribution to replan trigger detection SHALL exclude unresolved ambiguities. Replan triggers continue to fire on spec_change, e2e_failure, domain_failure, coverage_gap, and batch_complete.

#### Scenario: AMBs no longer trigger replan in JIT mode
- **WHEN** `amb_resolution: jit` AND the digest produces unresolved ambiguities
- **AND** no other replan trigger condition is met
- **THEN** the auto-replan loop SHALL NOT fire

#### Scenario: Inline mode preserves today's behavior
- **WHEN** `amb_resolution: inline`
- **THEN** AMBs continue to flow into the planner prompt as today (no behavior change)

## MODIFIED Requirements

### Requirement: Python digest API invocation
The system SHALL provide `call_digest_api()` in `digest.py` that calls Claude via `subprocess_utils.run_claude()` with the digest prompt and returns structured JSON output. The prompt SHALL be passed as a `list[ContentBlock]` with declared `cache_control` breakpoints (see capability `planner-prompt-caching`).

#### Scenario: Successful API call
- **WHEN** the digest prompt blocks are sent to Claude
- **THEN** the response is parsed as JSON containing requirements, ambiguities, and coverage data

#### Scenario: API failure
- **WHEN** the Claude API call fails or returns non-JSON
- **THEN** the system logs the error and returns a failure status without crashing

#### Scenario: Cache observability
- **WHEN** the digest API call returns
- **THEN** `cache_read_tokens` and `cache_create_tokens` SHALL be recorded in the resulting `LLM_CALL` event
