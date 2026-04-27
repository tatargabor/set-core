# Memory Rules Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Rules file format
The system SHALL support a `.claude/rules.yaml` file at the project root with the following structure:

```yaml
rules:
  - id: <kebab-case-string>
    topics: [<keyword>, ...]
    content: |
      <rule text>
```

Each rule SHALL have: `id` (unique string), `topics` (non-empty list of lowercase keywords), `content` (non-empty string).

#### Scenario: Valid rules file is parsed
- **WHEN** `.claude/rules.yaml` exists and is valid YAML
- **THEN** the hook SHALL parse all rules successfully

#### Scenario: Missing rules file is silently skipped
- **WHEN** `.claude/rules.yaml` does not exist
- **THEN** the hook SHALL inject no rules section and continue normally

#### Scenario: Malformed rules file is silently skipped
- **WHEN** `.claude/rules.yaml` exists but contains invalid YAML
- **THEN** the hook SHALL skip rules injection and log a warning to the debug log
- **AND** the rest of hook execution SHALL continue normally

### Requirement: Topic-based rule injection in UserPromptSubmit
The UserPromptSubmit hook handler SHALL inject matching rules before the PROJECT MEMORY section.

A rule matches when at least one of its topics keywords appears (case-insensitive) in the user prompt text.

#### Scenario: Rule matches user prompt
- **WHEN** a rule has `topics: [customer, sql]`
- **AND** the user prompt contains "customer"
- **THEN** the hook output SHALL include a `MANDATORY RULES` section containing that rule's content

#### Scenario: Rule does not match
- **WHEN** no rule's topics overlap with the prompt text
- **THEN** no `MANDATORY RULES` section is injected

#### Scenario: Multiple rules match
- **WHEN** two or more rules match the prompt
- **THEN** all matching rules SHALL be included in the `MANDATORY RULES` section

### Requirement: MANDATORY RULES section format
When rules are injected, they SHALL appear as:

```
=== MANDATORY RULES ===
[<id>] <content>

[<id>] <content>
===========================
```

The section SHALL appear before the `=== PROJECT MEMORY ===` section in the hook's `additionalContext` output.

#### Scenario: Section appears before project memory
- **WHEN** both rules match AND project memory exists
- **THEN** `=== MANDATORY RULES ===` SHALL appear before `=== PROJECT MEMORY ===` in the output

### Requirement: set-memory rules CLI subcommand
`set-memory rules` SHALL provide subcommands: `add`, `list`, `remove`.

#### Scenario: Add a rule
- **WHEN** user runs `set-memory rules add --topics "customer,sql" "Use customer_ro / XYZ123"`
- **THEN** a new entry is appended to `.claude/rules.yaml`
- **AND** `id` is auto-generated as a kebab-case slug of the first 4 words of the content

#### Scenario: List rules
- **WHEN** user runs `set-memory rules list`
- **THEN** all rules are printed with id, topics, and content preview

#### Scenario: Remove a rule
- **WHEN** user runs `set-memory rules remove <id>`
- **AND** a rule with that id exists
- **THEN** the rule is removed from `.claude/rules.yaml`

#### Scenario: Remove non-existent rule
- **WHEN** user runs `set-memory rules remove <id>`
- **AND** no rule with that id exists
- **THEN** an error message is shown and exit code is 1

### Requirement: Rules file is project-root relative
The rules file path SHALL be resolved via `git rev-parse --show-toplevel`, falling back to `$CLAUDE_PROJECT_DIR` if not in a git repo.

#### Scenario: Resolves in git repo
- **WHEN** the hook runs inside a git repository
- **THEN** `.claude/rules.yaml` is resolved relative to the git root

#### Scenario: Fallback to CLAUDE_PROJECT_DIR
- **WHEN** not in a git repo but `$CLAUDE_PROJECT_DIR` is set
- **THEN** `.claude/rules.yaml` is resolved relative to `$CLAUDE_PROJECT_DIR`
