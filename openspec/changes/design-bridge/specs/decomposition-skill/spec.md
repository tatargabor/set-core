## MODIFIED Requirements

### Requirement: Decompose queries design MCP for frame inventory
The decompose skill SHALL detect design MCP availability and query it for a frame/component inventory during change scoping.

#### Scenario: Design MCP available during decompose
- **WHEN** `detect_design_mcp` returns a design tool name and the decompose skill runs in a Claude Code session
- **THEN** the skill queries the design MCP for available frames/pages and maps them to planned changes
- **AND** each change's scope description includes the relevant design frame reference (e.g., `design_ref: "frame:Login"`)

#### Scenario: Design MCP not available during decompose
- **WHEN** no design MCP is registered
- **THEN** decompose behaves identically to today — no design references in change scoping

### Requirement: Decompose flags design gaps as ambiguities
When a planned change involves UI but no matching design frame exists, the decompose skill SHALL flag it as a design gap ambiguity in the plan output.

#### Scenario: Spec requires page without design frame
- **WHEN** the spec describes a "Checkout" page but the design tool has no matching frame
- **THEN** the decompose output includes an ambiguity entry of type `design_gap` with the missing page name
- **AND** the change can still proceed but the ambiguity is recorded for user resolution
