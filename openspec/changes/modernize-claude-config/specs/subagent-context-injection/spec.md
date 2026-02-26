## ADDED Requirements

### Requirement: SubagentStart hook injects memory context
The system SHALL register a SubagentStart hook (matcher: `""`) that calls `wt-hook-memory SubagentStart` to inject relevant project memory context into spawned subagents.

#### Scenario: Custom subagent receives memory context
- **WHEN** a custom subagent (e.g., code-reviewer, gui-tester) is spawned via the Task tool
- **THEN** the SubagentStart hook SHALL fire and inject relevant memories as additional context

#### Scenario: Built-in subagents receive memory context
- **WHEN** a built-in subagent (Explore, Plan, general-purpose) is spawned via the Task tool
- **THEN** the SubagentStart hook SHALL fire and inject relevant memories

#### Scenario: Hook timeout prevents blocking
- **WHEN** the SubagentStart hook fires
- **THEN** it SHALL have a timeout of 10 seconds to prevent blocking subagent startup

### Requirement: wt-hook-memory supports SubagentStart event
The `wt-hook-memory` script SHALL handle the `SubagentStart` event by performing a proactive context recall based on the subagent's task description and returning relevant memories as additional context.

#### Scenario: Memory script processes SubagentStart
- **WHEN** `wt-hook-memory SubagentStart` is called with stdin containing subagent task description
- **THEN** it SHALL perform proactive context recall and output relevant memories

#### Scenario: Memory script handles missing subagent context gracefully
- **WHEN** `wt-hook-memory SubagentStart` is called with minimal or no task description
- **THEN** it SHALL return general project context without errors
