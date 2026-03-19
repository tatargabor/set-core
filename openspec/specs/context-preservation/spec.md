## ADDED Requirements

### Requirement: Compact instructions in CLAUDE.md
CLAUDE.md SHALL contain a "Compact Instructions" section that tells Claude what to preserve when context is compacted. This section SHALL list: current change name and task progress, list of modified files, active worktree path, and test commands with their last results.

#### Scenario: Compact instructions present in CLAUDE.md
- **WHEN** CLAUDE.md is loaded at session start
- **THEN** it SHALL contain a "Compact Instructions" section with preservation directives

#### Scenario: Compact instructions guide auto-compaction
- **WHEN** Claude Code auto-compacts the context
- **THEN** the compact instructions SHALL be included in the compaction prompt to preserve critical state

### Requirement: SessionStart compact hook re-injects memory
The system SHALL register a SessionStart hook with matcher `compact` that calls `set-hook-memory SessionStart` to re-inject project memory context after auto-compaction.

#### Scenario: Memory context restored after compaction
- **WHEN** auto-compaction occurs during a session
- **THEN** the SessionStart[compact] hook SHALL fire and re-inject relevant memories as system-reminder context

#### Scenario: Hook reuses existing memory script
- **WHEN** the SessionStart[compact] hook fires
- **THEN** it SHALL call the same `set-hook-memory SessionStart` command used for normal session start
- **AND** no new hook script SHALL be required

#### Scenario: Hook does not duplicate normal SessionStart
- **WHEN** a session starts normally (not from compaction)
- **THEN** only the existing SessionStart hook (matcher: `""`) SHALL fire, not the compact matcher

### Requirement: CLAUDE.md slimmed to essential content
CLAUDE.md SHALL contain only universally-needed sections: Persistent Memory (managed), Help & Documentation, Auto-Commit After Apply (managed), and Compact Instructions. GUI-specific, OpenSpec-specific, and README-specific content SHALL be moved to `.claude/rules/` files.

#### Scenario: CLAUDE.md line count reduced
- **WHEN** the modernization is complete
- **THEN** CLAUDE.md SHALL be approximately 60-80 lines (down from ~144)

#### Scenario: No content is deleted
- **WHEN** content is removed from CLAUDE.md
- **THEN** the same content SHALL exist in a corresponding `.claude/rules/` file
- **AND** no instructions SHALL be lost in the migration

### Requirement: Skill frontmatter optimization
Selected skills SHALL have frontmatter additions for context efficiency: `context: fork` for exploration-heavy skills and `disable-model-invocation: true` for rarely-used skills.

#### Scenario: Explore skill runs in forked context
- **WHEN** the `openspec-explore` skill is invoked
- **THEN** it SHALL run in an isolated forked context that does not pollute the main conversation

#### Scenario: Rarely-used skills hidden from auto-invocation
- **WHEN** `openspec-onboard`, `openspec-bulk-archive-change`, or `openspec-sync-specs` have `disable-model-invocation: true`
- **THEN** their descriptions SHALL NOT consume context budget until explicitly invoked by the user
