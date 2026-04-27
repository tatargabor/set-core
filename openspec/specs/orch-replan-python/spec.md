# Orch Replan Python Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Python auto-replan cycle without bash dependency
The Python engine SHALL implement `auto_replan_cycle()` entirely in Python, eliminating the circular dependency where Python shells out to bash which shells back to Python.

#### Scenario: Auto-replan triggered after all changes complete
- **WHEN** all changes reach terminal status and `auto_replan` directive is true
- **THEN** the Python monitor SHALL call `engine.auto_replan_cycle()` directly (Python function)
- **AND** `auto_replan_cycle()` SHALL NOT shell out to bash `planner.sh`

### Requirement: Python replan collects context via Python functions
The Python `auto_replan_cycle()` SHALL collect replan context by calling Python functions directly.

#### Scenario: Replan context collection
- **WHEN** `auto_replan_cycle()` starts
- **THEN** it SHALL call `planner.collect_replan_context()` to gather completed changes and file context
- **AND** it SHALL archive completed changes to `state-archive.jsonl`
- **AND** it SHALL call `planner.build_decomposition_context()` for the planning prompt

### Requirement: Python replan calls Claude directly
The Python `auto_replan_cycle()` SHALL call Claude for decomposition via `subprocess_utils.run_claude()`, not via bash `run_claude()`.

#### Scenario: Replan Claude invocation
- **WHEN** `auto_replan_cycle()` needs to generate a new plan
- **THEN** it SHALL call Claude via `subprocess_utils.run_claude()` with the decomposition prompt
- **AND** it SHALL parse the JSON response and validate with `planner.validate_plan()`

### Requirement: Python replan respects cycle limits
The Python replan SHALL enforce the same cycle limits and retry logic as bash.

#### Scenario: Cycle limit reached
- **WHEN** replan cycle count reaches `max_replan_cycles`
- **THEN** the engine SHALL mark status as "done" with `replan_limit_reached: true`
- **AND** SHALL NOT attempt further replanning

#### Scenario: Replan failure with retry
- **WHEN** a replan attempt fails (Claude error, validation failure)
- **THEN** the engine SHALL increment `replan_attempt` counter
- **AND** retry after 30 second delay
- **AND** give up after `MAX_REPLAN_RETRIES` consecutive failures

### Requirement: Python replan novelty check
The Python replan SHALL check whether new changes are truly novel before dispatching.

#### Scenario: No novel changes found
- **WHEN** the replan generates changes that are all duplicates of previously failed changes
- **THEN** `auto_replan_cycle()` SHALL return "no new work" and the engine SHALL mark orchestration as done
