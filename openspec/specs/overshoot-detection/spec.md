# Overshoot Detection Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Verify skill detects implementation overshoot
The verify-change skill SHALL perform backward verification: checking that new implementation artifacts (routes, endpoints, components, exports, database tables) can be traced back to a spec requirement. Items that cannot be traced SHALL be flagged as potential overshoot.

#### Scenario: New route matches spec requirement
- **WHEN** the verify skill scans the diff and finds a new route/endpoint
- **AND** the route corresponds to a requirement in the delta specs
- **THEN** no overshoot warning SHALL be generated for that route

#### Scenario: New route without spec requirement
- **WHEN** the verify skill scans the diff and finds a new route/endpoint
- **AND** the route does NOT correspond to any requirement in the delta specs or IN SCOPE section
- **THEN** it SHALL report a WARNING: "Potential overshoot — new route not in spec: <route>"
- **AND** the recommendation SHALL be: "Remove <route> or add a spec requirement for it"

#### Scenario: Helper functions and internal utilities
- **WHEN** the verify skill detects new internal helper functions or utility code
- **AND** those helpers serve an implementation detail of a spec requirement (not a user-facing feature)
- **THEN** no overshoot warning SHALL be generated
- **AND** the verify skill SHALL use LLM judgment to distinguish implementation details from new features

#### Scenario: Overshoot severity is WARNING not CRITICAL
- **WHEN** overshoot is detected
- **THEN** the severity SHALL be WARNING, not CRITICAL
- **AND** the verification report SHALL note: "Overshoot detection uses heuristics — review flagged items manually"

### Requirement: Overshoot check integrates with existing verify flow
The overshoot check SHALL run within the existing verify-change skill execution, after completeness and correctness checks, as part of the coherence dimension.

#### Scenario: No delta specs available
- **WHEN** the verify skill runs overshoot detection
- **AND** no delta specs exist for the change
- **THEN** overshoot detection SHALL be skipped
- **AND** the report SHALL note "No delta specs — overshoot check skipped"

#### Scenario: No IN SCOPE section available
- **WHEN** the verify skill runs overshoot detection
- **AND** delta specs exist but lack IN SCOPE sections
- **THEN** overshoot detection SHALL fall back to checking new artifacts against requirement names only
