## ADDED Requirements

<!--
IN SCOPE:
- Per-change `unresolved_ambiguities` attachment in plan.
- Just-in-time clarification call when a change's implementing agent starts work.
- Decoupling: ambiguities no longer trigger a full replan of the whole spec.
- Preservation of `triage.md` as the gap-analysis source of truth.
- Directive `amb_resolution: jit | inline`.

OUT OF SCOPE:
- Ambiguity *detection* (still done in the digest, unchanged).
- `triage.md` schema or generation logic (unchanged).
- Pre-flight ambiguity batches resolved by a single planner pass.
-->

### Requirement: Ambiguities attach to changes in JIT mode
When `amb_resolution: jit` is configured, the planner SHALL attach unresolved ambiguities to the affected change(s) as `unresolved_ambiguities: [<ambiguity_id>, ...]` and SHALL NOT inject the ambiguity body into the planner prompt itself.

#### Scenario: JIT mode populates per-change list
- **WHEN** the digest produces ambiguities with `affects_requirements: ["REQ-AUTH-001"]` and `resolution` is empty or `"deferred"`
- **AND** `amb_resolution: jit` is set
- **AND** the planner produces a change `auth-foundation` whose requirements include `REQ-AUTH-001`
- **THEN** the change `auth-foundation` SHALL have `unresolved_ambiguities` containing the ambiguity's id

#### Scenario: Inline mode unchanged (default)
- **WHEN** `amb_resolution: inline`
- **THEN** the planner prompt SHALL contain the existing "Deferred Ambiguities" section as today
- **AND** changes SHALL NOT carry `unresolved_ambiguities`

### Requirement: triage.md is unchanged across modes
The system SHALL produce byte-equivalent `triage.md` and `coverage.json` files regardless of the value of `amb_resolution`, on a clean run with the same input spec.

#### Scenario: Gap-analysis byte equivalence
- **WHEN** the same spec is digested with `amb_resolution: jit` and again with `amb_resolution: inline`
- **THEN** the resulting `triage.md` and `coverage.json` files SHALL be byte-identical
- **AND** the digest test suite SHALL include this as a regression assertion

### Requirement: JIT clarification call when agent starts work
When a change with non-empty `unresolved_ambiguities` is dispatched, the dispatcher SHALL invoke a clarification Claude call (default model: Sonnet, max 2k tokens) before the implementing agent's first tool call, asking the agent to resolve each ambiguity (returning a `resolution_note`) or escalate it (`resolution: "human"`).

#### Scenario: Clarification call invoked on dispatch
- **WHEN** `dispatcher.dispatch_change()` runs for a change with `unresolved_ambiguities = ["AMB-001", "AMB-002"]`
- **AND** `amb_resolution: jit` is set
- **THEN** the dispatcher SHALL call Claude with a clarification prompt before starting the agent's main loop
- **AND** the clarification prompt SHALL list each ambiguity by id with its description and source
- **AND** the response SHALL be parsed as `[{"id": "AMB-001", "resolution": "resolved" | "human", "resolution_note": "..."}]`

#### Scenario: Resolution patched into change scope
- **WHEN** the clarification call returns `resolution: "resolved"` for an ambiguity
- **THEN** the dispatcher SHALL append the `resolution_note` to the change's `scope` text under a "Resolved Ambiguities" footer
- **AND** the resolution SHALL be journalled in the change's events stream

#### Scenario: Human escalation pauses dispatch
- **WHEN** the clarification call returns `resolution: "human"` for any ambiguity
- **THEN** the dispatcher SHALL pause the change with status `awaiting_clarification`
- **AND** SHALL emit a sentinel finding listing the ambiguities awaiting human resolution

### Requirement: AMBs do not trigger replan in JIT mode
When `amb_resolution: jit`, the auto-replan trigger detection SHALL NOT classify "ambiguity present" as a replan trigger. The replan triggers spec_change, e2e_failure, domain_failure, coverage_gap, batch_complete remain in effect.

#### Scenario: Ambiguity does not trigger replan
- **WHEN** `amb_resolution: jit` AND the digest contains 5 unresolved ambiguities
- **AND** all changes are still pending or running
- **THEN** the auto-replan loop SHALL NOT fire on the ambiguities alone
- **AND** the orchestrator SHALL proceed to dispatch changes for JIT clarification

#### Scenario: Ambiguity triggers replan in inline mode
- **WHEN** `amb_resolution: inline` AND the digest contains unresolved ambiguities
- **THEN** the replan trigger detection SHALL behave as today (ambiguities part of inline planner prompt; replan fires on the existing trigger conditions)

### Requirement: JIT model is configurable and cheaper than planner
The JIT clarification call SHALL use the model configured by `models.amb_clarify` (default `sonnet`), which SHALL be a smaller/cheaper model than `models.decompose_*`.

#### Scenario: Default model is Sonnet
- **WHEN** no `models.amb_clarify` is configured
- **THEN** the JIT call SHALL use Sonnet

#### Scenario: Override via directive
- **WHEN** `models.amb_clarify: haiku` is configured
- **THEN** the JIT call SHALL use Haiku
