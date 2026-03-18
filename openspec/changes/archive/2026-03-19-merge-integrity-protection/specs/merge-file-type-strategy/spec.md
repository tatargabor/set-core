## ADDED Requirements

## IN SCOPE
- File-type-aware merge strategy configuration in project-knowledge.yaml
- Strategy types: additive (entity-counted), llm_with_conservation (default)
- Entity counting for "additive" strategy files relative to merge-base
- LLM prompt enrichment with file-type hints
- Post-merge validation commands per file type
- Profile system integration (profiles supply default strategies via line-delimited file)
- Agent rule for DB type safety (prohibit `any` on DB client parameters)

## OUT OF SCOPE
- Automatic conflict resolution beyond existing LLM mechanism
- Schema-aware parsing (AST-level analysis of Prisma/TypeScript files)
- Per-project custom merge scripts (only declarative config)
- Modifying the JSON deep-merge or lockfile regeneration (already working, runs before LLM)
- `json_deep_merge` and `regenerate` strategy types (already handled by existing pre-LLM pipeline)

### Requirement: Merge strategy configuration
Projects SHALL be able to declare file-type merge strategies in `project-knowledge.yaml` under a `merge_strategies` key. Each strategy maps file patterns to merge behavior. `wt-merge` SHALL parse strategy config using `python3 -c` (YAML parsing is not feasible in pure bash; the existing codebase already depends on Python).

#### Scenario: Strategy configuration format
- **WHEN** a project has `merge_strategies` in `project-knowledge.yaml`
- **THEN** each entry SHALL have:
  - `patterns`: array of glob patterns (e.g., `["prisma/schema.prisma", "*.prisma"]`)
  - `strategy`: one of `"additive"`, `"llm_with_conservation"`
  - `entity_pattern` (optional): regex for counting named entities
  - `validate_command` (optional): shell command to run after merge (non-zero = block)
  - `llm_hint` (optional): additional context injected into LLM merge prompt for matching files

#### Scenario: Default strategy for unconfigured files
- **WHEN** a conflicted file does not match any configured pattern
- **THEN** the `llm_with_conservation` strategy SHALL be applied (LLM resolve + generic conservation check)

#### Scenario: Strategy config interaction with existing pre-LLM pipeline
- **WHEN** a file matches both the existing pre-LLM auto-resolve pipeline (JSON deep merge, lockfile regeneration) and a merge strategy
- **THEN** the pre-LLM pipeline runs first (as today)
- **AND** merge strategies only apply to files that reach `llm_resolve_conflicts()` (i.e., files not already resolved by the pre-LLM pipeline)

### Requirement: Additive merge strategy with entity counting
Files matched by an "additive" strategy SHALL be merged with the LLM resolver but with additional pre/post entity count validation relative to merge-base. If entities added by either side are missing from the merged result, the merge SHALL be blocked.

#### Scenario: Entity count preserved after merge
- **WHEN** file F matches an "additive" strategy with `entity_pattern` regex R
- **AND** merge-base version has B entities matching R
- **AND** ours version has N entities matching R (ours_added = N - B)
- **AND** theirs version has M entities matching R (theirs_added = M - B)
- **AND** the LLM-resolved version has P entities matching R
- **AND** P >= B + ours_added + theirs_added (i.e., union of both sides' additions)
- **THEN** the entity count check SHALL pass

#### Scenario: Entity count drops after merge
- **WHEN** file F matches an "additive" strategy
- **AND** the LLM-resolved version has fewer entities than expected (B + ours_added + theirs_added)
- **THEN** the merge SHALL be blocked
- **AND** the log SHALL include: "MERGE BLOCKED: entity count dropped in {file} (expected {expected}, got {actual})"

#### Scenario: Additive strategy enriches LLM prompt
- **WHEN** file F matches an "additive" strategy with `llm_hint`
- **THEN** the LLM merge prompt for F SHALL include the hint text before the conflict hunks
- **AND** SHALL include: "This file uses additive merge — NEVER remove entities from either side"

### Requirement: Post-merge validation command
When a strategy specifies `validate_command`, it SHALL be executed after LLM resolution and entity check, before commit. The command runs from the project root with the resolved file already on disk.

#### Scenario: Validation command passes
- **WHEN** file F matches a strategy with `validate_command` C
- **AND** the conservation check and entity check pass
- **THEN** `wt-merge` SHALL execute C via `bash -c`
- **AND** if exit code is 0, the merge SHALL proceed

#### Scenario: Validation command fails
- **WHEN** the validation command returns non-zero
- **THEN** the merge SHALL be blocked
- **AND** the log SHALL include: "MERGE BLOCKED: validation failed for {file}: {command output}"

### Requirement: LLM prompt enrichment from strategy config
When resolving conflicts, the LLM merge prompt SHALL be enriched with file-type context from matching strategies. Hints are injected into the INPUT prompt only — the output format (`--- FILE: <path> ---`) SHALL NOT be modified.

#### Scenario: LLM receives file-type hint
- **WHEN** `llm_resolve_conflicts()` processes file F
- **AND** F matches a strategy with `llm_hint` H
- **THEN** the prompt SHALL include H as context before the conflict hunks for F
- **AND** the prompt SHALL indicate the strategy type (e.g., "Merge strategy: additive — keep all entities from both sides")

### Requirement: Profile system supplies default merge strategies
Project profiles SHALL be able to supply default merge strategies that apply when no project-level config exists. Profile defaults are written as a JSON file at `.wt-tools/.merge-strategies.json` during `wt-project init`.

#### Scenario: Profile provides defaults
- **WHEN** a profile implements `merge_strategies()` method
- **AND** the project has no `merge_strategies` in `project-knowledge.yaml`
- **THEN** the profile's default strategies SHALL be used (read from `.wt-tools/.merge-strategies.json`)

#### Scenario: Project config overrides profile defaults
- **WHEN** both profile and project-knowledge.yaml define strategies for the same pattern
- **THEN** the project-knowledge.yaml entry SHALL take precedence

### Requirement: Agent rule prohibiting DB type hacks
A new agent rule SHALL be deployed to consumer projects prohibiting the use of `any` type on database client parameters.

#### Scenario: Rule file exists and is deployed
- **WHEN** `wt-project init` runs on a consumer project
- **THEN** `.claude/rules/web/db-type-safety.md` SHALL be created
- **AND** it SHALL contain instructions prohibiting `prisma: any`, `prisma as any`, and similar patterns
- **AND** it SHALL instruct: "If a DB model is missing from the schema, add the model — do not work around it with type hacks"

#### Scenario: Verify gate checks for DB type hacks
- **WHEN** the verify gate runs code review on a change
- **THEN** the review prompt SHALL flag `any` type usage on database client parameters as CRITICAL
