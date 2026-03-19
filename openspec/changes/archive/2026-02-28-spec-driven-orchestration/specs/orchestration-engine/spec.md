## ADDED Requirements

### Requirement: Dual-mode plan generation
The `generate_plan()` function SHALL support two input modes: brief mode (bash-parsed) and spec mode (LLM-extracted).

#### Scenario: Brief mode activation
- **WHEN** the input is a `project-brief.md` with a valid `### Next` section
- **AND** `--spec` is not provided
- **THEN** the system SHALL use the existing bash-parsed flow with `parse_next_items()` results
- **AND** the decomposition prompt SHALL reference "the Next section of the brief"

#### Scenario: Spec mode activation
- **WHEN** `--spec <path>` is provided
- **THEN** the system SHALL skip `parse_next_items()` bash parsing
- **AND** the decomposition prompt SHALL instruct the LLM to analyze the full document for actionable items

### Requirement: Enhanced decomposition prompt
The decomposition prompt for spec mode SHALL guide the LLM to extract and decompose in a single call.

#### Scenario: Spec mode prompt structure
- **WHEN** generating a plan from a spec document
- **THEN** the prompt SHALL instruct the LLM to:
  1. Identify completed items (status markers: checkboxes, emoji, "done"/"implemented"/"kész" text)
  2. Determine the next logical batch respecting phases, priorities, and dependencies
  3. If `--phase` hint is given, focus on that phase
  4. Decompose the selected batch into OpenSpec changes

#### Scenario: Plan JSON with phase metadata
- **WHEN** the LLM produces a plan from spec mode
- **THEN** the JSON output SHALL include:
  - `changes`: array of change objects (same format as current)
  - `phase_detected`: string describing which section/phase was selected
  - `reasoning`: string explaining why this batch was chosen

#### Scenario: Existing context in prompt
- **WHEN** the decomposition prompt is built
- **THEN** it SHALL include (regardless of mode):
  - Existing spec names from `openspec/specs/`
  - Active change names from `openspec/changes/`
  - Memory context from `set-memory` (if available)

### Requirement: find_input() replaces find_brief()
The input discovery function SHALL support both brief and spec sources.

#### Scenario: Input resolution order
- **WHEN** the orchestrator starts
- **THEN** the input SHALL be resolved in this order:
  1. `--spec <path>` → spec mode (LLM extraction)
  2. `--brief <path>` → brief mode (bash parsing)
  3. `openspec/project-brief.md` with `### Next` items → brief mode
  4. `openspec/project.md` with `### Next` items → brief mode (legacy fallback)
  5. None found → error with usage hint

#### Scenario: Input mode in state
- **WHEN** a plan is generated
- **THEN** the orchestration state SHALL record `input_mode: "brief"` or `input_mode: "spec"` and the source path

### Requirement: CLI argument additions
The orchestrator CLI SHALL accept new flags for spec-driven input.

#### Scenario: --spec flag
- **WHEN** `--spec <path>` is provided on the command line
- **THEN** the system SHALL use spec mode with the given file path

#### Scenario: --phase flag
- **WHEN** `--phase <hint>` is provided on the command line
- **THEN** it SHALL be passed to the LLM as a phase selection hint
- **AND** it SHALL only be valid when used with `--spec` (error if used with `--brief` or brief auto-detect)

#### Scenario: --max-parallel CLI override
- **WHEN** `--max-parallel <N>` is provided on the command line
- **THEN** it SHALL override the `max_parallel` directive from all other sources

#### Scenario: Help text
- **WHEN** `--help` is invoked
- **THEN** the help output SHALL document `--spec`, `--phase`, and `--max-parallel` flags with examples
