## MODIFIED Requirements

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
