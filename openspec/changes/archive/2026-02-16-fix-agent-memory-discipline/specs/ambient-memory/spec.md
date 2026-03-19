## ADDED Requirements

### Requirement: Agent discovery saving in ambient context
The CLAUDE.md proactive memory section SHALL instruct the agent to save its OWN non-obvious discoveries immediately — not just user-shared knowledge. The instruction SHALL establish the "Discover → Save → Tell" ordering: save the finding BEFORE summarizing it to the user. Discoveries include: unexpected behavior from running commands, architecture findings from reading code, environment quirks from testing, and gotchas from verification.

#### Scenario: Agent discovers a gotcha during investigation
- **WHEN** the agent runs a command and discovers non-obvious behavior (e.g., "set-memory uses basename for project isolation, so two repos with the same directory name share memory")
- **THEN** the agent saves a Learning memory IMMEDIATELY
- **THEN** the agent summarizes the finding to the user AFTER saving

#### Scenario: Agent discovers routine information
- **WHEN** the agent reads code and finds expected, well-documented behavior
- **THEN** the agent does NOT save a memory (routine observations are excluded)
