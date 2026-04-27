## ADDED Requirements

### Requirement: Spec-verify gate has classifier fallback when sentinel missing
The spec-verify gate SHALL fall back to the LLM verdict classifier when the primary LLM output does not contain a recognisable `VERIFY_RESULT` or `CRITICAL_COUNT` sentinel. The classifier's structured verdict SHALL determine the gate result instead of the existing "no sentinel = probably OK" backward-compat default.

#### Scenario: Missing sentinel triggers classifier fallback
- **GIVEN** a primary spec-verify output that does not contain `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` as literal lines
- **AND** the directive `llm_verdict_classifier_enabled` is True
- **WHEN** the spec-verify gate runs
- **THEN** the classifier is invoked on the output
- **AND** the classifier's verdict drives the gate result
- **AND** a WARNING log line notes that the sentinel was missing and the classifier fallback was used

#### Scenario: Missing sentinel with classifier disabled keeps backward-compat
- **GIVEN** a primary spec-verify output with no sentinel
- **AND** the directive `llm_verdict_classifier_enabled` is False
- **WHEN** the spec-verify gate runs
- **THEN** the gate returns PASS with an `[ANOMALY]` WARNING log (old behaviour)

#### Scenario: Classifier error on missing sentinel fails closed
- **GIVEN** a primary spec-verify output with no sentinel
- **AND** the classifier is enabled but the Sonnet call fails (timeout or non-zero exit)
- **WHEN** the spec-verify gate runs
- **THEN** the gate returns FAIL
- **AND** an ERROR log line identifies the classifier failure
- **AND** the retry context explains that the verdict could not be determined
