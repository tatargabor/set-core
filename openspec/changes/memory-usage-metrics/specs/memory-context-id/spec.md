## ADDED Requirements

### Requirement: Context ID generation for injected memories
Each memory fragment injected by hook output SHALL be prefixed with a unique context ID in the format `[MEM#xxxx]` where `xxxx` is a 4-character lowercase hex string.

#### Scenario: Proactive recall with multiple results
- **WHEN** `proactive_and_format()` returns 3 memory lines for a UserPromptSubmit hook
- **THEN** each line SHALL be prefixed with a unique context ID: `[MEM#a1b2] memory content...`, `[MEM#c3d4] memory content...`, `[MEM#e5f6] memory content...`

#### Scenario: Recall with single result
- **WHEN** `recall_and_format()` returns 1 memory line for a PostToolUse hook
- **THEN** the line SHALL be prefixed with a context ID: `[MEM#xxxx] memory content...`

#### Scenario: ID uniqueness within session
- **WHEN** multiple hook invocations occur within a single session
- **THEN** all generated context IDs SHALL be unique within that session (no reuse across invocations)

### Requirement: Context ID recorded in metrics
Each injection metrics record SHALL include the list of context IDs that were injected.

#### Scenario: Metrics record with context IDs
- **WHEN** a hook injects 3 memories with IDs `a1b2`, `c3d4`, `e5f6`
- **THEN** the metrics record `_metrics` entry SHALL include `"context_ids": ["a1b2", "c3d4", "e5f6"]`

#### Scenario: Empty injection metrics
- **WHEN** a hook produces no results (dedup hit or no matches)
- **THEN** the metrics record SHALL include `"context_ids": []`

### Requirement: Injected content stored for passive matching
Each injection SHALL store the raw memory content alongside its context ID in the session cache, enabling post-session transcript matching.

#### Scenario: Content stored in session cache
- **WHEN** a hook injects a memory with ID `a1b2` and content "flock-based locking for RocksDB per-project"
- **THEN** the session cache `_injected_content` dict SHALL contain `{"a1b2": "flock-based locking for RocksDB per-project"}`

#### Scenario: Content accumulates across invocations
- **WHEN** multiple hook invocations inject memories within a session
- **THEN** all injected content SHALL be accumulated in `_injected_content` (not overwritten)

### Requirement: Passive transcript matching
The Stop hook SHALL detect memory usage by comparing injected memory content against agent responses in the transcript, without requiring any agent action.

#### Scenario: Agent uses injected memory content
- **WHEN** a memory with ID `a1b2` was injected with content "flock-based locking for RocksDB per-project" and an assistant message within 5 turns contains "flock" and "RocksDB"
- **THEN** the memory SHALL be marked as "passively matched" with `context_id=a1b2`

#### Scenario: No keyword overlap
- **WHEN** a memory was injected but no assistant message contains 2+ significant keywords from that memory
- **THEN** the memory SHALL NOT be marked as matched

#### Scenario: Common words excluded
- **WHEN** keyword extraction runs on memory content
- **THEN** common words (the, a, is, file, function, code, etc.) SHALL be excluded from the keyword set

#### Scenario: Turn window for matching
- **WHEN** checking if an assistant message matches an injected memory
- **THEN** only assistant messages within 5 turns after the injection point SHALL be considered

#### Scenario: Legacy explicit citations still detected
- **WHEN** the transcript contains "From memory:" or other legacy citation patterns
- **THEN** these SHALL be detected as before (backward compatible) with `type: "explicit"`

### Requirement: Usage rate calculation
The metrics system SHALL calculate a usage rate as `matched_ids / injected_ids` per session and across sessions.

#### Scenario: Session with 15 injected IDs and 5 passively matched
- **WHEN** a session injected 15 unique context IDs and passive matching found 5 matches
- **THEN** the session usage rate SHALL be `5/15 = 33.3%`

#### Scenario: Session with no injections
- **WHEN** a session had zero memory injections
- **THEN** the usage rate SHALL be reported as `N/A` (not 0%)

#### Scenario: Aggregate usage rate
- **WHEN** reporting across multiple sessions
- **THEN** the aggregate usage rate SHALL be `total_matched_ids / total_injected_ids` across all sessions in the time range
