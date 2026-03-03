## MODIFIED Requirements

### Requirement: Enhanced LLM conflict resolution for additive patterns
The LLM merge conflict resolver SHALL explicitly handle the pattern where both sides add new entries to the same collection.

#### Scenario: Additive pattern guidance in prompt
- **WHEN** `llm_resolve_conflicts()` constructs the merge prompt
- **THEN** the prompt SHALL include explicit instructions for the additive pattern:
  - "When both sides ADD new entries to the same list, array, object, or import block, KEEP ALL entries from BOTH sides"
- **AND** the prompt SHALL include a concrete example showing both sides' additions merged together

#### Scenario: Example format
- **WHEN** the additive pattern example is included in the prompt
- **THEN** it SHALL show a conflict marker block with additions on both sides
- **AND** the correct resolution with all entries preserved
- **AND** the example SHALL be generic (not language-specific)

#### Scenario: Existing resolution behavior preserved
- **WHEN** conflicts involve modifications (not pure additions)
- **THEN** the existing behavior SHALL be unchanged: "prefer the source branch" for contradictory changes
- **AND** the additive pattern guidance SHALL only apply when both sides are adding, not modifying or deleting

#### Scenario: Prompt size impact
- **WHEN** the enhanced prompt is constructed
- **THEN** the additive pattern section SHALL add no more than ~200 tokens
- **AND** model selection thresholds (200-line Sonnet/Opus boundary) SHALL remain unchanged
