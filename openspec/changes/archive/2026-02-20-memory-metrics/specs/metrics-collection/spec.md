## ADDED Requirements

### Requirement: Per-injection metrics recording
The hook system SHALL record structured metrics for every memory injection in layers L1-L4. Each metrics record SHALL include: timestamp, session_id, layer identifier, event name, query text, result count (pre-filter), filtered count (post-filter), relevance scores array, duration in milliseconds, estimated token count, and dedup hit flag.

#### Scenario: Successful injection with results
- **WHEN** a UserPromptSubmit hook fires and proactive recall returns 3 memories with relevance scores [0.72, 0.45, 0.31]
- **THEN** a metrics record SHALL be appended to the session cache `_metrics` array with `result_count=3`, `filtered_count=3`, `avg_relevance=0.49`, `max_relevance=0.72`, `min_relevance=0.31`

#### Scenario: Injection filtered to zero results
- **WHEN** a PreToolUse hook fires and all recalled memories have relevance scores below 0.3
- **THEN** a metrics record SHALL be appended with `result_count` equal to the pre-filter count and `filtered_count=0`

#### Scenario: Dedup cache hit
- **WHEN** a PreToolUse hook fires and the query matches a dedup cache entry
- **THEN** a metrics record SHALL be appended with `dedup_hit=1`, `result_count=0`, and `duration_ms` reflecting only the cache check time

### Requirement: Session cache metrics storage
Metrics SHALL be stored in the existing session cache file (`/tmp/set-memory-session-{SESSION_ID}.json`) under a `_metrics` key containing an array of injection records.

#### Scenario: Metrics array structure
- **WHEN** a session has 5 injections
- **THEN** the session cache file SHALL contain `_metrics` as an array of 5 objects alongside the existing dedup keys

#### Scenario: Metrics cap
- **WHEN** the `_metrics` array reaches 500 entries
- **THEN** no further entries SHALL be appended for that session (prevent unbounded growth)

### Requirement: Timing instrumentation
Each hook layer SHALL measure its own execution time using millisecond-precision timestamps at entry and exit.

#### Scenario: Duration measurement
- **WHEN** a UserPromptSubmit hook starts at t=0ms and completes at t=850ms
- **THEN** the metrics record SHALL have `duration_ms=850`

### Requirement: Token estimation
Each injection SHALL estimate the token count of the injected context using a `len(text) / 4` heuristic.

#### Scenario: Token count calculation
- **WHEN** an injection produces 1200 characters of additionalContext
- **THEN** the metrics record SHALL have `token_estimate=300`

#### Scenario: Empty injection
- **WHEN** an injection produces no additionalContext (dedup hit or no results)
- **THEN** the metrics record SHALL have `token_estimate=0`

### Requirement: Enable/disable toggle
Metrics collection SHALL be toggleable via a flag file at `~/.local/share/set-core/metrics/.enabled`.

#### Scenario: Metrics disabled (default)
- **WHEN** the flag file does not exist
- **THEN** hooks SHALL skip all metrics recording code with zero overhead

#### Scenario: Metrics enabled
- **WHEN** the flag file exists
- **THEN** hooks SHALL record metrics for every injection

#### Scenario: Toggle via CLI
- **WHEN** `set-memory metrics --enable` is run
- **THEN** the flag file SHALL be created (and parent directory if needed)
- **WHEN** `set-memory metrics --disable` is run
- **THEN** the flag file SHALL be removed

### Requirement: SQLite persistence in Stop hook
The Stop hook SHALL flush session metrics from the session cache to a SQLite database at `~/.local/share/set-core/metrics/metrics.db`.

#### Scenario: Normal session end
- **WHEN** the Stop hook fires and the session cache contains `_metrics` with 20 entries
- **THEN** all 20 entries SHALL be inserted into the `injections` table and a summary row into the `sessions` table

#### Scenario: SQLite write failure
- **WHEN** the SQLite write fails (permissions, disk full, etc.)
- **THEN** the error SHALL be logged to stderr and the hook SHALL continue normally (metrics are best-effort)

#### Scenario: Database auto-creation
- **WHEN** the Stop hook runs and `metrics.db` does not exist
- **THEN** the database and all tables/indexes SHALL be created automatically

### Requirement: Citation scanning in Stop hook
The Stop hook SHALL scan the session transcript for explicit memory citations by the LLM.

#### Scenario: Explicit citation found
- **WHEN** the transcript contains an assistant message with "From memory: always use opsx:* skills"
- **THEN** a citation record SHALL be created with `citation_type="explicit"` and the matched text

#### Scenario: Citation patterns
- **WHEN** scanning the transcript
- **THEN** the scanner SHALL match patterns including: "From memory:", "from past experience", "Based on memory", "a memória szerint", "From project memory", "Based on past"

#### Scenario: Only assistant messages scanned
- **WHEN** a system-reminder contains the text "From memory:"
- **THEN** it SHALL NOT be counted as a citation (only assistant role messages are scanned)
