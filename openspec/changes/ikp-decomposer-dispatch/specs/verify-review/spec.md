## MODIFIED Requirements

### Requirement: LLM code review
The review gate SHALL generate a diff, build a review prompt, and run LLM review with model escalation. When the change has IKP packs, the review prompt SHALL include L4 (testing) context with sandbox setup, mock strategies, and edge cases relevant to the integration.

#### Scenario: Review with IKP testing context
- **WHEN** reviewing a change with `ikp_packs: ["billingo"]`
- **AND** `has_ikp_pipeline()` returns True
- **THEN** the review prompt SHALL include an IKP testing section
- **AND** the section SHALL contain sandbox setup instructions, recommended mock strategies, and edge cases to check

#### Scenario: Review without IKP
- **WHEN** reviewing a change with no `ikp_packs`
- **THEN** the review prompt SHALL be unchanged from existing behavior
