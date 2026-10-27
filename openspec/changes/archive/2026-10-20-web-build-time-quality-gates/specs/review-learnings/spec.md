## MODIFIED Requirements

### Requirement: Review gate receives learnings checklist
The review gate SHALL receive the persistent learnings checklist as part of the review prompt, so the reviewer LLM can enforce violations. The implementation agent SHALL also receive the same learnings as a top-of-prompt MUST / MUST NOT block in `input.md`, surfaced before scope and requirements rather than appended at the end of the file.

#### Scenario: Review prompt includes learnings
- **WHEN** `_execute_review_gate()` runs for a change
- **THEN** the review prompt SHALL include a learnings section via `prompt_prefix`
- **AND** the section SHALL list relevant persistent learnings with severity and count
- **AND** the reviewer SHALL treat violations of high-count CRITICAL learnings as [CRITICAL] findings

#### Scenario: Implementation agent input.md surfaces learnings at the top
- **WHEN** `_build_review_learnings()` is invoked while assembling `input.md` for a change with non-empty filtered learnings
- **THEN** the rendered learnings section SHALL appear before the scope and requirements sections in `input.md`
- **AND** the section heading SHALL be a plain-text marker that the agent cannot mistake for prose
- **AND** each finding category SHALL render as MUST / MUST NOT bullets with one example per category

#### Scenario: No learnings available
- **WHEN** no learnings exist (empty JSONL, no baseline)
- **THEN** the review prompt SHALL not include a learnings prefix
- **AND** the implementation agent's `input.md` SHALL not include the top-of-prompt learnings section
- **AND** review behavior SHALL be unchanged from current
