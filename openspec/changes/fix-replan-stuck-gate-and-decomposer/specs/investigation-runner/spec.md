## ADDED Requirements

### Requirement: Auto-escalate to fix-iss on retry-budget exhaustion
When the verify-gate retry budget for a given `stop_gate` is exhausted on a change (e.g. `review 5/5` or `design-fidelity 4/4`), the engine SHALL automatically create a `fix-iss-<NNN>-<slug>` change via the investigation pipeline and redirect dispatch to it. The parent change SHALL be marked `status=failed:retry_budget_exhausted` with a reference to the generated fix-iss change name in `change.fix_iss_child`.

This machinery already exists on a prior run (produced `fix-iss-004-review-gate-failed-5-retry-6-2`) but was not triggered on `craftbrew-run-20260418-1719` because the stuck-loop circuit short-circuited before the retry budget was formally declared exhausted.

#### Scenario: Review gate 5/5 fail triggers fix-iss
- **WHEN** a change's review gate fails for the 5th time (budget exhausted)
- **THEN** the engine SHALL invoke `investigation_runner.create_fix_iss(change, stop_gate="review", findings=<latest>)`
- **AND** the result SHALL be a new change dir `openspec/changes/fix-iss-<NNN>-<slug>/` with `proposal.md` describing the failing findings
- **AND** the parent change SHALL have `status="failed:retry_budget_exhausted"` and `fix_iss_child="fix-iss-<NNN>-<slug>"`
- **AND** dispatch SHALL route to the new fix-iss change on the next monitor poll

#### Scenario: Stuck-loop circuit breaker also triggers fix-iss
- **WHEN** `stuck_loop_count >= max_stuck_loops` fires (see `retry-loop-completion` spec delta)
- **THEN** the engine SHALL invoke `investigation_runner.create_fix_iss(change, stop_gate=<last>, findings=<last>)` with the same contract as retry-budget exhaustion
- **AND** the parent change SHALL have `status="failed:stuck_no_progress"` and `fix_iss_child="fix-iss-<NNN>-<slug>"`

#### Scenario: Token-runaway also triggers fix-iss
- **WHEN** `TOKEN_RUNAWAY` fires on a change (see `orchestration-token-tracking` spec delta)
- **THEN** the engine SHALL invoke `investigation_runner.create_fix_iss(...)` with `stop_gate=<last>` and include the runaway metadata in the proposal
- **AND** the parent SHALL have `status="failed:token_runaway"` and `fix_iss_child="fix-iss-<NNN>-<slug>"`

### Requirement: fix-iss change gets a diagnostic proposal
`investigation_runner.create_fix_iss()` SHALL produce a `proposal.md` with sections `Why`, `What Changes`, `Capabilities`, `Impact`, `Fix Target` where `Fix Target` is either `consumer` (findings local to the project) or `framework` (findings implicate set-core). Classification SHALL be driven by a heuristic on the findings' file paths: paths inside `lib/set_orch/`, `modules/*/`, `templates/core/rules/`, `.claude/rules/` → framework; any other path → consumer.

#### Scenario: Consumer findings produce Target: consumer
- **WHEN** all findings point to files outside `lib/set_orch/`, `modules/*/`, `templates/core/rules/`, `.claude/rules/`
- **THEN** the generated `proposal.md` SHALL have `Target: consumer` and the Reasoning SHALL cite the file paths

#### Scenario: Framework findings produce Target: framework
- **WHEN** any finding points to a file under `lib/set_orch/`, `modules/*/`, `templates/core/rules/`, or `.claude/rules/`
- **THEN** the generated `proposal.md` SHALL have `Target: framework` and the Reasoning SHALL name the affected set-core module

### Requirement: fix_iss_child state field
`orchestration-state.json`'s per-change Change dataclass SHALL gain `fix_iss_child: str | None` (default `None`). Written by the engine when an auto-escalation creates a fix-iss change; read by the monitor/reporter to render the parent→child link in the dashboard. Serialised via `to_dict()` only when not None; deserialised via `from_dict()`.

#### Scenario: fix_iss_child round-trips through JSON
- **WHEN** a Change with `fix_iss_child="fix-iss-007-foo"` is serialised and deserialised
- **THEN** the resulting Change SHALL have `fix_iss_child="fix-iss-007-foo"`

#### Scenario: fix_iss_child None is omitted
- **WHEN** a Change with `fix_iss_child=None` is serialised via `to_dict()`
- **THEN** the key `fix_iss_child` SHALL NOT appear in the output dict
