## ADDED Requirements

### Requirement: Token cost estimation display
Show estimated USD cost based on token consumption and model pricing.

#### Scenario: Cost in StatusHeader
- **WHEN** the orchestration has token data
- **THEN** the StatusHeader shows an estimated cost (e.g., "$2.34") next to the token counts
- **THEN** the cost is calculated using model-specific pricing (input/output/cache rates)

#### Scenario: Cost per change
- **WHEN** a change has `input_tokens`, `output_tokens`, `cache_read_tokens`, and `model` fields
- **THEN** the ChangeTable shows a cost column with per-change estimated cost

#### Scenario: Cost calculation formula
- **WHEN** computing cost
- **THEN** use: `(input_tokens * input_rate + output_tokens * output_rate + cache_read_tokens * cache_rate) / 1_000_000`
- **THEN** rates are defined client-side per model (haiku: $0.80/$4, sonnet: $3/$15, opus: $15/$75, cache_read: 10% of input)

#### Scenario: Unknown model
- **WHEN** the model field is missing or unrecognized
- **THEN** use sonnet pricing as default
