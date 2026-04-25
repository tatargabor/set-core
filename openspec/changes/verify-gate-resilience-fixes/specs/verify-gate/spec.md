## ADDED Requirements

### Requirement: Verify retry ceiling sourced from DIRECTIVE_DEFAULTS
The verify gate's retry ceiling (`max_verify_retries`) SHALL be read from `DIRECTIVE_DEFAULTS["max_verify_retries"]` as the canonical default, with the `EngineConfig @dataclass` field reading from the same source via `field(default_factory=...)`. The default SHALL be raised from 8 to 12.

#### Scenario: Default verify retry ceiling is 12
- **WHEN** an operator starts a run without setting `max_verify_retries` in directives
- **THEN** the engine uses 12 as the verify-retry ceiling
- **AND** verify failures are retried up to 11 times before terminal failure
