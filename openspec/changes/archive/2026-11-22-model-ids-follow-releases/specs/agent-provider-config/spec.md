## ADDED Requirements

### Requirement: The framework knows the ids it shipped before

Beside the default mapping, the framework SHALL carry every value it has shipped for a short name and since moved away from. A value in a machine's `model_ids` block that set-core once shipped for that name, and that differs from the current default, SHALL count as a stale copy and not as a deliberate pin. Moving a shorthand to a new release SHALL add its previous value to that record.

#### Scenario: Classifying a machine entry

- **WHEN** a machine block maps `haiku` to `claude-haiku-4-5-20251001` after the shipped `haiku` moved to `claude-haiku-5-5`
- **THEN** that entry is classified as a stale copy

### Requirement: The model check reports a stale copied pin

The check that compares the provider's published models with what set-core ships SHALL also report each stale copy in the machine's anthropic `model_ids` block. It SHALL name the short name, the copied id and the current id. A file with any stale copy SHALL get the verdict `behind`, and the advice SHALL name the refresh command.

#### Scenario: This machine after the 5.5 move

- **WHEN** the machine block still maps `sonnet` to `claude-sonnet-4-6`
- **THEN** the check says `behind`, names `sonnet`, `claude-sonnet-4-6` and `claude-sonnet-5-5`, and points at `set-providers refresh`
