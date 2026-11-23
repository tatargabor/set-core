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

#### Scenario: Pipeline validated end-to-end on real run
- **WHEN** an E2E orchestration run completes with at least 2 merged changes
- **THEN** the following SHALL be verified:
  - Learnings JSONL files exist at `set/orchestration/review-learnings.jsonl` or template baseline path
  - `review_learnings_checklist()` returns non-empty content for at least one change's scope categories
  - At least one dispatched agent's `input.md` contains a "Review Learnings" section
  - At least one review gate execution's prompt includes learnings as prefix
- **AND** any pipeline gaps found SHALL be documented and fixed

#### Scenario: Unit tests guard pipeline wiring
- **WHEN** the test suite runs
- **THEN** at least one test SHALL verify `review_learnings_checklist()` produces output from a fixture JSONL
- **AND** at least one test SHALL verify `_build_input_content()` includes learnings when present in context
