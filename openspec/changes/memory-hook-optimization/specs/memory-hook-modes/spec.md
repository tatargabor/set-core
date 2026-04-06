# Spec: Memory Hook Modes

## ADDED Requirements

## IN SCOPE
- Environment variable to control hook injection behavior (full/lite/off)
- Relevance threshold tuning
- Per-injection token budget
- Content-based dedup across hook fires within a session
- Display truncation of injected memory content
- Reduced default limits for proactive/recall
- Hit-rate tracking metrics

## OUT OF SCOPE
- Changes to the shodh-memory daemon or recall algorithm itself
- Changes to the Stop hook (transcript extraction, commit saving)
- Changes to the SessionStart cheat-sheet recall
- Changes to frustration detection
- Changes to rules.yaml matching
- UI/dashboard changes for memory metrics visualization

### Requirement: Hook mode environment variable

The system SHALL support a `SET_MEMORY_HOOKS` environment variable that controls which hook layers are active.

#### Scenario: Lite mode (default)
- **WHEN** `SET_MEMORY_HOOKS` is unset or set to `lite`
- **THEN** only SessionStart and UserPromptSubmit hooks inject memory context; PostToolUse, PostToolUseFailure, SubagentStart, and SubagentStop hooks SHALL return None without performing recall

#### Scenario: Full mode
- **WHEN** `SET_MEMORY_HOOKS` is set to `full`
- **THEN** all hook layers inject memory context (same behavior as pre-change)

#### Scenario: Off mode
- **WHEN** `SET_MEMORY_HOOKS` is set to `off`
- **THEN** no hooks inject memory context; all handlers return None immediately; the Stop hook (transcript extraction, commit save) SHALL still execute normally

### Requirement: Relevance threshold filtering

The system SHALL use a minimum relevance score threshold to filter low-quality memory matches.

#### Scenario: Threshold filters low-relevance memories
- **WHEN** a memory has a relevance_score below 0.55
- **THEN** it SHALL be excluded from hook injection output

#### Scenario: Memories without scores pass through
- **WHEN** a memory has no relevance_score or score is "N/A"
- **THEN** it SHALL not be filtered by the threshold (pass through)

### Requirement: Reduced injection limits

The system SHALL use reduced default limits for memory recall in active hooks.

#### Scenario: UserPromptSubmit limit
- **WHEN** UserPromptSubmit hook fires
- **THEN** proactive_context SHALL be called with limit=3 (not 5)

#### Scenario: SessionStart limit
- **WHEN** SessionStart hook fires
- **THEN** proactive_context SHALL be called with limit=3 (not 5)

#### Scenario: PostToolUseFailure limit (when full mode)
- **WHEN** PostToolUseFailure fires in full mode
- **THEN** recall_memories SHALL be called with limit=2 (not 3)

### Requirement: Content-based dedup

The system SHALL prevent the same memory content from being injected multiple times in a session, even if returned under different memory IDs.

#### Scenario: Same content different IDs
- **WHEN** a memory's content (first 100 chars) matches a previously injected memory in this session
- **THEN** it SHALL be skipped and not included in the hook output

#### Scenario: Dedup persists across hook types
- **WHEN** a memory was injected by SessionStart
- **THEN** the same content SHALL not be re-injected by UserPromptSubmit or any other hook

### Requirement: Display content truncation

The system SHALL truncate each memory's displayed content to a maximum length in hook output.

#### Scenario: Long memory content
- **WHEN** a memory's content exceeds 300 characters
- **THEN** the displayed content in hook output SHALL be truncated to 300 characters with "..." appended

#### Scenario: Short memory content
- **WHEN** a memory's content is 300 characters or fewer
- **THEN** it SHALL be displayed in full

### Requirement: Per-injection token budget

The system SHALL enforce a maximum token budget per hook injection to prevent runaway context growth.

#### Scenario: Budget exceeded
- **WHEN** the cumulative estimated tokens of formatted memories exceeds 800 tokens for a single hook fire
- **THEN** remaining memories SHALL be skipped even if they pass relevance and dedup filters

#### Scenario: Budget not exceeded
- **WHEN** total formatted output is within 800 tokens
- **THEN** all passing memories SHALL be included

### Requirement: Hit-rate metrics

The system SHALL track whether injected memories were likely referenced by the assistant, enabling measurement of injection usefulness.

#### Scenario: Metrics record includes token estimate
- **WHEN** a hook injects memory context
- **THEN** the metrics record SHALL include `token_estimate` (estimated tokens injected) and `memory_count` (number of memories injected)

#### Scenario: Aggregate stats available
- **WHEN** session ends (Stop hook)
- **THEN** metrics flush SHALL include per-layer aggregates: total injections, total tokens, total dedup hits, total empty results
