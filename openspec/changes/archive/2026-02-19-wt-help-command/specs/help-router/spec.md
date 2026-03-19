## ADDED Requirements

### Requirement: CLAUDE.md contains help router section
The project CLAUDE.md SHALL contain a "Help & Documentation" section that tells the LLM where to find answers when users ask about features.

#### Scenario: Help router section exists
- **WHEN** the LLM reads CLAUDE.md at session start
- **THEN** it SHALL find a "Help & Documentation" section

### Requirement: Help router maps question types to documentation sources
The help router SHALL map common question categories to specific documentation paths.

#### Scenario: CLI tool questions routed
- **WHEN** a user asks how a CLI tool works
- **THEN** the router SHALL direct the LLM to run `wt-<tool> --help` or read the help command

#### Scenario: Skill questions routed
- **WHEN** a user asks about `/opsx:*` or `/wt:*` skills
- **THEN** the router SHALL direct the LLM to read the relevant SKILL.md or help command

#### Scenario: Memory system questions routed
- **WHEN** a user asks about the memory system
- **THEN** the router SHALL direct the LLM to `docs/developer-memory.md`

#### Scenario: General overview questions routed
- **WHEN** a user asks for a general overview of set-core features
- **THEN** the router SHALL direct the LLM to the `/wt:help` command

### Requirement: Help router is concise
The help router section in CLAUDE.md SHALL be no more than 10 lines to minimize always-loaded context cost.

#### Scenario: Size constraint
- **WHEN** the help router section is measured
- **THEN** it SHALL be 10 lines or fewer (excluding the section header)
