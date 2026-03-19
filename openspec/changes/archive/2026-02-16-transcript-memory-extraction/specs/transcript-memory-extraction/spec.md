## ADDED Requirements

### Requirement: Transcript skill detection
The Stop hook SHALL read `transcript_path` from stdin JSON and scan the JSONL file for opsx/openspec skill invocations. It SHALL detect skill usage by searching for `"skill":"opsx:` or `"skill":"openspec-` patterns in tool_use blocks.

#### Scenario: Session with opsx skill
- **WHEN** the Stop hook runs and the session transcript contains a Skill tool_use with `"skill":"opsx:apply"`
- **THEN** the hook SHALL proceed to insight extraction

#### Scenario: Session without opsx skill
- **WHEN** the Stop hook runs and the session transcript contains no opsx/openspec skill invocations
- **THEN** the hook SHALL skip extraction and continue to existing commit-based logic only

#### Scenario: Missing or unreadable transcript
- **WHEN** the Stop hook receives no `transcript_path` or the file does not exist
- **THEN** the hook SHALL skip extraction silently (exit 0)

### Requirement: Stop hook active guard
The hook SHALL check `stop_hook_active` from stdin JSON and exit immediately if true, to prevent infinite loops.

#### Scenario: Stop hook active is true
- **WHEN** `stop_hook_active` is `true` in the stdin JSON
- **THEN** the hook SHALL exit 0 immediately without any processing

### Requirement: LLM insight extraction
When opsx/openspec skills are detected, the hook SHALL extract the last ~100 lines of the transcript JSONL and send them to `claude -p --model haiku` with a structured extraction prompt. The prompt SHALL instruct the LLM to identify: errors encountered, user corrections/knowledge, discovered patterns, and decision rationale.

#### Scenario: Successful extraction with insights
- **WHEN** haiku analyzes the transcript and finds extractable insights
- **THEN** the hook SHALL receive structured output lines in format `Type|tags|content` and save each via `set-memory remember --type <Type> --tags <tags>`

#### Scenario: Extraction finds no insights
- **WHEN** haiku analyzes the transcript and finds nothing worth saving
- **THEN** the hook SHALL output `NONE` and the hook SHALL skip saving

#### Scenario: LLM call fails or times out
- **WHEN** the `claude -p` call fails, times out, or returns empty output
- **THEN** the hook SHALL skip extraction silently (exit 0) without blocking

### Requirement: Agent deduplication
The hook SHALL check if the agent already performed memory saves during the session by scanning the transcript for evidence of `set-memory remember` calls or `[Memory saved:` / `[Agent insights saved:` confirmation strings.

#### Scenario: Agent already saved memories
- **WHEN** the transcript contains evidence of successful agent memory saves
- **THEN** the hook SHALL include a note in the extraction prompt telling haiku to only extract things the agent likely missed

#### Scenario: Agent did not save memories
- **WHEN** the transcript contains no evidence of agent memory saves
- **THEN** the hook SHALL proceed with full extraction

### Requirement: Insight quality constraints
The extraction prompt SHALL limit output to a maximum of 5 insights per session. Each insight MUST be concrete and actionable — not vague observations. The prompt SHALL explicitly exclude: routine observations, session-specific context, things any developer would know.

#### Scenario: Haiku returns too many insights
- **WHEN** haiku output contains more than 5 insight lines
- **THEN** the hook SHALL process only the first 5 lines

#### Scenario: Insight content validation
- **WHEN** an insight line does not match the `Type|tags|content` format
- **THEN** the hook SHALL skip that line silently

### Requirement: Parallel commit-based extraction preserved
The existing commit-based design choice extraction (scanning `design.md` for `**Choice**:` lines after new commits) SHALL continue to function alongside the new transcript-based extraction.

#### Scenario: Both paths trigger
- **WHEN** a session has both new git commits and opsx skill activity
- **THEN** both the transcript-based extraction and commit-based extraction SHALL execute independently
