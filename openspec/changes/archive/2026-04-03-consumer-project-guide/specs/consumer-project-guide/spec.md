## ADDED Requirements

## IN SCOPE
- Core rule template explaining set-core project structure to consumer project agents
- File ownership documentation (set-* managed vs project-owned)
- Guidelines for adding custom project rules
- Guidelines for extending conventions with domain-specific patterns
- OpenSpec change-writing guidance within set-core projects
- Config and knowledge file location reference

## OUT OF SCOPE
- Changes to deploy logic (existing `templates/core/rules/` mechanism handles deployment)
- Project-type-specific guidance (mobile, fintech patterns themselves — those are project-owned rules)
- Interactive onboarding or wizard flows

### Requirement: Project guide rule template
The system SHALL include a `templates/core/rules/project-guide.md` file that gets deployed to consumer projects as `.claude/rules/set-project-guide.md`.

#### Scenario: Guide deployed on init
- **WHEN** `set-project init` runs on a consumer project
- **THEN** `.claude/rules/set-project-guide.md` exists in the project
- **AND** it contains sections on file ownership, custom rules, extending conventions, and OpenSpec usage

### Requirement: File ownership documentation
The guide SHALL clearly document which files are set-core managed and which are project-owned.

#### Scenario: Agent reads guide before modifying rules
- **WHEN** a Claude agent in the consumer project reads `.claude/rules/set-project-guide.md`
- **THEN** it understands that `set-*.md` files are managed by set-core and SHALL NOT be modified directly
- **AND** it understands that non-prefixed `.claude/rules/*.md` files are project-owned and can be freely edited

### Requirement: Custom rule creation guidance
The guide SHALL explain how to add project-specific rules.

#### Scenario: Agent adds domain-specific rule
- **WHEN** a Claude agent needs to add mobile navigation patterns
- **THEN** the guide instructs it to create `.claude/rules/mobile-navigation.md` (without `set-` prefix)
- **AND** the guide explains that these rules are preserved across `set-project init` re-runs

### Requirement: OpenSpec change guidance
The guide SHALL explain how to write OpenSpec changes within a set-core consumer project.

#### Scenario: Agent creates change respecting conventions
- **WHEN** a Claude agent uses `/opsx:new` to plan a change in the consumer project
- **THEN** the guide informs it that OpenSpec artifacts, commands, and skills are available
- **AND** the guide explains that changes should respect existing `.claude/rules/` conventions

### Requirement: Extension guidance for domain-specific patterns
The guide SHALL explain how to extend the project with domain-specific conventions.

#### Scenario: Project needs mobile-specific patterns
- **WHEN** a project needs patterns not covered by the deployed project-type rules
- **THEN** the guide explains to create custom rules in `.claude/rules/` and knowledge in `set/knowledge/`
- **AND** the guide explains these will be respected by orchestration alongside set-core rules
