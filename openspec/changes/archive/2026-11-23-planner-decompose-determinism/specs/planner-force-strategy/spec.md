## ADDED Requirements

### Requirement: planner.force_strategy knob

The orchestration config schema SHALL accept an optional string field `planner.force_strategy` whose allowed values are exactly `"flat"`, `"domain-parallel"`, and `"auto"`. Default when the key is absent or the parent section is missing is `"auto"`. Any other value SHALL be treated as a config error and logged at WARN level; the planner MUST fall back to `"auto"` semantics.

#### Scenario: Default is auto

- **GIVEN** an `orchestration.yaml` with no `planner.force_strategy` key
- **WHEN** the planner reaches the strategy decision in digest mode
- **THEN** the threshold check at `req_count >= DOMAIN_PARALLEL_MIN_REQS` runs as today

#### Scenario: force_strategy=flat overrides the threshold

- **GIVEN** `orchestration.yaml` contains `planner:\n  force_strategy: flat`
- **AND** the digest produced 100 requirements (well over threshold)
- **WHEN** the planner reaches the strategy decision in digest mode
- **THEN** the planner takes the single-call decompose branch
- **AND** `_try_domain_parallel_decompose` is NOT called
- **AND** an INFO log line records `decompose strategy=flat, source=force_strategy, req_count=100`

#### Scenario: force_strategy=domain-parallel overrides the threshold

- **GIVEN** `orchestration.yaml` contains `planner:\n  force_strategy: domain-parallel`
- **AND** the digest produced 12 requirements (well under threshold)
- **WHEN** the planner reaches the strategy decision in digest mode
- **THEN** the planner takes the 3-phase domain-parallel branch
- **AND** an INFO log line records `decompose strategy=domain-parallel, source=force_strategy, req_count=12`

#### Scenario: Unknown value falls back to auto with a warning

- **GIVEN** `orchestration.yaml` contains `planner:\n  force_strategy: aggressive`
- **WHEN** the planner reaches the strategy decision
- **THEN** a WARN log line names the unknown value and the field
- **AND** the strategy decision proceeds as if `force_strategy: auto` were set

### Requirement: Strategy decision logging is symmetric

The planner SHALL emit exactly one INFO log line per strategy decision in digest mode that names `decompose strategy=<flat|domain-parallel>`, `source=<threshold|force_strategy>`, `req_count=<N>`, and `threshold=<T>`. The line MUST be emitted on BOTH branches (large-spec → domain-parallel, small-spec → flat) so forensic review can reconstruct every plan's strategy origin uniformly.

#### Scenario: Flat branch logs symmetrically

- **GIVEN** digest mode with `req_count=12` and `force_strategy=auto`
- **WHEN** the planner picks the flat branch
- **THEN** an INFO log line of the form `decompose strategy=flat, source=threshold, req_count=12, threshold=30` is emitted

#### Scenario: Domain-parallel branch logs symmetrically

- **GIVEN** digest mode with `req_count=42` and `force_strategy=auto`
- **WHEN** the planner picks the domain-parallel branch
- **THEN** an INFO log line of the form `decompose strategy=domain-parallel, source=threshold, req_count=42, threshold=30` is emitted

#### Scenario: Forced branch names force_strategy as source

- **GIVEN** any digest mode run with `force_strategy=flat`
- **WHEN** the planner emits the strategy decision log
- **THEN** the `source=` field is `force_strategy` (not `threshold`)
