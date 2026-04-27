# Modular Source Structure Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Editor library extraction
The system SHALL extract all editor-related functions from `bin/set-common.sh` into `lib/editor.sh`. Scripts that use editor functions (set-config, set-work, set-new, set-focus) SHALL source `lib/editor.sh` explicitly. `set-common.sh` SHALL NOT contain editor functions after extraction.

#### Scenario: set-common.sh sources editor lib
- **WHEN** any script sources `set-common.sh`
- **THEN** editor functions are NOT available unless `lib/editor.sh` is also sourced

#### Scenario: Editor-using scripts work unchanged
- **WHEN** set-config, set-work, set-new, or set-focus is executed
- **THEN** all editor detection and configuration functions work identically to before extraction

### Requirement: Memory module extraction
The system SHALL split `bin/set-memory` into a thin dispatcher (~300 lines) and 7 sourced modules under `lib/memory/`: core.sh, maintenance.sh, rules.sh, todos.sh, sync.sh, migrate.sh, ui.sh. All CLI commands SHALL work identically after extraction.

#### Scenario: set-memory dispatcher sources modules
- **WHEN** `set-memory` starts
- **THEN** it sources infrastructure functions, then sources all `lib/memory/*.sh` modules before dispatching to the requested subcommand

#### Scenario: All subcommands work after split
- **WHEN** any `set-memory` subcommand is executed (remember, recall, forget, rules, todo, sync, etc.)
- **THEN** it produces identical output and side effects as the monolithic version

### Requirement: Hook-memory module extraction
The system SHALL split `bin/set-hook-memory` into a thin bash dispatcher and Python modules under `lib/set_hooks/`: util.py, session.py, memory_ops.py, events.py, stop.py. All hook event handlers SHALL work identically after extraction.

#### Scenario: Shared daemon helpers in util.py
- **WHEN** any hook module (memory_ops.py, stop.py) needs a daemon client or daemon status check
- **THEN** it SHALL import `get_daemon_client` and `daemon_is_running` from `set_hooks.util`
- **AND** SHALL NOT define local copies of these functions

#### Scenario: Shared heuristic patterns in util.py
- **WHEN** any hook module needs to detect heuristic memory patterns
- **THEN** it SHALL import `HEURISTIC_RE` from `set_hooks.util`
- **AND** SHALL NOT define a local copy of the pattern list or compiled regex

#### Scenario: All hook events handled after split
- **WHEN** Claude Code emits any hook event (SessionStart, UserPromptSubmit, PostToolUse, Stop, etc.)
- **THEN** `set-hook-memory` dispatches to the correct handler in `lib/hooks/events.sh` and produces identical JSON output

### Requirement: Loop module extraction
The system SHALL split `bin/set-loop` into a thin dispatcher (~500 lines) and 4 sourced modules under `lib/loop/`: state.sh, tasks.sh, prompt.sh, engine.sh. All CLI commands and the Ralph loop engine SHALL work identically after extraction.

#### Scenario: Ralph loop runs after split
- **WHEN** `set-loop start` is executed
- **THEN** the loop engine runs iterations with identical behavior (prompt building, task detection, done detection, token budget)

#### Scenario: Loop CLI commands work after split
- **WHEN** any `set-loop` subcommand is executed (start, stop, status, list, monitor, history, resume, budget)
- **THEN** it produces identical output and behavior as the monolithic version

### Requirement: Orchestration state refactor
The system SHALL split `lib/orchestration/state.sh` into 4 focused modules: config.sh, state.sh (core), orch-memory.sh, utils.sh. The system SHALL extract `builder.sh` and `monitor.sh` from `lib/orchestration/dispatcher.sh`. All sourcing scripts SHALL work identically.

#### Scenario: Orchestrator runs after state split
- **WHEN** `set-orchestrate` sources orchestration libraries
- **THEN** all state queries, config lookups, memory helpers, and utility functions work identically

#### Scenario: BASE_BUILD cache deduplicated
- **WHEN** base build health is checked by dispatcher or merger
- **THEN** both use `builder.sh` as the single source of truth for BASE_BUILD_* state

### Requirement: Project deploy refactor
The system SHALL split `deploy_set_tools()` in `bin/set-project` into focused functions: deploy_hooks(), deploy_commands(), deploy_skills(), deploy_mcp(), deploy_memory(). The `set-project init` command SHALL work identically.

#### Scenario: Project init works after refactor
- **WHEN** `set-project init` is executed
- **THEN** hooks, commands, skills, MCP server, and memory are deployed identically to before

### Requirement: Unit test coverage for extracted modules
Each extracted `lib/` module SHALL have a corresponding test file in `tests/unit/`. Tests SHALL source the lib file directly and test functions in isolation using simple assert helpers.

#### Scenario: Unit tests pass for extracted module
- **WHEN** `tests/unit/test_<module>.sh` is executed
- **THEN** all assertions pass, verifying the module's functions work correctly in isolation

#### Scenario: Test helpers available
- **WHEN** a unit test sources `tests/unit/helpers.sh`
- **THEN** `assert_equals`, `assert_contains`, `assert_exit_code` functions are available

### Requirement: Source order and dependency documentation
Each extracted module SHALL declare its dependencies in a header comment. Main scripts SHALL document source order. Infrastructure functions SHALL always be sourced before domain modules.

#### Scenario: Module header documents dependencies
- **WHEN** a developer reads any `lib/<domain>/*.sh` file
- **THEN** the file header lists which other modules or functions it depends on

#### Scenario: Main script documents source order
- **WHEN** a developer reads a main `bin/set-*` script
- **THEN** the source statements are in dependency order with comments explaining why
