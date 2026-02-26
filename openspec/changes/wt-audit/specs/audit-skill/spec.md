## ADDED Requirements

### Requirement: Skill invocation
The system SHALL provide a `/wt:audit` skill invocable from Claude Code.

#### Scenario: User runs audit skill
- **WHEN** user invokes `/wt:audit` in a Claude Code session
- **THEN** the skill runs `wt-audit scan --json`, parses the output, and presents findings grouped by dimension

#### Scenario: Skill with focus argument
- **WHEN** user invokes `/wt:audit design-docs`
- **THEN** the skill runs full scan but highlights the specified dimension and offers to address its gaps first

### Requirement: Interactive gap remediation
After presenting scan results, the skill SHALL offer to address findings interactively.

#### Scenario: Multiple gaps found
- **WHEN** scan shows ❌ and ⚠️ findings
- **THEN** the skill lists actionable items and asks which the user wants to address

#### Scenario: Address a gap
- **WHEN** user selects a gap to address (e.g., "create ui-conventions.md")
- **THEN** the skill reads the source files listed in the guidance, reads `lib/audit/reference.md` for the category description, and creates a project-specific file based on what it finds in the actual codebase

#### Scenario: All checks pass
- **WHEN** scan shows all ✅
- **THEN** the skill reports clean health and suggests running again after significant changes

### Requirement: Skill reads actual code for content creation
When creating missing files, the skill SHALL read the project's actual source code — not use templates.

#### Scenario: Creating ui-conventions.md
- **WHEN** the skill creates a missing design doc
- **THEN** it reads the source pointers from the guidance (e.g., component files, CSS, package.json), identifies actual patterns used in the project, and documents what it finds

#### Scenario: Creating a code-reviewer agent
- **WHEN** the skill creates a missing `.claude/agents/code-reviewer.md`
- **THEN** it reads existing design docs and CLAUDE.md conventions to build a project-specific review checklist, not a generic one

### Requirement: Command file deployment
The skill SHALL be deployable to projects via `wt-project init`.

#### Scenario: Command file exists
- **WHEN** `wt-project init` runs on a project
- **THEN** `.claude/commands/wt/audit.md` exists in the project, enabling `/wt:audit` invocation

#### Scenario: SKILL.md updated
- **WHEN** the audit skill is created
- **THEN** `.claude/skills/wt/SKILL.md` includes an audit section describing the command
