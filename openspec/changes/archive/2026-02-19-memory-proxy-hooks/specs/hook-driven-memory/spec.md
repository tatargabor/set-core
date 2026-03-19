## MODIFIED Requirements

### Requirement: Hooks replace inline memory instructions in skills and commands
All `<!-- set-memory hooks -->` blocks (including `hooks-midflow`, `hooks-remember`, `hooks-reflection`, `hooks-save` variants) SHALL be removed from OpenSpec skill SKILL.md files and opsx command .md files. The hook system now covers 7 events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, SubagentStop, Stop) via a single unified handler — skills SHALL NOT contain manual `set-memory recall` or `set-memory remember` instructions.

#### Scenario: Skill file without memory hooks
- **WHEN** any OpenSpec skill SKILL.md is loaded
- **THEN** it SHALL NOT contain `set-memory recall` or `set-memory remember` instructions
- **AND** memory injection is handled by the hook system across all tool events

### Requirement: CLAUDE.md uses explicit memory-use instructions
The CLAUDE.md "Persistent Memory" section SHALL explicitly instruct the agent to read and use injected memory context from system-reminder tags. It SHALL NOT use the phrase "invisible to you".

#### Scenario: CLAUDE.md memory section content
- **WHEN** a project CLAUDE.md is deployed by `set-project init`
- **THEN** it SHALL contain "you MUST read and use this context"
- **AND** SHALL contain "On EVERY prompt, check for injected memory context"
- **AND** SHALL reference system-reminder labels: "PROJECT MEMORY", "PROJECT CONTEXT", "MEMORY: Context for this command", "MEMORY: Context for this file"
- **AND** SHALL instruct "Start by summarizing what you already know from the injected memory, then fill in gaps"

### Requirement: Skills retain full functionality without memory hooks
After removing inline memory hooks, all OpenSpec skills (apply, continue, ff, explore, archive, verify, sync, new) SHALL continue to function identically for their primary purpose. Memory operations are handled by the automatic hook layer across all tool events.

#### Scenario: Explore skill with memory context
- **WHEN** the explore skill is invoked
- **AND** memory context is injected via system-reminders
- **THEN** the agent SHALL acknowledge and use the memory context before exploring the codebase
