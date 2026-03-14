## ADDED Requirements

### Requirement: Python planning orchestration
The planning pipeline orchestration (input detection, freshness check, triage gate, Claude invocation, response parsing, plan enrichment) SHALL be available as a Python function callable from `auto_replan_cycle()` and eventually from a `wt-orch-core plan run` CLI command.

#### Scenario: Planning from Python replan
- **WHEN** `auto_replan_cycle()` needs to generate a new plan
- **THEN** it SHALL call `planner.run_planning_pipeline()` which orchestrates the full flow
- **AND** the pipeline SHALL use existing Python functions: `detect_test_infra()`, `build_decomposition_context()`, `validate_plan()`, `enrich_plan_metadata()`

### Requirement: Design bridge integration in Python planning
The Python planning pipeline SHALL support design bridge integration (Figma/Penpot snapshot) when a design MCP server is registered.

#### Scenario: Design snapshot fetch during planning
- **WHEN** planning detects a registered design MCP server
- **THEN** it SHALL fetch the design snapshot and include design tokens in the decomposition prompt
- **AND** it SHALL write `design-snapshot.md` to the project root

#### Scenario: No design MCP available
- **WHEN** no design MCP server is registered
- **THEN** planning SHALL proceed without design context (no error)

### Requirement: Python planning handles triage gate
The Python planning pipeline SHALL check the triage gate before proceeding with decomposition.

#### Scenario: Triage gate blocks planning
- **WHEN** `check_triage_gate()` returns unresolved ambiguities and `auto_defer` is false
- **THEN** the pipeline SHALL pause and wait for triage resolution

#### Scenario: Auto-defer in automated mode
- **WHEN** `check_triage_gate()` returns unresolved ambiguities and `TRIAGE_AUTO_DEFER=true`
- **THEN** the pipeline SHALL auto-defer ambiguous items and proceed with planning
