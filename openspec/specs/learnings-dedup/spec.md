# Learnings Dedup Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- LLM-based semantic deduplication of learnings entries at merge time
- Merging semantically identical patterns into single entries with aggregated metadata
- Fallback behavior when LLM dedup call fails

### Out of scope
- Deduplication at query/dispatch time (too costly)
- Cross-profile deduplication (web.jsonl vs other profiles)
- User-interactive dedup review

## Requirements

### Requirement: Semantic dedup at merge time
After classification and before writing to JSONL, the system SHALL run a Sonnet call to identify semantically equivalent patterns among all entries (existing + new). Equivalent patterns SHALL be merged into a single entry.

#### Scenario: Near-duplicate patterns merged
- **WHEN** persist_review_learnings() processes new pattern "No middleware.ts — admin routes unprotected"
- **AND** existing JSONL contains "Missing src/middleware.ts" and "No middleware — admin routes are unprotected"
- **THEN** all three SHALL be merged into one entry
- **AND** the merged entry's `count` SHALL be the sum of all individual counts
- **AND** the merged entry's `source_changes` SHALL be the union of all source_changes (capped at last 10)
- **AND** the merged entry's `last_seen` SHALL be the most recent timestamp
- **AND** the merged entry's `pattern` text SHALL be the shortest clear description from the group

#### Scenario: Dissimilar patterns preserved
- **WHEN** persist_review_learnings() processes "No auth middleware" and "Missing CSRF protection"
- **THEN** both SHALL remain as separate entries
- **AND** no merging SHALL occur between them

#### Scenario: LLM dedup call fails
- **WHEN** the Sonnet dedup call times out or returns non-zero exit code
- **THEN** the system SHALL skip deduplication and write entries as-is (current behavior)
- **AND** the failure SHALL be logged at WARNING level

### Requirement: Dedup prompt design
The dedup prompt SHALL ask the LLM to group patterns by semantic equivalence. The prompt SHALL instruct the LLM to only merge patterns that describe the EXACT same issue (conservative). The prompt SHALL return a JSON array of merge groups, where each group is an array of entry indices.

#### Scenario: Dedup prompt produces valid output
- **WHEN** 5 patterns are sent to the dedup call
- **AND** patterns 0,2,4 are semantically identical and patterns 1,3 are different
- **THEN** the LLM SHALL return `[[0, 2, 4], [1], [3]]`
- **AND** the system SHALL merge entries 0,2,4 into one and keep 1,3 separate

#### Scenario: Dedup prompt returns unparseable output
- **WHEN** the LLM returns text that cannot be parsed as a JSON array of arrays
- **THEN** the system SHALL fall back to no deduplication
- **AND** the failure SHALL be logged at WARNING level
