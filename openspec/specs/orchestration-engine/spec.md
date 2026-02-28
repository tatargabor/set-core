### Requirement: Plan generation from project input
The orchestrator SHALL decompose a project brief or specification document into an ordered list of OpenSpec changes via a single Claude CLI invocation.

#### Scenario: Brief mode plan generation
- **WHEN** `wt-orchestrate plan` is invoked
- **AND** a valid `openspec/project-brief.md` with `### Next` items exists (or `--brief` flag)
- **THEN** the orchestrator SHALL parse Next items via bash regex
- **AND** invoke Claude (Opus model) with the items, existing spec names, active changes, and memory context
- **AND** write the result to `orchestration-plan.json`

#### Scenario: Spec mode plan generation
- **WHEN** `wt-orchestrate plan` is invoked with `--spec <path>`
- **THEN** the orchestrator SHALL read the spec document
- **AND** if the spec exceeds ~8000 tokens, summarize it first using a cheap model (haiku by default)
- **AND** invoke Claude (Opus) with instructions to identify completed items and determine the next actionable batch
- **AND** include `phase_detected` and `reasoning` fields in the plan JSON

#### Scenario: Phase hint for spec mode
- **WHEN** `--phase <hint>` is provided alongside `--spec`
- **THEN** the orchestrator SHALL include the hint in the Claude prompt to focus decomposition

#### Scenario: Spec summary cache
- **WHEN** a large spec is summarized
- **THEN** the summary SHALL be cached in `.claude/spec-summary-cache.json` keyed by the spec file's SHA-256 hash
- **AND** subsequent plans with the same hash SHALL reuse the cached summary

### Requirement: Plan approval before execution
The orchestrator SHALL require explicit developer approval before executing a plan.

#### Scenario: Show existing plan
- **WHEN** `wt-orchestrate plan --show` is invoked
- **THEN** the orchestrator SHALL display change names, complexity, scopes, and dependency order

#### Scenario: Start requires plan
- **WHEN** `wt-orchestrate start` is invoked without an existing `orchestration-plan.json`
- **THEN** the orchestrator SHALL exit with an error suggesting `wt-orchestrate plan`

### Requirement: Plan validation
The orchestrator SHALL validate plans for structural issues before execution.

#### Scenario: Scope overlap detection
- **WHEN** a plan is validated
- **THEN** the orchestrator SHALL compute keyword jaccard similarity between all change scope pairs
- **AND** warn if any pair exceeds 40% similarity
- **AND** also check overlap against active worktrees from `orchestration-state.json`
- **AND** skip scopes with fewer than 3 words (3+ characters each)

