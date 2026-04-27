# Planner Validation Hardening Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope

- Python hard validation for change count, complexity, model, scope length in `validate_plan()`
- `planning_rules()` and `cross_cutting_files()` methods on `ProjectType` ABC
- Web module implements both methods with web-specific knowledge
- Core `_PLANNING_RULES_CORE` trimmed to universal rules only
- Validation failures trigger LLM retry with error context

### Out of scope
- Changing the LLM prompt structure or planning strategy
- Adding new planning phases or domain-parallel decompose logic
- Modifying digest, dispatch, or gate pipelines
- New CLI commands or dashboard changes

## Requirements

### Requirement: Hard validation of change count
`validate_plan()` SHALL reject plans where `len(changes) > max_change_target`. The `max_change_target` value SHALL be passed to the validator (from `max_parallel * 2`). Rejection SHALL trigger LLM retry with the specific error.

#### Scenario: Plan within change limit
- **WHEN** `validate_plan()` receives a plan with 5 changes and `max_change_target=6`
- **THEN** no error is raised for change count

#### Scenario: Plan exceeds change limit
- **WHEN** `validate_plan()` receives a plan with 8 changes and `max_change_target=6`
- **THEN** a validation error is returned: "Plan has 8 changes, max allowed is 6. Merge related changes."
- **AND** the planner retries the LLM call with this error appended

### Requirement: Hard validation of change complexity
`validate_plan()` SHALL reject any change with `complexity` not in `{"S", "M"}`. L complexity is forbidden — the LLM must split large changes.

#### Scenario: Valid complexity values
- **WHEN** all changes have `complexity` of `"S"` or `"M"`
- **THEN** no error is raised for complexity

#### Scenario: L complexity rejected
- **WHEN** a change has `complexity: "L"`
- **THEN** a validation error is returned: "Change '<name>' has complexity L. Split into S or M changes."

### Requirement: Hard validation of model assignment
`validate_plan()` SHALL reject any change with `model` not in `{"opus", "sonnet"}`.

#### Scenario: Valid model values
- **WHEN** all changes have `model` of `"opus"` or `"sonnet"`
- **THEN** no error is raised for model

#### Scenario: Invalid model rejected
- **WHEN** a change has `model: "haiku"`
- **THEN** a validation error is returned: "Change '<name>' has invalid model 'haiku'. Use 'opus' or 'sonnet'."

### Requirement: Hard validation of scope length
`validate_plan()` SHALL reject any change with `len(scope) > 2000`. Oversized scopes indicate the change should be split.

#### Scenario: Scope within limit
- **WHEN** a change has a scope of 1500 characters
- **THEN** no error is raised for scope length

#### Scenario: Oversized scope rejected
- **WHEN** a change has a scope of 2500 characters
- **THEN** a validation error is returned: "Change '<name>' scope is 2500 chars (max 2000). Split the change or reduce scope."

### Requirement: Profile provides planning rules
`ProjectType` ABC SHALL define `planning_rules() -> str` returning module-specific planning rules as plain text. Default: empty string. `render_planning_prompt()` SHALL append profile rules after core rules.

#### Scenario: Core profile returns no planning rules
- **WHEN** `CoreProfile.planning_rules()` is called
- **THEN** it returns an empty string
- **AND** the planner prompt contains only `_PLANNING_RULES_CORE` universal rules

#### Scenario: Web profile returns web-specific rules
- **WHEN** `WebProjectType.planning_rules()` is called
- **THEN** it returns rules including: schema/migration ordering, CRUD test requirements, i18n namespace convention
- **AND** the planner prompt appends these after core rules

### Requirement: Profile provides cross-cutting file list
`ProjectType` ABC SHALL define `cross_cutting_files() -> list[str]` returning file patterns that need serialization when touched by multiple changes. Default: empty list. `_assign_cross_cutting_ownership()` SHALL use this list instead of the hardcoded one.

#### Scenario: Core profile returns no cross-cutting files
- **WHEN** `CoreProfile.cross_cutting_files()` is called
- **THEN** it returns an empty list
- **AND** no cross-cutting ownership is assigned

#### Scenario: Web profile returns web cross-cutting files
- **WHEN** `WebProjectType.cross_cutting_files()` is called
- **THEN** it returns patterns including: `layout.tsx`, `middleware.ts`, `tailwind.config.ts`, `next.config.mjs`, `globals.css`, `schema.prisma`
- **AND** `_assign_cross_cutting_ownership()` uses this list to detect multi-change file conflicts

### Requirement: Core planning rules contain only universal rules
`_PLANNING_RULES_CORE` in `templates.py` SHALL contain only project-type-agnostic rules: complexity limits, dependency ordering (infra→foundation→feature→cleanup), scope length guidance, change grouping rules, phase assignment. All web-specific rules SHALL be removed.

#### Scenario: Non-web project gets no web rules
- **WHEN** a project uses `CoreProfile` (no web module)
- **AND** `render_planning_prompt()` is called
- **THEN** the prompt does NOT contain "layout.tsx", "middleware", "tailwind", "CRUD", "schema/migration", "i18n"

#### Scenario: Web project gets full rules
- **WHEN** a project uses `WebProjectType`
- **AND** `render_planning_prompt()` is called
- **THEN** the prompt contains both core universal rules AND web-specific rules from `planning_rules()`
