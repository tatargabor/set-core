## MODIFIED Requirements

### Requirement: Developer Memory User Guide
The project SHALL have a `docs/developer-memory.md` file that serves as the comprehensive user-facing guide for the developer memory system. The guide SHALL include a "Migration from Legacy Hooks" section that links to `MIGRATION.md` and briefly summarizes the transition from `wt-memory-hooks install` to `wt-deploy-hooks`.

#### Scenario: Guide file exists
- **WHEN** a user looks for memory documentation
- **THEN** `docs/developer-memory.md` exists with complete usage instructions

#### Scenario: Migration section exists
- **WHEN** a user with legacy hooks reads the guide
- **THEN** they find a "Migration from Legacy Hooks" section that links to MIGRATION.md and explains the old-to-new transition in 2-3 sentences

## ADDED Requirements

### Requirement: Architecture summary reflects SYN-06 results
The guide SHALL include an architecture summary section documenting the 5-layer hook system with benchmark evidence: +34% weighted quality, -20% token consumption (SYN-06).

#### Scenario: User reads architecture summary
- **WHEN** a user reads the architecture section
- **THEN** they see a description of the 5-layer hook system (UserPromptSubmit, PreToolUse, PostToolUse, SubagentStop, Stop) with performance data from SYN-06
