## IN SCOPE
- HTTP endpoint exposing the resolved per-profile gate registry for a project, including each gate's name, label, phase, position, integration flag, and retry policy.
- Inclusion of universal gates and profile-registered gates (web, mobile, future plugins) in the response, with the resolution order matching pipeline registration.
- Per-change-type defaults declared on each `GateDefinition` (e.g., `feature: "run"`, `infrastructure: "skip"`).
- Graceful degradation when profile loading fails — return 200 with an empty `gates` array and a `warning` field, never 5xx.

## OUT OF SCOPE
- Mutating gate registration via HTTP (read-only endpoint).
- Per-change overrides (`gate_overrides()` per change_type) — those are returned in the existing `/api/{project}/changes/{name}` response, not the registry endpoint.
- Real-time push of registry changes (polled on project load; stable per profile).
- Authorization or rate limiting beyond what other `/api/{project}/...` endpoints already enforce.

## ADDED Requirements

### Requirement: Registry endpoint shall return resolved per-profile gates
The system SHALL expose `GET /api/{project}/gates/registry` returning JSON `{gates: GateRegistryEntry[], warning?: string}` where each `GateRegistryEntry` contains `name`, `label`, `phase`, `position`, `run_on_integration`, `retry_policy`, and `change_type_defaults`. The `gates` array SHALL include both universal gates (from `_get_universal_gates()`) and profile-registered gates (from `profile.register_gates()`), in their pipeline registration order.

#### Scenario: Web project lists all 13 gates
- **WHEN** `GET /api/{project}/gates/registry` is called for a project whose active profile is `WebProjectType`
- **THEN** the response SHALL include all 8 universal gates (`build`, `test`, `scope_check`, `test_files`, `e2e_coverage`, `review`, `rules`, `spec_verify`) AND all 5 web gates (`i18n_check`, `e2e`, `lint`, `design-fidelity`, `required-components`)
- **AND** each entry SHALL carry the `change_type_defaults` declared on its `GateDefinition`

#### Scenario: Mobile project includes xcode-build
- **WHEN** the project's active profile is `MobileProjectType`
- **THEN** the response SHALL include `xcode-build` alongside the universal gates

#### Scenario: Profile load failure returns empty + warning
- **GIVEN** a project whose profile cannot be resolved (entry-point error, missing module)
- **WHEN** the registry endpoint is called
- **THEN** the response SHALL be HTTP 200 with `{"gates": [], "warning": "<one-line cause>"}`
- **AND** the response SHALL NOT be 5xx

### Requirement: Registry entries shall declare retry policy per gate
Each `GateRegistryEntry` SHALL carry a `retry_policy` field whose value is one of `"always"`, `"cached"`, or `"scoped"`, sourced from `profile.gate_retry_policy()`. Gates with no explicit policy SHALL default to `"always"`.

#### Scenario: Cached gate has explicit policy
- **GIVEN** the web profile declares `gate_retry_policy()["e2e"] == "cached"`
- **WHEN** the registry endpoint returns the `e2e` entry
- **THEN** the entry's `retry_policy` field SHALL equal `"cached"`

#### Scenario: Unspecified gate defaults to always
- **GIVEN** a gate whose name is absent from `gate_retry_policy()`
- **WHEN** the registry endpoint returns its entry
- **THEN** the entry's `retry_policy` field SHALL equal `"always"`

### Requirement: Registry assembly shall be observable
The registry endpoint SHALL emit a DEBUG log on every call naming the project, the resolved profile class, and the count of gates returned. Profile load failures SHALL emit a WARNING with `exc_info=True`.

#### Scenario: Successful call logs DEBUG
- **WHEN** the registry endpoint completes successfully for a project
- **THEN** a DEBUG log line SHALL be emitted including the project name, profile class name, and gate count

#### Scenario: Profile failure logs WARNING with traceback
- **GIVEN** profile resolution raises an exception
- **WHEN** the registry endpoint handles the failure
- **THEN** a WARNING log line SHALL be emitted with the exception's traceback attached
