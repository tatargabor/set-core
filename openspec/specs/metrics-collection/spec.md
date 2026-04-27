# Metrics Collection Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Per-injection metrics recording
The hook system SHALL record structured metrics for every memory injection in layers L1-L4. Each metrics record SHALL include: timestamp, session_id, layer identifier, event name, query text, result count (pre-filter), filtered count (post-filter), relevance scores array, duration in milliseconds, estimated token count, dedup hit flag, and context_ids array.

#### Scenario: Successful injection with results
- **WHEN** a UserPromptSubmit hook fires and proactive recall returns 3 memories with relevance scores [0.72, 0.45, 0.31]
- **THEN** a metrics record SHALL be appended to the session cache `_metrics` array with `result_count=3`, `filtered_count=3`, `avg_relevance=0.49`, `max_relevance=0.72`, `min_relevance=0.31`, and `context_ids` containing 3 unique 4-char hex IDs

#### Scenario: Injection filtered to zero results
- **WHEN** a PostToolUse hook fires and all recalled memories have relevance scores below 0.3
- **THEN** a metrics record SHALL be appended with `result_count` equal to the pre-filter count, `filtered_count=0`, and `context_ids=[]`

#### Scenario: Dedup cache hit
- **WHEN** a PostToolUse hook fires and the query matches a dedup cache entry
- **THEN** a metrics record SHALL be appended with `dedup_hit=1`, `result_count=0`, `duration_ms` reflecting only the cache check time, and `context_ids=[]`
