# agent-self-reflection Specification

## Purpose
TBD - created by archiving change agent-insight-memory. Update Purpose after archive.
## Requirements
### Requirement: Agent self-reflection at session end
Each OpenSpec skill that creates or modifies artifacts (continue, ff, explore) SHALL include an agent self-reflection step at the end of the session, where the agent reviews its own insights from the session and saves them to set-memory.

#### Scenario: Continue skill session ends with agent insights
- **WHEN** the continue skill finishes creating an artifact
- **THEN** the agent reviews the session for its own insights (decision rationale, discovered patterns, architectural observations)
- **AND** saves each valuable insight via `set-memory remember --type <Learning|Decision> --tags change:<name>,phase:continue,source:agent,<topic>`
- **AND** confirms with `[Agent insights saved: N items]`

#### Scenario: Continue skill session with no agent insights
- **WHEN** the continue skill finishes creating an artifact
- **AND** the agent has no insights worth saving (routine work, no surprises)
- **THEN** the agent confirms with `[Agent insights saved: 0 items]`
- **AND** does not call `set-memory remember`

#### Scenario: FF skill session ends with agent insights
- **WHEN** the ff skill finishes creating all artifacts
- **THEN** the agent reviews the session for its own insights
- **AND** saves each valuable insight via `set-memory remember --type <Learning|Decision> --tags change:<name>,phase:ff,source:agent,<topic>`
- **AND** confirms with `[Agent insights saved: N items]`

#### Scenario: Explore skill session ends with agent insights
- **WHEN** the explore skill session ends (user moves on or starts a change)
- **THEN** the agent reviews the session for its own insights
- **AND** saves each valuable insight via `set-memory remember --type <Learning|Decision> --tags change:<topic>,phase:explore,source:agent,<topic>`
- **AND** confirms with `[Agent insights saved: N items]`

### Requirement: Self-reflection saves only future-valuable insights
The agent SHALL only save insights that a future agent in a different session would benefit from knowing. The agent SHALL NOT save routine observations, session-specific context, or general knowledge.

#### Scenario: Agent discovers a codebase pattern
- **WHEN** the agent discovers a non-obvious pattern in the codebase during artifact creation (e.g., "all services use event sourcing, not CRUD")
- **THEN** the agent saves it as `--type Learning`

#### Scenario: Agent makes a decision with rationale
- **WHEN** the agent chooses approach X over Y with clear reasoning (e.g., "chose SQLite over Redis because the data is per-project and doesn't need shared access")
- **THEN** the agent saves it as `--type Decision`

#### Scenario: Agent performs routine work
- **WHEN** the agent creates a straightforward artifact with no surprises
- **THEN** the agent does NOT save any self-reflection memory

### Requirement: Self-reflection does not duplicate mid-flow saves
The agent self-reflection step SHALL NOT re-save insights that were already saved by mid-flow user-knowledge recognition during the same session.

#### Scenario: User shares knowledge and agent reflects
- **WHEN** the user shares a constraint mid-flow and it is saved via the mid-flow hook
- **AND** the agent reaches the self-reflection step
- **THEN** the agent does NOT save the same constraint again
- **AND** the agent only saves its own novel insights from the session

### Requirement: Self-reflection tags include source:agent
All memories saved by the agent self-reflection step SHALL include the tag `source:agent` to distinguish them from user-shared knowledge (tagged `source:user`).

#### Scenario: Agent insight tagged correctly
- **WHEN** the agent saves a self-reflection insight
- **THEN** the `--tags` argument includes `source:agent`
- **AND** includes `phase:<skill-name>` indicating which skill phase generated the insight

#### Scenario: Existing mid-flow user saves tagged correctly
- **WHEN** the mid-flow hook saves user-shared knowledge
- **THEN** the `--tags` argument includes `source:user`