#### Scenario: Circular dependency detection
- **WHEN** a plan is validated
- **THEN** the orchestrator SHALL run topological sort (Kahn's algorithm)
- **AND** fail if a cycle is detected

### Requirement: Dispatch creates proposal.md
The orchestrator SHALL pre-create `proposal.md` in the change directory during dispatch.

#### Scenario: Proposal pre-creation on dispatch
- **WHEN** `dispatch_change()` creates a new change in a worktree
- **AND** no `proposal.md` exists yet
- **THEN** the orchestrator SHALL create `openspec/changes/{name}/proposal.md` with:
  - `## Why` section containing the roadmap item
  - `## What Changes` section containing the scope text
  - `## Capabilities` section with the change name
  - `## Impact` section (placeholder)
- **AND** if dispatch memories are available, append a `## Context from Memory` section (max 1000 chars)

### Requirement: Change dispatch with dependency ordering
The orchestrator SHALL dispatch changes respecting the dependency graph and parallelism limits.

#### Scenario: Dependency-ordered dispatch
- **WHEN** pending changes exist
- **THEN** the orchestrator SHALL dispatch only changes whose `depends_on` entries all have status `merged`
- **AND** respect the `max_parallel` limit (concurrent running + dispatched)

#### Scenario: Worktree creation and Ralph launch
- **WHEN** a change is dispatched
- **THEN** the orchestrator SHALL create a worktree via `wt-new`, bootstrap it (env files + dependencies), create the OpenSpec change, pre-create proposal.md, and start a Ralph loop via `wt-loop start --max 30 --done openspec --label {name} --model opus`

### Requirement: Monitor loop polling
The orchestrator monitor loop SHALL poll active changes every 15 seconds.

#### Scenario: Poll interval
- **WHEN** the monitor loop is running
- **THEN** it SHALL sleep for `POLL_INTERVAL` (15) seconds between poll cycles

#### Scenario: Active time tracking
- **WHEN** polling and at least one Ralph loop is making progress (loop-state.json mtime < 5 minutes)
- **THEN** the orchestrator SHALL increment `active_seconds` by `POLL_INTERVAL`
- **AND** NOT count time during token budget wait or when all loops are stalled

### Requirement: State initialization
The `init_state()` function SHALL initialize change objects with correct field types.

#### Scenario: New state initialization
- **WHEN** `init_state()` creates orchestration state from a plan
- **THEN** each change object SHALL include `verify_retry_count: 0` (integer)
- **AND** SHALL NOT include `verify_retried` (boolean)
- **AND** SHALL include: name, scope, complexity, depends_on, roadmap_item, status ("pending"), worktree_path (null), ralph_pid (null), started_at (null), completed_at (null), tokens_used (0), test_result (null)

### Requirement: Stalled change cooldown resume
The monitor loop SHALL automatically resume stalled changes after a 5-minute cooldown.

#### Scenario: Stalled change resume after cooldown
- **WHEN** a change has status `stalled`
- **AND** at least 300 seconds have elapsed since `stalled_at`
- **THEN** the orchestrator SHALL call `resume_change()`

### Requirement: Failed build retry in monitor loop
The monitor loop SHALL attempt lightweight retries for build failures before full replan.

#### Scenario: Build failure retry
- **WHEN** a change has status `failed` and `build_result: "fail"`
- **AND** `gate_retry_count` < `max_verify_retries`
- **THEN** the orchestrator SHALL set `retry_context` with build error output, set status to `pending`, and call `resume_change()`

### Requirement: Token budget enforcement
The orchestrator SHALL enforce a cumulative token budget across all changes.

#### Scenario: Budget exceeded
- **WHEN** `token_budget` > 0 and total tokens across all changes exceed it
- **THEN** the orchestrator SHALL stop dispatching new changes
- **AND** continue polling running changes until they complete naturally

### Requirement: Auto-replan system
The orchestrator SHALL support automatic replanning when all changes complete.

#### Scenario: Auto-replan on completion
- **WHEN** all changes reach terminal status (done/merged/merge-blocked/failed)
- **AND** `auto_replan` directive is true
- **THEN** the orchestrator SHALL re-run `cmd_plan` with completed roadmap items as context
- **AND** if new changes are found (rc=0), dispatch them and continue monitoring
- **AND** if no new work (rc=1), set status to `done` and exit
- **AND** if plan fails (rc=2), retry up to `MAX_REPLAN_RETRIES` (3) before giving up

#### Scenario: Replan preserves cumulative state
- **WHEN** a replan cycle reinitializes state
- **THEN** the orchestrator SHALL preserve `active_seconds`, `started_epoch`, `time_limit_secs`, and `prev_total_tokens`

#### Scenario: Failed change deduplication in replan
- **WHEN** a replan produces only previously-failed change names
- **THEN** the orchestrator SHALL return rc=1 (no new work) instead of dispatching the same failures

### Requirement: Time limit safety net
The orchestrator SHALL enforce an active time limit to prevent runaway execution.

#### Scenario: Time limit reached
- **WHEN** `active_seconds` exceeds `time_limit_secs` (default: 5h, "none" to disable)
- **THEN** the orchestrator SHALL set status to `time_limit`, send notification, and break the monitor loop
- **AND** the user can resume with `wt-orchestrate start`

### Requirement: Directive resolution with 4-level precedence
The orchestrator SHALL resolve directives from multiple sources with a defined precedence.

#### Scenario: Precedence chain for config directives
- **WHEN** resolving directives (max_parallel, merge_policy, checkpoint_every, test_command, etc.)
- **THEN** the orchestrator SHALL apply: (1) CLI flags > (2) `.claude/orchestration.yaml` > (3) in-document directives > (4) built-in defaults
- **AND** currently only `--max-parallel` participates in the merge chain via `resolve_directives()`

#### Scenario: CLI-only flags bypass directive chain
- **WHEN** `--time-limit` is provided
- **THEN** it SHALL be consumed directly in the monitor loop via `CLI_TIME_LIMIT` variable
- **AND** SHALL NOT be merged into the directives JSON object

### Requirement: Human checkpoint system
The orchestrator SHALL pause for human approval at configured intervals.

#### Scenario: Periodic checkpoint
- **WHEN** `changes_since_checkpoint` reaches `checkpoint_every`
- **THEN** the orchestrator SHALL generate `orchestration-summary.md`, send desktop notification, set status to `checkpoint`, and poll for approval every 5 seconds

#### Scenario: Checkpoint approval
- **WHEN** `wt-orchestrate approve` is invoked
- **THEN** the orchestrator SHALL set the latest checkpoint's `approved` to true
- **AND** if `--merge` flag: also execute the merge queue

### Requirement: Pause and resume
The orchestrator SHALL support pausing and resuming individual changes or all changes.

#### Scenario: Pause a change
- **WHEN** `wt-orchestrate pause <name>` is invoked
- **THEN** the orchestrator SHALL send SIGTERM to the Ralph terminal PID and mark status `paused`

#### Scenario: Resume a change
- **WHEN** `wt-orchestrate resume <name>` is invoked
- **THEN** the orchestrator SHALL restart Ralph with the appropriate task description and mark status `running`

### Requirement: Auto-detect test command (DEFERRED — not wired)
The function `auto_detect_test_command()` exists but is NOT currently called. It detects test scripts from package.json (test, test:unit, test:ci) with package manager detection. A future change should introduce this as an opt-in directive.

#### Scenario: Current behavior — no auto-detection
- **WHEN** no `test_command` is set via CLI, config file, or in-document directives
- **THEN** the verify gate SHALL skip test execution entirely

### Requirement: Orchestrator logging
The orchestrator SHALL maintain an append-only log file with rotation.

#### Scenario: Log rotation
- **WHEN** `.claude/orchestration.log` exceeds 100KB
- **THEN** the orchestrator SHALL truncate to the last 50KB

#### Scenario: Log format
- **WHEN** logging an event
- **THEN** the format SHALL be `[ISO-8601-timestamp] [LEVEL] message`
## Requirements
### Requirement: Monitor loop poll interval
The orchestrator monitor loop SHALL poll active changes every 15 seconds.

#### Scenario: Poll interval timing
- **WHEN** the monitor loop is running
- **THEN** it SHALL sleep for 15 seconds between poll cycles
- **AND** the constant `POLL_INTERVAL` SHALL be set to 15

### Requirement: Dispatch creates proposal.md
The orchestrator SHALL pre-create `proposal.md` (not `brief-context.md`) in the change directory during dispatch, providing Ralph with structured scope context.

#### Scenario: Proposal pre-creation on dispatch
- **WHEN** `dispatch_change()` creates a new change in a worktree
- **AND** no `proposal.md` exists yet
- **THEN** the orchestrator SHALL create `openspec/changes/{name}/proposal.md` with:
  - `## Why` section containing the roadmap item
  - `## What Changes` section containing the scope text
  - `## Capabilities` section with the change name
  - `## Impact` section (placeholder)
- **AND** if dispatch memories are available, append a `## Context from Memory` section (max 1000 chars)

### Requirement: State initialization with integer verify retry count
The `init_state()` function SHALL initialize `verify_retry_count` as an integer (0), not a boolean.

#### Scenario: New state initialization
- **WHEN** `init_state()` creates the orchestration state from a plan
- **THEN** each change object SHALL include `verify_retry_count: 0` (integer)
- **AND** SHALL NOT include `verify_retried` (boolean)

### Requirement: Stalled change cooldown resume
The monitor loop SHALL automatically resume stalled changes after a 5-minute cooldown period.

#### Scenario: Stalled change resume after cooldown
- **WHEN** a change has status `stalled`
- **AND** at least 300 seconds have elapsed since `stalled_at`
- **THEN** the orchestrator SHALL call `resume_change()` for that change

#### Scenario: Stalled change within cooldown
- **WHEN** a change has status `stalled`
- **AND** less than 300 seconds have elapsed since `stalled_at`
- **THEN** the orchestrator SHALL skip the change (wait for cooldown)

### Requirement: Failed build retry in monitor loop
The monitor loop SHALL attempt lightweight retries for changes that failed build verification before triggering a full replan cycle.

#### Scenario: Build failure retry
- **WHEN** a change has status `failed` and `build_result: "fail"`
- **AND** `gate_retry_count` is less than `max_verify_retries`
- **THEN** the orchestrator SHALL increment `gate_retry_count`
- **AND** set `retry_context` with the build error output
- **AND** set status to `pending` and call `resume_change()`

#### Scenario: Build failure retry exhausted
- **WHEN** a change has status `failed` and `build_result: "fail"`
- **AND** `gate_retry_count` >= `max_verify_retries`
- **THEN** the orchestrator SHALL skip the change (remain in `failed`)

### Requirement: Auto-detect test command (DEFERRED — not wired)
The function `auto_detect_test_command()` exists but is NOT currently called. It is dead code from the original VG-3 spec. Wiring it in would change behavior for projects that previously had no test gate, potentially breaking stable orchestration runs. A future change should introduce this as an opt-in directive (e.g., `auto_detect_tests: true`).

#### Scenario: Current behavior — no auto-detection
- **WHEN** no `test_command` is set via CLI, config file, or in-document directives
- **THEN** the verify gate SHALL skip test execution entirely
- **AND** `auto_detect_test_command()` SHALL NOT be called

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
  - Memory context from `wt-memory` (if available)

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

