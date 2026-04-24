## ADDED Requirements

### Requirement: Web profile registers the client-boundary gate

The `WebProjectType.register_gates()` method SHALL include a `GateDefinition` entry for the `client-boundary` gate. The entry SHALL:
- Bind to the executor `execute_client_boundary_gate` in `modules/web/set_project_web/gates.py`.
- Declare `position="before:build"` so the check runs before any build-cost work.
- Declare phase `verify` (default; NOT `run_on_integration`) — the check is deterministic per commit.
- Default to `run` for change types `foundational` and `feature`; `skip` for `infrastructure`, `schema`, `cleanup-before`, `cleanup-after`.
- Map results into `result_fields=("client_boundary_result", "gate_client_boundary_ms")`.

#### Scenario: Gate appears in web profile registration

- **WHEN** `WebProjectType().register_gates()` is called
- **THEN** the returned list SHALL contain an entry with name `"client-boundary"`
- **AND** that entry's `executor` SHALL be `execute_client_boundary_gate`
- **AND** that entry's `position` SHALL be `"before:build"`

#### Scenario: Feature change runs the gate

- **GIVEN** a `feature`-type change
- **WHEN** the pipeline runner resolves gate defaults for that change
- **THEN** `client-boundary` SHALL be scheduled to run

#### Scenario: Infrastructure change skips the gate

- **GIVEN** an `infrastructure`-type change
- **WHEN** the pipeline runner resolves gate defaults
- **THEN** `client-boundary` SHALL be `skip`ped (infra changes don't touch render code)

#### Scenario: Gate does NOT run on integration branch

- **GIVEN** a change entering the integration-e2e phase
- **WHEN** the integration pipeline iterates registered gates
- **THEN** `client-boundary` SHALL NOT execute on the integration branch (already verified per-commit)

### Requirement: Web profile retry policy treats client-boundary as cheap

The web profile's `gate_retry_policy()` SHALL classify `client-boundary` as a cheap gate (re-runs fully on every retry, no verdict caching). The gate is deterministic, fast, and has no LLM cost — caching would only hide the effect of the agent's fix.

#### Scenario: Retry re-executes the gate

- **GIVEN** a prior failing run of `client-boundary`
- **WHEN** the agent pushes a fix and the gate retries
- **THEN** the gate SHALL re-scan the current working tree (no cached verdict)
