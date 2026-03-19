## ADDED Requirements

### Requirement: Decomposition skill for planning agent

A `/wt:decompose` skill SHALL exist that guides the planning agent through spec-to-execution-plan conversion. The skill SHALL be deployed to consumer projects via `set-project init`.

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
