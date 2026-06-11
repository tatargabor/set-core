## MODIFIED Requirements

### Requirement: Resolver runs six deterministic detection layers per change
The change-category-resolver SHALL compute the union of categories from deterministic layers before considering LLM input. When a change has non-empty `ikp_packs` in its metadata, the resolver SHALL add `"integration"` to the category set as an additional deterministic signal.

#### Scenario: Change with ikp_packs
- **WHEN** a change has `ikp_packs: ["billingo"]` in its metadata
- **THEN** the resolver SHALL add `"integration"` to the deterministic category union
- **AND** SHALL include this in the audit log record

#### Scenario: Change without ikp_packs
- **WHEN** a change has no `ikp_packs` or an empty list
- **THEN** the resolver SHALL NOT add `"integration"` from this signal
- **AND** the resolver behavior SHALL be unchanged from existing logic

#### Scenario: Integration category in taxonomy
- **WHEN** the profile's `category_taxonomy()` is queried
- **THEN** it SHALL include `"integration"` as a valid category
