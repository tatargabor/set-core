## MODIFIED Requirements

### Requirement: Review gate receives learnings checklist
The review gate SHALL receive the persistent learnings checklist as part of the review prompt, so the reviewer LLM can enforce violations. Currently only the implementation agent sees learnings via input.md.

#### Scenario: Review prompt includes learnings
- **WHEN** `_execute_review_gate()` runs for a change
- **THEN** the review prompt SHALL include a learnings section via `prompt_prefix`
- **AND** the section SHALL list relevant persistent learnings with severity and count
- **AND** the reviewer SHALL treat violations of high-count CRITICAL learnings as [CRITICAL] findings

#### Scenario: No learnings available
- **WHEN** no learnings exist (empty JSONL, no baseline)
- **THEN** the review prompt SHALL not include a learnings prefix
- **AND** review behavior SHALL be unchanged from current

### Requirement: Severity-weighted eviction replaces timestamp LRU
The `_merge_learnings()` method SHALL use a scoring formula for eviction instead of pure `last_seen` ordering. Score: `count * severity_weight * recency_factor`. Cap raised from 50 to 200 entries with hysteresis (evict to 180 when 200 reached).

#### Scenario: High-signal pattern survives over low-signal
- **WHEN** the JSONL has 200 entries and a new pattern arrives
- **AND** pattern A has count=8, severity=CRITICAL, last_seen=20 days ago (score=8*3*0.7=16.8)
- **AND** pattern B has count=1, severity=HIGH, last_seen=2 days ago (score=1*2*1.0=2.0)
- **THEN** pattern B SHALL be evicted before pattern A

#### Scenario: Eviction hysteresis
- **WHEN** the JSONL reaches 200 entries
- **THEN** eviction SHALL remove the lowest-scoring entries until 180 remain
- **AND** subsequent merges SHALL not trigger eviction until 200 is reached again

### Requirement: Classifier prompt includes few-shot examples
The `_classify_patterns()` prompt SHALL include few-shot examples demonstrating template vs project classification.

#### Scenario: Classifier uses examples
- **WHEN** `_classify_patterns()` builds its prompt
- **THEN** the prompt SHALL include at least 4 example classifications
- **AND** examples SHALL cover both template (generic security/framework) and project (domain-specific) patterns

### Requirement: Expanded review pattern clusters
`REVIEW_PATTERN_CLUSTERS` SHALL include clusters for IDOR, cascade-delete, race-condition, missing-validation, and open-redirect patterns in addition to existing clusters.

#### Scenario: IDOR patterns clustered
- **WHEN** findings include "IDOR — user can modify other users' data" and "No ownership check on delete"
- **THEN** both SHALL be clustered under the "idor" cluster in cross-change learnings

### Requirement: fix_hint truncated at storage
The `fix_hint` field SHALL be truncated to 200 characters when persisting to JSONL. Code blocks and multi-line content SHALL be stripped to a single-line summary.

#### Scenario: Long fix_hint truncated
- **WHEN** a review finding has a fix_hint of 500 characters with code blocks
- **THEN** the persisted entry SHALL have fix_hint truncated to 200 characters
- **AND** trailing `...` SHALL indicate truncation
