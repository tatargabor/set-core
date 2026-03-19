## MODIFIED Requirements

### Requirement: Change dispatch with dependency ordering
The orchestrator SHALL dispatch changes respecting the dependency graph and parallelism limits.

#### Scenario: Dependency-ordered dispatch
- **WHEN** pending changes exist
- **THEN** the orchestrator SHALL first cascade failed dependencies (marking pending changes as failed if any dependency has status `failed` or `merge-blocked`)
- **AND** then dispatch only changes whose `depends_on` entries all have status `merged` or `skipped`
- **AND** respect the `max_parallel` limit (concurrent running + dispatched)

#### Scenario: Failed dependency cascade before dispatch
- **WHEN** a change has status `pending`
- **AND** any of its `depends_on` entries has status `failed` or `merge-blocked`
- **THEN** the orchestrator SHALL mark the pending change as `failed` with failure_reason indicating which dependency failed
- **AND** this cascade SHALL happen BEFORE any dispatch attempt in each monitor loop iteration

#### Scenario: Worktree creation and Ralph launch
- **WHEN** a change is dispatched
- **THEN** the orchestrator SHALL create a worktree via `wt-new`, bootstrap it (env files + dependencies), create the OpenSpec change, pre-create proposal.md, and start a Ralph loop via `wt-loop start --max 30 --done openspec --label {name} --model {effective_model} --change {name}`
- **AND** the effective model SHALL be resolved via `resolve_change_model()` (see per-change-model spec)
- **AND** no per-change token budget SHALL be passed — the iteration limit (`--max 30`) provides the safety net instead

### MODIFIED Requirements

### Requirement: Monitor loop polling
The orchestrator monitor loop SHALL poll active changes every 15 seconds.

#### Scenario: Poll interval
- **WHEN** the monitor loop is running
- **THEN** it SHALL sleep for `POLL_INTERVAL` (15) seconds between poll cycles

#### Scenario: Active time tracking
- **WHEN** polling and at least one change is actively progressing (Ralph loop with recent loop-state.json mtime, OR change in `verifying` status)
- **THEN** the orchestrator SHALL increment `active_seconds` by `POLL_INTERVAL`
- **AND** NOT count time during token budget wait or when all changes are idle

### Requirement: CLI entry point subcommands
The `set-orch-core` CLI SHALL support the following subcommands: `process`, `state`, `template`, and `serve`. The `serve` subcommand SHALL start the FastAPI web dashboard server. The `cli.py` module SHALL import and delegate to `server.py` for the serve command.

#### Scenario: Serve subcommand
- **WHEN** user runs `set-orch-core serve --port 7400`
- **THEN** the FastAPI server starts with API endpoints, WebSocket support, and static file serving

#### Scenario: Existing subcommands unchanged
- **WHEN** user runs `set-orch-core process check-pid --pid 1234 --expect-cmd wt-loop`
- **THEN** the behavior is identical to the pre-change implementation

#### Scenario: Help text
- **WHEN** user runs `set-orch-core --help`
- **THEN** all four subcommands (process, state, template, serve) are listed with descriptions

### Requirement: run_claude supports MCP config passthrough
The `run_claude()` function SHALL accept MCP config passthrough via the `DESIGN_MCP_CONFIG` environment variable. When set, it adds `--mcp-config "$DESIGN_MCP_CONFIG"` to the claude CLI invocation.

#### Scenario: MCP config provided
- **WHEN** `DESIGN_MCP_CONFIG` is set to a valid JSON file path
- **THEN** `run_claude` includes `--mcp-config <path>` in the claude CLI command
- **AND** the spawned claude process has access to the design MCP tools

#### Scenario: No MCP config
- **WHEN** `DESIGN_MCP_CONFIG` is empty or unset
- **THEN** `run_claude` behaves identically to today — no `--mcp-config` flag

### Requirement: Planner injects design context when available
The planner SHALL detect design MCP, set up the MCP config passthrough, and inject a design prompt section into the planning prompt.

#### Scenario: Planning with design MCP
- **WHEN** `detect_design_mcp` returns a design tool name
- **THEN** the planner exports `DESIGN_MCP_CONFIG`, injects `design_prompt_section` into the prompt, and `run_claude` passes `--mcp-config` so the LLM can query the design tool during planning

#### Scenario: Planning without design MCP
- **WHEN** `detect_design_mcp` returns non-zero
- **THEN** the planner skips all design-related context injection — identical to current behavior

### Requirement: Dispatcher injects design references into proposals
The dispatcher SHALL check for `design_ref` fields in plan changes and inject them into the proposal.md written to each worktree.

#### Scenario: Change has design reference
- **WHEN** a plan change has `design_ref: "frame:Login"` (set by decompose/planner)
- **THEN** the dispatcher appends a `## Design Reference` section to proposal.md with the frame reference and instructions to query the design MCP

#### Scenario: Change has no design reference
- **WHEN** a plan change has no `design_ref` field
- **THEN** the dispatcher does not add a design reference section — proposal.md is identical to today

### Requirement: Missing design elements surface as ambiguities
When the planner or decompose identifies a function/page that has no corresponding design frame, it SHALL flag it in the plan's standard ambiguity format.

#### Scenario: Cart page missing from design
- **WHEN** the spec requires a "Cart" page but no matching frame exists in the design tool
- **THEN** an ambiguity is added: `{"type":"design_gap","description":"Cart page has no design frame","resolution_needed":"Create Cart frame in Figma or confirm implementation without design"}`
