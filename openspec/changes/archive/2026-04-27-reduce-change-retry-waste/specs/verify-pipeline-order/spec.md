## MODIFIED Requirements

### Requirement: spec_verify runs before review in the pre-merge pipeline
The verify pipeline SHALL register and execute `spec_verify` BEFORE `review`. The full pre-merge gate order SHALL be: `build`, `test`, profile gates (`e2e`, `lint`), `scope_check`, `test_files`, `e2e_coverage`, `spec_verify`, `rules`, `review`.

#### Scenario: Ordering when all gates pass
- **WHEN** a change's verify pipeline runs and every gate passes
- **THEN** the pipeline records results in the new order
- **AND** `spec_verify` appears before `review` in the per-gate timing map emitted on `VERIFY_GATE`

#### Scenario: spec_verify blocks review on spec gap
- **WHEN** a change implements most requirements but misses a persisted entity required by the spec
- **AND** `spec_verify` fails with at least one CRITICAL finding
- **THEN** the pipeline stops at `spec_verify` and does NOT run `review`
- **AND** the retry context handed to the agent contains the spec_verify failure

#### Scenario: review still runs when spec_verify passes
- **WHEN** `spec_verify` passes
- **THEN** the pipeline proceeds to `rules` and then to `review`
- **AND** review operates identically to the prior order (no behavior change when it runs)

### Requirement: review and spec_verify remain independent
The review gate executor SHALL NOT read `spec_verify_output` or `spec_coverage_result` from the change state. The spec_verify gate executor SHALL NOT read `review_output` or `review_result`.

#### Scenario: Review prompt construction
- **WHEN** `_execute_review_gate` builds its prompt
- **THEN** the prompt contains prior review findings, e2e coverage report, and shadcn detection results
- **AND** the prompt does NOT reference spec_verify output, coverage, or status

#### Scenario: Spec verify prompt construction
- **WHEN** `_execute_spec_verify_gate` builds its prompt
- **THEN** the prompt invokes `/opsx:verify` against the change artifacts
- **AND** the prompt does NOT reference review output, findings, or status

### Requirement: Pipeline order regression test
A test SHALL assert the pre-merge gate registration order. The test MAY inspect the registered names on a pipeline instance or walk the source to extract the order.

#### Scenario: Gate order regression
- **WHEN** a developer accidentally moves `review` before `spec_verify`
- **THEN** the regression test fails with a diff showing the expected vs actual order
