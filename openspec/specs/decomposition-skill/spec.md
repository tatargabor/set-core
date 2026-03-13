## ADDED Requirements

### Requirement: Decomposition skill for planning agent

A `/wt:decompose` skill SHALL exist that guides the planning agent through spec-to-execution-plan conversion. The skill SHALL be deployed to consumer projects via `wt-project init`.

#### Scenario: Skill invocation with spec path
- **WHEN** the planning agent receives the decomposition task
- **THEN** the skill prompt SHALL instruct the agent to:
  1. Read the spec file
  2. Read project type config (`wt/plugins/project-type.yaml`) if present
  3. Read project knowledge (`wt/knowledge/project-knowledge.yaml`) if present
  4. Scan active requirements (`wt/requirements/*.yaml`)
  5. Use Agent tool (Explore) to scan codebase for existing implementations
  6. Recall memories with `phase:planning` tag filter
  7. List existing OpenSpec specs and active changes to avoid duplication
  8. Generate `orchestration-plan.json` following the existing schema

### Requirement: Context size management in skill

The decomposition skill SHALL include explicit context management instructions to prevent the planning agent from overloading its context window.

#### Scenario: Large spec handling
- **WHEN** the spec file exceeds 200 lines
- **THEN** the skill SHALL instruct the agent to use Agent tool (Explore) to analyze spec sections rather than reading the entire spec into context

#### Scenario: Codebase exploration delegation
- **WHEN** the planning agent needs to understand existing code structure
- **THEN** it SHALL use Agent tool (Explore) sub-agents for parallel codebase search
- **AND** sub-agents SHALL return summaries, not full file contents

#### Scenario: Project knowledge and requirements
- **WHEN** project knowledge and requirements files exist
- **THEN** these SHALL be read directly (they are small files)
- **AND** their content SHALL inform change decomposition (e.g., cross-cutting files affect dependency ordering)

### Requirement: Plan output validation

The decomposition skill SHALL produce output that passes the existing `validate_plan()` function.

#### Scenario: Valid plan output
- **WHEN** the planning agent completes decomposition
- **THEN** the output SHALL be a JSON file matching the `orchestration-plan.json` schema
- **AND** it SHALL include: `changes` array with `name`, `scope`, `complexity`, `change_type`, `model`, `depends_on`, `roadmap_item` per change
- **AND** `validate_plan()` SHALL pass (no circular dependencies, valid complexity values, etc.)

### Requirement: Project type context injection

The decomposition skill SHALL incorporate project type information when available.

#### Scenario: Project type available
- **WHEN** `wt/plugins/project-type.yaml` exists
- **THEN** the planning agent SHALL read verification rules and conventions from it
- **AND** use them to inform change_type assignment, dependency ordering, and complexity estimation
- **AND** project-type-specific patterns (e.g., "DB migration must be sequential") SHALL be reflected in the plan

#### Scenario: No project type configured
- **WHEN** `wt/plugins/project-type.yaml` does not exist
- **THEN** the skill SHALL proceed without project type context (graceful degradation)

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
