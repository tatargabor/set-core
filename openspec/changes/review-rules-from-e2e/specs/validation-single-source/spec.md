# validation-single-source

Delta spec for `.claude/rules/web/api-design.md`.

## ADDED Requirements

### Requirement: Single source of truth for validation

When business logic validates the same data at multiple points (e.g., cart preview and checkout confirmation, form preview and form submission), the validation logic MUST be extracted into a single shared function. Both code paths SHALL call the same validation function. Duplicated validation logic leads to drift where one path accepts data the other rejects, causing confusing user experiences and potential data integrity issues.

#### Scenario: Cart preview and checkout use same validation

- **WHEN** a cart preview endpoint validates item availability and pricing, and a checkout endpoint validates the same data before creating an order
- **THEN** both endpoints call the same `validateCart()` (or equivalent) function, not separate inline validation logic

#### Scenario: Validation logic updated in one place

- **WHEN** a new validation rule is added (e.g., maximum quantity per item)
- **THEN** the rule is added to the shared validation function and automatically applies to all code paths that call it
