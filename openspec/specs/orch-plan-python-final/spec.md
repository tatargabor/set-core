# Orch Plan Python Final Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Python plan orchestration
The system SHALL provide `run_plan()` in `lib/set_orch/planner.py` that replicates the full `cmd_plan()` bash orchestration: digest freshness check, triage gate, design bridge setup, directives resolution, Claude decomposition call, JSON extraction/validation, and coverage mapping.

#### Scenario: Full plan run
- **WHEN** `set-orch-core plan run --state-file <path> --spec-dir <dir>` is invoked
- **THEN** the system executes the complete planning pipeline and writes the plan JSON

#### Scenario: Triage gate blocks planning
- **WHEN** unresolved critical ambiguities exist in the digest
- **THEN** the system halts with a triage gate error listing unresolved items

#### Scenario: Design bridge integration
- **WHEN** a design MCP server is registered and design-snapshot.md exists
- **THEN** design tokens and component hierarchy are injected into the decomposition prompt

### Requirement: Python agent-based planning
The system SHALL provide `plan_via_agent()` in `planner.py` that creates a planning worktree and dispatches a Ralph loop with decomposition skills, replicating the bash `plan_via_agent()`.

#### Scenario: Agent plan dispatch
- **WHEN** agent-based planning is requested
- **THEN** a worktree is created, the decomposition skill is loaded, and Ralph loop is started

### Requirement: Python plan CLI subcommand
The system SHALL register `set-orch-core plan run` as a CLI subcommand in `cli.py` that invokes `planner.run_plan()`.

#### Scenario: CLI invocation
- **WHEN** `set-orch-core plan run` is called with required arguments
- **THEN** it invokes the Python planning pipeline and exits with appropriate status code

### Requirement: Bash planner.sh becomes thin wrapper
After migration, `planner.sh` SHALL retain only CLI entry point dispatch (`cmd_plan()` calling `set-orch-core plan run`) and helper functions that are still needed by other bash files. All orchestration logic SHALL be removed.

#### Scenario: Thin wrapper delegation
- **WHEN** `cmd_plan()` is called in bash
- **THEN** it delegates to `set-orch-core plan run` with equivalent arguments
