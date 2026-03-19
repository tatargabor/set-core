## ADDED Requirements

### Requirement: Resolve effective model for change
The system SHALL resolve the implementation model using three-tier priority: (1) explicit per-change model from state, (2) complexity-based routing when enabled, (3) default model from directive. Doc-named changes (doc-*, *-doc-*, *-docs, *-docs-*) SHALL always route to sonnet. Sonnet SHALL be overridden to opus for non-doc code changes.

#### Scenario: Explicit per-change model
- **WHEN** a change has an explicit model field in state
- **THEN** that model is used (unless sonnet for non-doc change, which overrides to opus)

#### Scenario: Complexity-based routing
- **WHEN** model_routing is "complexity" and change is S-complexity non-feature
- **THEN** the change routes to sonnet

#### Scenario: Doc change always sonnet
- **WHEN** change name matches doc-* or *-docs pattern
- **THEN** model resolves to sonnet regardless of other settings

#### Scenario: Default model fallback
- **WHEN** no explicit model and no routing match
- **THEN** the default model from directive is used

### Requirement: Dispatch change to worktree
The system SHALL create a worktree via `set-new`, bootstrap it, prune orchestrator context, build proposal.md with scope/memory/project-knowledge/sibling context, and launch set-loop. Token counters SHALL be reset on fresh dispatch. If worktree already exists, stale loop state SHALL be cleaned up.

#### Scenario: Fresh dispatch
- **WHEN** dispatch_change is called for a pending change with no existing worktree
- **THEN** worktree is created, bootstrapped, proposal.md written, set-loop started, status set to "running"

#### Scenario: Existing worktree reuse
- **WHEN** worktree directory already exists at expected path
- **THEN** stale loop-state.json is cleaned up if PID is dead, worktree is reused

#### Scenario: Worktree creation failure
- **WHEN** set-new fails
- **THEN** change status is set to "failed" and function returns error

### Requirement: Dispatch via set-loop backend
The system SHALL start set-loop in a subshell, verify startup by polling for loop-state.json (up to 10 seconds), extract terminal PID, and update state with ralph_pid and status "running".

#### Scenario: Successful set-loop start
- **WHEN** set-loop is invoked and loop-state.json appears within 10 seconds
- **THEN** terminal_pid is extracted and change status is set to "running"

#### Scenario: set-loop fails to start
- **WHEN** loop-state.json does not appear after 10 seconds
- **THEN** change status is set to "failed" and an ERROR event is emitted

### Requirement: Dispatch ready changes with scheduling
The system SHALL dispatch pending changes in topological order, gated by phase and max_parallel limit. Ready changes SHALL be sorted by complexity (L > M > S) to reduce tail latency.

#### Scenario: Dispatch within parallel limit
- **WHEN** running count is below max_parallel and pending changes have deps satisfied
- **THEN** changes are dispatched in complexity-sorted order until limit is reached

#### Scenario: Phase gating
- **WHEN** a change belongs to a future phase
- **THEN** it is skipped even if its deps are satisfied

### Requirement: Build proposal with enrichment context
The system SHALL enrich proposal.md with dispatch memory (from memory recall), project knowledge (feature touches, cross-cutting files), sibling change status, design context, digest mode spec references, and retry context for redispatched changes.

#### Scenario: Proposal with project knowledge
- **WHEN** project-knowledge.yaml exists and change scope matches a feature
- **THEN** feature touches and cross-cutting files are appended to proposal

#### Scenario: Proposal with retry context
- **WHEN** change has retry_context in state
- **THEN** retry context is appended to proposal and cleared from state

### Requirement: Dispatcher prepares worktree CLAUDE.md with startup guide
The `dispatch_change()` function SHALL call the startup guide generator after copying artifacts to the worktree. The generator SHALL append an `## Application Startup` section to CLAUDE.md if one does not already exist.

#### Scenario: First dispatch to fresh worktree
- **WHEN** `dispatch_change()` prepares a worktree for the first time
- **AND** the worktree's CLAUDE.md has no `## Application Startup` section
- **THEN** the dispatcher SHALL append the generated startup guide

#### Scenario: Re-dispatch to existing worktree (retry)
- **WHEN** `dispatch_change()` re-dispatches a change after verify failure
- **AND** the worktree's CLAUDE.md already contains `## Application Startup`
- **THEN** the dispatcher SHALL NOT modify the startup section

### Requirement: Build-inclusive smoke command auto-detection
The config module SHALL provide `auto_detect_smoke_command(directory)` that resolves the smoke command using this chain:
1. Explicit `smoke_command` from orchestration.yaml (if non-empty)
2. If a build script exists (`build` or `build:ci` in package.json): `<pm> run build && <test_command>`
3. Fall back to `test_command` alone

#### Scenario: Build script exists and no explicit smoke_command
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has no `smoke_command` set
- **AND** package.json has a `build` script
- **AND** the detected test command is `pnpm test`
- **THEN** the function SHALL return `pnpm run build && pnpm test`

#### Scenario: Explicit smoke_command in config
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has `smoke_command: "pnpm test:smoke"`
- **THEN** the function SHALL return `pnpm test:smoke` (config takes precedence)

#### Scenario: No build script and no explicit smoke_command
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has no `smoke_command` set
- **AND** package.json has no `build` or `build:ci` script
- **THEN** the function SHALL fall back to the test_command
