## ADDED Requirements

<!--
IN SCOPE:
- Directive `planner.strategy` with values `serial | parallel | auto` (default `auto`).
- `auto` mode that picks `serial` or `parallel` based on estimated flat-prompt input tokens.
- Function `estimate_flat_prompt_tokens(digest_dir, replan_ctx)` that returns an integer estimate without invoking Claude.
- Removal of the legacy `DOMAIN_PARALLEL_MIN_REQS = 30` heuristic.
- Single-call decompose path becomes the primary code path (the existing flat path at `planner.py:2674-2693` lifted out of the fallback branch).

OUT OF SCOPE:
- Choosing models per strategy (covered by `model_config` and the cost-optimized preset).
- The 3-phase pipeline implementation itself (covered by `orch-plan-python`).
- Replan strategy selection (covered by `replan-scoped-patch`).
-->

### Requirement: Planner strategy directive
The system SHALL honor a directive `planner.strategy` with values `serial`, `parallel`, or `auto`. The default value SHALL be `auto`. The directive SHALL be readable from `orchestration.yaml::planner.strategy`, the project state file's `extras.directives.planner.strategy`, and the env var `SET_ORCH_PLANNER_STRATEGY` (in that order of precedence).

#### Scenario: Default strategy is auto
- **WHEN** no `planner.strategy` is configured anywhere
- **THEN** `run_planning_pipeline()` SHALL resolve the strategy via the `auto` decision rule

#### Scenario: Explicit serial forces single-call
- **WHEN** `planner.strategy: serial` is configured
- **THEN** `run_planning_pipeline()` SHALL execute the single-call (flat) decompose path regardless of digest size
- **AND** SHALL NOT invoke `_phase1_planning_brief`, `_phase2_parallel_decompose`, or `_phase3_merge_plans`

#### Scenario: Explicit parallel forces 3-phase
- **WHEN** `planner.strategy: parallel` is configured
- **THEN** `run_planning_pipeline()` SHALL execute the 3-phase domain-parallel path (`_try_domain_parallel_decompose`) regardless of digest size

### Requirement: Auto strategy decision rule
When `planner.strategy: auto`, the system SHALL invoke `estimate_flat_prompt_tokens(digest_dir, replan_ctx)` and select `serial` if the estimate is less than or equal to `SINGLE_CALL_MAX_INPUT_TOKENS` (default 120 000), else `parallel`. The decision SHALL be deterministic given the same digest content.

#### Scenario: Small digest routes to serial
- **WHEN** `planner.strategy: auto` AND `estimate_flat_prompt_tokens()` returns 45000
- **THEN** the system SHALL route to the `serial` path

#### Scenario: Large digest routes to parallel
- **WHEN** `planner.strategy: auto` AND `estimate_flat_prompt_tokens()` returns 145000
- **THEN** the system SHALL route to the `parallel` path

#### Scenario: Decision is logged
- **WHEN** the auto strategy decision is made
- **THEN** the system SHALL log at INFO level: `planner.strategy=auto resolved=<serial|parallel> estimated_tokens=<N> threshold=<T>`

#### Scenario: Threshold override via directive
- **WHEN** `planner.single_call_max_input_tokens: 80000` is configured
- **THEN** the auto rule SHALL use 80000 as the threshold instead of the default 120000

### Requirement: Token estimator does not invoke Claude
The `estimate_flat_prompt_tokens(digest_dir, replan_ctx)` function SHALL be a pure Python computation that reads digest files from disk and returns an integer estimate. It SHALL NOT invoke Claude or any other LLM.

#### Scenario: Estimator reads digest files
- **WHEN** `estimate_flat_prompt_tokens('/path/to/digest', None)` is called
- **THEN** it SHALL read `conventions.json`, `requirements.json`, `domains/*.md`, `dependencies.json`, `ambiguities.json` from the digest directory
- **AND** SHALL sum their byte sizes plus a fixed overhead for the planner-rules block, output schema, and replan context
- **AND** SHALL divide by 3.5 to convert chars to tokens
- **AND** SHALL return an integer

#### Scenario: Estimator handles missing files gracefully
- **WHEN** the digest directory is missing any of the standard files
- **THEN** the estimator SHALL treat each missing file's size as 0
- **AND** SHALL NOT raise an exception

#### Scenario: Estimator includes replan context
- **WHEN** `replan_ctx` is non-empty (contains `completed`, `e2e_failures`, etc.)
- **THEN** the estimate SHALL add the byte size of the serialized `replan_ctx` to the total

### Requirement: Legacy req-count heuristic removed
The constant `DOMAIN_PARALLEL_MIN_REQS = 30` and any code paths that select strategy based solely on `req_count` SHALL be removed. The strategy decision SHALL be based on the `planner.strategy` directive only.

#### Scenario: req_count alone does not force parallel
- **WHEN** a digest has 50 requirements AND `planner.strategy: auto` AND `estimate_flat_prompt_tokens()` returns 60000
- **THEN** the system SHALL route to `serial`
- **AND** SHALL NOT route to `parallel` based on the req_count

### Requirement: Serial path is the primary code path
The single-call decompose code (currently the fallback branch at `planner.py:2674-2693`) SHALL become a first-class function `_run_serial_decompose(input_mode, input_path, ...)` that returns a complete plan. The 3-phase function `_try_domain_parallel_decompose` becomes equally first-class. Both SHALL be invoked from `run_planning_pipeline()` based on the resolved strategy.

#### Scenario: Serial path is named and reachable
- **WHEN** `planner.strategy` resolves to `serial`
- **THEN** `run_planning_pipeline()` SHALL call `_run_serial_decompose(...)` directly
- **AND** the serial function SHALL NOT be reached via an `except Exception` fallback branch

#### Scenario: Serial path produces same plan shape as parallel
- **WHEN** the serial path completes successfully
- **THEN** the returned plan dict SHALL have the same top-level keys (`changes`, `phase_detected`, `reasoning`) as the parallel path's output
- **AND** SHALL pass `validate_plan()` with the same constraints

### Requirement: Strategy is recorded in plan metadata
The resolved strategy (`serial` or `parallel`) SHALL be recorded in `orchestration-plan.json` under `plan_method` (existing field) with values `serial` or `parallel`. Today's `api` value SHALL be replaced.

#### Scenario: Plan records serial method
- **WHEN** the serial path completes
- **THEN** `orchestration-plan.json::plan_method` SHALL equal `serial`

#### Scenario: Plan records parallel method
- **WHEN** the parallel path completes
- **THEN** `orchestration-plan.json::plan_method` SHALL equal `parallel`

### Requirement: Cost telemetry per strategy
The `LLM_CALL` events emitted during decompose SHALL be tagged with a `strategy` field (`serial` or `parallel`) so post-run cost analysis can attribute spend per strategy.

#### Scenario: LLM_CALL events include strategy tag
- **WHEN** any decompose-purpose LLM_CALL event is emitted
- **THEN** the event payload SHALL include a `strategy` field with the resolved value
