## ADDED Requirements

### Requirement: Planning guide document
The project SHALL include a `docs/planning-guide.md` document that covers how to write effective orchestration plan inputs. The guide SHALL be organized by planning concern (scope, dependencies, testing, sizing, design rules) rather than workflow steps.

#### Scenario: User consults guide before first orchestration run
- **WHEN** a user needs to write a spec document or project brief for orchestration
- **THEN** the guide provides concrete examples of both input formats (spec mode and brief mode) with annotated structure

### Requirement: Input format documentation
The guide SHALL document both input modes (spec mode via `--spec` and brief mode via `project-brief.md`) with complete examples showing correct structure, directive placement, and content expectations.

#### Scenario: Spec mode input example
- **WHEN** the guide covers spec mode
- **THEN** it includes an annotated example showing: section organization, status markers for completed items, phase grouping, and the `## Orchestrator Directives` section

#### Scenario: Brief mode input example
- **WHEN** the guide covers brief mode
- **THEN** it includes an annotated example showing: the `### Next` section with well-scoped bullet items, the `### Done` section for tracking, and directive placement

### Requirement: Scope isolation guidance
The guide SHALL explain how to write change scopes that minimize merge conflicts. It SHALL cover the principle that changes touching the same files (especially shared types, barrel exports, config files) MUST declare dependencies or be sequenced.

#### Scenario: Parallel-safe scope description
- **WHEN** the guide covers scope isolation
- **THEN** it provides examples of good scopes (isolated modules) vs bad scopes (overlapping files) with an explanation of why overlapping scopes cause merge conflicts

### Requirement: Dependency declaration guidance
The guide SHALL explain when and how to use `depends_on` in plan inputs. It SHALL cover both explicit dependencies (code imports) and implicit dependencies (shared schema migrations, type definitions, config changes).

#### Scenario: Identifying implicit dependencies
- **WHEN** the guide covers dependencies
- **THEN** it lists common implicit dependency patterns: DB schema changes, shared type unions, barrel export files, config/env additions, package.json modifications

### Requirement: Testing requirements in plans
The guide SHALL explain how to specify test requirements in plan inputs so the decomposition prompt produces changes with adequate test coverage.

#### Scenario: Test specification guidance
- **WHEN** the guide covers testing
- **THEN** it explains that each change scope should mention: what to test (happy path, error cases), test style (unit/integration), and any shared test infrastructure needs

### Requirement: Plan sizing and splitting strategies
The guide SHALL explain how to assess whether a plan is too large and how to split it into phases. It SHALL cover the trade-offs between fewer large changes and many small changes.

#### Scenario: Sizing guidance
- **WHEN** the guide covers sizing
- **THEN** it provides guidelines: S (<10 tasks) for focused changes, M (10-25 tasks) for features, L (25+ tasks) as a warning sign that should be split; and that a batch of 4-6 changes is optimal for parallel execution

#### Scenario: Phase splitting
- **WHEN** a spec document covers more work than fits in one orchestration batch
- **THEN** the guide explains how to use phase markers in the spec so the orchestrator picks one phase at a time, and how `--phase` can focus on a specific phase

### Requirement: Design rules guidance
The guide SHALL explain what design constraints to specify in plan inputs (architecture patterns, naming conventions, specific libraries) vs what to leave to the agent (implementation details, file organization within modules).

#### Scenario: What to specify
- **WHEN** the guide covers design rules
- **THEN** it lists effective constraints: tech stack, API patterns (REST/GraphQL), auth approach, DB access patterns, error handling strategy, naming conventions

#### Scenario: What to leave open
- **WHEN** the guide covers design rules
- **THEN** it lists things that are counterproductive to over-specify: exact file paths, line-level implementation details, variable names, internal function decomposition

### Requirement: Web project planning patterns
The guide SHALL include a dedicated section on planning patterns for typical web projects with database persistence, authentication, API routes, and deployment platforms.

#### Scenario: DB schema change pattern
- **WHEN** the guide covers web project patterns
- **THEN** it explains that schema migrations MUST be in a separate change that other changes depend on, because parallel schema changes cause migration conflicts

#### Scenario: Auth layer pattern
- **WHEN** the guide covers web project patterns
- **THEN** it explains that authentication/authorization changes are foundational and MUST be early dependencies, not parallel work

#### Scenario: Deployment considerations
- **WHEN** the guide covers web project patterns
- **THEN** it mentions environment variables, build commands, and platform-specific constraints (e.g., Railway, Vercel) that should be specified in the plan

### Requirement: Anti-patterns section
The guide SHALL document common planning mistakes with explanations of why they fail and how to fix them.

#### Scenario: Anti-pattern examples
- **WHEN** the guide covers anti-patterns
- **THEN** it includes at least: overlapping scopes without dependencies, missing test requirements, oversized changes, vague scope descriptions, and forgetting shared infrastructure setup

### Requirement: Plan review checklist
The project SHALL include a `docs/plan-checklist.md` quick-reference document with a scannable checklist for reviewing an orchestration plan before execution.

#### Scenario: Checklist covers critical items
- **WHEN** a user reviews the checklist
- **THEN** it includes checks for: scope overlap, dependency completeness, test requirements, sizing, shared file conflicts, infrastructure setup, and directive configuration

#### Scenario: Checklist is standalone
- **WHEN** a user opens the checklist
- **THEN** it is usable without reading the full planning guide — each item is self-explanatory with a brief rationale
