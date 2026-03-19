## ADDED Requirements

### Requirement: Hybrid recall fallback when proactive returns insufficient results
The `set-memory proactive` command SHALL fall back to `recall --mode hybrid` when `proactive_context()` returns fewer than `min(limit, 2)` results with relevance_score >= 0.4. Hybrid results SHALL be appended after proactive results, deduplicated by content prefix (first 50 chars), and assigned a synthetic relevance_score of 0.35.

#### Scenario: Proactive returns zero results for short query
- **WHEN** `set-memory proactive "levelibéka"` is called
- **AND** `proactive_context()` returns 0 results with score >= 0.4
- **THEN** the command SHALL execute `recall("levelibéka", mode="hybrid")`
- **AND** SHALL return hybrid results with synthetic score 0.35

#### Scenario: Proactive returns sufficient results
- **WHEN** `set-memory proactive "cross-platform compatibility"` is called
- **AND** `proactive_context()` returns 3 results with score >= 0.4
- **THEN** the command SHALL NOT execute hybrid fallback
- **AND** SHALL return only proactive results with original scores

#### Scenario: Both paths return overlapping results
- **WHEN** proactive returns 1 result with content "A levelibéka zöld"
- **AND** hybrid fallback also returns "A levelibéka zöld"
- **THEN** the deduplicated output SHALL contain only one copy
- **AND** SHALL use the proactive result's original score (not synthetic)

#### Scenario: Hybrid fallback adds new results
- **WHEN** proactive returns 1 result about topic X
- **AND** hybrid returns 2 results: topic X (duplicate) and topic Y (new)
- **THEN** output SHALL contain 2 results: topic X (proactive score) and topic Y (score 0.35)

### Requirement: Consistent output format
Hybrid fallback results SHALL have the same JSON structure as proactive results, including `content`, `relevance_score`, `tags`, and `memory_type` fields. The `relevance_score` for hybrid-only results SHALL be 0.35.

#### Scenario: Hybrid result format
- **WHEN** a hybrid-only result is included in output
- **THEN** it SHALL have `relevance_score` set to 0.35
- **AND** SHALL include all standard memory fields (`content`, `tags`, `memory_type`)

### Requirement: Fallback latency budget
The hybrid fallback SHALL only execute when the fallback trigger condition is met. The total `set-memory proactive` command (including fallback) SHALL complete within the hook's timeout.

#### Scenario: Happy path latency unchanged
- **WHEN** proactive returns sufficient results
- **THEN** no hybrid recall is executed
- **AND** latency is identical to before this change

#### Scenario: Fallback path adds one recall call
- **WHEN** fallback triggers
- **THEN** exactly one additional `recall()` call is made
- **AND** total added latency is ~50-100ms
