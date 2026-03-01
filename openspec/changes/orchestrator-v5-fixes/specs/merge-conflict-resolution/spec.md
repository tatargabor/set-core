## ADDED Requirements

### Requirement: Size-based model selection for conflict resolution
The `llm_resolve_conflicts()` function SHALL select the LLM model based on the total conflict size. If total conflict hunk lines exceed 200, the function SHALL skip sonnet and invoke opus directly. If total conflict hunk lines are 200 or fewer, the function SHALL try sonnet first and fall back to opus on failure.

#### Scenario: Large conflict goes directly to opus
- **WHEN** merge conflicts have total hunk lines exceeding 200
- **THEN** the function SHALL invoke opus with 600s timeout without trying sonnet first

#### Scenario: Small conflict tries sonnet first
- **WHEN** merge conflicts have total hunk lines of 200 or fewer
- **THEN** the function SHALL invoke sonnet with 300s timeout
- **AND** if sonnet fails or times out, fall back to opus with 600s timeout

#### Scenario: Total lines computed before model selection
- **WHEN** conflict hunks are extracted for all conflicted files
- **THEN** the function SHALL compute `total_lines` from all files before making the first LLM call
- **AND** use this total to decide the model path
