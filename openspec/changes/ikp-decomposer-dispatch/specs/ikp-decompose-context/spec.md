## ADDED Requirements

## IN SCOPE
- Decomposer reads IKP L1+L2 layers and includes integration summaries in planning prompt
- Planner output schema includes `ikp_packs` field per change
- Plan enrichment preserves `ikp_packs` with fallback keyword matching

## OUT OF SCOPE
- IKP pack loading (handled by ikp-bridge)
- Automatic pack detection without `.ikp.yaml` (future)
- Per-capability granular layer loading

### Requirement: IKP context in decomposition prompt
The decomposer SHALL include an IKP context section in the planning prompt when the project has an active IKP pipeline. The section SHALL contain per-pack summaries from L1 (knowledge) and L2 (planning) layers.

#### Scenario: Project with IKP packs
- **WHEN** `has_ikp_pipeline()` returns True and the project declares packs `["billingo", "wise-payments", "google-gmail"]`
- **THEN** `build_decomposition_context()` SHALL include an `ikp_context` field
- **AND** the context SHALL contain per-pack sections with capabilities, complexity ratings, and pitfalls

#### Scenario: Project without IKP
- **WHEN** `has_ikp_pipeline()` returns False
- **THEN** `build_decomposition_context()` SHALL set `ikp_context` to an empty string
- **AND** the planning prompt SHALL NOT contain an IKP section

#### Scenario: Token budget for IKP context
- **WHEN** the combined IKP context exceeds 15K tokens
- **THEN** the system SHALL truncate to pack.yaml summaries only (capabilities + pitfalls, omitting full L1+L2 content)
- **AND** SHALL log a warning about truncation

### Requirement: Planner assigns ikp_packs per change
The planner output schema SHALL support an optional `ikp_packs` field on each change. The planner SHALL assign relevant pack names when a change involves external API integrations listed in the IKP context section.

#### Scenario: Integration change
- **WHEN** the planner creates a change with scope "Billingo API integration for invoice generation"
- **AND** the IKP context lists a `billingo` pack
- **THEN** the change output SHALL include `"ikp_packs": ["billingo"]`

#### Scenario: Non-integration change
- **WHEN** the planner creates a change with scope "Prisma schema — base entities"
- **THEN** the change output SHALL include `"ikp_packs": []` or omit the field

#### Scenario: Planner omits ikp_packs
- **WHEN** the planner response does not include `ikp_packs` for a change
- **THEN** plan enrichment SHALL default to `[]`

### Requirement: Fallback pack assignment
The plan enrichment step SHALL attempt keyword-based pack assignment when the planner did not assign `ikp_packs` but the change scope mentions integration-related terms.

#### Scenario: Keyword match fallback
- **WHEN** a change has empty `ikp_packs` but scope text contains "billingo"
- **AND** "billingo" is in the project's `.ikp.yaml` packs list
- **THEN** enrichment SHALL set `ikp_packs: ["billingo"]`
- **AND** SHALL log a warning that fallback assignment was used

#### Scenario: No keyword match
- **WHEN** a change has empty `ikp_packs` and scope text does not match any pack name
- **THEN** `ikp_packs` SHALL remain empty
