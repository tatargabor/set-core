# Custom Subagents Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Code reviewer subagent
The system SHALL provide `.claude/agents/code-reviewer.md` defining a read-only code review subagent with model `sonnet`, tools restricted to `Read, Grep, Glob`, and instructions focused on code quality, pattern consistency (PySide6/Qt, bash conventions), and security review.

#### Scenario: Code reviewer cannot edit files
- **WHEN** the code-reviewer subagent is spawned
- **THEN** it SHALL only have access to Read, Grep, and Glob tools
- **AND** it SHALL NOT have access to Edit, Write, or Bash tools

#### Scenario: Code reviewer uses sonnet model
- **WHEN** the code-reviewer subagent is spawned
- **THEN** it SHALL use the sonnet model for nuanced code analysis

### Requirement: GUI tester subagent
The system SHALL provide `.claude/agents/gui-tester.md` defining a test runner subagent with model `haiku`, tools `Bash, Read, Grep, Glob`, and instructions to run `PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short` and report pass/fail summary with failure details.

#### Scenario: GUI tester runs pytest
- **WHEN** the gui-tester subagent is spawned
- **THEN** it SHALL execute the GUI test suite via pytest
- **AND** it SHALL report a concise pass/fail summary

#### Scenario: GUI tester uses haiku for cost efficiency
- **WHEN** the gui-tester subagent is spawned
- **THEN** it SHALL use the haiku model (cheapest, fastest)

#### Scenario: GUI tester has max turn limit
- **WHEN** the gui-tester subagent is spawned
- **THEN** it SHALL have a maxTurns limit to prevent runaway execution

### Requirement: OpenSpec verifier subagent
The system SHALL provide `.claude/agents/openspec-verifier.md` defining an artifact verification subagent with model `sonnet`, tools `Read, Grep, Glob, Bash`, and instructions to compare change artifacts (proposal, design, tasks, specs) against actual implementation for coherence and completeness.

#### Scenario: Verifier checks artifact-code coherence
- **WHEN** the openspec-verifier subagent is spawned with a change name
- **THEN** it SHALL read the change artifacts and compare against the implemented code
- **AND** it SHALL report discrepancies categorized as CRITICAL, WARNING, or SUGGESTION

#### Scenario: Verifier has Bash for openspec CLI
- **WHEN** the openspec-verifier subagent is spawned
- **THEN** it SHALL have access to Bash to run `openspec status` and similar CLI commands

### Requirement: Subagent markdown files use YAML frontmatter
Each agent file SHALL contain YAML frontmatter with at minimum: `name`, `description`, `tools`, and `model` fields. Optional fields include `maxTurns`, `permissionMode`, and `memory`.

#### Scenario: Agent file frontmatter structure
- **WHEN** a `.claude/agents/*.md` file is loaded by Claude Code
- **THEN** the YAML frontmatter SHALL contain `name`, `description`, `tools`, and `model`
- **AND** the markdown body SHALL contain the agent's system instructions
