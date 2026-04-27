## ADDED Requirements

## IN SCOPE
- Detect shadcn/ui projects by presence of `components.json` with valid schema
- Integrate detection into the planner preflight design context pipeline
- Trigger local snapshot generation when shadcn/ui detected and no design MCP available
- Bridge function `detect_shadcn_project()` callable from bash and Python

## OUT OF SCOPE
- Detecting other CSS-in-JS or component library setups (Chakra, MUI, etc.)
- Auto-installing shadcn/ui in projects that don't have it
- Detecting shadcn/ui in monorepo sub-packages (only project root)

### Requirement: Detect shadcn/ui project
The bridge SHALL provide a `detect_shadcn_project()` function that checks for shadcn/ui presence in the project root.

#### Scenario: shadcn/ui project detected
- **WHEN** `components.json` exists in the project root
- **AND** it contains a valid `tailwind` section (with `config` and `css` keys)
- **THEN** `detect_shadcn_project()` returns 0 and prints the path to `components.json`

#### Scenario: Non-shadcn project
- **WHEN** `components.json` does not exist or lacks the expected structure
- **THEN** `detect_shadcn_project()` returns 1 silently

### Requirement: Preflight integration
The planner preflight SHALL attempt local shadcn snapshot generation when no design MCP is detected.

#### Scenario: No MCP but shadcn/ui present
- **WHEN** `detect_design_mcp()` returns 1 (no design MCP registered)
- **AND** `detect_shadcn_project()` returns 0 (shadcn/ui found)
- **AND** no cached `design-snapshot.md` exists (or `force=True`)
- **THEN** the planner calls the shadcn parser to generate `design-snapshot.md`
- **AND** the generated snapshot is cached in the same location as MCP-fetched snapshots

#### Scenario: MCP takes priority over local detection
- **WHEN** `detect_design_mcp()` returns 0 (Figma/Penpot MCP registered)
- **AND** `detect_shadcn_project()` would also return 0
- **THEN** the MCP-based fetch is used (MCP is authoritative)
- **AND** the shadcn local parser is NOT invoked

#### Scenario: Neither MCP nor shadcn/ui
- **WHEN** both `detect_design_mcp()` and `detect_shadcn_project()` return 1
- **THEN** the planner continues without design context (existing behavior unchanged)
