## ADDED Requirements

### Requirement: Typed state schema with dataclasses
The system SHALL define the orchestration state schema as Python dataclasses (`OrchestratorState`, `Change`, `WatchdogState`, `TokenStats`). Each dataclass SHALL map 1:1 to the JSON structure in `orchestration-state.json`.

#### Scenario: All state fields represented
- **WHEN** the dataclass schema is compared against a production `orchestration-state.json`
- **THEN** every JSON field has a corresponding typed dataclass field with no missing or extra fields

#### Scenario: Type annotations match actual data
- **WHEN** `load_state()` deserializes a valid `orchestration-state.json`
- **THEN** all fields have the correct Python types (str, int, float, list, Optional, etc.) matching the JSON value types

### Requirement: State loading with validation
`load_state(path)` SHALL read `orchestration-state.json`, validate JSON structure, and return a typed `OrchestratorState` instance. It SHALL reject corrupt or structurally invalid JSON.

#### Scenario: Valid state file
- **WHEN** `load_state("orchestration-state.json")` is called with a well-formed state file
- **THEN** it returns an `OrchestratorState` instance with all fields populated

#### Scenario: Corrupt JSON
- **WHEN** `load_state()` is called on a file containing invalid JSON (truncated, malformed)
- **THEN** it raises a `StateCorruptionError` with the file path and parse error details

#### Scenario: Missing required fields
- **WHEN** `load_state()` is called on a JSON file missing the `changes` array
- **THEN** it raises a `StateCorruptionError` indicating the missing field

#### Scenario: Unknown fields preserved
- **WHEN** the JSON contains fields not in the dataclass schema (future additions)
- **THEN** `load_state()` preserves them in a catch-all dict and `save_state()` writes them back

### Requirement: Atomic state saving
`save_state(state, path)` SHALL serialize the `OrchestratorState` to JSON and write atomically (tempfile in same directory + rename). It SHALL validate the output is non-empty before rename.

#### Scenario: Successful save
- **WHEN** `save_state(state, "orchestration-state.json")` is called with a valid state
- **THEN** the file is written atomically — readers never see a partial write

#### Scenario: Disk full or write error
- **WHEN** the tempfile write fails (disk full, permission denied)
- **THEN** the original file is not modified and an exception is raised

### Requirement: State initialization from plan
`init_state(plan_file, output_path)` SHALL replace the 40-line jq filter in `state.sh:init_state()`. It SHALL read the plan JSON, transform changes into the state schema with all default fields, and write the initial state atomically.

#### Scenario: Plan with multiple changes
- **WHEN** `init_state("plan.json", "orchestration-state.json")` is called with a plan containing 5 changes with dependencies
- **THEN** the output state has all 5 changes with `status: "pending"`, `ralph_pid: null`, `tokens_used: 0`, and all other defaults

#### Scenario: Plan with optional fields
- **WHEN** a change in the plan has `requirements`, `also_affects_reqs`, and `model` fields
- **THEN** these optional fields are preserved in the output state change object

### Requirement: Change queries
The module SHALL provide query functions that replace complex jq filters: `query_changes(state, status)` for filtering, `aggregate_tokens(state)` for token summation.

#### Scenario: Filter by status
- **WHEN** `query_changes(state, status="running")` is called with a state containing 3 running and 2 pending changes
- **THEN** it returns a list of 3 Change objects

#### Scenario: Aggregate tokens
- **WHEN** `aggregate_tokens(state)` is called on a state with changes having tokens_used of [1000, 2000, 500]
- **THEN** it returns a TokenStats with total=3500

### Requirement: CLI bridge for state operations
The `wt-orch-core state` subcommand SHALL expose state operations to bash scripts.

#### Scenario: init subcommand
- **WHEN** bash calls `wt-orch-core state init --plan-file plan.json --output state.json`
- **THEN** the state file is created with the transformed schema and exit code is 0

#### Scenario: query subcommand
- **WHEN** bash calls `wt-orch-core state query --file state.json --status running`
- **THEN** stdout contains a JSON array of matching change objects

#### Scenario: get subcommand for single change
- **WHEN** bash calls `wt-orch-core state get --file state.json --change "my-change" --field status`
- **THEN** stdout contains the field value as a raw string
