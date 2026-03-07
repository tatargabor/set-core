## MODIFIED Requirements

### Requirement: Plan generation from project input
The orchestrator SHALL decompose a project brief or specification document into an ordered list of OpenSpec changes via a single Claude CLI invocation, OR via an agent-based decomposition in a planning worktree.

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

#### Scenario: Agent-based plan generation
- **WHEN** `wt-orchestrate plan` is invoked
- **AND** directive `plan_method: agent` is set in orchestration config
- **THEN** the orchestrator SHALL create a planning worktree via `wt-new wt-planning-v{N}`
- **AND** dispatch a Ralph loop with the `/wt:decompose` skill as task context
- **AND** wait for the Ralph loop to complete
- **AND** extract and validate `orchestration-plan.json` from the planning worktree
- **AND** copy the validated plan to the project root
- **AND** clean up the planning worktree

#### Scenario: Agent planning fallback on failure
- **WHEN** agent-based planning fails (timeout, invalid JSON, validation error)
- **THEN** the orchestrator SHALL log a warning with the failure reason
- **AND** fall back to the existing API-based planning method
- **AND** clean up the planning worktree

#### Scenario: Phase hint for spec mode
- **WHEN** `--phase <hint>` is provided alongside `--spec`
- **THEN** the orchestrator SHALL include the hint in the Claude prompt to focus decomposition

#### Scenario: Spec summary cache
- **WHEN** a large spec is summarized
- **THEN** the summary SHALL be cached in `.claude/spec-summary-cache.json` keyed by the spec file's SHA-256 hash
- **AND** subsequent plans with the same hash SHALL reuse the cached summary

#### Scenario: Plan metadata fields
- **WHEN** any plan is generated (API or agent method)
- **THEN** the plan JSON SHALL include `plan_phase` (`"initial"` or `"iteration"`) and `plan_method` (`"api"` or `"agent"`)
- **AND** agent-method plans SHALL additionally include `planning_worktree` with the worktree name

#### Scenario: Backward-compatible metadata
- **WHEN** an existing plan JSON lacks `plan_phase` or `plan_method`
- **THEN** the orchestrator SHALL treat missing `plan_phase` as `"initial"` and missing `plan_method` as `"api"`
