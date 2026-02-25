# ambient-memory Specification

## Purpose
TBD - created by archiving change proactive-memory. Update Purpose after archive.
## Requirements
### Requirement: CLAUDE.md proactive memory instruction
The project's `CLAUDE.md` SHALL include a "Persistent Memory" section that instructs the agent to recognize and use injected memory context on EVERY prompt. The instruction SHALL be structured as a numbered action list (not a single paragraph) for higher compliance:

1. **Scan**: On every prompt, scan `<system-reminder>` tags for "PROJECT MEMORY", "PROJECT CONTEXT", or "MEMORY: Context for this command"
2. **Match**: Check if any memory directly answers the user's question or provides a known fix
3. **Cite**: If a match is found, cite it explicitly: "From memory: ..." — do NOT re-investigate problems with known solutions
4. **Proceed**: Only after checking memory context, proceed with independent research

The section SHALL also instruct the agent that memory context applies to EVERY turn, not just the first one in a session.

#### Scenario: Agent recognizes learning during ad-hoc work
- **WHEN** user says "egyébként a wt-status timeout-ol ha nincs git repo" during a regular coding session (no skill active)
- **THEN** the agent runs `wt-memory health`, and if healthy, saves an Observation memory about the wt-status timeout behavior

#### Scenario: Agent recognizes decision during debugging
- **WHEN** user says "from now on always run tests before committing" during debugging
- **THEN** the agent saves a Decision memory about the testing workflow preference

#### Scenario: Agent does NOT save during skills that have their own hooks
- **WHEN** user is inside `/opsx:apply` or `/opsx:explore` (which have their own memory hooks)
- **THEN** the CLAUDE.md instruction defers to the skill's built-in hooks — no duplicate saves

#### Scenario: Injected memory cited on subsequent turn
- **WHEN** a PostToolUse hook injects memory "Prisma 7 requires driver adapters, not direct connection"
- **AND** the user then asks "miért nem működik a Prisma connection?"
- **THEN** the agent SHALL cite: "From memory: Prisma 7 requires driver adapters..."
- **AND** SHALL NOT re-investigate the Prisma 7 setup from scratch

### Requirement: Memory save threshold
The CLAUDE.md instruction SHALL define clear criteria for when to save vs when to skip. The threshold SHALL be: save only when the user shares something that would be valuable to recall in a FUTURE session (different conversation, different agent). Ephemeral context ("fix this typo") is NOT saved.

#### Scenario: Valuable for future — save
- **WHEN** user shares "this project uses PySide6 not PyQt5, ne keverd össze"
- **THEN** the agent saves because a future agent working on this project would benefit from knowing this

#### Scenario: Session-specific — don't save
- **WHEN** user says "edit that line to say 'hello'" or "futtasd a tesztet"
- **THEN** the agent does NOT save because this is only relevant to the current task

### Requirement: Confirmation format
When the agent proactively saves a memory outside of a skill, it SHALL show a brief inline confirmation that doesn't disrupt the conversation flow. The confirmation SHALL include the memory type and a short summary.

#### Scenario: Inline confirmation
- **WHEN** agent saves a memory proactively
- **THEN** it shows something like: `[Memory saved: Learning — wt-status timeout without git repo]` and continues with the current work

#### Scenario: No confirmation for recalls
- **WHEN** the CLAUDE.md instruction suggests the agent also recall before starting major work
- **THEN** recalls are silent — they inform the agent's behavior but are not announced to the user (unless directly relevant results are found)

